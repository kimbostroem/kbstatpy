import os
import numpy as np
import pandas as pd
import polars as pl
from pymer4.models import lmer as Lmer
from pymer4.models import glmer as Glmer
import rpy2.robjects as ro
import matplotlib.pyplot as plt
import seaborn as sns
import scipy.stats as stats

ro.r('emmeans::emm_options(msg.interaction = FALSE)')
ro.r('options(contrasts = c("contr.sum", "contr.poly"))')

from .options import KbstatOptions


class Kbstat:
    """Generalized linear mixed model analysis with post-hoc pairwise comparisons."""

    def __init__(self, options: KbstatOptions):
        self.options = options
        self.data: pd.DataFrame = None
        self.model = None
        self.anova_table: pd.DataFrame = None
        self.posthoc_table: pd.DataFrame = None
        self.statistics_table: pd.DataFrame = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self):
        """Run the full analysis pipeline."""
        self._load_data()
        self._apply_categorical()
        self._apply_constraints()
        if self.options.remove_outliers:
            self.remove_outliers_pre()
        self.fit()
        if self.options.remove_outliers:
            self.remove_outliers_post()
            self.fit()
        self.anova()
        self.posthoc()
        self.plot_diagnostics()
        self.plot()
        if self.options.out_dir:
            self.save()

    def fit(self):
        """Load data and fit the LMM or GLMM depending on distribution."""
        if self.data is None:
            self._load_data()
        data_to_use = self.data
        if 'is_outlier' in self.data.columns:
            data_to_use = self.data[~self.data['is_outlier']]
        formula = self._build_formula()
        family = self._family()
        link = self.options.link if self.options.link not in ('auto', '') else 'default'
        data_pl = pl.from_pandas(data_to_use)
        if family == 'gaussian':
            self.model = Lmer(formula, data=data_pl)
        else:
            self.model = Glmer(formula, data=data_pl, family=family, link=link)
        self.model.fit(summarize=False)

    def anova(self):
        """Extract and enrich the ANOVA table from the fitted model.

        Degrees of freedom are estimated using the Satterthwaite approximation
        via R's lmerTest/emmeans. Note: MATLAB's fitglme does not support
        Satterthwaite; this is a deliberate difference from the MATLAB kbstat
        implementation.
        """
        if self.model is None:
            raise RuntimeError('Call fit() before anova()')

        data_to_use = self.data
        if 'is_outlier' in self.data.columns:
            data_to_use = self.data[~self.data['is_outlier']]

        self.model.anova(jointtest_kwargs={'mode': 'satterthwaite', 'lmer_df': 'satterthwaite'})
        raw = self.model.result_anova.to_pandas() if hasattr(self.model.result_anova, 'to_pandas') else self.model.result_anova
        raw = raw.rename(columns={
            'model term': 'Term',
            'df1': 'DF1',
            'df2': 'DF2',
            'F_ratio': 'F',
            'Chisq': 'Chisq',
            'p_value': 'p',
        })
        n_obs = len(data_to_use)
        raw['etaSqp'] = _f2eta_sq_p(raw['F'], raw['DF1'], raw['DF2'], n_obs)
        raw['SMD'] = _f2smd(raw['F'], raw['DF1'], raw['DF2'], n_obs)
        raw['effectSize'] = raw['etaSqp'].apply(_effect_label_eta)
        raw['significance'] = raw['p'].apply(_sig_stars)
        self.anova_table = raw
        return self.anova_table

    def posthoc(self):
        """Perform post-hoc pairwise comparisons and build a comparison table.

        For LMMs (distribution='normal') emmeans uses the Satterthwaite
        approximation and returns finite df. For GLMMs (any other distribution)
        Satterthwaite is not defined and emmeans falls back to asymptotic
        inference (df=Inf). This is expected behaviour, not an error.
        """
        if self.model is None:
            raise RuntimeError('Call fit() before posthoc()')
        factors = self.options.x if self.options.x else []
        if not factors:
            return None
        self.model.set_factors(factors)
        # Override the contr.treatment default that set_factors() hard-codes
        self.model.set_contrasts({f: 'contr.sum' for f in factors})
        emm_result = self.model.emmeans(
            marginal_var=factors[0],
            p_adjust=self.options.posthoc_correction,
        )
        self.posthoc_table = emm_result
        self.statistics_table = self._build_statistics_table(factors)
        return self.posthoc_table

    def save(self):
        """Write result tables and summary to out_dir."""
        if self.model is None:
            raise RuntimeError('Call fit() before save()')
        out_dir = self.options.out_dir
        os.makedirs(out_dir, exist_ok=True)

        if self.anova_table is not None:
            anova_df = self.anova_table.to_pandas() if hasattr(self.anova_table, 'to_pandas') else self.anova_table
            anova_df.to_excel(os.path.join(out_dir, 'Anova.xlsx'), index=False)
            print(f'Saved Anova.xlsx to {out_dir}')

        if self.posthoc_table is not None:
            ph_df = self.posthoc_table.to_pandas() if hasattr(self.posthoc_table, 'to_pandas') else self.posthoc_table
            ph_df.to_excel(os.path.join(out_dir, 'Posthoc.xlsx'), index=False)
            print(f'Saved Posthoc.xlsx to {out_dir}')

        if self.statistics_table is not None:
            self.statistics_table.to_excel(os.path.join(out_dir, 'Statistics.xlsx'), index=False)
            print(f'Saved Statistics.xlsx to {out_dir}')

        if self.data is not None:
            self.data.to_csv(os.path.join(out_dir, 'Data.csv'), index=False)
            print(f'Saved Data.csv to {out_dir}')

        self._write_summary(out_dir)
        print(f'Saved Summary.txt to {out_dir}')

    def remove_outliers_pre(self):

        if self.options.x:
            grouped_categories = self.data.groupby(self.options.x)
            z_scores = grouped_categories[self.options.y].transform(self._calculate_z_score)
        else:
            z_scores = self._calculate_z_score(self.data[self.options.y])

        self.data['is_outlier'] = z_scores > 3

    def remove_outliers_post(self):
        if self.model is None:
            raise RuntimeError("You must fit the model before removing post outliers.")
            return

        r_obj = getattr(self.model, 'r_model', getattr(self.model, 'model_obj', None))

        if r_obj is not None:
            residuals = np.array(ro.r('residuals')(r_obj, type="pearson"))
        else:
            raise RuntimeError("Unable to find R model, rerun the fit")

        z_scores = np.abs((residuals-residuals.mean())/(residuals.std()+1e-9))

        new_outliers = z_scores > 3

        healthy_points = self.data[~self.data['is_outlier']].index
        self.data.loc[healthy_points, 'is_outlier'] = new_outliers


    def plot(self):
        """Plot data with significance brackets (to be implemented)."""
        pass

    def plot_diagnostics(self):
        """Generate a grid of 6 diagnostic plots for the model."""
        if self.model is None:
            raise RuntimeError ("You must fit the model before plotting diagnostics.")

        r_obj = getattr(self.model, 'r_model', getattr(self.model, 'model_obj', None))

        if r_obj is not None:
            self.model.residuals = np.array(ro.r('residuals')(r_obj, type="pearson"))
        else:
            raise RuntimeError("Unable to find R model, rerun the fit")
            
        if r_obj is not None:
            self.model.fits = np.array(ro.r('fitted')(r_obj))
        else:
            raise RuntimeError("Unable to find R model, rerun the fit")

        # Create a 2x3 grid of subplots (15 inches wide, 10 inches tall)
        fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(15, 10))
        axes = axes.flatten()

        # ---------------------------------------------------------
        # Plot 1: Histogram of Residuals
        # ---------------------------------------------------------
        sns.histplot(self.model.residuals, kde=True, ax=axes[0])
        axes[0].set_title("Histogram of Residuals")
        axes[0].set_xlabel("Residuals")

        # ---------------------------------------------------------
        # Plot 2: Normal Q-Q Plot
        # ---------------------------------------------------------
        stats.probplot(self.model.residuals, dist="norm", plot=axes[1])
        axes[1].set_title("Normal Q-Q Plot")

        # ---------------------------------------------------------
        # Plot 3: Residuals vs Fitted
        # ---------------------------------------------------------
        sns.scatterplot(x=self.model.fits, y=self.model.residuals, ax=axes[2])
        axes[2].axhline(0, color='red', linestyle='--')
        axes[2].set_title("Residuals vs Fitted")
        axes[2].set_xlabel("Fitted Values")
        axes[2].set_ylabel("Residuals")

        # ---------------------------------------------------------
        # Plot 4: Lagged Residuals
        # ---------------------------------------------------------
        sns.scatterplot(x=self.model.residuals[:-1], y=self.model.residuals[1:], ax=axes[3])
        axes[3].set_title("Lagged Residuals")
        axes[3].set_xlabel("Residual (i)")
        axes[3].set_ylabel("Residual (i+1)")

        # ---------------------------------------------------------
        # Plot 5: Fitted vs Response
        # ---------------------------------------------------------
        if 'is_outlier' in self.data.columns:
            y_actual = self.data[~self.data['is_outlier']]
            y_actual = y_actual[self.options.y]
        else:
            y_actual = self.data[self.options.y]
            
        sns.scatterplot(x=y_actual, y=self.model.fits, ax=axes[4])
        
        min_val = min(self.model.fits.min(), y_actual.min())
        max_val = max(self.model.fits.max(), y_actual.max())
        axes[4].plot([min_val, max_val], [min_val, max_val], color='red', linestyle='--')
        
        axes[4].set_title("Fitted vs Response")
        axes[4].set_xlabel("Fitted Values")
        axes[4].set_ylabel("Actual Raw Data")

        # ---------------------------------------------------------
        # Plot 6: Symmetry Plot
        # ---------------------------------------------------------
        res = self.model.residuals
        median_res = np.median(res)
        
        # Sort residuals below median ascending (most negative first)
        lower_half = np.sort(res[res <= median_res])
        # Sort residuals above median descending (most positive first)
        upper_half = np.sort(res[res > median_res])[::-1]
        
        min_len = min(len(lower_half), len(upper_half))
        
        if min_len > 0:
            lower_dist = median_res - lower_half[:min_len]
            upper_dist = upper_half[:min_len] - median_res
            sns.scatterplot(x=lower_dist, y=upper_dist, ax=axes[5])
            
            max_dist = max(lower_dist.max(), upper_dist.max())
            axes[5].plot([0, max_dist], [0, max_dist], color='red', linestyle='--')
            
        axes[5].set_title("Symmetry Plot")
        axes[5].set_xlabel("Distance below median")
        axes[5].set_ylabel("Distance above median")

        # Fixes overlapping text and margins
        plt.tight_layout()

        if self.options.out_dir:
            os.makedirs(self.options.out_dir, exist_ok=True)
            fig.savefig(os.path.join(self.options.out_dir, 'Diagnostics.pdf'))
            fig.savefig(os.path.join(self.options.out_dir, 'Diagnostics.png'), dpi=150)
            print(f'Saved Diagnostics.pdf/.png to {self.options.out_dir}')

        plt.show(block=False)
        plt.pause(3)
        plt.close(fig)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    #

    def _calculate_z_score(self, data):
        # We add 1e-9 to prevent Divide By Zero crashes if a group's std is 0
        return np.abs((data - data.mean()) / (data.std() + 1e-9))

    def _load_data(self):
        """Read data from in_file into a DataFrame."""
        path = self.options.in_file
        if not path:
            raise ValueError('options.in_file is required')
        if path.endswith('.csv'):
            self.data = pd.read_csv(path, sep=None, engine='python', encoding_errors='replace')
            self.data.columns = self.data.columns.str.lstrip('﻿')
        else:
            self.data = pd.read_excel(path)

    def _build_formula(self) -> str:
        """Compose a Wilkinson formula from options, or return the explicit one."""
        if self.options.formula:
            return self.options.formula
        y = self.options.y
        x = ' * '.join(self.options.x)
        subject = self.options.id
        if subject:
            return f'{y} ~ {x} + (1 | {subject})'
        return f'{y} ~ {x}'

    def _family(self) -> str:
        """Map options.distribution to an R family name string."""
        mapping = {
            'normal':           'gaussian',
            'binomial':         'binomial',
            'poisson':          'poisson',
            'gamma':            'Gamma',
            'inverse_gaussian': 'inverse.gaussian',
        }
        return mapping.get(self.options.distribution.lower(), 'gaussian')

    def _write_summary(self, out_dir: str):
        """Write Summary.txt with model info, fit statistics, ANOVA table, and explanatory notes."""
        lines = []

        sep = '=' * 70

        # --- Header ---
        lines += [sep, 'kbstatpy — Analysis Summary', sep, '']

        # --- Formula ---
        formula = self._build_formula()
        lines += ['FORMULA', '-------', formula, '']

        # --- Model information ---
        n_obs = len(self.data) if self.data is not None else '?'
        family = self._family()
        link = self.options.link if self.options.link not in ('auto', '') else 'default'
        fit_method = self.options.fit_method
        lines += [
            'MODEL INFORMATION',
            '-----------------',
            f'  Number of observations : {n_obs}',
            f'  Distribution           : {self.options.distribution}',
            f'  Link function          : {link}',
            f'  Fit method             : {fit_method}',
        ]
        if self.options.id:
            lines.append(f'  Random grouping factor : {self.options.id}')
        lines.append(f'  Contrast coding        : effects (contr.sum)')
        lines.append('')

        # --- Fit statistics ---
        if hasattr(self.model, 'fit_stats') and self.model.fit_stats is not None:
            fs = self.model.fit_stats
            fs_df = fs.to_pandas() if hasattr(fs, 'to_pandas') else fs
            lines += ['FIT STATISTICS', '--------------']
            for col in fs_df.columns:
                val = fs_df[col].iloc[0] if len(fs_df) > 0 else '?'
                lines.append(f'  {col:<24}: {val}')
            lines.append('')

        # --- Fixed effects ---
        if hasattr(self.model, 'coefs') and self.model.coefs is not None:
            coef_df = self.model.coefs
            if hasattr(coef_df, 'to_pandas'):
                coef_df = coef_df.to_pandas()
            lines += ['FIXED EFFECTS', '-------------', coef_df.to_string(), '']

        # --- ANOVA table ---
        if self.anova_table is not None:
            at = self.anova_table.to_pandas() if hasattr(self.anova_table, 'to_pandas') else self.anova_table
            lines += ['ANOVA (Type III)', '----------------', at.to_string(index=False), '']

            # Check for infinite df2 and add explanatory note
            has_inf_df = False
            if 'DF2' in at.columns:
                has_inf_df = bool(np.any(np.isinf(at['DF2'].astype(float).values)))
            if has_inf_df:
                lines += [
                    'NOTE: df = Inf in ANOVA table',
                    '------------------------------',
                    'The Satterthwaite approximation for degrees of freedom is only defined',
                    'for linear mixed models (LMMs, distribution = normal). For generalised',
                    'linear mixed models (GLMMs) the likelihood is not quadratic and the',
                    'Satterthwaite formula does not apply. R\'s emmeans therefore falls back',
                    'to asymptotic inference, yielding df = Inf and Wald chi-square tests.',
                    '',
                    'This is mathematically correct behaviour — not a software error.',
                    '',
                    'For comparison: MATLAB\'s fitglme also does not support Satterthwaite',
                    'for GLMMs. Instead it uses the finite approximation df2 = n - p, where',
                    'n is the number of observations and p is the number of fixed-effect',
                    'columns. Both approaches are approximations; the asymptotic (df = Inf)',
                    'method used here is the more principled one.',
                    '',
                ]

        # --- Post-hoc ---
        if self.posthoc_table is not None:
            ph = self.posthoc_table
            if hasattr(ph, 'to_pandas'):
                ph = ph.to_pandas()
            lines += ['POST-HOC PAIRWISE COMPARISONS', '-----------------------------']
            lines += [f'  Correction: {self.options.posthoc_correction}', '']
            lines += [ph.to_string(index=False), '']

        # --- Significance key ---
        lines += [
            'SIGNIFICANCE',
            '------------',
            '  *** p < 0.001',
            '  **  p < 0.01',
            '  *   p < 0.05',
            '  n.s. not significant',
            '',
            sep,
        ]

        out_path = os.path.join(out_dir, 'Summary.txt')
        with open(out_path, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(lines) + '\n')

    def _build_statistics_table(self, factors: list) -> pd.DataFrame:
        """Build descriptive statistics table per group."""
        y = self.options.y
        rows = []
        groups = self.data.groupby(factors)
        for keys, group in groups:
            if not isinstance(keys, tuple):
                keys = (keys,)
            row = dict(zip(factors, keys))
            vals = group[y].dropna()
            row['N'] = len(vals)
            row['mean'] = vals.mean()
            row['std'] = vals.std()
            row['SE'] = vals.sem()
            row['median'] = vals.median()
            row['q25'] = vals.quantile(0.25)
            row['q75'] = vals.quantile(0.75)
            ci = 1.96 * vals.sem()
            row['CI95_lower'] = vals.mean() - ci
            row['CI95_upper'] = vals.mean() + ci
            rows.append(row)
        return pd.DataFrame(rows)

    def _apply_categorical(self):
        categorical_vars = self.options.x.copy()
        if self.options.id:
            categorical_vars.append(self.options.id)

        if self.data is not None:
            for var in categorical_vars:
                if var in self.data.columns:
                    unique_categories = self.data[var].unique().tolist()
                    self.data[var] = pd.Categorical(
                        self.data[var],
                        categories=unique_categories,
                        ordered=False
                    )

    def _apply_constraints(self):
        if self.options.constraints != '':
            self.data = self.data.query(self.options.constraints)

