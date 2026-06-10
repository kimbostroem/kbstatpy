import os
import numpy as np
import pandas as pd
import polars as pl
from pymer4.models import lmer as Lmer
from pymer4.models import glmer as Glmer
import rpy2.robjects as ro

ro.r('emmeans::emm_options(msg.interaction = FALSE)')

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
        self.fit()
        self.anova()
        self.posthoc()
        self.plot()
        if self.options.out_dir:
            self.save()

    def fit(self):
        """Load data and fit the LMM or GLMM depending on distribution."""
        if self.data is None:
            self._load_data()
        formula = self._build_formula()
        family = self._family()
        link = self.options.link if self.options.link not in ('auto', '') else 'default'
        data_pl = pl.from_pandas(self.data)
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
        n_obs = len(self.data)
        raw['etaSqp'] = _f2eta_sq_p(raw['F'], raw['DF1'], raw['DF2'], n_obs)
        raw['SMD'] = _f2smd(raw['F'], raw['DF1'], raw['DF2'], n_obs)
        raw['effectSize'] = raw['etaSqp'].apply(_effect_label_eta)
        raw['significance'] = raw['p'].apply(_sig_stars)
        self.anova_table = raw
        return self.anova_table

    def posthoc(self):
        """Perform post-hoc pairwise comparisons and build a comparison table."""
        if self.model is None:
            raise RuntimeError('Call fit() before posthoc()')
        factors = self.options.x if self.options.x else []
        if not factors:
            return None
        self.model.set_factors(factors)
        emm_result = self.model.emmeans(
            marginal_var=factors[0],
            p_adjust=self.options.posthoc_correction,
        )
        self.posthoc_table = emm_result
        self.statistics_table = self._build_statistics_table(factors)
        return self.posthoc_table

    def save(self):
        """Write result tables to out_dir as xlsx files."""
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

    def plot(self):
        """Plot data with significance brackets (to be implemented)."""
        pass

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
