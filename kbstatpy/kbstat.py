import os
import warnings
import numpy as np
import pandas as pd
import polars as pl
from pymer4.models import lm as Lm
from pymer4.models import lmer as Lmer
import rpy2.robjects as ro
import matplotlib.pyplot as plt
import seaborn as sns
import scipy.stats as stats

ro.r('emmeans::emm_options(msg.interaction = FALSE)')
ro.r('options(contrasts = c("contr.sum", "contr.poly"))')

from dataclasses import dataclass, field

from .options import KbstatOptions
from ._glmmtmb import GlmmTMB


@dataclass
class ModelResult:
    """Results of fitting one dependent variable."""
    y: str = ''
    formula: str = ''
    anova: object = None          # ANOVA table (DataFrame)
    posthoc: object = None        # post-hoc pairwise table (DataFrame)
    statistics: object = None     # descriptive statistics table (DataFrame)
    summary: str = ''             # human-readable summary text
    data: object = None           # the data the model was fitted on
    fig_data: object = None       # data plot figure
    fig_diagnostics: object = None  # diagnostics figure


@dataclass
class CorrelationResult:
    """Results of a correlation analysis."""
    correlation_table: object = None
    partial_table: object = None
    vif_table: object = None
    fig_scatter: object = None
    fig_table: object = None
    fig_partial_scatter: object = None
    fig_partial_table: object = None


@dataclass
class Output:
    """Everything produced by run(): one ModelResult per dependent variable
    plus an optional CorrelationResult. Read it for results, or pass to save()."""
    results: list = field(default_factory=list)   # list[ModelResult]
    correlation: object = None                     # CorrelationResult or None
    multiple_comparisons: object = None            # across-y correction table or None