# ------------------------------------------------------------------
# Statistical helper functions
# ------------------------------------------------------------------

def _f2eta_sq_p(F, df1, df2, n_obs=None):
    """Partial eta-squared from F statistic. Uses sample size as df2 when df2 is infinite."""
    df2 = df2.copy() if hasattr(df2, 'copy') else df2
    if n_obs is not None:
        df2 = df2.where(~np.isinf(df2), other=float(n_obs)) if hasattr(df2, 'where') else (n_obs if np.isinf(df2) else df2)
    return (F * df1) / (F * df1 + df2)


def _f2smd(F, df1, df2, n_obs=None):
    """Standardised mean difference (Cohen's d equivalent) from F."""
    eta = _f2eta_sq_p(F, df1, df2, n_obs)
    return np.sqrt(4 * eta / (1 - eta))


def _effect_label_eta(eta):
    """Verbal effect size label from partial eta-squared."""
    if eta < 0.01:
        return 'negligible'
    if eta < 0.06:
        return 'small'
    if eta < 0.14:
        return 'medium'
    if eta < 0.35:
        return 'large'
    return 'very large'


def _sig_stars(p):
    """Significance stars from p-value."""
    if p < 0.001:
        return '***'
    if p < 0.01:
        return '**'
    if p < 0.05:
        return '*'
    return 'n.s.'

