import os
import numpy as np
import pandas as pd
import polars as pl
from pymer4.models import lm as Lm
from pymer4.models import lmer as Lmer
from pymer4.models import glmer as Glmer
import rpy2.robjects as ro
import matplotlib.pyplot as plt
import seaborn as sns
import scipy.stats as stats

ro.r('emmeans::emm_options(msg.interaction = FALSE)')
ro.r('options(contrasts = c("contr.sum", "contr.poly"))')

from .options import KbstatOptions
from ._glmer_direct import GlmerDirect


class Kbstat:
    """Generalized linear mixed model analysis with post-hoc pairwise comparisons."""

    def __init__(self, options: KbstatOptions):
        self.options = options
        self.data: pd.DataFrame = None
        self.model = None
        self.anova_table: pd.DataFrame = None
        self.posthoc_table: pd.DataFrame = None
        self.contrasts_table: pd.DataFrame = None
        self.statistics_table: pd.DataFrame = None
        self.fig_diagnostics = None
        self.fig_data = None

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
        self.plot_data()
        if self.options.out_dir:
            self.save()

    def fit(self):
        """Load data and fit the LMM or GLMM depending on distribution."""
        if self.data is None:
            self._load_data()
        formula = self._build_formula()
        self._backfill_options_from_formula(formula)
        self._validate_options_vs_formula(formula)
        self._validate_slopes()
        data_to_use = self.data
        if 'is_outlier' in self.data.columns:
            data_to_use = self.data[~self.data['is_outlier']]
        family = self._family()
        link = self.options.link if self.options.link not in ('auto', '') else 'default'
        has_random = bool(self._parse_formula(formula)['id'])
        has_slopes = bool(self._parse_formula(formula)['slopes'])
        data_pl = pl.from_pandas(data_to_use)
        if family == 'gaussian' and not has_random:
            # Plain linear model — no random effects
            self.model = Lm(formula, data=data_pl)
        elif family == 'gaussian':
            self.model = Lmer(formula, data=data_pl)
        elif has_slopes:
            # pymer4 Glmer crashes when random slopes are present (broom.tidy bug).
            # Use the direct rpy2 wrapper instead — lme4 itself handles slopes correctly.
            print('Random slopes detected in GLMM — using direct lme4 interface.')
            self.model = GlmerDirect(formula, data=data_to_use, family=family, link=link)
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
        emm_df = emm_result.to_pandas() if hasattr(emm_result, 'to_pandas') else emm_result

        # Pairwise contrasts (adjusted for brackets; raw for the p column)
        import rpy2.robjects.pandas2ri as p2ri
        r_obj = getattr(self.model, 'r_model', getattr(self.model, 'model_obj', None))
        ct_adj = None
        ct_raw = None
        if r_obj is not None:
            try:
                _emm = ro.r('emmeans::emmeans')(r_obj, ro.Formula(f'~{factors[0]}'))
                ct_adj = p2ri.rpy2py(ro.r('as.data.frame')(
                    ro.r('pairs')(_emm, adjust=self.options.posthoc_correction)))
                ct_raw = p2ri.rpy2py(ro.r('as.data.frame')(
                    ro.r('pairs')(_emm, adjust='none')))
            except Exception:
                pass

        self.contrasts_table = ct_adj  # used for significance brackets in plot_data

        # Build the rich posthoc table
        if ct_adj is not None and ct_raw is not None and factors[0] in emm_df.columns:
            factor_col = factors[0]

            def _parse_level(part, levels):
                """Match a contrast part like 'group1' to a level value."""
                for lev in levels:
                    ls = str(lev)
                    if part == ls or part == f'{factor_col}{ls}' or part == f'{factor_col} {ls}':
                        return lev
                return part  # fallback: return raw string

            def _emm_ci_str(lev):
                row = emm_df[emm_df[factor_col] == lev]
                if len(row) == 0:
                    return ''
                r = row.iloc[0]
                return f"{r['emmean']:.3f} ({r['lower_CL']:.3f}, {r['upper_CL']:.3f})"

            levels = emm_df[factor_col].tolist()
            rows = []
            for (_, cadj), (_, craw) in zip(ct_adj.iterrows(), ct_raw.iterrows()):
                parts = [p.strip() for p in str(cadj['contrast']).split(' - ')]
                lev1 = _parse_level(parts[0], levels) if len(parts) > 0 else ''
                lev2 = _parse_level(parts[1], levels) if len(parts) > 1 else ''
                t_val = float(cadj['t.ratio'])
                df_val = float(cadj['df'])
                smd = 2 * abs(t_val) / np.sqrt(df_val) if df_val > 0 else np.nan
                p_raw  = float(craw['p.value'])
                p_corr = float(cadj['p.value'])
                rows.append({
                    f'{factor_col}_1':  str(lev1),
                    f'{factor_col}_2':  str(lev2),
                    'emm_1':            _emm_ci_str(lev1),
                    'emm_2':            _emm_ci_str(lev2),
                    'diff':             float(cadj['estimate']),
                    't':                t_val,
                    'df':               df_val,
                    'p':                p_raw,
                    'pCorr':            p_corr,
                    'SMD':              smd,
                    'effectSize':       _d_label(smd),
                    'significance':     _sig_stars(p_corr),
                })
            self.posthoc_table = pd.DataFrame(rows)
        else:
            self.posthoc_table = emm_df  # fallback to marginal means

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
            # Round numeric columns for clean display
            for col in ph_df.columns:
                if col in ('p', 'pCorr'):
                    ph_df[col] = ph_df[col].round(4)
                elif ph_df[col].dtype == float:
                    ph_df[col] = ph_df[col].round(3)
            ph_path = os.path.join(out_dir, 'Posthoc.xlsx')
            with pd.ExcelWriter(ph_path, engine='openpyxl') as writer:
                ph_df.to_excel(writer, index=False, sheet_name='Posthoc')
                ws = writer.sheets['Posthoc']
                for col_cells in ws.columns:
                    width = max(len(str(cell.value or '')) for cell in col_cells) * 0.85 + 1
                    ws.column_dimensions[col_cells[0].column_letter].width = width
            print(f'Saved Posthoc.xlsx to {out_dir}')

        if self.statistics_table is not None:
            self.statistics_table.to_excel(os.path.join(out_dir, 'Statistics.xlsx'), index=False)
            print(f'Saved Statistics.xlsx to {out_dir}')

        if self.data is not None:
            self.data.to_csv(os.path.join(out_dir, 'Data.csv'), index=False)
            print(f'Saved Data.csv to {out_dir}')

        self._write_summary(out_dir)
        print(f'Saved Summary.txt to {out_dir}')

        if self.fig_data is not None:
            self.fig_data.savefig(os.path.join(out_dir, 'DataPlots.pdf'))
            self.fig_data.savefig(os.path.join(out_dir, 'DataPlots.png'), dpi=150, bbox_inches='tight')
            plt.close(self.fig_data)
            self.fig_data = None
            print(f'Saved DataPlots.pdf/.png to {out_dir}')

        if self.fig_diagnostics is not None:
            self.fig_diagnostics.savefig(os.path.join(out_dir, 'Diagnostics.pdf'))
            self.fig_diagnostics.savefig(os.path.join(out_dir, 'Diagnostics.png'), dpi=150)
            plt.close(self.fig_diagnostics)
            self.fig_diagnostics = None
            print(f'Saved Diagnostics.pdf/.png to {out_dir}')

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


    def plot_data(self):
        """Generate publication-ready summary plots matching the MATLAB kbstat style.

        Layout mirrors plotGroups.m: one panel per level of the 2nd independent
        variable (or a single panel when there is only one x-variable).  Within
        each panel the 1st x-variable is on the x-axis with colored violins,
        scatter points in matching colors, paired-subject connecting lines,
        a white median marker with an IQR bar, and significance brackets.
        """
        if not self.options.x:
            print("No independent variables to plot.")
            return

        # Ensure the outlier column exists
        if 'is_outlier' not in self.data.columns:
            self.data['is_outlier'] = False

        n_vars = len(self.options.x)
        x_var = self.options.x[0]       # Violin / x-axis variable  (e.g. Chocolate)
        y_var = self.options.y           # Dependent variable        (e.g. Distance)
        facet_var = self.options.x[1] if n_vars > 1 else None  # Panel variable (e.g. Gender)
        id_var = self.options.id         # Subject identifier for connecting lines
        y_units = getattr(self.options, 'y_units', '')
        y_label = f"{y_var} [{y_units}]" if y_units else y_var

        # Use MATLAB's default color cycle (first N colors from 'tab10')
        x_levels = self.data[x_var].cat.categories.tolist() if hasattr(self.data[x_var], 'cat') else sorted(self.data[x_var].unique())
        palette = dict(zip(x_levels, sns.color_palette(self.options.colors, len(x_levels))))

        # Determine facets
        if facet_var:
            facet_levels = self.data[facet_var].cat.categories.tolist() if hasattr(self.data[facet_var], 'cat') else sorted(self.data[facet_var].unique())
        else:
            facet_levels = [None]

        n_panels = len(facet_levels)
        fig, axes = plt.subplots(1, n_panels, figsize=(5 * n_panels, 6), sharey=True)
        if n_panels == 1:
            axes = [axes]

        healthy_data = self.data[~self.data['is_outlier']]
        outlier_data = self.data[self.data['is_outlier']]

        for idx, facet_val in enumerate(facet_levels):
            ax = axes[idx]

            # Subset for this panel
            if facet_var is not None:
                panel_healthy = healthy_data[healthy_data[facet_var] == facet_val]
                panel_outlier = outlier_data[outlier_data[facet_var] == facet_val]
            else:
                panel_healthy = healthy_data
                panel_outlier = outlier_data

            # --- LAYER 1: Violins (centered on each x-tick, colored per level) ---
            sns.violinplot(
                data=panel_healthy, x=x_var, y=y_var, order=x_levels,
                hue=x_var, hue_order=x_levels, palette=palette, dodge=False,
                cut=0, inner=None, linewidth=1, saturation=0.4,
                ax=ax, legend=False, density_norm='width'
            )

            # --- LAYER 2: Swarm plot (dots distributed within violin shape) ---
            n_coll_before = len(ax.collections)
            sns.swarmplot(
                data=panel_healthy, x=x_var, y=y_var, order=x_levels,
                color='black', size=3, alpha=0.7, ax=ax, warn_thresh=1
            )
            swarm_collections = ax.collections[n_coll_before:]

            # --- LAYER 2b: Outlier points (red X markers) ---
            if len(panel_outlier) > 0:
                sns.swarmplot(
                    data=panel_outlier, x=x_var, y=y_var, order=x_levels,
                    color='red', size=5, marker='X', alpha=0.9, ax=ax, warn_thresh=1
                )

            # --- LAYER 3: Connecting lines for paired subjects ---
            # Only drawn when each subject has exactly one observation per condition
            # (true paired design). With multiple obs per subject the concept is ambiguous.
            if id_var and len(x_levels) == 2 and len(swarm_collections) >= 2:
                counts = panel_healthy.groupby([id_var, x_var])[y_var].count()
                is_paired = (counts == 1).all()
                if is_paired:
                    pivot = panel_healthy.pivot_table(index=id_var, columns=x_var, values=y_var, observed=True)
                    if x_levels[0] in pivot.columns and x_levels[1] in pivot.columns:
                        paired = pivot.dropna()
                        def _y_to_x(coll):
                            offs = coll.get_offsets()
                            return {round(float(y), 10): float(x) for x, y in offs}
                        lookup0 = _y_to_x(swarm_collections[0])
                        lookup1 = _y_to_x(swarm_collections[1])
                        for _, row in paired.iterrows():
                            y0, y1 = row[x_levels[0]], row[x_levels[1]]
                            xa = lookup0.get(round(float(y0), 10))
                            xb = lookup1.get(round(float(y1), 10))
                            if xa is not None and xb is not None:
                                ax.plot([xa, xb], [y0, y1],
                                        color='black', alpha=0.4, linewidth=1.0, zorder=3)

            # --- LAYER 4: Median marker + IQR bar ---
            for i, level in enumerate(x_levels):
                subset = panel_healthy[panel_healthy[x_var] == level][y_var].dropna()
                if len(subset) == 0:
                    continue
                median = subset.median()
                q25 = subset.quantile(0.25)
                q75 = subset.quantile(0.75)
                # Dark IQR bar
                ax.plot([i, i], [q25, q75], color='0.2', linewidth=2, zorder=5)
                # White median dot
                ax.scatter(i, median, color='white', edgecolors='0.2',
                           s=48, zorder=6, linewidths=1.2)

            # Expand y-limits so violin tops are not clipped and brackets have room
            y_lo, y_hi = ax.get_ylim()
            y_pad = (y_hi - y_lo) * 0.08
            ax.set_ylim(bottom=y_lo - y_pad, top=y_hi + y_pad)

            # --- LAYER 5: Significance brackets ---
            if self.contrasts_table is not None:
                ct = self.contrasts_table
                if 'p.value' in ct.columns:
                    y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
                    bracket_step = y_range * 0.07
                    bracket_y = ax.get_ylim()[1] + bracket_step * 0.3

                    def _contrast_positions(contrast_str, x_var, x_levels):
                        """Return (i, j) indices into x_levels for a contrast string."""
                        parts = [p.strip() for p in contrast_str.split(' - ')]
                        if len(parts) != 2:
                            return None, None
                        found = []
                        for part in parts:
                            for i, lev in enumerate(x_levels):
                                ls = str(lev)
                                if part == ls or part.endswith(ls) or part == f'{x_var} {ls}':
                                    found.append(i)
                                    break
                        return (found[0], found[1]) if len(found) == 2 else (None, None)

                    for _, crow in ct.iterrows():
                        p_val = crow['p.value']
                        if p_val >= 0.05:
                            continue
                        label = '***' if p_val < 0.001 else ('**' if p_val < 0.01 else '*')
                        xi, xj = _contrast_positions(str(crow['contrast']), x_var, x_levels)
                        if xi is None:
                            xi, xj = 0, len(x_levels) - 1
                        tick_h = bracket_step * 0.3
                        ax.plot([xi, xi, xj, xj],
                                [bracket_y - tick_h, bracket_y, bracket_y, bracket_y - tick_h],
                                color='black', linewidth=1.5)
                        ax.text((xi + xj) / 2, bracket_y, label,
                                ha='center', va='bottom', fontsize=12, fontweight='bold')
                        bracket_y += bracket_step * 1.4
                    ax.set_ylim(top=bracket_y)

            # --- Axis formatting ---
            ax.set_xlabel('')
            ax.set_xticks(range(len(x_levels)))
            ax.set_xticklabels([f"{x_var} = {lev}" for lev in x_levels])
            if idx == 0:
                ax.set_ylabel(y_label)
            else:
                ax.set_ylabel('')
            if facet_var is not None:
                ax.set_title(f"{facet_var} = {facet_val}", fontweight='bold')

        # Super title
        fig.suptitle(y_var, fontweight='bold', fontsize=14)
        fig.tight_layout()

        self.fig_data = fig
        plt.show(block=False)
        plt.pause(3)

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
        axes[0].get_lines()[0].set_color('red')

        # ---------------------------------------------------------
        # Plot 2: Normal Q-Q Plot
        # ---------------------------------------------------------
        stats.probplot(self.model.residuals, dist="norm", plot=axes[1])
        axes[1].set_title("Normal Q-Q Plot")
        # probplot draws with raw matplotlib (plain blue); recolour to match seaborn default
        seaborn_color = sns.color_palette()[0]
        axes[1].get_lines()[0].set(color=seaborn_color, markerfacecolor=seaborn_color,
                                   markeredgecolor=seaborn_color)
        axes[1].get_lines()[1].set_color('red')

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

        self.fig_diagnostics = fig
        plt.show(block=False)
        plt.pause(3)

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

    def _validate_options_vs_formula(self, formula: str):
        """Warn when explicit options fields disagree with an explicitly provided formula.

        Only runs when the user has set both options.formula and one or more of
        y / x / id / slope, since that combination is likely a mistake.
        """
        # Nothing to check if formula was built from the fields rather than set explicitly
        if not self.options.formula:
            return

        parsed = self._parse_formula(formula)
        problems = []

        if self.options.y and self.options.y != parsed['y']:
            problems.append(
                f"  options.y='{self.options.y}' but formula has dependent variable '{parsed['y']}'"
            )
        if self.options.id and self.options.id != parsed['id']:
            problems.append(
                f"  options.id='{self.options.id}' but formula has grouping variable '{parsed['id']}'"
            )
        if self.options.x:
            formula_x = set(parsed['x']) - set(self.options.covariate)
            options_x = set(self.options.x)
            extra   = options_x - formula_x
            missing = formula_x - options_x
            if extra:
                problems.append(f"  options.x contains {sorted(extra)} not found as fixed effects in formula")
            if missing:
                problems.append(f"  options.x is missing {sorted(missing)} that appear as fixed effects in formula")
        if self.options.slope:
            formula_slopes = set(parsed['slopes'])
            options_slopes = set(self.options.slope)
            extra   = options_slopes - formula_slopes
            missing = formula_slopes - options_slopes
            if extra:
                problems.append(f"  options.slope contains {sorted(extra)} not present as random slopes in formula")
            if missing:
                problems.append(f"  options.slope is missing {sorted(missing)} that appear as random slopes in formula")

        if problems:
            msg = "options fields are inconsistent with the explicit formula:\n" + "\n".join(problems)
            raise ValueError(msg)

    def _validate_slopes(self):
        """Raise a clear error if any slope variable is not among the fixed-effect factors."""
        unknown = [s for s in self.options.slope if s not in self.options.x]
        if unknown:
            raise ValueError(
                f"Random slope variable(s) {unknown} not found in fixed-effect factors "
                f"{self.options.x}. Each slope must be one of the fixed-effect variables."
            )

    def _build_formula(self) -> str:
        """Compose a Wilkinson formula from options, or return the explicit one."""
        if self.options.formula:
            return self.options.formula
        y = self.options.y
        x = ' * '.join(self.options.x)
        covs = ' + '.join(self.options.covariate)
        rhs = f'{x} + {covs}' if covs else x
        subject = self.options.id
        if subject:
            slopes = self.options.slope
            if slopes:
                random_term = ' + '.join(['1'] + slopes)
                return f'{y} ~ {rhs} + ({random_term} | {subject})'
            return f'{y} ~ {rhs} + (1 | {subject})'
        return f'{y} ~ {rhs}'

    def _parse_formula(self, formula: str) -> dict:
        """Extract y, x, id, and random slopes from a Wilkinson formula string.

        Handles formulas of the form:
            y ~ A * B + (1 | id)
            y ~ A + B + (A + B | id)
            y ~ A * B              (no random effect)
        Returns a dict with keys: y, x (list), id, slopes (list).
        """
        import re

        formula = formula.replace(' ', '')

        # Split on ~
        lhs, rhs = formula.split('~', 1)
        y = lhs.strip()

        # Extract all random-effect groups: (... | grouping)
        random_terms = re.findall(r'\(([^)]+)\)', rhs)
        id_var = ''
        slopes = []
        for term in random_terms:
            if '|' in term:
                left, right = term.split('|', 1)
                id_var = right.strip()
                # Slopes are everything before | except the intercept (1)
                slope_parts = [s.strip() for s in left.split('+') if s.strip() != '1']
                slopes = slope_parts

        # Remove random-effect groups from rhs to isolate fixed effects
        fixed_rhs = re.sub(r'\+?\s*\([^)]+\)', '', rhs).strip().strip('+').strip()

        # Collect unique main-effect variable names (ignore interaction terms with :)
        x = []
        seen = set()
        for term in re.split(r'[+]', fixed_rhs):
            term = term.strip()
            # Expand * into constituent names (A*B → A, B)
            parts = re.split(r'[*:]', term)
            for part in parts:
                part = part.strip()
                if part and part not in seen:
                    seen.add(part)
                    x.append(part)

        return {'y': y, 'x': x, 'id': id_var, 'slopes': slopes}

    def _backfill_options_from_formula(self, formula: str):
        """Fill in options.y, .x, .id from formula if not already set."""
        parsed = self._parse_formula(formula)
        if not self.options.y:
            self.options.y = parsed['y']
            print(f'Detected dependent variable  : {self.options.y}')
        if not self.options.x:
            # Exclude declared covariates so they don't appear as factors
            covs = set(self.options.covariate)
            self.options.x = [v for v in parsed['x'] if v not in covs]
            print(f'Detected independent variables: {", ".join(self.options.x)}')
            if covs:
                print(f'Detected covariates          : {", ".join(self.options.covariate)}')
        if not self.options.id:
            self.options.id = parsed['id']
            if self.options.id:
                print(f'Detected grouping variable   : {self.options.id}')
        if not self.options.slope and parsed['slopes']:
            self.options.slope = parsed['slopes']
            print(f'Detected random slopes       : {", ".join(self.options.slope)}')
        print(f'Formula                      : {formula}')

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


def _d_label(d):
    """Verbal Cohen's d effect size label (matches MATLAB effprint for type 'd')."""
    d = abs(d)
    if np.isnan(d):
        return ''
    if d < 0.05:
        return 'very small'
    if d < 0.225:
        return 'small'
    if d < 0.425:
        return 'small to medium'
    if d < 0.575:
        return 'medium'
    if d < 0.725:
        return 'medium to large'
    if d < 0.9:
        return 'large'
    return 'very large'