class Kbstat:
    """Generalized linear mixed model analysis with post-hoc pairwise comparisons."""

    def __init__(self, options: KbstatOptions):
        self.options = options
        self.data: pd.DataFrame = None
        self.model = None
        self.anova_table: pd.DataFrame = None
        self.posthoc_table: pd.DataFrame = None
        self.contrasts_table: pd.DataFrame = None
        self.contrasts_by_var: dict = {}   # {factor: contrasts table} per posthoc_compare variable
        self.posthoc_by_var: dict = {}      # {factor: posthoc table} per posthoc_compare variable
        self.statistics_table: pd.DataFrame = None
        self.AIC    = None
        self.BIC    = None
        self.logLik = None
        self._display_names: dict = {}   # internal col → display label (from options.rename)
        self.fig_diagnostics = None
        self.fig_data = None
        self.fig_correlation = None
        self.correlation_table: pd.DataFrame = None
        self._data_raw: pd.DataFrame = None   # untransformed data, for plotting
        self._transform_fn = None             # forward transform: array → array
        self._inverse_fn   = None             # inverse transform: array → array
        self._emm_df       = None             # raw emmeans DataFrame, stored after posthoc()
        self._emm_df_full  = None             # full interaction EMM grid (multi-factor models)
        self._df_runtime   = None             # df method after any runtime KR fallback (set in anova)
        self.output: Output = None            # populated by run(); read or pass to save()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def _body_font(self):
        """The configured body font, or None when unset: '' or 'auto' (case-
        insensitive) both mean 'use matplotlib's default font'."""
        f = self.options.font
        if not f or (isinstance(f, str) and f.strip().lower() == 'auto'):
            return None
        return f

    def _apply_font(self):
        """Apply options.font to matplotlib rcParams unless it is unset ('' / 'auto')."""
        f = self._body_font()
        if f:
            plt.rcParams['font.family'] = f

    @staticmethod
    def _split_csv(value):
        """Split a comma-separated string into a stripped list, or pass a list through."""
        if isinstance(value, str):
            return [v.strip() for v in value.split(',') if v.strip()]
        return list(value)

    def _resolve_path(self, path):
        """Resolve a relative path against the current working directory.

        Standard Python behaviour: a relative in_file/out_dir is taken relative
        to where the user is working, never the package or script location, so
        output lands in the user's own (writable) directory.
        """
        if not path or os.path.isabs(path):
            return path
        return os.path.abspath(path)

    def _disp(self, name):
        """Return the display label for an internal column name."""
        return self._display_names.get(name, name)

    def _disp_cols(self, df: 'pd.DataFrame') -> 'pd.DataFrame':
        """Return a copy of df with column names substituted via _display_names.

        Handles exact matches and trailing _1/_2 suffixes (e.g. cyl_1 → cylinder_1).
        """
        if not self._display_names:
            return df
        def _map(c):
            if c in self._display_names:
                return self._display_names[c]
            for suffix in ('_1', '_2'):
                if c.endswith(suffix):
                    base = c[:-len(suffix)]
                    if base in self._display_names:
                        return self._display_names[base] + suffix
            return c
        return df.rename(columns=_map)

    def _disp_vals(self, df: 'pd.DataFrame', col: str) -> 'pd.DataFrame':
        """Return a copy of df with values in `col` substituted via _display_names."""
        if not self._display_names or col not in df.columns:
            return df
        df = df.copy()
        df[col] = df[col].map(lambda v: self._display_names.get(str(v), v))
        return df

    def _normalize_options(self):
        """Normalize comma-separated string options to lists and resolve paths."""
        o = self.options
        o.in_file = self._resolve_path(o.in_file)
        o.out_dir = self._resolve_path(o.out_dir)
        for attr in ('x', 'slope', 'covariate'):
            v = getattr(o, attr)
            if isinstance(v, str):
                setattr(o, attr, self._split_csv(v))
        # y_correction: normalize to lowercase, validate against the allowed set.
        yc = o.y_correction
        o.y_correction = (yc or 'none').strip().lower()
        if o.y_correction in ('', 'none'):
            o.y_correction = 'none'
        elif o.y_correction not in _Y_CORRECTION_MAP:
            raise ValueError(
                "y_correction must be one of: none, bonferroni, holm, FDR, "
                f"FDR_correlated (got {yc!r})")
        # interaction: a flat comma-separated string becomes a flat list (single interaction pair)
        if isinstance(o.interaction, str):
            o.interaction = self._split_csv(o.interaction)
        # y_units / x_units: normalize to list, matched positionally to y / x variables
        if isinstance(o.y_units, str):
            o.y_units = self._split_csv(o.y_units)
        if isinstance(o.x_units, str):
            o.x_units = self._split_csv(o.x_units)
        if isinstance(o.correlation, str):
            o.correlation = self._split_csv(o.correlation)
        # x_order: parse 'var: l1, l2; var2: l1, l2' string into dict
        if isinstance(o.x_order, str):
            result = {}
            for part in o.x_order.split(';'):
                part = part.strip()
                if ':' in part:
                    var, levels = part.split(':', 1)
                    result[var.strip()] = [l.strip() for l in levels.split(',') if l.strip()]
            o.x_order = result
        # rename: parse string into level renames (dict) and variable display names.
        # Two forms per semicolon-separated entry:
        #   'cyl -> cylinder'         — variable rename (no colon) → _display_names
        #   'cyl: 4 -> 4 cyl, ...'   — level rename (has colon)   → options.rename dict
        if isinstance(o.rename, str):
            level_renames = {}
            for part in o.rename.split(';'):
                part = part.strip()
                if not part:
                    continue
                if ':' in part:
                    # Level rename
                    var, pairs_str = part.split(':', 1)
                    mapping = {}
                    for pair in pairs_str.split(','):
                        if '->' in pair:
                            orig, renamed = pair.split('->', 1)
                            mapping[orig.strip()] = renamed.strip()
                    level_renames[var.strip()] = mapping
                elif '->' in part:
                    # Variable display rename
                    orig, renamed = part.split('->', 1)
                    self._display_names[orig.strip()] = renamed.strip()
            o.rename = level_renames
        # Remap x_order keys: allow display names as well as original column names.
        # _display_names maps original → display; invert it to resolve display → original.
        if isinstance(o.x_order, dict) and self._display_names:
            inv = {v: k for k, v in self._display_names.items()}
            o.x_order = {inv.get(k, k): v for k, v in o.x_order.items()}

    def run(self):
        """Compute the full analysis and gather the results into ``self.output``.

        run() never writes files — it fits a model for each dependent variable
        defined (skipped entirely if none is), runs the correlation analysis if
        ``correlation`` is set, displays each result as it goes, and collects
        everything into ``self.output`` (an :class:`Output`). Call :meth:`save`
        afterwards to persist it to ``out_dir``. Returns ``self.output``.
        """
        import copy

        self._normalize_options()
        self.output = Output()

        y_list = self._split_csv(self.options.y)
        units_list = self.options.y_units  # already normalized to list
        if len(units_list) == 1:
            units_list = units_list * max(len(y_list), 1)
        multi = len(y_list) > 1

        for i, y_var in enumerate(y_list):
            if multi:
                opts = copy.deepcopy(self.options)
                opts.y = y_var
                opts.y_units = units_list[i] if i < len(units_list) else ''
                worker = Kbstat(opts)
                worker._display_names = self._display_names.copy()
            else:
                self.options.y = y_var
                self.options.y_units = units_list[i] if i < len(units_list) else ''
                worker = self
            worker._compute_single()
            worker.print_summary()
            self.output.results.append(ModelResult(
                y=worker.options.y,
                formula=worker._build_formula(),
                anova=worker.anova_table,
                posthoc=(worker.posthoc_by_var or None),  # {var: table} per posthoc_compare, or None
                statistics=worker.statistics_table,
                summary=worker._summary_text() if worker.model is not None else '',
                data=worker.data,
                fig_data=worker.fig_data,
                fig_diagnostics=worker.fig_diagnostics,
            ))

        # Across-y multiple-comparison correction (one family per model term).
        # Only meaningful with more than one dependent variable.
        if self.options.y_correction != 'none' and len(self.output.results) > 1:
            self.output.multiple_comparisons = _multiple_comparisons_table(
                self.output.results, self.options.y_correction)
            print(f"Applied y_correction='{self.options.y_correction}' across "
                  f"{len(self.output.results)} dependent variables "
                  f"(per term) -> MultipleComparisons table")

        if self.options.correlation:
            if self.data is None:
                self._load_data()
                self._apply_constraints()
            self.output.correlation = self.correlate()

        return self.output

    def run_save(self):
        """Convenience: :meth:`run` then :meth:`save`.

        Computes and displays the analysis, then writes it to ``out_dir`` (a
        no-op if ``out_dir`` is unset). Equivalent to calling ``run()`` and
        ``save()`` in sequence. Returns ``self.output``.
        """
        self.run()
        self.save()
        return self.output

    def download_link(self, path=None, archive_name=None):
        """Zip a results directory and return an IPython FileLink for one-click
        download — handy when running on a remote Jupyter server, where save()
        writes to the server, not your machine.

        Defaults to ``options.out_dir``; pass ``path`` to archive a different
        folder (e.g. a parent holding several runs). Call after :meth:`save`.
        Outside a notebook it just prints the archive path.
        """
        import shutil
        target = path or self.options.out_dir
        if not target or not os.path.isdir(target):
            print('Nothing to download — set out_dir and call save() first.')
            return None
        base = archive_name or os.path.basename(os.path.normpath(target))
        archive = shutil.make_archive(base, 'zip', target)
        try:
            from IPython.display import FileLink
            return FileLink(os.path.relpath(archive))
        except Exception:
            print(f'Results archived to {archive}')
            return archive

    def _gather_output(self):
        """Build an Output from the current state (used by save() when run() was
        not called — e.g. after step-by-step fit()/anova()/... calls)."""
        out = Output()
        if self.model is not None:
            out.results.append(ModelResult(
                y=self.options.y if isinstance(self.options.y, str) else '',
                formula=self._build_formula(),
                anova=self.anova_table,
                posthoc=(self.posthoc_by_var or None),  # {var: table} per posthoc_compare, or None
                statistics=self.statistics_table,
                summary=self._summary_text(),
                data=self.data,
                fig_data=self.fig_data,
                fig_diagnostics=self.fig_diagnostics,
            ))
        return out

    def _compute_single(self):
        """Compute (but do not save) the pipeline for a single dependent variable."""
        self._load_data()
        self._apply_rename()
        self._apply_categorical()
        self._apply_constraints()
        if self.options.remove_outliers_prefit:
            self.remove_outliers_pre()
        self.fit()
        if self.options.remove_outliers_postfit:
            self.remove_outliers_post()
            self.fit()
        self.anova()
        self.posthoc()
        self.plot_diagnostics()
        self.plot_data()

    def fit(self):
        """Load data and fit the LMM or GLMM depending on distribution."""
        if self.data is None:
            self._load_data()
        self._normalize_options()
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
            # LMM via lmer/lmerTest (keeps Satterthwaite degrees of freedom)
            self.model = Lmer(formula, data=data_pl)
        else:
            # All non-Gaussian GLMMs use glmmTMB. lme4::glmer returns mis-scaled
            # standard errors for the continuous dispersion families (Gamma,
            # inverse Gaussian); glmmTMB estimates the dispersion explicitly and
            # gives a correct covariance, and it handles random slopes natively.
            self.model = GlmmTMB(formula, data=data_to_use, family=family, link=link,
                                 max_iterations=self.options.max_iterations)
        self.model.fit(summarize=False)
        self._df_runtime = None                 # re-resolve df method for the (re)fitted model
        if not getattr(self, '_df_validated', False):
            self._validate_df_method()          # warn once if df_method is unavailable here
            self._df_validated = True

        # Extract AIC, BIC, logLik from the R model object
        r_obj = getattr(self.model, 'r_model', getattr(self.model, 'model_obj', None))
        if r_obj is not None:
            try:
                self.AIC    = float(ro.r('AIC')(r_obj)[0])
                self.BIC    = float(ro.r('BIC')(r_obj)[0])
                self.logLik = float(ro.r('logLik')(r_obj)[0])
            except Exception:
                self.AIC = self.BIC = self.logLik = None
        else:
            self.AIC = self.BIC = self.logLik = None

    # Accepted options.df_method values (normalized) -> canonical request.
    _DF_ALIASES = {
        'auto': 'auto',
        'kr': 'kenward-roger', 'kenward-roger': 'kenward-roger', 'kenwardroger': 'kenward-roger',
        'satt': 'satterthwaite', 'satterthwaite': 'satterthwaite',
        'wald': 'asymptotic', 'asymptotic': 'asymptotic',
    }

    def _pbkrtest_available(self):
        """True if the R package pbkrtest (needed for Kenward-Roger) is installed."""
        cache = getattr(type(self), '_pbkrtest', None)
        if cache is None:
            try:
                cache = bool(ro.r('requireNamespace')('pbkrtest', quietly=True)[0])
            except Exception:
                cache = False
            type(self)._pbkrtest = cache
        return cache

    def _canonical_df_request(self):
        """Normalize options.df_method to a canonical request ('auto',
        'kenward-roger', 'satterthwaite', 'asymptotic'); None if unrecognised."""
        raw = getattr(self.options, 'df_method', 'auto')
        if raw is None:
            return 'auto'
        key = str(raw).strip().lower().replace('_', '-').replace(' ', '')
        return self._DF_ALIASES.get(key)

    def _resolve_df_method(self):
        """Effective df method for the fitted model after honouring
        options.df_method, pbkrtest availability and any runtime fallback. One of
        'kenward-roger', 'satterthwaite', 'asymptotic', 'exact'."""
        if self._df_runtime:                            # runtime KR fallback already decided
            return self._df_runtime
        if not isinstance(self.model, Lmer):
            # Plain LM -> exact residual df; GLMM -> asymptotic. Not user-changeable.
            return 'exact' if isinstance(self.model, Lm) else 'asymptotic'
        req = self._canonical_df_request() or 'auto'    # unknown value -> auto (validate warns)
        if req in ('auto', 'kenward-roger'):
            return 'kenward-roger' if self._pbkrtest_available() else 'satterthwaite'
        return req                                      # 'satterthwaite' or 'asymptotic'

    def _df_method(self):
        """emmeans lmer.df argument for the current model, honouring df_method.

        The ANOVA and the post-hoc both use this so the two strata stay
        consistent. Returns None where lmer.df does not apply: plain LMs (exact
        residual df) and GLMMs (asymptotic by default)."""
        if not isinstance(self.model, Lmer):
            return None                                 # LM: ignored (exact); GLMM: default asymptotic
        return self._resolve_df_method()                # 'kenward-roger'|'satterthwaite'|'asymptotic'

    def _df_method_label(self):
        """Human-readable denominator-df method, for reporting in Summary.txt."""
        return {
            'kenward-roger': 'Kenward-Roger',
            'satterthwaite': 'Satterthwaite',
            'asymptotic':    'asymptotic (Wald z, df = Inf)',
            'exact':         'exact residual df (n - p)',
        }[self._resolve_df_method()]

    def _validate_df_method(self):
        """Warn if options.df_method cannot be honoured for the fitted model and
        recommend alternatives (including 'auto'). Resolution falls back
        gracefully; this only surfaces the reason to the user."""
        if self.model is None:
            return
        raw = getattr(self.options, 'df_method', 'auto')
        req = self._canonical_df_request()
        if req is None:
            warnings.warn(
                f"df_method={raw!r} is not recognised; using 'auto'. Valid values: "
                "'auto', 'kenward-roger', 'satterthwaite', 'asymptotic' "
                "(aliases 'kr', 'satt', 'wald').", stacklevel=2)
            return
        if req == 'auto':
            return
        if isinstance(self.model, Lm):
            warnings.warn(
                f"df_method={req!r} has no effect for a plain linear model (no random "
                "effects): exact residual df (n - p) are always used. Set df_method='auto' "
                "to silence this.", stacklevel=2)
        elif not isinstance(self.model, Lmer):          # GLMM
            if req != 'asymptotic':
                warnings.warn(
                    f"df_method={req!r} is not defined for generalised linear mixed models "
                    f"(distribution={self.options.distribution!r}); using asymptotic "
                    "(Wald z, df = Inf). Set df_method to 'asymptotic' or 'auto'.", stacklevel=2)
        else:                                           # Gaussian LMM
            if req == 'kenward-roger' and not self._pbkrtest_available():
                warnings.warn(
                    "df_method='kenward-roger' requires the R package 'pbkrtest', which is "
                    "not installed; using Satterthwaite. Install pbkrtest, or set df_method "
                    "to 'satterthwaite', 'asymptotic', or 'auto'.", stacklevel=2)

    def anova(self):
        """Extract and enrich the ANOVA table from the fitted model.

        Denominator degrees of freedom follow _df_method(): Kenward-Roger for
        Gaussian LMMs when pbkrtest is available, else Satterthwaite. The
        post-hoc uses the same method, so the two strata are consistent. (GLMMs
        are asymptotic; plain LMs use exact df.)
        """
        if self.model is None:
            raise RuntimeError('Call fit() before anova()')

        data_to_use = self.data
        if 'is_outlier' in self.data.columns:
            data_to_use = self.data[~self.data['is_outlier']]

        method = self._df_method() or 'satterthwaite'  # ignored by LM (exact) / GLMM (asymptotic)
        try:
            self.model.anova(jointtest_kwargs={'mode': method, 'lmer_df': method})
        except Exception as exc:
            if method != 'kenward-roger':
                raise
            # KR can fail for some models/datasets (e.g. singular fits); fall back
            # to Satterthwaite and keep the post-hoc and reporting consistent.
            warnings.warn(
                f"Kenward-Roger could not be computed for this model/dataset "
                f"({type(exc).__name__}); falling back to Satterthwaite. Set "
                "df_method='satterthwaite' or 'auto' to silence this.", stacklevel=2)
            self._df_runtime = 'satterthwaite'
            method = 'satterthwaite'
            self.model.anova(jointtest_kwargs={'mode': method, 'lmer_df': method})
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

        For Gaussian LMMs the contrast df use the same method as the ANOVA
        (Kenward-Roger when pbkrtest is available, else Satterthwaite), pinned
        via emm_options below so the result does not depend on the ambient
        emmeans default. For GLMMs neither applies and emmeans falls back to
        asymptotic inference (df=Inf); plain LMs use exact df. This is expected
        behaviour, not an error.
        """
        if self.model is None:
            raise RuntimeError('Call fit() before posthoc()')
        factors = self.options.x if self.options.x else []
        if not factors:
            return None
        self.model.set_factors(factors)
        # Override the contr.treatment default that set_factors() hard-codes
        self.model.set_contrasts({f: 'contr.sum' for f in factors})
        # Pin the contrast df method to match anova() (KR/Satterthwaite); no-op
        # for LM (exact) and GLMM (asymptotic), which ignore lmer.df.
        _dfm = self._df_method()
        if _dfm:
            ro.r("emmeans::emm_options(lmer.df = '%s')" % _dfm)
        self.model.emmeans(
            marginal_var=factors[0],
            p_adjust=self.options.posthoc_correction,
        )

        # Use R directly so factor labels are the actual level values, not the
        # integer indices pymer4 returns.
        import rpy2.robjects.pandas2ri as p2ri
        r_obj = getattr(self.model, 'r_model', getattr(self.model, 'model_obj', None))

        # Full interaction EMM grid (independent of which factor is compared) so
        # plot_data() can place each panel's CI bar at the correct per-cell value.
        self._emm_df_full = None
        if r_obj is not None and len(factors) > 1:
            try:
                _formula_full = ' * '.join(factors)
                _emm_full = ro.r('emmeans::emmeans')(r_obj, ro.Formula(f'~{_formula_full}'), type='response')
                _emm_full_r = ro.r('as.data.frame')(_emm_full)
                ro.r.assign('._emm_full_tmp', _emm_full_r)
                for _fc in factors:
                    ro.r(f'._emm_full_tmp[["{_fc}"]] <- as.character(._emm_full_tmp[["{_fc}"]])')
                self._emm_df_full = p2ri.rpy2py(ro.r('._emm_full_tmp'))
            except Exception:
                pass

        # Pairwise comparisons for each factor named by options.posthoc_compare,
        # each marginal (averaged over the other factors). 'none'/'' -> none.
        compare_vars = self._compare_vars()
        self.contrasts_by_var = {}
        self.posthoc_by_var = {}
        primary_emm = None
        for var in compare_vars:
            if r_obj is None:
                break
            ct_adj, ph_df, var_emm = self._pairwise_for(r_obj, var)
            if ct_adj is not None:
                self.contrasts_by_var[var] = ct_adj
            if ph_df is not None:
                self.posthoc_by_var[var] = ph_df
            if primary_emm is None:
                primary_emm = var_emm

        # Primary tables (first compared variable, or None when comparisons are
        # off) — kept for the summary text and backward compatibility.
        primary = compare_vars[0] if compare_vars else None
        self.contrasts_table = self.contrasts_by_var.get(primary)
        self.posthoc_table = self.posthoc_by_var.get(primary)

        # EMM table for the single-factor dot fallback (plot_data prefers the full
        # grid; this covers single-factor models and the comparisons-off case).
        if primary_emm is None and r_obj is not None:
            _, _, primary_emm = self._pairwise_for(r_obj, factors[0])
        self._emm_df = primary_emm
        self.statistics_table = self._build_statistics_table(factors)
        return self.posthoc_table

    def _compare_vars(self):
        """Resolve options.posthoc_compare into the list of factors to compare.

        '' / 'none' -> [] (comparisons off); 'auto' -> [first factor]; otherwise
        the listed factors. Raises if a factor is named with a reserved word
        ('auto'/'none') or if a listed name is not a fixed-effect factor.
        """
        factors = list(self.options.x or [])
        clash = [f for f in factors if str(f).strip().lower() in ('auto', 'none')]
        if clash:
            raise ValueError(
                f"Fixed-effect factor(s) {clash} use a name reserved by "
                f"options.posthoc_compare ('auto'/'none'). Please rename them.")
        spec = str(self.options.posthoc_compare or '').strip()
        low = spec.lower()
        if low in ('', 'none'):
            return []
        if low == 'auto':
            return factors[:1]
        requested = [v.strip() for v in spec.split(',') if v.strip()]
        bad = [v for v in requested if v not in factors]
        if bad:
            raise ValueError(
                f"options.posthoc_compare lists {bad}, which are not fixed-effect "
                f"factors (x = {factors}).")
        return requested

    def _pairwise_for(self, r_obj, var):
        """Marginal pairwise contrasts + rich posthoc table for one factor ``var``
        (averaged over the other factors). Returns (contrasts_adj, posthoc_df,
        emm_df); any element may be None on failure."""
        import rpy2.robjects.pandas2ri as p2ri
        ct_adj = ct_raw = emm_df = None
        try:
            # Link-scale emmeans: pairs() contrast strings and t/z ratios are correct here
            _emm_link = ro.r('emmeans::emmeans')(r_obj, ro.Formula(f'~{var}'))
            ct_adj = p2ri.rpy2py(ro.r('as.data.frame')(
                ro.r('pairs')(_emm_link, adjust=self.options.posthoc_correction)))
            ct_raw = p2ri.rpy2py(ro.r('as.data.frame')(
                ro.r('pairs')(_emm_link, adjust='none')))
            # Response-scale emmeans: EMM/CI display values for the table and plot
            _emm_resp = ro.r('emmeans::emmeans')(r_obj, ro.Formula(f'~{var}'), type='response')
            _emm_df_r = ro.r('as.data.frame')(_emm_resp)
            ro.r.assign('._emm_df_tmp', _emm_df_r)
            ro.r(f'._emm_df_tmp[["{var}"]] <- as.character(._emm_df_tmp[["{var}"]])')
            emm_df = p2ri.rpy2py(ro.r('._emm_df_tmp'))
        except Exception:
            pass
        return ct_adj, self._build_posthoc_table(var, emm_df, ct_adj, ct_raw), emm_df

    def _build_posthoc_table(self, factor_col, emm_df, ct_adj, ct_raw):
        """Build the rich pairwise posthoc DataFrame for factor ``factor_col``."""
        if not (emm_df is not None and ct_adj is not None and ct_raw is not None
                and factor_col in emm_df.columns):
            return emm_df if emm_df is not None else pd.DataFrame()

        def _parse_level(part, levels):
            for lev in levels:
                ls = str(lev)
                if part == ls or part == f'{factor_col}{ls}' or part == f'{factor_col} {ls}':
                    return lev
            return part

        inv = self._inverse_fn  # None if no transform

        def _bt(val):
            return float(inv(np.array([val]))[0]) if inv is not None else float(val)

        emm_col = next((c for c in ('emmean', 'rate', 'response', 'prob')
                        if c in emm_df.columns), emm_df.columns[1])
        lo_col = next((c for c in ('lower.CL', 'lower_CL', 'asymp.LCL') if c in emm_df.columns), None)
        hi_col = next((c for c in ('upper.CL', 'upper_CL', 'asymp.UCL') if c in emm_df.columns), None)

        def _emm_ci_str(lev):
            row = emm_df[emm_df[factor_col] == lev]
            if len(row) == 0:
                return ''
            r = row.iloc[0]
            emm = _bt(r[emm_col])
            lo = _bt(r[lo_col]) if lo_col else np.nan
            hi = _bt(r[hi_col]) if hi_col else np.nan
            if np.isnan(lo) or np.isnan(hi):
                return f"{emm:.3f}"
            return f"{emm:.3f} ({lo:.3f}, {hi:.3f})"

        def _emm_val(lev):
            row = emm_df[emm_df[factor_col] == lev]
            if len(row) == 0:
                return np.nan
            return _bt(row.iloc[0][emm_col])

        levels = emm_df[factor_col].tolist()
        rows = []
        for (_, cadj), (_, craw) in zip(ct_adj.iterrows(), ct_raw.iterrows()):
            parts = [p.strip() for p in str(cadj['contrast']).split(' - ')]
            lev1 = _parse_level(parts[0], levels) if len(parts) > 0 else ''
            lev2 = _parse_level(parts[1], levels) if len(parts) > 1 else ''
            ratio_col = 't.ratio' if 't.ratio' in cadj.index else 'z.ratio'
            t_val = float(cadj[ratio_col])
            df_val = float(cadj['df']) if 'df' in cadj.index else float('inf')
            smd = 2 * abs(t_val) / np.sqrt(df_val) if df_val > 0 else np.nan
            p_raw = float(craw['p.value'])
            p_corr = float(cadj['p.value'])
            diff = _emm_val(lev1) - _emm_val(lev2)
            rows.append({
                f'{factor_col}_1': str(lev1),
                f'{factor_col}_2': str(lev2),
                'emm_1': _emm_ci_str(lev1),
                'emm_2': _emm_ci_str(lev2),
                'diff': diff, 't': t_val, 'df': df_val,
                'p': p_raw, 'pCorr': p_corr, 'SMD': smd,
                'effectSize': _d_label(smd), 'significance': _sig_stars(p_corr),
            })
        return pd.DataFrame(rows)

    def correlate(self):
        """Compute pairwise Pearson and partial correlations, VIF, and scatter grids.

        Variables are taken from options.correlation (must be numeric).
        VIF is computed for numeric variables in options.x + options.covariate.
        Partial correlations are produced when len(vars) >= 3; with only 2 variables
        there is nothing to control for and partial == raw.
        """
        import itertools
        from scipy.stats import pearsonr
        from sklearn.linear_model import LinearRegression

        if self.data is None:
            self._load_data()

        vars_ = self.options.correlation
        if not vars_:
            return

        # --- VIF: for numeric predictors (x and covariate) ---
        vif_table = None
        vif_map = {}
        all_predictors = self.options.x + self.options.covariate
        x_numeric = [v for v in all_predictors
                     if v in self.data.columns
                     and pd.api.types.is_numeric_dtype(self.data[v])]
        if len(x_numeric) > 1:
            X = self.data[x_numeric].dropna().astype(float)
            vif_rows = []
            for v in x_numeric:
                others = [c for c in x_numeric if c != v]
                r2 = LinearRegression().fit(X[others], X[v]).score(X[others], X[v])
                vif = 1 / (1 - r2) if r2 < 1.0 else float('inf')
                vif_map[v] = vif
                vif_rows.append({
                    'variable': v,
                    'VIF':      round(vif, 3),
                    'verdict':  'OK' if vif < 5 else ('concerning' if vif < 10 else 'severe'),
                })
            vif_table = pd.DataFrame(vif_rows)
            for row in vif_rows:
                print(f"VIF  {row['variable']:<24}: {row['VIF']:.3f}  ({row['verdict']})")

        # --- Raw Pearson correlation table ---
        rows = []
        for v1, v2 in itertools.combinations(vars_, 2):
            xy = self.data[[v1, v2]].dropna()
            r, p = pearsonr(xy[v1].astype(float), xy[v2].astype(float))
            rows.append({
                'var_1':        v1,
                'var_2':        v2,
                'r':            round(r, 4),
                'p':            round(p, 4),
                'significance': _sig_stars(p),
                'effectSize':   _r_label(r),
            })
        self.correlation_table = pd.DataFrame(rows)

        # --- Partial correlation table (only meaningful when n >= 3) ---
        partial_table = None
        residuals = {}
        if len(vars_) >= 3:
            clean = self.data[vars_].dropna().astype(float)
            for v in vars_:
                others = [o for o in vars_ if o != v]
                e = clean[v].values - LinearRegression().fit(
                    clean[others], clean[v]).predict(clean[others])
                residuals[v] = e
            part_rows = []
            for v1, v2 in itertools.combinations(vars_, 2):
                r, p = pearsonr(residuals[v1], residuals[v2])
                part_rows.append({
                    'var_1':        v1,
                    'var_2':        v2,
                    'r':            round(r, 4),
                    'p':            round(p, 4),
                    'significance': _sig_stars(p),
                    'effectSize':   _r_label(r),
                })
            partial_table = pd.DataFrame(part_rows)

        # Build the figures for display; persistence is deferred to save().
        n_pairs = len(self.correlation_table)
        corr_title   = 'Correlation'   if n_pairs == 1 else 'Correlations'
        pcorr_title  = 'Partial Correlation'   if n_pairs == 1 else 'Partial Correlations'

        fig_scatter = self._plot_corr_scatter(
            self.correlation_table, vars_,
            {v: self.data[v].astype(float).values for v in vars_},
            corr_title)

        fig_partial_scatter = None
        if partial_table is not None:
            fig_partial_scatter = self._plot_corr_scatter(
                partial_table, vars_, residuals,
                pcorr_title + '\n(residuals after removing all other variables)',
                xlabel_suffix=' (residual)', ylabel_suffix=' (residual)')

        fig_table = self._plot_corr_table(self.correlation_table, vars_, corr_title)

        fig_partial_table = None
        if partial_table is not None:
            fig_partial_table = self._plot_corr_table(partial_table, vars_, pcorr_title)

        return CorrelationResult(
            correlation_table=self.correlation_table,
            partial_table=partial_table,
            vif_table=vif_table,
            fig_scatter=fig_scatter,
            fig_table=fig_table,
            fig_partial_scatter=fig_partial_scatter,
            fig_partial_table=fig_partial_table,
        )

    def _plot_corr_scatter(self, corr_df, vars_, data_arrays, title,
                           xlabel_suffix='', ylabel_suffix=''):
        """Scatter plot grid for a correlation table. Returns the figure."""
        self._apply_font()
        pairs = [(vars_[i], vars_[j])
                 for i in range(len(vars_)) for j in range(i + 1, len(vars_))]
        n_pairs = len(pairs)
        ncols = min(n_pairs, max(2, int(np.ceil(np.sqrt(n_pairs)))))
        nrows = int(np.ceil(n_pairs / ncols))
        fig, axes = plt.subplots(nrows, ncols, figsize=(3.2 * ncols, 3.2 * nrows),
                                 squeeze=False)
        color = sns.color_palette()[0]

        for idx, (v1, v2) in enumerate(pairs):
            ax = axes[idx // ncols][idx % ncols]
            x_data = np.asarray(data_arrays[v1], dtype=float)
            y_data = np.asarray(data_arrays[v2], dtype=float)
            mask = ~(np.isnan(x_data) | np.isnan(y_data))
            x_data, y_data = x_data[mask], y_data[mask]

            ax.scatter(x_data, y_data, color=color, alpha=0.6, s=20, linewidths=0)
            m, b = np.polyfit(x_data, y_data, 1)
            x_line = np.array([x_data.min(), x_data.max()])
            ax.plot(x_line, m * x_line + b, color='red', linewidth=1.2)

            r_row = corr_df[(corr_df['var_1'] == v1) & (corr_df['var_2'] == v2)]
            if len(r_row):
                r_val = r_row.iloc[0]['r']
                p_val = r_row.iloc[0]['p']
                stars = r_row.iloc[0]['significance']
                ax.set_title(f"r = {r_val:.3f}{stars}    p = {p_val:.4f}",
                             fontsize=7, color='0.3', fontstyle='italic', pad=3)

            ax.set_xlabel(self._disp(v1) + xlabel_suffix, fontsize=8)
            ax.set_ylabel(self._disp(v2) + ylabel_suffix, fontsize=8)
            ax.tick_params(labelsize=6)

        for idx in range(n_pairs, nrows * ncols):
            axes[idx // ncols][idx % ncols].set_visible(False)

        fig.suptitle(title, fontweight='bold', fontsize=11,
                     fontfamily=self._title_font_family())
        plt.tight_layout()
        self._show_fig(fig)
        return fig

    def _plot_corr_table(self, corr_df, vars_, title):
        """Colour-coded lower-triangle correlation heatmap table. Returns the figure."""
        self._apply_font()
        import matplotlib.patches as mpatches
        cmap = plt.cm.RdBu_r

        row_vars = vars_[1:]
        col_vars = vars_[:-1]
        nr = len(row_vars)
        nc = len(col_vars)

        cell_size  = 1.4
        header_size = 1.8
        top_margin  = 1.5
        fig_w = header_size + nc * cell_size
        fig_h = top_margin  + nr * cell_size
        fig_t, ax_t = plt.subplots(figsize=(fig_w, fig_h))
        ax_t.set_xlim(-0.15, nc + 0.15)
        ax_t.axis('off')

        bg_sig   = '0.93'
        bg_empty = '1.0'
        fs = max(5, min(9, 72 / len(vars_)))

        for ri, v_row in enumerate(row_vars):
            for ci, v_col in enumerate(col_vars):
                x = ci
                y = nr - 1 - ri
                orig_row = vars_.index(v_row)
                orig_col = vars_.index(v_col)

                if orig_col < orig_row:
                    r_row = corr_df[
                        (corr_df['var_1'] == v_col) & (corr_df['var_2'] == v_row)]
                    if len(r_row) == 0:
                        r_row = corr_df[
                            (corr_df['var_1'] == v_row) & (corr_df['var_2'] == v_col)]
                    if len(r_row):
                        r_val = float(r_row.iloc[0]['r'])
                        p_val = float(r_row.iloc[0]['p'])
                        stars = str(r_row.iloc[0]['significance'])
                        sig   = p_val < 0.05
                    else:
                        r_val, p_val, stars, sig = 0.0, 1.0, '', False

                    if sig:
                        facecolor = cmap((r_val + 1) / 2)
                        textcolor = 'white' if abs(r_val) > 0.5 else '0.2'
                        label     = f"{r_val:.3f}{stars}"
                    else:
                        facecolor = bg_sig
                        textcolor = '0.6'
                        label     = 'n.s.'

                    ax_t.add_patch(mpatches.FancyBboxPatch(
                        (x + 0.04, y + 0.04), 0.92, 0.92,
                        boxstyle='square,pad=0', linewidth=0.4,
                        edgecolor='0.7', facecolor=facecolor,
                        transform=ax_t.transData))
                    if label:
                        ax_t.text(x + 0.5, y + 0.5, label,
                                  ha='center', va='center',
                                  fontsize=fs, color=textcolor, fontweight='bold')

                elif orig_col == orig_row:
                    ax_t.add_patch(mpatches.FancyBboxPatch(
                        (x + 0.04, y + 0.04), 0.92, 0.92,
                        boxstyle='square,pad=0', linewidth=0.4,
                        edgecolor='0.7', facecolor=bg_empty,
                        transform=ax_t.transData))

        for ci, v in enumerate(col_vars):
            ax_t.text(ci + 0.5, nr + 0.1, self._disp(v), ha='center', va='bottom',
                      fontsize=fs, fontweight='bold', rotation=45)
        for ri, v in enumerate(row_vars):
            ax_t.text(-0.1, nr - 1 - ri + 0.5, self._disp(v), ha='right', va='center',
                      fontsize=fs, fontweight='bold')

        ax_t.set_ylim(-0.15, nr + 0.7)
        ax_t.set_title(title, fontweight='bold', fontsize=13, pad=8,
                       fontfamily=self._title_font_family())
        plt.tight_layout()
        self._show_fig(fig_t)
        return fig_t

    def save(self):
        """Persist ``self.output`` (produced by :meth:`run`) to ``out_dir``.

        Writes only what was produced — each artifact is saved only if present,
        so a correlation-only run writes just the correlation outputs, a model
        run writes its tables/figures, etc. Each dependent variable's results go
        into its own subdirectory (named after the variable), whether the run has
        one DV or many. No-op (with a notice) when ``out_dir`` is empty.
        """
        out_dir = self.options.out_dir
        if not out_dir:
            print('out_dir is empty — results shown inline only, nothing written. '
                  'Set options.out_dir to save tables and figures.')
            return
        # Prefer the gathered output from run(); fall back to the current state
        # so a step-by-step fit()/anova()/... then save() still works.
        output = self.output if self.output is not None else self._gather_output()
        if output is None or (not output.results and output.correlation is None):
            print('Nothing to save — run the analysis (run/run_save) or fit it first.')
            return
        os.makedirs(out_dir, exist_ok=True)

        # Each dependent variable's results go into their own subdirectory,
        # named after the variable — consistently, whether the run has one DV
        # or many. (Previously a single-DV run wrote flat into out_dir, which
        # made downstream result-collecting code special-case the two layouts.)
        for res in output.results:
            d = os.path.join(out_dir, res.y)
            os.makedirs(d, exist_ok=True)
            if res.anova is not None:
                anova_df = res.anova.to_pandas() if hasattr(res.anova, 'to_pandas') else res.anova
                self._disp_vals(anova_df, 'Term').to_excel(os.path.join(d, 'Anova.xlsx'), index=False)
                print(f'Saved Anova.xlsx to {d}')
            if res.posthoc is not None:
                # posthoc is a {variable: table} dict (one per posthoc_compare
                # variable); write each as Posthoc_<variable>.xlsx.
                if isinstance(res.posthoc, dict):
                    for var, ph in res.posthoc.items():
                        self._write_posthoc_xlsx(ph, os.path.join(d, f'Posthoc_{var}.xlsx'))
                        print(f'Saved Posthoc_{var}.xlsx to {d}')
                else:
                    self._write_posthoc_xlsx(res.posthoc, os.path.join(d, 'Posthoc.xlsx'))
                    print(f'Saved Posthoc.xlsx to {d}')
            if res.statistics is not None:
                self._disp_cols(res.statistics).to_excel(os.path.join(d, 'Statistics.xlsx'), index=False)
                print(f'Saved Statistics.xlsx to {d}')
            if res.data is not None:
                res.data.to_csv(os.path.join(d, 'Data.csv'), index=False)
                print(f'Saved Data.csv to {d}')
            if res.summary:
                with open(os.path.join(d, 'Summary.txt'), 'w', encoding='utf-8') as fh:
                    fh.write(res.summary + '\n')
                print(f'Saved Summary.txt to {d}')
            if res.fig_data is not None:
                # fig_data is a single Figure (<=3 factors) or a dict
                # {level_suffix: Figure} when a 4th+ factor split it into files.
                if isinstance(res.fig_data, dict):
                    for suffix, f in res.fig_data.items():
                        self._write_fig(f, d, f'DataPlots_{suffix}', html=True, tight=True)
                else:
                    self._write_fig(res.fig_data, d, 'DataPlots', html=True, tight=True)
            if res.fig_diagnostics is not None:
                self._write_fig(res.fig_diagnostics, d, 'Diagnostics', html=True, tight=False)

        if output.multiple_comparisons is not None:
            mc_path = os.path.join(out_dir, 'MultipleComparisons.xlsx')
            output.multiple_comparisons.to_excel(mc_path, index=False)
            print(f'Saved MultipleComparisons.xlsx to {out_dir}')

        cr = output.correlation
        if cr is not None:
            if cr.correlation_table is not None:
                self._write_corr_xlsx(cr.correlation_table, os.path.join(out_dir, 'Correlation.xlsx'), 'Correlation')
                print(f'Saved Correlation.xlsx to {out_dir}')
            if cr.partial_table is not None:
                self._write_corr_xlsx(cr.partial_table, os.path.join(out_dir, 'PartialCorrelation.xlsx'), 'PartialCorrelation')
                print(f'Saved PartialCorrelation.xlsx to {out_dir}')
            if cr.vif_table is not None:
                self._write_corr_xlsx(cr.vif_table, os.path.join(out_dir, 'VIF.xlsx'), 'VIF', disp_vals=False)
                print(f'Saved VIF.xlsx to {out_dir}')
            for fig, stem in [(cr.fig_scatter, 'Correlation'), (cr.fig_table, 'CorrelationTable'),
                              (cr.fig_partial_scatter, 'PartialCorrelation'),
                              (cr.fig_partial_table, 'PartialCorrelationTable')]:
                if fig is not None:
                    self._write_fig(fig, out_dir, stem, html=False, tight=True)

    @staticmethod
    def _autofit_xlsx(writer, sheet_name):
        ws = writer.sheets[sheet_name]
        for col_cells in ws.columns:
            width = max(len(str(cell.value or '')) for cell in col_cells) * 0.85 + 2
            ws.column_dimensions[col_cells[0].column_letter].width = width

    def _write_posthoc_xlsx(self, posthoc, path):
        ph_df = posthoc.to_pandas() if hasattr(posthoc, 'to_pandas') else posthoc
        ph_df = self._disp_cols(ph_df)
        for col in ph_df.columns:
            if col in ('p', 'pCorr'):
                ph_df[col] = ph_df[col].round(4)
            elif ph_df[col].dtype == float:
                ph_df[col] = ph_df[col].round(3)
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            ph_df.to_excel(writer, index=False, sheet_name='Posthoc')
            self._autofit_xlsx(writer, 'Posthoc')

    def _write_corr_xlsx(self, table, path, sheet, disp_vals=True):
        out = self._disp_vals(self._disp_vals(table, 'var_1'), 'var_2') if disp_vals else table
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            out.to_excel(writer, index=False, sheet_name=sheet)
            self._autofit_xlsx(writer, sheet)

    def _write_fig(self, fig, d, stem, html=False, tight=True):
        fig.savefig(os.path.join(d, f'{stem}.pdf'))
        if tight:
            fig.savefig(os.path.join(d, f'{stem}.png'), dpi=150, bbox_inches='tight')
        else:
            fig.savefig(os.path.join(d, f'{stem}.png'), dpi=150)
        if html:
            self._save_interactive(fig, os.path.join(d, f'{stem}.html'))
        if self.options.figure_display != 'show_keep':
            plt.close(fig)
        print(f'Saved {stem}.pdf/.png to {d}')

    def remove_outliers_pre(self):
        """Flag outliers per group using the IQR rule (1.5 × IQR beyond Q1/Q3)."""
        y = self.options.y

        def _iqr_mask(series):
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            return (series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)

        if self.options.x:
            flags = self.data.groupby(self.options.x)[y].transform(_iqr_mask)
        else:
            flags = _iqr_mask(self.data[y])

        self.data['is_outlier'] = flags.astype(bool)
        n = int(flags.sum())
        if n:
            print(f"Pre-fit outlier removal: {n} observation(s) flagged by IQR rule.")

    def remove_outliers_post(self):
        if self.model is None:
            raise RuntimeError("You must fit the model before removing post outliers.")
            return

        r_obj = getattr(self.model, 'r_model', getattr(self.model, 'model_obj', None))

        if r_obj is not None:
            residuals = np.array(ro.r('residuals')(r_obj, type="pearson"))
        else:
            raise RuntimeError("Unable to find R model, rerun the fit")

        z_scores = np.abs((residuals - residuals.mean()) / (residuals.std() + 1e-9))

        new_outliers = z_scores > 3

        if 'is_outlier' not in self.data.columns:
            self.data['is_outlier'] = False
        healthy_points = self.data[~self.data['is_outlier']].index
        self.data.loc[healthy_points, 'is_outlier'] = new_outliers
        n = int(new_outliers.sum())
        if n:
            print(f"Post-fit outlier removal: {n} observation(s) flagged by Pearson residual z > 3.")


    @staticmethod
    def _interactive_backend():
        """True only for interactive GUI backends (MacOSX, Qt, Tk, …).

        False for the Jupyter inline backend and headless Agg, where there is
        no window to service and ``plt.pause`` would merely stall.
        """
        import matplotlib
        try:
            from matplotlib.backends import BackendFilter, backend_registry
            interactive = {b.lower() for b in
                           backend_registry.list_builtin(BackendFilter.INTERACTIVE)}
        except Exception:  # pragma: no cover - older matplotlib fallback
            interactive = {b.lower() for b in getattr(matplotlib.rcsetup, 'interactive_bk', [])}
        return matplotlib.get_backend().lower() in interactive

    def _show_fig(self, fig, close=False):
        """Display ``fig`` according to ``options.figure_display``.

        Modes (all still save files elsewhere):
          'save_only'  — do not display
          'show_close' — display briefly (~3 s); default
          'show_keep'  — display and leave the window open

        The ~3 s pause only applies to interactive GUI backends. Under the
        Jupyter inline backend (or headless Agg) there is no window to keep
        alive, so the pause is skipped and 'show_close'/'show_keep' both just
        render the figure inline once; 'save_only' still suppresses it.

        Pass ``close=True`` for figures that are saved in place (the
        correlation plots) so they are also closed here; figures saved later
        in :meth:`save` pass ``close=False`` and are closed there instead.
        'show_keep' never closes.
        """
        mode = getattr(self.options, 'figure_display', 'show_close')
        if mode != 'save_only':
            plt.show(block=False)
            if mode == 'show_close' and self._interactive_backend():
                plt.pause(3)
        if close and mode != 'show_keep':
            plt.close(fig)

    # Cache of resolved title fonts, keyed by the base (body) font name. The
    # title font is a condensed/narrow variant of the body font when installed.
    _resolved_title_font = {}

    def _title_font_family(self):
        """Resolve the title font: options.title_font if set; otherwise a
        condensed/narrow variant of the body font (options.font) when one is
        installed — e.g. 'Arial' -> 'Arial Narrow', 'DejaVu Sans' -> 'DejaVu Sans
        Condensed' — else the body font itself. Probed quietly so absent families
        don't emit matplotlib 'font not found' warnings."""
        if self.options.title_font:
            return self.options.title_font
        base = self._body_font() or plt.rcParams.get('font.family', 'sans-serif')
        base_name = base[0] if isinstance(base, (list, tuple)) else str(base)
        cache = Kbstat._resolved_title_font
        if base_name not in cache:
            from matplotlib import font_manager as fm
            available = {f.name for f in fm.fontManager.ttflist}
            cache[base_name] = next(
                (fam for fam in (f'{base_name} Condensed', f'{base_name} Narrow')
                 if fam in available), base_name)
        return cache[base_name]

    def _add_suptitle(self, fig, text, max_size=14):
        """Create the bold figure suptitle in a narrow/condensed font (see
        options.title_font). Call :meth:`_fit_suptitle_to_axes` after the layout
        is final to centre it over the plot box and shrink it to that width.
        Returns the Text object."""
        return fig.suptitle(text, fontweight='bold', fontsize=max_size,
                            fontfamily=self._title_font_family())

    def _fit_suptitle_to_axes(self, st, fig, min_size=8, margin=0.98):
        """Centre the suptitle over the axes (plot box) span and shrink its font
        so it stays within the box's horizontal extent. Call after the layout is
        settled (e.g. after tight_layout), when axes positions are final."""
        if st is None:
            return
        boxes = [a.get_position() for a in fig.axes]
        if not boxes:
            return
        x0 = min(b.x0 for b in boxes)
        x1 = max(b.x1 for b in boxes)
        st.set_x(0.5 * (x0 + x1))
        avail_px = (x1 - x0) * fig.get_figwidth() * fig.dpi
        try:
            text_px = st.get_window_extent(renderer=fig.canvas.get_renderer()).width
        except Exception:
            # Fallback estimate: a bold condensed glyph is roughly 0.55 em wide.
            text_px = len(st.get_text()) * 0.55 * st.get_fontsize() * fig.dpi / 72.0
        if text_px > margin * avail_px:
            st.set_fontsize(max(min_size, st.get_fontsize() * margin * avail_px / text_px))

    def plot_data(self):
        """Generate publication-ready summary plots matching the MATLAB kbstat style.

        Layout mirrors plotGroups.m: one panel per level of the 2nd independent
        variable (or a single panel when there is only one x-variable).  Within
        each panel the 1st x-variable is on the x-axis with colored violins,
        scatter points in matching colors, paired-subject connecting lines,
        a white EMM marker with a 95 % CI bar, and significance brackets.
        """
        self._apply_font()
        if not self.options.x:
            print("No independent variables to plot.")
            return
        # Use raw (untransformed) data for plotting so the y-axis is in original units
        base = self._data_raw if self._data_raw is not None else self.data
        # Ensure the outlier column exists (mirror from self.data if needed)
        if base is not None and 'is_outlier' not in base.columns:
            base = base.copy()
            base['is_outlier'] = (self.data['is_outlier'].values
                                  if 'is_outlier' in self.data.columns else False)

        x_all = list(self.options.x)

        def _is_continuous(v):
            if self.data is None:
                return False
            col = self.data[v]
            underlying = col.cat.categories if hasattr(col, 'cat') else col
            n_unique = len(underlying.unique()) if hasattr(underlying, 'unique') else len(set(underlying))
            return pd.api.types.is_numeric_dtype(underlying) and n_unique > 15

        compare_vars = self._compare_vars()

        # Comparisons off: a single plain plot (first factor on the x-axis, no
        # significance brackets), saved as DataPlots.* with no variable suffix.
        if not compare_vars:
            if _is_continuous(x_all[0]):
                print(f"Skipping data plot: '{x_all[0]}' is continuous — violin plots need a categorical x variable.")
                self.fig_data = None
                return
            self.fig_data = self._build_data_figure(base, x_all[:3], {}, contrasts=None)
            return

        # One comparison plot per requested variable, each with that variable on
        # the x-axis (as if it were first) and the others as facet panels. Files
        # are keyed by the original variable name -> DataPlots_<var>.*.
        figs = {}
        for var in compare_vars:
            if _is_continuous(var):
                print(f"Skipping posthoc_compare='{var}': continuous variable, no level comparison.")
                continue
            x_ordered = [var] + [v for v in x_all if v != var]
            figs.update(self._compare_figures(base, var, x_ordered,
                                               self.contrasts_by_var.get(var)))
        self.fig_data = figs if figs else None

    def _compare_figures(self, base, var, x_ordered, contrasts):
        """Build the data figure(s) for one comparison variable, keyed by the
        original variable name (plus a level suffix when a 4th+ factor splits it).

        A data plot shows at most three factors (x-axis, column facets, row
        facets); a further factor produces one figure per level-combination.
        """
        if len(x_ordered) <= 3:
            return {var: self._build_data_figure(base, x_ordered, {}, contrasts=contrasts)}
        import itertools
        split_vars = x_ordered[3:]
        base_x = x_ordered[:3]

        def _levels(df, v):
            c = df[v]
            return c.cat.categories.tolist() if hasattr(c, 'cat') else sorted(c.dropna().unique())

        out = {}
        for combo in itertools.product(*[_levels(base, v) for v in split_vars]):
            sub = base
            for v, lev in zip(split_vars, combo):
                sub = sub[sub[v] == lev]
            if sub.empty:
                continue
            suffix = '_'.join(str(lev) for lev in combo)
            out[f'{var}_{suffix}'] = self._build_data_figure(
                sub, base_x, dict(zip(split_vars, combo)), contrasts=contrasts)
        return out

    def _build_data_figure(self, plot_data, x_list, emm_extra, contrasts=None):
        """Build one data-plot figure from ``plot_data`` using up to three factors
        in ``x_list`` (x-axis, column facets, row facets). ``emm_extra`` maps any
        further factors held fixed for this figure to their level, used to pick the
        matching cell of the EMM grid. Returns the matplotlib Figure.
        """
        n_vars = len(x_list)
        x_var = x_list[0]                # Violin / x-axis variable  (e.g. Chocolate)
        y_var = self.options.y           # Dependent variable        (e.g. Distance)
        facet_var = x_list[1] if n_vars > 1 else None  # Panel variable (e.g. Gender)
        id_var = self.options.id         # Subject identifier for connecting lines
        # y_units is a scalar string for this variable, but fit() re-runs
        # _normalize_options and re-wraps it into a single-element list; accept
        # either form so the units aren't silently dropped from the axis label.
        yu = self.options.y_units
        if isinstance(yu, (list, tuple)):
            yu = yu[0] if len(yu) == 1 else ''
        y_units = yu if isinstance(yu, str) else ''
        # options.y_label controls the y-axis label:
        #   'variable_with_units' (default) variable name plus '[units]'
        #   'variable_only'                 variable name, no units
        #   'none'                          no y-axis label at all
        y_style = (self.options.y_label or 'variable_with_units').lower()
        if y_style == 'none':
            y_label = ''
        elif y_units and y_style != 'variable_only':
            y_label = f"{self._disp(y_var)} [{y_units}]"
        else:
            y_label = self._disp(y_var)
        if y_label and self.options.y_transform:
            y_label = f"{y_label}  (original scale)"

        # Determine plot style: 'auto' uses bar for binary outcomes, violin for continuous
        y_vals = plot_data[y_var].dropna()
        is_binary = set(y_vals.unique()).issubset({0, 1, 0.0, 1.0}) and len(y_vals.unique()) <= 2
        style = self.options.plot_style
        use_bar = (style == 'bar') or (style == 'auto' and is_binary)
        use_violin = not use_bar
        if use_bar and is_binary and y_style != 'none':
            y_label = f"{self._disp(y_var)} (proportion)"

        # Use MATLAB's default color cycle (first N colors from 'tab10')
        x_levels = plot_data[x_var].cat.categories.tolist() if hasattr(plot_data[x_var], 'cat') else sorted(plot_data[x_var].unique())
        palette = dict(zip(x_levels, sns.color_palette(self.options.color_scheme, len(x_levels))))

        # Determine column facets (x[1]) and row facets (x[2])
        row_var = x_list[2] if n_vars > 2 else None

        if facet_var:
            facet_levels = plot_data[facet_var].cat.categories.tolist() if hasattr(plot_data[facet_var], 'cat') else sorted(plot_data[facet_var].unique())
        else:
            facet_levels = [None]

        if row_var:
            row_levels = plot_data[row_var].cat.categories.tolist() if hasattr(plot_data[row_var], 'cat') else sorted(plot_data[row_var].unique())
        else:
            row_levels = [None]

        n_cols = len(facet_levels)
        n_rows = len(row_levels)

        # Per-panel width is fixed (4 in). Panel height shrinks once there is more
        # than one row so multi-row figures don't become excessively tall: the
        # first row is 4.8 in, each further row adds only 3.6 in (1 row -> 4.8,
        # 2 -> 8.4, 3 -> 12) instead of a flat 4.8 in per row.
        fig_height = 4.8 + 3.6 * (n_rows - 1)
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, fig_height), sharey=True)
        # Normalise to a 2-D list so axes[row_idx][col_idx] always works
        if n_rows == 1 and n_cols == 1:
            axes = [[axes]]
        elif n_rows == 1:
            axes = [list(axes)]
        elif n_cols == 1:
            axes = [[ax] for ax in axes]
        else:
            axes = [list(row) for row in axes]

        healthy_data = plot_data[~plot_data['is_outlier']]
        outlier_data = plot_data[plot_data['is_outlier']]

        for row_idx, row_val in enumerate(row_levels):
          for col_idx, facet_val in enumerate(facet_levels):
            ax = axes[row_idx][col_idx]

            # Subset for this panel
            mask_h = pd.Series(True, index=healthy_data.index)
            mask_o = pd.Series(True, index=outlier_data.index)
            if facet_var is not None:
                mask_h = mask_h & (healthy_data[facet_var] == facet_val)
                mask_o = mask_o & (outlier_data[facet_var] == facet_val)
            if row_var is not None:
                mask_h = mask_h & (healthy_data[row_var] == row_val)
                mask_o = mask_o & (outlier_data[row_var] == row_val)
            panel_healthy = healthy_data[mask_h]
            panel_outlier = outlier_data[mask_o]

            # --- LAYER 1: Violins (skipped in bar style) ---
            violin_colls = []
            if use_violin:
                n_viol_before = len(ax.collections)
                sns.violinplot(
                    data=panel_healthy, x=x_var, y=y_var, order=x_levels,
                    hue=x_var, hue_order=x_levels, palette=palette, dodge=False,
                    cut=0.3, inner=None, linewidth=1, saturation=self.options.color_sat,
                    ax=ax, legend=False, density_norm='width'
                )
                violin_colls = ax.collections[n_viol_before:]
                for coll in violin_colls:
                    coll.set_alpha(self.options.color_alpha)

            def _violin_hw(xi, y_val):
                """Half-width of the violin for group xi at height y_val."""
                for coll in violin_colls:
                    for path in coll.get_paths():
                        verts = path.vertices
                        if abs(verts[:, 0].mean() - xi) > 0.6:
                            continue
                        xs = []
                        for i in range(len(verts) - 1):
                            x0, y0 = verts[i];  x1, y1 = verts[i + 1]
                            if y0 == y1:
                                continue
                            if min(y0, y1) <= y_val <= max(y0, y1):
                                t = (y_val - y0) / (y1 - y0)
                                xs.append(x0 + t * (x1 - x0))
                        if len(xs) >= 2:
                            return (max(xs) - min(xs)) / 2
                return 0.35  # fallback if violin not found

            # --- LAYER 2: Jittered scatter (violin style) or observed mean/proportion bar (bar style) ---
            n_pts = len(panel_healthy)
            dot_size = float(np.clip(25 / np.sqrt(max(n_pts, 1)), 5, 7))
            rng = np.random.default_rng(0)
            dot_xy = {}   # level -> (x_positions, y_values) for paired-line lookup
            id_xy = {}    # level -> {subject id: (x_position, y_value)} for connecting lines
            for xi, level in enumerate(x_levels):
                sub_df = panel_healthy[panel_healthy[x_var] == level].dropna(subset=[y_var])
                subset = sub_df[y_var]
                if len(subset) == 0:
                    dot_xy[level] = (np.array([]), np.array([]))
                    id_xy[level] = {}
                    continue
                if use_bar:
                    bar_val = subset.mean()
                    color = palette[level]
                    ax.bar(xi, bar_val, width=0.4, color=color,
                           alpha=self.options.color_alpha,
                           edgecolor='black', linewidth=1.0, zorder=2)
                    dot_xy[level] = (np.array([xi]), np.array([bar_val]))
                else:
                    jx = np.array([
                        xi + rng.uniform(-_violin_hw(xi, y) * 0.75, _violin_hw(xi, y) * 0.75)
                        for y in subset.values
                    ])
                    sc = ax.scatter(jx, subset.values, color='black', s=dot_size ** 2,
                                    alpha=0.4, zorder=4, linewidths=0)
                    tip_labels = [
                        f'obs {idx}, {self._disp(x_var)}={level}, {self._disp(y_var)}={v:.3f}'
                        for idx, v in zip(subset.index, subset.values)
                    ]
                    self._tooltip(ax, sc, tip_labels)
                    dot_xy[level] = (jx, subset.values)
                    # record subject id -> (x, y) for identity-based connecting lines
                    if id_var:
                        id_xy[level] = {
                            sid: (jxi, yi) for sid, jxi, yi
                            in zip(sub_df[id_var].values, jx, subset.values)
                        }

            # --- LAYER 2b: Outliers (red X markers, count text, or hidden) ---
            # Controlled by options.show_outliers: 'plot' (default), 'none', or
            # 'text'. Unknown values fall back to 'plot'.
            show_out = (self.options.show_outliers or 'plot').lower()
            if show_out == 'text':
                n_out = int(panel_outlier[y_var].notna().sum())
                n_tot = n_out + int(panel_healthy[y_var].notna().sum())
                pct = 100.0 * n_out / n_tot if n_tot else 0.0
                ax.text(0.02, 0.02, f'{n_out} outliers ({pct:.1f}% of {n_tot})',
                        transform=ax.transAxes, ha='left', va='bottom',
                        fontsize=8, color='black', zorder=7)
            elif show_out != 'none' and len(panel_outlier) > 0:
                for xi, level in enumerate(x_levels):
                    subset = panel_outlier[panel_outlier[x_var] == level][y_var].dropna()
                    if len(subset) == 0:
                        continue
                    jx = np.array([
                        xi + rng.uniform(-_violin_hw(xi, y) * 0.75, _violin_hw(xi, y) * 0.75)
                        for y in subset.values
                    ])
                    sc = ax.scatter(jx, subset.values, color='red', s=dot_size ** 2,
                                    marker='X', alpha=0.9, zorder=4, linewidths=0)
                    tip_labels = [
                        f'obs {idx}, {self._disp(x_var)}={level}, {self._disp(y_var)}={v:.3f} [outlier]'
                        for idx, v in zip(subset.index, subset.values)
                    ]
                    self._tooltip(ax, sc, tip_labels)

            # --- LAYER 3: Connecting lines for paired subjects ---
            # Drawn when the design is paired, i.e. at most one (healthy) observation per
            # subject per level. Each subject is connected across adjacent levels by its
            # identity (id_var), so the lines are correct for any number of levels and
            # tolerate outlier removal: a removed point simply drops the segments touching
            # it, while the subject's remaining points stay connected.
            if id_var and not use_bar and len(x_levels) >= 2:
                counts = panel_healthy.groupby([id_var, x_var], observed=True)[y_var].count()
                if counts.empty or (counts <= 1).all():
                    for li in range(len(x_levels) - 1):
                        map_a = id_xy.get(x_levels[li], {})
                        map_b = id_xy.get(x_levels[li + 1], {})
                        for sid in map_a.keys() & map_b.keys():
                            xa, ya = map_a[sid]
                            xb, yb = map_b[sid]
                            ax.plot([xa, xb], [ya, yb],
                                    color='black', alpha=0.4, linewidth=1.0, zorder=3)

            # --- LAYER 4: EMM marker + 95 % CI bar ---
            # Prefer full interaction grid for multi-factor models (correct per-panel values)
            _full = getattr(self, '_emm_df_full', None)
            emm_df_plot = _full if (_full is not None and not _full.empty) else getattr(self, '_emm_df', None)
            inv = getattr(self, '_inverse_fn', None)

            def _bt_plot(val):
                return float(inv(np.array([val]))[0]) if inv is not None else float(val)

            for i, level in enumerate(x_levels):
                subset = panel_healthy[panel_healthy[x_var] == level][y_var].dropna()
                if len(subset) == 0:
                    continue

                emm_val = ci_lo = ci_hi = None
                if emm_df_plot is not None and not emm_df_plot.empty:
                    factor_col_plot = x_var if x_var in emm_df_plot.columns else emm_df_plot.columns[0]
                    row_mask = emm_df_plot[factor_col_plot].astype(str) == str(level)
                    # In multi-factor models also filter by the facet and row variables for this panel
                    if facet_var is not None and facet_var in emm_df_plot.columns and facet_val is not None:
                        row_mask = row_mask & (emm_df_plot[facet_var].astype(str) == str(facet_val))
                    if row_var is not None and row_var in emm_df_plot.columns and row_val is not None:
                        row_mask = row_mask & (emm_df_plot[row_var].astype(str) == str(row_val))
                    # Hold any further (4th+) factors fixed at this figure's level
                    for _ev, _el in emm_extra.items():
                        if _ev in emm_df_plot.columns:
                            row_mask = row_mask & (emm_df_plot[_ev].astype(str) == str(_el))
                    if row_mask.any():
                        row = emm_df_plot[row_mask].iloc[0]
                        emm_col = next((c for c in ('emmean', 'rate', 'response', 'prob')
                                        if c in emm_df_plot.columns), None)
                        lo_col  = next((c for c in ('lower.CL', 'lower_CL', 'asymp.LCL')
                                        if c in emm_df_plot.columns), None)
                        hi_col  = next((c for c in ('upper.CL', 'upper_CL', 'asymp.UCL')
                                        if c in emm_df_plot.columns), None)
                        if emm_col:
                            emm_val = _bt_plot(row[emm_col])
                        if lo_col:
                            ci_lo = _bt_plot(row[lo_col])
                        if hi_col:
                            ci_hi = _bt_plot(row[hi_col])

                # Fall back to median / IQR if no EMM available
                if emm_val is None:
                    emm_val = subset.median()
                if ci_lo is None:
                    ci_lo = subset.quantile(0.25)
                if ci_hi is None:
                    ci_hi = subset.quantile(0.75)

                # CI bar
                ax.plot([i, i], [ci_lo, ci_hi], color='0.2', linewidth=4, zorder=5)
                # EMM dot
                emm_sc = ax.scatter(i, emm_val, color='white', edgecolors='0.2',
                                    s=80, zorder=6, linewidths=1.2)
                self._tooltip(ax, emm_sc,
                              [f'{self._disp(x_var)}={level}, {self._disp(y_var)}={emm_val:.3f}'
                               f' [{ci_lo:.3f}, {ci_hi:.3f}]'])
                # n= label above CI top (bar style only)
                if use_bar:
                    n = len(subset)
                    y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
                    ax.text(i, ci_hi + y_range * 0.02, f'n={n}', ha='center', va='bottom',
                            fontsize=8, color='0.4', zorder=7)

            # y-limit expansion and bracket drawing are deferred to after the
            # panel loop so that sharey=True doesn't cause compounding expansions.

            # --- Axis formatting ---
            x_units_list = self.options.x_units  # already a list
            x_unit = x_units_list[0] if len(x_units_list) > 0 else ''
            x_name = f"{self._disp(x_var)} [{x_unit}]" if x_unit and x_unit != '1' else self._disp(x_var)
            x_style = (self.options.x_label or 'variable_below_levels').lower()
            ax.set_xticks(range(len(x_levels)))
            if x_style == 'none':
                # no x-axis labelling at all: hide both level ticks and variable
                ax.set_xticklabels([''] * len(x_levels))
                ax.set_xlabel('')
            elif x_style == 'variable_equals_level':
                # each tick reads 'Variable = level'; no separate axis label
                ax.set_xticklabels([f'{self._disp(x_var)} = {lev}' for lev in x_levels])
                ax.set_xlabel('')
            elif x_style == 'levels':
                # only the level names; the variable name is not shown
                ax.set_xticklabels([str(lev) for lev in x_levels])
                ax.set_xlabel('')
            else:  # 'variable_below_levels' (default): levels as ticks, variable name below
                ax.set_xticklabels([str(lev) for lev in x_levels])
                ax.set_xlabel(x_name)
            # y-axis label: leftmost column only; row label replaces it when there are multiple rows
            if col_idx == 0:
                if n_rows > 1:
                    ax.set_ylabel(f'{self._disp(row_var)} = {row_val}', fontweight='bold')
                else:
                    ax.set_ylabel(y_label)
            else:
                ax.set_ylabel('')
            # column header: top row only
            if row_idx == 0 and facet_var is not None:
                facet_unit = x_units_list[1] if len(x_units_list) > 1 else ''
                facet_label = f"{self._disp(facet_var)} [{facet_unit}]" if facet_unit and facet_unit != '1' else self._disp(facet_var)
                ax.set_title(f"{facet_label} = {facet_val}", fontweight='bold')

        # Super title
        plot_title = f'{self.options.title} ({self._disp(y_var)})' \
            if self.options.title else self._disp(y_var)
        _data_suptitle = self._add_suptitle(fig, plot_title)

        # --- Post-loop: expand y-limits once, then draw brackets ---
        # sharey=True means a set_ylim on any panel affects all; doing this after
        # all data is drawn avoids compounding expansions across panels.
        ref_ax = axes[0][0]
        y_lo, y_hi = ref_ax.get_ylim()   # data-driven limits before any expansion
        y_range = y_hi - y_lo
        if use_bar and is_binary:
            ref_ax.set_ylim(bottom=0.0, top=1.15)
            for row in axes:
                for ax in row:
                    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'{v:.0%}'))
        elif use_bar:
            ref_ax.set_ylim(bottom=0.0, top=y_hi * 1.15)
        else:
            y_pad = y_range * 0.08
            ref_ax.set_ylim(bottom=y_lo - y_pad * 0.5, top=y_hi + y_pad)

        if contrasts is not None:
            ct = contrasts
            if 'p.value' in ct.columns:
                bracket_step = y_range * 0.07

                # Visual top of a panel: the highest point of any violin polygon,
                # data point, bar, or CI bar. seaborn's violins do NOT update
                # ax.dataLim, so the KDE tail (cut=0.3) and the CI bar sit above
                # dataLim.y1 — we therefore introspect the rendered artists.
                from matplotlib.collections import PolyCollection

                def _panel_top(ax):
                    top = -np.inf
                    for coll in ax.collections:
                        if isinstance(coll, PolyCollection):          # violins
                            for path in coll.get_paths():
                                v = path.vertices
                                if len(v):
                                    top = max(top, float(np.nanmax(v[:, 1])))
                        else:                                         # scatter
                            off = np.asarray(coll.get_offsets())
                            if off.size:
                                top = max(top, float(np.nanmax(off[:, 1])))
                    for patch in ax.patches:                          # bars
                        top = max(top, patch.get_y() + patch.get_height())
                    for line in ax.lines:                             # CI bars
                        yd = np.asarray(line.get_ydata(), dtype=float)
                        if yd.size:
                            top = max(top, float(np.nanmax(yd)))
                    return top if np.isfinite(top) else ax.dataLim.y1

                # Each panel's brackets are anchored just above THAT panel's own
                # violins, so they track the data per panel. With sharey=True the
                # shared y-axis is expanded once afterwards to fit the tallest
                # panel's bracket stack so nothing is clipped.

                def _contrast_positions(contrast_str, x_var, x_levels):
                    parts = [p.strip() for p in contrast_str.split(' - ')]
                    if len(parts) != 2:
                        return None, None
                    found = []
                    for part in parts:
                        # emmeans wraps level names containing special characters
                        # (e.g. the hyphen in 'Med-ADHD') in parentheses or
                        # backticks; strip one such layer so the name matches the
                        # categorical level instead of falling back to full width.
                        part = part.strip().strip('`').strip()
                        if part.startswith('(') and part.endswith(')'):
                            part = part[1:-1].strip()
                        for i, lev in enumerate(x_levels):
                            ls = str(lev)
                            if part == ls or part.endswith(ls) or part == f'{x_var} {ls}':
                                found.append(i)
                                break
                    return (found[0], found[1]) if len(found) == 2 else (None, None)

                bracket_y_max = -np.inf
                for row_idx, row_val in enumerate(row_levels):
                    for col_idx, facet_val in enumerate(facet_levels):
                        ax = axes[row_idx][col_idx]
                        # anchor just above THIS panel's tallest rendered content
                        bracket_y = _panel_top(ax) + bracket_step * 0.5
                        tick_h = bracket_step * 0.3
                        for _, crow in ct.iterrows():
                            p_val = crow['p.value']
                            if p_val >= 0.05:
                                continue
                            label = '***' if p_val < 0.001 else ('**' if p_val < 0.01 else '*')
                            xi, xj = _contrast_positions(str(crow['contrast']), x_var, x_levels)
                            if xi is None:
                                xi, xj = 0, len(x_levels) - 1
                            ax.plot([xi, xi, xj, xj],
                                    [bracket_y - tick_h, bracket_y, bracket_y, bracket_y - tick_h],
                                    color='black', linewidth=1.5)
                            ax.text((xi + xj) / 2, bracket_y, label,
                                    ha='center', va='bottom', fontsize=12, fontweight='bold')
                            bsc = ax.scatter((xi + xj) / 2, bracket_y, s=200, alpha=0, zorder=10)
                            self._tooltip(ax, bsc, [f'{crow["contrast"]}: p={p_val:.4f} ({label})'])
                            bracket_y += bracket_step * 1.4
                        bracket_y_max = max(bracket_y_max, bracket_y)
                # expand the shared y-axis once to fit the tallest panel's stack
                # (headroom so the topmost bracket label isn't jammed at the frame)
                if np.isfinite(bracket_y_max):
                    ref_ax.set_ylim(top=bracket_y_max + bracket_step * 0.6)

        # Place the suptitle a constant physical gap above the panels, matching the
        # diagnostics plot, independent of figure height. tight_layout reserves no
        # room for a suptitle, so on a tall faceted grid a fixed-fraction title would
        # collide with the top row; anchoring it just above the rendered top of the
        # panels (column titles included) keeps the same small gap at any height.
        fig.tight_layout()
        fig.canvas.draw()
        _inv = fig.transFigure.inverted()
        _top_y = max(ax.get_tightbbox(fig.canvas.get_renderer()).transformed(_inv).y1
                     for ax in fig.axes)
        _data_suptitle.set_verticalalignment('bottom')
        _data_suptitle.set_y(min(0.999, _top_y + 0.167 / fig_height))
        self._fit_suptitle_to_axes(_data_suptitle, fig)

        self._show_fig(fig)
        return fig

    def _diagnostic_residuals(self, r_obj):
        """Residuals for the diagnostic panels, with a label describing their type.

        Prefer DHARMa simulation-based quantile residuals transformed to the
        normal scale: under a correctly specified model these are ~N(0, 1) for
        *any* family (gaussian, gamma, binomial, Poisson, ...), so the histogram
        Normal overlay and the Q-Q-vs-normal plot become honest checks. Fall back
        to deviance residuals (better-behaved than Pearson for GLMs) if DHARMa is
        unavailable or the simulation fails, and to Pearson only as a last resort.
        """
        try:
            if int(ro.r('as.integer(requireNamespace("DHARMa", quietly=TRUE))')[0]) == 1:
                ro.r('suppressMessages(library(DHARMa))')
                ro.globalenv['._kbstat_rmodel'] = r_obj
                ro.r('''
                ._kbstat_dharma <- DHARMa::simulateResiduals(._kbstat_rmodel, n = 250,
                                                             plot = FALSE, seed = 42)
                ._kbstat_qres <- residuals(._kbstat_dharma, quantileFunction = qnorm,
                                           outlierValues = c(-7, 7))
                ''')
                res = np.asarray(ro.r('._kbstat_qres'), dtype=float)
                if res.size and np.isfinite(res).any():
                    return res, 'DHARMa quantile residuals'
        except Exception:
            pass
        try:
            return np.asarray(ro.r('residuals')(r_obj, type='deviance'), dtype=float), \
                'deviance residuals'
        except Exception:
            return np.asarray(ro.r('residuals')(r_obj, type='pearson'), dtype=float), \
                'Pearson residuals'

    def plot_diagnostics(self):
        """Generate a grid of 6 diagnostic plots for the model."""
        self._apply_font()
        if self.model is None:
            raise RuntimeError ("You must fit the model before plotting diagnostics.")

        r_obj = getattr(self.model, 'r_model', getattr(self.model, 'model_obj', None))

        if r_obj is not None:
            self.model.residuals, self._resid_label = self._diagnostic_residuals(r_obj)
        else:
            raise RuntimeError("Unable to find R model, rerun the fit")
            
        if r_obj is not None:
            self.model.fits = np.array(ro.r('fitted')(r_obj))
        else:
            raise RuntimeError("Unable to find R model, rerun the fit")

        # Create a 2x3 grid of subplots. Keep the window within a typical laptop
        # screen: 12 x 7.5 in is ~1200 x 750 px at the default 100 dpi.
        fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(12, 7.5))
        axes = axes.flatten()

        # Page title mirrors the data-plot title, prefixed with "Diagnostics of".
        _diag_y = self._disp(self.options.y)
        diag_title = (f'Diagnostics of {self.options.title} ({_diag_y})'
                      if self.options.title else f'Diagnostics of {_diag_y}')
        _diag_suptitle = self._add_suptitle(fig, diag_title)

        n_diag = len(self.model.residuals)
        s_diag = (5 * 1.2) ** 2  # fixed dot size for all diagnostic plots

        # Build per-observation group label for hover tooltips.
        # active_data must hold exactly the rows the model was fit on, in fit
        # order: non-outlier *complete cases* over the formula variables. R drops
        # any row with NA in a model variable, so self.model.fits/residuals have
        # length = complete cases; without dropping NaNs here too, active_data and
        # y_actual desync from them and the diagnostic plots raise a length error.
        fit_rows = self.data[~self.data['is_outlier']] \
            if 'is_outlier' in self.data.columns else self.data
        _model_vars = []
        for _grp in (self.options.y, self.options.x, self.options.covariate,
                     self.options.slope, self.options.id):
            if isinstance(_grp, list):
                _model_vars.extend(_grp)
            elif _grp:
                _model_vars.append(_grp)
        _model_vars = [v for v in dict.fromkeys(_model_vars) if v in fit_rows.columns]
        active_data = fit_rows.dropna(subset=_model_vars).reset_index(drop=True)
        x_vars = [v for v in (self.options.x if isinstance(self.options.x, list) else [self.options.x])
                  if v in active_data.columns]
        def _group_label(i):
            parts = [f'obs {i}']
            for v in x_vars:
                parts.append(f'{self._disp(v)}={active_data.at[i, v]}')
            return ', '.join(parts)

        # ---------------------------------------------------------
        # Plot 1: Histogram of Residuals with a Normal reference curve
        # ---------------------------------------------------------
        # Overlay N(mean, sd) of the residuals (not a KDE, which would merely
        # trace the bars) so departures from normality — skew, heavy tails — show
        # as gaps between the histogram and the dashed reference curve.
        resid = np.asarray(self.model.residuals, dtype=float)
        resid = resid[np.isfinite(resid)]
        sns.histplot(resid, stat='density', ax=axes[0])
        mu, sd = float(np.mean(resid)), float(np.std(resid, ddof=1))
        if sd > 0:
            xs = np.linspace(float(resid.min()), float(resid.max()), 200)
            axes[0].plot(xs, stats.norm.pdf(xs, mu, sd), color='red', linestyle='--')
        axes[0].set_title("Histogram of Residuals")
        axes[0].set_xlabel("Residuals", labelpad=4)
        axes[0].set_ylabel("Density", labelpad=4)

        # ---------------------------------------------------------
        # Plot 2: Normal Q-Q Plot
        # ---------------------------------------------------------
        stats.probplot(self.model.residuals, dist="norm", plot=axes[1])
        axes[1].set_title("Normal Q-Q Plot")
        # probplot draws with raw matplotlib (plain blue); recolour to match seaborn default
        seaborn_color = sns.color_palette()[0]
        axes[1].get_lines()[0].set(color=seaborn_color, markerfacecolor=seaborn_color,
                                   markeredgecolor='none')
        axes[1].get_lines()[1].set(color='red', linestyle='--')
        axes[1].set_xlabel(axes[1].get_xlabel(), labelpad=4)
        axes[1].set_ylabel(axes[1].get_ylabel(), labelpad=4)

        # ---------------------------------------------------------
        # Plot 3: Residuals vs Fitted
        # ---------------------------------------------------------
        sns.scatterplot(x=self.model.fits, y=self.model.residuals, ax=axes[2], s=s_diag)
        axes[2].axhline(0, color='red', linestyle='--')
        axes[2].set_title("Residuals vs Fitted")
        axes[2].set_xlabel("Fitted Values", labelpad=4)
        axes[2].set_ylabel("Residuals", labelpad=4)
        self._tooltip(axes[2], axes[2].collections[-1],
                      [f'{_group_label(i)}, fitted={self.model.fits[i]:.3f}, resid={self.model.residuals[i]:.3f}'
                       for i in range(n_diag)])

        # ---------------------------------------------------------
        # Plot 4: Lagged Residuals
        # ---------------------------------------------------------
        sns.scatterplot(x=self.model.residuals[:-1], y=self.model.residuals[1:], ax=axes[3], s=s_diag)
        axes[3].set_title("Lagged Residuals")
        axes[3].set_xlabel("Residual (i)", labelpad=4)
        axes[3].set_ylabel("Residual (i+1)", labelpad=4)
        self._tooltip(axes[3], axes[3].collections[-1],
                      [f'{_group_label(i)}, r(i)={self.model.residuals[i]:.3f}, r(i+1)={self.model.residuals[i+1]:.3f}'
                       for i in range(n_diag - 1)])

        # ---------------------------------------------------------
        # Plot 5: Fitted vs Response
        # ---------------------------------------------------------
        # Same fit-row frame as active_data, so length/order match self.model.fits.
        y_actual = active_data[self.options.y]

        sns.scatterplot(x=y_actual, y=self.model.fits, ax=axes[4], s=s_diag)

        min_val = min(self.model.fits.min(), y_actual.min())
        max_val = max(self.model.fits.max(), y_actual.max())
        axes[4].plot([min_val, max_val], [min_val, max_val], color='red', linestyle='--')

        axes[4].set_title("Fitted vs Response")
        axes[4].set_xlabel("Actual Raw Data", labelpad=4)
        axes[4].set_ylabel("Fitted Values", labelpad=4)
        self._tooltip(axes[4], axes[4].collections[-1],
                      [f'{_group_label(i)}, actual={float(y_actual.iloc[i]):.3f}, fitted={self.model.fits[i]:.3f}'
                       for i in range(n_diag)])

        # ---------------------------------------------------------
        # Plot 6: Random-effects Q-Q (if random effects present) else Scale-Location
        # ---------------------------------------------------------
        # When the model has a random effect (any LMM or GLMM), show a normal
        # Q-Q of the per-group random intercepts (conditional modes / BLUPs),
        # which checks the mixed-model assumption that the random effects are
        # normally distributed. When there is no random effect to plot (a plain
        # linear model), fall back to a Scale-Location plot so the panel is never
        # empty. Both apply regardless of family.
        re_vals = None
        grp = self.options.id
        if r_obj is not None and grp:
            try:
                # ranef() dispatches for both glmmTMB (nested under $cond) and
                # lme4 merMod / lmerModLmerTest (keyed by grouping factor).
                _re_extract = ro.r('''
                function(m, grp) {
                    r <- ranef(m)
                    if (!is.null(r$cond)) r <- r$cond
                    as.numeric(r[[grp]][["(Intercept)"]])
                }
                ''')
                re_vals = np.asarray(_re_extract(r_obj, grp), dtype=float)
            except Exception:
                re_vals = None

        if re_vals is not None and len(re_vals) >= 3 and np.ptp(re_vals) > 0:
            # Random-effects Q-Q plot
            stats.probplot(re_vals, dist="norm", plot=axes[5])
            axes[5].set_title("Random Effects Q-Q Plot")
            seaborn_color = sns.color_palette()[0]
            axes[5].get_lines()[0].set(color=seaborn_color, markerfacecolor=seaborn_color,
                                       markeredgecolor='none')
            axes[5].get_lines()[1].set(color='red', linestyle='--')
            axes[5].set_xlabel(axes[5].get_xlabel(), labelpad=4)
            axes[5].set_ylabel(f'Random intercept ({self._disp(grp)})', labelpad=4)
        else:
            # Scale-Location fallback (no random effect): sqrt(|residual|) vs
            # fitted. A flat trend confirms homoscedasticity.
            fitted = np.asarray(self.model.fits, dtype=float)
            sqrt_abs = np.sqrt(np.abs(np.asarray(self.model.residuals, dtype=float)))
            sns.scatterplot(x=fitted, y=sqrt_abs, ax=axes[5], s=s_diag)
            order = np.argsort(fitted)
            try:  # lowess trend if available, else a linear fit
                from statsmodels.nonparametric.smoothers_lowess import lowess
                sm = lowess(sqrt_abs, fitted, frac=0.67, return_sorted=True)
                axes[5].plot(sm[:, 0], sm[:, 1], color='red', linestyle='--', linewidth=1.2)
            except Exception:
                if len(fitted) > 2:
                    coef = np.polyfit(fitted, sqrt_abs, 1)
                    axes[5].plot(fitted[order], np.polyval(coef, fitted[order]),
                                 color='red', linestyle='--', linewidth=1.2)
            axes[5].set_title("Scale-Location")
            axes[5].set_xlabel("Fitted Values", labelpad=4)
            axes[5].set_ylabel(r"$\sqrt{|\mathrm{Residuals}|}$", labelpad=4)
            self._tooltip(axes[5], axes[5].collections[-1],
                          [f'{_group_label(i)}, fitted={fitted[i]:.3f}, '
                           f'sqrt|resid|={sqrt_abs[i]:.3f}' for i in range(n_diag)])

        # Footer row: formula + fit statistics
        parts = [f'Formula: {self._build_formula()}']
        if self.AIC is not None:
            parts += [f'AIC = {self.AIC:.3f}', f'BIC = {self.BIC:.3f}', f'logLik = {self.logLik:.3f}']
        parts.append(getattr(self, '_resid_label', 'residuals'))
        footer = '     |     '.join(parts)
        fig.subplots_adjust(bottom=0.08)
        fig.text(0.5, 0.02, footer, ha='center', va='bottom', fontsize=10,
                 fontstyle='italic', color='0.3')

        # Reserve the bottom band for the footer; let the top auto-fit (as the
        # data plot does) so the suptitle sits close to the panels rather than
        # leaving a large fixed gap.
        plt.tight_layout(rect=[0, 0.06, 1, 1.0])
        # Align y-labels within each column. (The previous fixed offset of -0.18
        # axes-units pushed the middle/right columns' labels into the panel to
        # their left; align_ylabels keeps each label just outside its own panel.)
        fig.align_ylabels(axes)
        self._fit_suptitle_to_axes(_diag_suptitle, fig)

        self.fig_diagnostics = fig
        self._show_fig(fig)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    #

    def _save_interactive(self, fig, path, scale=0.6):
        """Save a matplotlib figure as interactive HTML with hover tooltips via mpld3."""
        try:
            import mpld3
            orig_size = fig.get_size_inches()
            orig_dpi = fig.get_dpi()
            orig_params = dict(fig.subplotpars.__dict__)
            fig.set_size_inches(orig_size * scale)
            # mpld3 bakes (inches * fig.dpi) into the HTML pixel size, while fonts
            # stay fixed in points. Pin the dpi so the HTML looks the same whatever
            # produced it — otherwise an interactive GUI backend on a Retina display
            # reports dpi 200 (vs 100 for the notebook inline backend), doubling the
            # figure and the markers relative to the text.
            fig.set_dpi(100)
            fig.tight_layout()
            try:
                # mpld3's exporter cannot represent matplotlib blended transforms
                # (seaborn's violins use them) and warns once per artist. The HTML
                # still renders; only its zoom behaviour is approximate. Silence the
                # known, unactionable warning so it doesn't flood the console.
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        'ignore', message='Blended transforms not yet supported')
                    mpld3.save_html(fig, path)
                print(f'Saved interactive HTML to {path}')
            finally:
                fig.set_size_inches(orig_size)
                fig.set_dpi(orig_dpi)
                fig.subplots_adjust(**{k: v for k, v in orig_params.items()
                                       if k in ('left', 'right', 'top', 'bottom', 'wspace', 'hspace')})
        except Exception as e:
            print(f'Warning: interactive HTML export failed ({e})')

    @staticmethod
    def _tooltip(ax, collection, labels):
        """Attach an mpld3 PointLabelTooltip to a scatter PathCollection."""
        try:
            import mpld3
            from mpld3 import plugins
            plugins.connect(ax.get_figure(), plugins.PointLabelTooltip(collection, labels=labels))
        except Exception:
            pass

    def _calculate_z_score(self, data):
        # We add 1e-9 to prevent Divide By Zero crashes if a group's std is 0
        return np.abs((data - data.mean()) / (data.std() + 1e-9))

    def _build_transform(self):
        """Parse options.y_transform and build forward/inverse functions.

        The transform string uses 'y' as the placeholder for the dependent
        variable, e.g. 'log(y)', 'sqrt(y)', 'y**2'. Sympy is used to derive
        the analytical inverse; if inversion fails a RuntimeError is raised.
        """
        expr_str = self.options.y_transform.strip()
        if not expr_str:
            return

        import sympy as sp

        y_sym  = sp.Symbol('y',  positive=True)
        yi_sym = sp.Symbol('yi', positive=True)

        try:
            fwd_expr = sp.sympify(expr_str, locals={'y': y_sym})
        except Exception as e:
            raise ValueError(f'Could not parse y_transform expression "{expr_str}": {e}')

        # Forward function via numpy eval
        np_ns = {k: getattr(np, k) for k in dir(np) if not k.startswith('_')}
        def _forward(arr, _expr=expr_str, _ns=np_ns):
            y = np.asarray(arr, dtype=float)
            return eval(_expr, {**_ns, 'y': y})
        self._transform_fn = _forward

        # Inverse via sympy: solve fwd_expr = yi for y
        try:
            solutions = sp.solve(fwd_expr - yi_sym, y_sym)
            if not solutions:
                raise ValueError('No solution found')
            inv_expr = solutions[0]
            inv_fn   = sp.lambdify(yi_sym, inv_expr, modules='numpy')
            self._inverse_fn = lambda arr: inv_fn(np.asarray(arr, dtype=float))
            print(f'Transform : {expr_str}')
            print(f'Inverse   : {sp.pretty(inv_expr, use_unicode=False)}')
        except Exception as e:
            raise RuntimeError(
                f'Could not derive analytical inverse of "{expr_str}": {e}. '
                'Specify the inverse manually or choose a simpler transform.'
            )

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

        # Apply y_transform: keep raw data for plotting, transform y for fitting
        self._build_transform()
        if self._transform_fn is not None:
            y_col = self.options.y
            self._data_raw = self.data.copy()
            self.data[y_col] = self._transform_fn(self.data[y_col].values)

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
        ia = self.options.interaction
        # Normalise: flat list ['A','B'] → [['A','B']]; nested stays as-is
        if ia and not isinstance(ia[0], list):
            ia = [ia]
        if ia:
            # Build fixed-effects string: use * for interacting pairs, + for the rest
            ia_sets = [set(pair) for pair in ia]
            placed = set()
            terms = []
            for pair in ia:
                term = ' * '.join(pair)
                terms.append(term)
                placed.update(pair)
            for var in self.options.x:
                if var not in placed:
                    terms.append(var)
            x = ' + '.join(terms)
        else:
            x = ' + '.join(self.options.x)
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

        # Collect interaction pairs (terms joined by * or :)
        interactions = []
        seen_ia = set()
        for term in re.split(r'[+]', fixed_rhs):
            term = term.strip()
            if '*' in term or ':' in term:
                parts = [p.strip() for p in re.split(r'[*:]', term) if p.strip()]
                key = tuple(sorted(parts))
                if key not in seen_ia:
                    seen_ia.add(key)
                    interactions.append(list(parts))

        return {'y': y, 'x': x, 'id': id_var, 'slopes': slopes, 'interactions': interactions}

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
        if not self.options.interaction and parsed['interactions']:
            ia = parsed['interactions']
            # Store as flat list when there is only one interaction pair
            self.options.interaction = ia[0] if len(ia) == 1 else ia
            ia_str = ', '.join(' * '.join(pair) for pair in self.options.interaction)
            print(f'Detected interactions        : {ia_str}')

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

    def _summary_text(self) -> str:
        """Build the human-readable analysis summary (formula, fit stats, ANOVA, post-hoc, notes)."""
        lines = []

        sep = '=' * 70

        # --- Header --- (version read live from the package single source of truth)
        from kbstatpy import __version__ as _kbstatpy_version
        lines += [sep, f'kbstatpy {_kbstatpy_version} — Analysis Summary', sep, '']

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
            f'  {"Software":<22} : kbstatpy {_kbstatpy_version}',
            f'  Number of observations : {n_obs}',
            f'  Distribution           : {self.options.distribution}',
            f'  Link function          : {link}',
            f'  Fit method             : {fit_method}',
        ]
        if self.options.id:
            lines.append(f'  Random grouping factor : {self.options.id}')
        lines.append(f'  Contrast coding        : effects (contr.sum)')
        if self.model is not None:
            lines.append(f'  {"Deg.-of-freedom method":<22} : {self._df_method_label()}')
        lines.append('')

        # --- Fit statistics ---
        lines += ['FIT STATISTICS', '--------------']
        if self.AIC is not None:
            lines.append(f'  {"AIC":<24}: {self.AIC:.3f}')
            lines.append(f'  {"BIC":<24}: {self.BIC:.3f}')
            lines.append(f'  {"logLik":<24}: {self.logLik:.3f}')
        if hasattr(self.model, 'fit_stats') and self.model.fit_stats is not None:
            fs = self.model.fit_stats
            fs_df = fs.to_pandas() if hasattr(fs, 'to_pandas') else fs
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
            lines += ['ANOVA (Type III)', '----------------', at.to_string(index=False),
                      f'  Denominator df method: {self._df_method_label()}', '']

            # Check for infinite df2 and add explanatory note
            has_inf_df = False
            if 'DF2' in at.columns:
                has_inf_df = bool(np.any(np.isinf(at['DF2'].astype(float).values)))
            if has_inf_df:
                lines += [
                    'NOTE: df = Inf in ANOVA table',
                    '------------------------------',
                    'Finite-sample df methods (Kenward-Roger and Satterthwaite) are defined',
                    'only for linear mixed models (LMMs, distribution = normal); this package',
                    'uses Kenward-Roger when pbkrtest is available, else Satterthwaite. For',
                    'generalised linear mixed models (GLMMs) the likelihood is not quadratic',
                    'and neither method applies, so R\'s emmeans falls back to asymptotic',
                    'inference, yielding df = Inf and Wald chi-square tests.',
                    '',
                    'This is mathematically correct behaviour — not a software error.',
                    '',
                    'For comparison: MATLAB\'s fitglme also does not support these methods',
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
            lines += [f'  Correction: {self.options.posthoc_correction}',
                      f'  Denominator df method: {self._df_method_label()}', '']
            lines += [ph.to_string(index=False), '']


        # --- Diagnostics note ---
        _resid = getattr(self, '_resid_label', None)
        if _resid:
            lines += ['DIAGNOSTICS', '-----------',
                      f'  The Diagnostics plot uses {_resid}.']
            if _resid.startswith('DHARMa'):
                lines += [
                    '  DHARMa simulation-based quantile residuals are ~N(0, 1) under a',
                    '  correctly specified model for any distribution family, so the residual',
                    '  histogram (with its Normal reference curve) and the Q-Q plot are valid',
                    '  normality checks even for non-Gaussian GLMMs.',
                ]
            else:
                lines += [
                    '  (DHARMa was unavailable; these residuals can be mildly skewed for',
                    '  non-Gaussian families even when the model is correct.)',
                ]
            lines.append('')

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

        return '\n'.join(lines)

    def _write_summary(self, out_dir: str):
        """Write the analysis summary to Summary.txt."""
        with open(os.path.join(out_dir, 'Summary.txt'), 'w', encoding='utf-8') as fh:
            fh.write(self._summary_text() + '\n')

    def print_summary(self):
        """Print the analysis summary to stdout (no-op if no model has been fitted)."""
        if self.model is not None:
            print(self._summary_text())

    def _build_statistics_table(self, factors: list) -> pd.DataFrame:
        """Build descriptive statistics table per group."""
        y = self.options.y
        inv = getattr(self, '_inverse_fn', None)

        # Prefer full interaction EMM grid; fall back to single-factor grid
        _full = getattr(self, '_emm_df_full', None)
        emm_src = _full if (_full is not None and not _full.empty) else getattr(self, '_emm_df', None)

        def _lookup_emm(keys_dict):
            if emm_src is None or emm_src.empty:
                return None
            mask = pd.Series(True, index=emm_src.index)
            for col, val in keys_dict.items():
                if col in emm_src.columns:
                    mask = mask & (emm_src[col].astype(str) == str(val))
            if not mask.any():
                return None
            row = emm_src[mask].iloc[0]
            emm_col = next((c for c in ('emmean', 'rate', 'response', 'prob')
                            if c in emm_src.columns), None)
            if emm_col is None:
                return None
            val = float(row[emm_col])
            return float(inv(np.array([val]))[0]) if inv is not None else val

        rows = []
        groups = self.data.groupby(factors)
        for keys, group in groups:
            if not isinstance(keys, tuple):
                keys = (keys,)
            keys_dict = dict(zip(factors, keys))
            row = dict(keys_dict)
            vals = group[y].dropna()
            row['N'] = len(vals)
            row['mean'] = vals.mean()
            row['std'] = vals.std()
            row['SE'] = vals.sem()
            row['median'] = vals.median()
            row['q25'] = vals.quantile(0.25)
            row['q75'] = vals.quantile(0.75)
            row['emm'] = _lookup_emm(keys_dict)
            ci = 1.96 * vals.sem()
            row['CI95_lower'] = vals.mean() - ci
            row['CI95_upper'] = vals.mean() + ci
            rows.append(row)
        return pd.DataFrame(rows)

    def _apply_rename(self):
        """Apply options.rename mappings to any column in the dataframe."""
        rename = self.options.rename
        if not isinstance(rename, dict) or self.data is None:
            return
        for col, mapping in rename.items():
            if col in self.data.columns and mapping:
                self.data[col] = self.data[col].astype(str).map(
                    lambda v, m=mapping: m.get(v, v))

    def _apply_categorical(self):
        categorical_vars = self.options.x.copy()
        if self.options.id:
            categorical_vars.append(self.options.id)

        if self.data is not None:
            for var in categorical_vars:
                if var in self.data.columns:
                    # Convert numeric-valued categoricals to string so rpy2 passes
                    # them as character vectors, which R treats as factors
                    col = self.data[var]
                    if pd.api.types.is_numeric_dtype(col):
                        col = col.astype(str)
                    # Resolve user-specified level order, if any
                    x_order = self.options.x_order
                    if isinstance(x_order, dict):
                        order = x_order.get(var, None)
                    elif isinstance(x_order, list) and var == self.options.x[0]:
                        order = x_order
                    else:
                        order = None
                    if order is not None:
                        categories = [str(v) for v in order]
                    else:
                        categories = col.unique().tolist()
                    self.data[var] = pd.Categorical(
                        col,
                        categories=categories,
                        ordered=False
                    )

    def _apply_constraints(self):
        if self.options.constraints != '':
            self.data = self.data.query(self.options.constraints)
            for col in self.data.columns:
                if hasattr(self.data[col], 'cat'):
                    self.data[col] = self.data[col].cat.remove_unused_categories()

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


def _r_label(r):
    """Verbal effect size label for Pearson r (Cohen, 1988)."""
    r = abs(r)
    if np.isnan(r):
        return ''
    if r < 0.1:
        return 'negligible'
    if r < 0.3:
        return 'small'
    if r < 0.5:
        return 'medium'
    return 'large'


def _sig_stars(p):
    """Significance stars from p-value."""
    if pd.isna(p):
        return ''
    if p < 0.001:
        return '***'
    if p < 0.01:
        return '**'
    if p < 0.05:
        return '*'
    return 'n.s.'


# User-facing y_correction value -> R p.adjust method name. Keys are lowercase;
# the option is matched case-insensitively.
_Y_CORRECTION_MAP = {
    'bonferroni':     'bonferroni',
    'holm':           'holm',
    'fdr':            'BH',   # Benjamini-Hochberg
    'fdr_correlated': 'BY',   # Benjamini-Yekutieli (valid under dependence)
}


def _adjust_pvalues(pvals, method):
    """Adjust a vector of p-values with R's p.adjust. `method` is a user-facing
    y_correction value (lowercased). NaNs are preserved and excluded from the
    family size n, so the adjustment is over the present p-values only."""
    p = np.asarray(pvals, dtype=float)
    out = np.full(p.shape, np.nan)
    mask = ~np.isnan(p)
    if not mask.any():
        return out
    r_method = _Y_CORRECTION_MAP[method]
    adjusted = ro.r['p.adjust'](ro.FloatVector(p[mask].tolist()), method=r_method)
    out[mask] = np.asarray(adjusted, dtype=float)
    return out


def _multiple_comparisons_table(results, method):
    """Build the across-dependent-variable correction table. For each model term,
    the per-y p-values form one family and are adjusted together. Returns a long
    DataFrame (variable, Term, p, p_corrected, significance, method), or None."""
    recs = []
    for res in results:
        anova = res.anova
        if anova is None:
            continue
        adf = anova.to_pandas() if hasattr(anova, 'to_pandas') else anova
        for _, row in adf.iterrows():
            recs.append({'variable': res.y, 'Term': str(row['Term']),
                         'p': float(row['p'])})
    df = pd.DataFrame(recs)
    if df.empty:
        return None
    df['p_corrected'] = np.nan
    for _, idx in df.groupby('Term').groups.items():
        df.loc[idx, 'p_corrected'] = _adjust_pvalues(df.loc[idx, 'p'].values, method)
    df['significance'] = df['p_corrected'].apply(_sig_stars)
    df['method'] = method
    return df.sort_values(['Term', 'p']).reset_index(drop=True)


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

