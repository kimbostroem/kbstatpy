"""options.curve: the kbstatpy side of the curve analysis (SPM1D-style).

The model kbstatpy would fit to one value per observation is fitted at every
point of a curve. Each model term gets an F curve, each pairwise comparison a
t curve, and random field theory (_curve.py) sets one threshold per curve from
the smoothness of the residual curves, so the chance of a false positive
anywhere on it is alpha. Mixed into Kbstat; kbstat.py only calls the hooks
_normalize_curve, _apply_curve_wide and _compute_curve.
"""
import itertools
import re
import textwrap
import warnings

import numpy as np
import pandas as pd
import rpy2.robjects as ro
from rpy2.robjects import default_converter, pandas2ri
from rpy2.robjects.conversion import localconverter

from . import _curve

_CURVE_DEFAULT_NAME = 'Time'
_CURVE_ROW = 'kbstat_curve'     # internal: which curve a row belongs to
_CURVE_NODE = 'kbstat_node'     # internal: index of the point on the curve
_MIN_POINTS = 5

# One R call fits every point: the loop in R costs a fraction of a round trip
# per point through rpy2. Returns, stacked over the points: the ANOVA (or the
# intercept test), the residuals by curve, the pairwise comparisons and the
# estimated marginal means.
_R_LOOP = r'''
function(d, formula, Q, use_lmer, df_method, cmp_vars, cmp_by, emm_vars,
         intercept_only, test_value) {
  f <- as.formula(formula)
  emm_args <- if (use_lmer && nzchar(df_method)) list(lmer.df = df_method) else list()
  tests <- list(); res <- list(); ph <- list(); emm <- list(); singular <- logical(Q)
  for (i in seq_len(Q)) {
    di <- d[d$kbstat_node == (i - 1), , drop = FALSE]
    if (use_lmer) {
      m <- suppressMessages(suppressWarnings(lme4::lmer(f, data = di, REML = TRUE)))
      singular[i] <- lme4::isSingular(m)
    } else {
      m <- lm(f, data = di)
    }
    if (intercept_only) {
      e1 <- do.call(emmeans::emmeans, c(list(m, ~ 1), emm_args))
      tt <- as.data.frame(emmeans::test(e1, null = test_value))
      tests[[i]] <- data.frame(node = i - 1, term = "(Intercept)", df1 = 1,
                               df2 = tt$df, stat = tt$t.ratio)
    } else {
      jt <- as.data.frame(do.call(emmeans::joint_tests, c(list(m), emm_args)))
      tests[[i]] <- data.frame(node = i - 1, term = as.character(jt[["model term"]]),
                               df1 = jt$df1, df2 = jt$df2, stat = jt$F.ratio)
    }
    res[[i]] <- data.frame(node = i - 1, curve = di$kbstat_curve, r = as.numeric(residuals(m)))
    for (j in seq_along(cmp_vars)) {
      by <- if (nzchar(cmp_by[j])) strsplit(cmp_by[j], ",", fixed = TRUE)[[1]] else NULL
      e <- do.call(emmeans::emmeans, c(list(m, specs = cmp_vars[j], by = by), emm_args))
      p <- as.data.frame(summary(pairs(e, adjust = "none"), infer = c(FALSE, TRUE)))
      cell <- if (is.null(by)) rep("", nrow(p)) else
        do.call(paste, c(lapply(by, function(b) paste0(b, " = ", as.character(p[[b]]))), sep = ", "))
      ph[[length(ph) + 1]] <- data.frame(node = i - 1, var = cmp_vars[j], cell = cell,
                                        k = ave(seq_len(nrow(p)), cell, FUN = seq_along),
                                        diff = p$estimate, df = p$df, t = p$t.ratio)
    }
    specs <- if (length(emm_vars)) emm_vars else "1"
    e <- if (length(emm_vars)) do.call(emmeans::emmeans, c(list(m, specs = emm_vars), emm_args))
         else do.call(emmeans::emmeans, c(list(m, ~ 1), emm_args))
    s <- as.data.frame(summary(e))
    out <- data.frame(node = rep(i - 1, nrow(s)), emmean = s$emmean,
                      lower = s$lower.CL, upper = s$upper.CL)
    for (v in emm_vars) out[[v]] <- as.character(s[[v]])
    emm[[i]] <- out
  }
  list(tests = do.call(rbind, tests), res = do.call(rbind, res),
       ph = if (length(ph)) do.call(rbind, ph) else data.frame(),
       emm = do.call(rbind, emm), singular = singular)
}
'''


class CurveMixin:
    """Curve analysis for Kbstat (options.curve)."""

    # --- the option -----------------------------------------------------------

    @staticmethod
    def _parse_curve(spec):
        """options.curve as ('long', column) or ('wide', name, first, last).

        'Time'                    -> long data, the column of curve points
        'KA_0 : KA_100'           -> wide data, a column range (file order)
        'Time = (KA_0 : KA_100)'  -> the same, naming the column it creates
        """
        spec = str(spec or '').strip()
        if not spec:
            return None
        named = re.fullmatch(r'([^=()]+?)\s*=\s*\((.*)\)', spec)
        name, inner = (named.group(1).strip(), named.group(2)) if named else (None, spec)
        if ':' in inner:
            first, _, last = inner.partition(':')
            if first.strip() and last.strip() and ':' not in last and '(' not in inner:
                return ('wide', name or _CURVE_DEFAULT_NAME, first.strip(), last.strip())
        if named or '=' in spec or '(' in spec or ':' in spec:
            raise ValueError(
                f"options.curve: {spec!r} is not understood. Give the column of "
                "curve points ('Time'), or a range of wide columns ('KA_0 : KA_100' "
                "or 'Time = (KA_0 : KA_100)').")
        return ('long', spec)

    def _curve_spec(self):
        return self._parse_curve(getattr(self.options, 'curve', ''))

    def _curve_col(self):
        spec = self._curve_spec()
        return None if spec is None else spec[1]

    def _normalize_curve(self):
        """Checks that need only the options. Wide data without options.y put
        their values in 'value', as wide2long does."""
        o = self.options
        spec = self._curve_spec()
        if spec is None:
            return
        if spec[0] == 'wide':
            if isinstance(o.wide2long, (list, tuple)) or str(o.wide2long or '').strip():
                raise ValueError(
                    "options.curve names wide columns and options.wide2long is set; "
                    "both would stack columns into options.y. Use one of them.")
            if not o.y:
                o.y = 'value'
                self._curve_value_default = True
        if self._split_csv(o.y) and len(self._split_csv(o.y)) > 1 and spec[0] == 'wide':
            raise ValueError(
                "options.curve with a wide column range holds one outcome; "
                "options.y names several.")
        reasons = []
        if str(o.distribution).lower() != 'normal':
            reasons.append(f"distribution = {o.distribution!r} (random field theory needs "
                           "normally distributed residual curves)")
        if o.y_transform:
            reasons.append('y_transform')
        if o.split:
            reasons.append('split')
        if o.remove_outliers_prefit or o.remove_outliers_postfit:
            reasons.append('outlier removal')
        if o.formula:
            reasons.append('formula (set x, id, slope and interaction instead)')
        if reasons:
            raise ValueError("options.curve does not support " + '; '.join(reasons) + ' yet.')

    # --- wide data --------------------------------------------------------------

    def _apply_curve_wide(self):
        """Stack the wide curve columns into long data: one row per curve and
        point, the values in options.y, the points in the named column."""
        spec = self._curve_spec()
        if spec is None or spec[0] != 'wide':
            return
        _, name, first, last = spec
        df = self.data
        cols = [str(c) for c in df.columns]
        df.columns = cols
        missing = [c for c in (first, last) if c not in cols]
        if missing:
            raise ValueError(
                f"options.curve: {', '.join(map(repr, missing))} "
                f"{'is not a column' if len(missing) == 1 else 'are not columns'} "
                f"of the data. Columns: {', '.join(cols[:30])}"
                + (' ...' if len(cols) > 30 else ''))
        i0, i1 = cols.index(first), cols.index(last)
        if i1 - i0 + 1 < _MIN_POINTS:
            raise ValueError(
                f"options.curve: {first!r} : {last!r} spans {max(i1 - i0 + 1, 0)} "
                f"columns; a curve needs at least {_MIN_POINTS} points, and "
                "the first column must come before the last.")
        rng = cols[i0:i1 + 1]
        y = self.options.y
        for c in (name, y, _CURVE_ROW):
            if c in cols and c not in rng:
                raise ValueError(
                    f"options.curve: the data already have a column {c!r}, which "
                    "the stacked curve would create"
                    + (" (the values go to options.y)" if c == y else '')
                    + ". Rename it, or name the new column differently.")
        values = df[rng].apply(pd.to_numeric, errors='coerce')
        bad = [c for c in rng if values[c].isna().sum() > df[c].isna().sum()]
        if bad:
            raise ValueError(
                f"options.curve: the columns {', '.join(bad[:10])} hold values "
                "that are not numbers.")
        positions, source = self._curve_positions_from_names(rng)
        long = df.drop(columns=rng).copy()
        long.insert(0, _CURVE_ROW, np.arange(len(df)))
        parts = []
        for pos, c in zip(positions, rng):
            part = long.copy()
            part[name] = pos
            part[y] = values[c].to_numpy()
            parts.append(part)
        out = pd.concat(parts, ignore_index=True)
        out = out.sort_values([_CURVE_ROW, name], kind='stable').reset_index(drop=True)
        self.data = out
        self._curve_positions_source = source
        if not getattr(self, '_curve_reported', False):
            print(f"curve: {len(rng)} columns {first} ... {last} -> {name!r} "
                  f"({source}), values in {y!r}"
                  + (" (default, since options.y is empty; set options.y to name "
                     "them)" if getattr(self, '_curve_value_default', False) else '')
                  + f"; {len(df)} curves")
            self._curve_reported = True

    @staticmethod
    def _curve_positions_from_names(cols):
        """Point positions from the numbers the column names end with
        (KA_0 ... KA_100), or 0 to 100 % spread evenly over the columns."""
        nums = []
        for c in cols:
            m = re.search(r'(-?\d+(?:\.\d+)?)$', str(c))
            if m is None:
                nums = None
                break
            nums.append(float(m.group(1)))
        if nums is not None and np.all(np.diff(nums) > 0):
            return nums, 'positions from the column names'
        return list(np.linspace(0, 100, len(cols))), 'positions 0 to 100 %'

    # --- the analysis -----------------------------------------------------------

    def _curve_key_cols(self):
        """Columns that identify which curve a row of long data belongs to."""
        o = self.options
        cols = list(o.x or []) + list(self._id_vars())
        cols += [c for c in self._covariate_names_for_curve() if c not in cols]
        for extra in ('file', 'wide_row'):
            if self.data is not None and extra in self.data.columns and extra not in cols:
                cols.append(extra)
        return [c for c in cols if self.data is not None and c in self.data.columns]

    def _covariate_names_for_curve(self):
        cov = self.options.covariate
        if not cov:
            return []
        return [c for c in (cov if isinstance(cov, list) else self._split_csv(cov))
                if isinstance(c, str)]

    def _curve_prepare(self):
        """Check the curves and index them: every curve has every point once,
        the points are equally spaced, y is complete. Sets the internal curve
        and point columns and returns the sorted positions."""
        col = self._curve_col()
        d = self.data
        y = self.options.y
        if col not in d.columns:
            raise ValueError(
                f"options.curve: {col!r} is not a column of the data. For wide "
                "data, give the range of curve columns as 'first : last'.")
        pos = pd.to_numeric(d[col], errors='coerce')
        if pos.isna().any():
            raise ValueError(f"options.curve: the column {col!r} holds values that are "
                             "not numbers; it must give the position on the curve.")
        if d[y].isna().any():
            n = int(d[y].isna().sum())
            raise ValueError(
                f"options.curve: {n} value(s) of {y!r} are missing. Every curve "
                "needs a value at every point; drop or fill the incomplete curves.")
        positions = np.sort(pos.unique())
        if len(positions) < _MIN_POINTS:
            raise ValueError(f"options.curve: {col!r} has {len(positions)} distinct points; "
                             f"a curve needs at least {_MIN_POINTS}.")
        steps = np.diff(positions)
        if not np.allclose(steps, steps[0], rtol=1e-6, atol=1e-9 * abs(steps[0])):
            raise ValueError(
                f"options.curve: the points of {col!r} are not equally spaced "
                f"(steps from {steps.min():g} to {steps.max():g}). Random field "
                "theory assumes equal steps; resample the curves to a common grid.")
        node = np.searchsorted(positions, pos.to_numpy())
        d = d.copy()
        d[_CURVE_NODE] = node
        if _CURVE_ROW not in d.columns:
            keys = self._curve_key_cols()
            # Trials without a trial column: the k-th row of a key at a point
            # belongs to its k-th curve.
            occ = d.groupby(keys + [_CURVE_NODE], observed=True, sort=False).cumcount() \
                if keys else d.groupby(_CURVE_NODE).cumcount()
            ident = d[keys].astype(str).agg('|'.join, axis=1) if keys else pd.Series('', index=d.index)
            ident = ident + '#' + occ.astype(str)
            d[_CURVE_ROW] = pd.factorize(ident)[0]
        counts = d.groupby(_CURVE_ROW)[_CURVE_NODE].agg(['size', 'nunique'])
        bad = counts[(counts['size'] != len(positions)) | (counts['nunique'] != len(positions))]
        if len(bad):
            raise ValueError(
                f"options.curve: {len(bad)} of {len(counts)} curves do not have each of "
                f"the {len(positions)} points exactly once. A curve is told apart by "
                f"{', '.join(self._curve_key_cols()) or 'nothing'} (and the order of "
                "its rows); add a column that tells repeated trials apart, or "
                "resample the curves to a common grid.")
        self.data = d.sort_values([_CURVE_ROW, _CURVE_NODE], kind='stable')
        return positions

    def _compute_curve(self):
        """The curve analysis for one dependent variable."""
        from pymer4.models import lmer as Lmer
        self._load_data()
        self._apply_rename()
        self._check_y_exists()
        self._apply_categorical()
        self._apply_constraints()
        self._scale_covariates()
        self._build_covariate_terms()
        positions = self._curve_prepare()
        full = self.data
        n_curves = int(full[_CURVE_ROW].nunique())
        Q = len(positions)

        # kbstatpy's own fit at the first point settles the model: the
        # validations, the random-slope structure, the df method.
        self.data = full[full[_CURVE_NODE] == 0].copy()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            self.fit()
        formula = self._build_formula()
        use_lmer = isinstance(self.model, Lmer)
        method = (self._df_method() or '') if use_lmer else ''
        if method == 'asymptotic':
            method = ''
        self.n_obs_fit = len(self.data)
        self._lift_emm_obs_limits(method or 'satterthwaite')
        self.data = full

        intercept_only = self._intercept_only()
        factors = [f for f in (self.options.x or []) if f in full.columns]
        cmp_vars, cmp_by = [], []
        if not intercept_only:
            for entry in self._compare_vars():
                var, by = self._curve_compare_parts(entry, factors)
                if var is not None:
                    cmp_vars.append(var)
                    cmp_by.append(','.join(by))

        cols = sorted({c for c in full.columns
                       if re.search(r'(?<![\w.])' + re.escape(str(c)) + r'(?![\w.])', formula)}
                      | {_CURVE_NODE, _CURVE_ROW})
        rdata = full[cols]
        with localconverter(default_converter + pandas2ri.converter):
            rdf = pandas2ri.py2rpy(rdata)
        tv = self.options.test_value
        out = ro.r(_R_LOOP)(rdf, formula, Q, use_lmer, method,
                            ro.StrVector(cmp_vars), ro.StrVector(cmp_by),
                            ro.StrVector(factors), intercept_only,
                            float(tv) if tv is not None else 0.0)
        with localconverter(default_converter + pandas2ri.converter):
            tests = ro.conversion.rpy2py(out.rx2('tests'))
            res = ro.conversion.rpy2py(out.rx2('res'))
            ph = ro.conversion.rpy2py(out.rx2('ph'))
            emm = ro.conversion.rpy2py(out.rx2('emm'))
        singular = int(np.sum(np.asarray(out.rx2('singular'))))

        R = res.pivot(index='curve', columns='node', values='r').to_numpy()
        fwhm = _curve.estimate_fwhm(R)
        step = float(positions[1] - positions[0])

        def at(x):
            return float(positions[0] + x * step)

        def describe(inf, stat_curve):
            for c in inf['clusters']:
                c['from'], c['to'] = at(c['start']), at(c['end'])
                if 'pair' in inf:
                    c['higher'] = str(inf['pair'][0] if c['sign'] > 0 else inf['pair'][1])
                c['peak_at'] = float(positions[c['peak']])
                c['peak_value'] = float(stat_curve[c['peak']])
            return inf

        alpha = self.options.alpha
        terms = {}
        for term, g in tests.groupby('term', sort=False):
            g = g.sort_values('node')
            stat = g['stat'].to_numpy(dtype=float)
            df2 = float(g['df2'].min())
            if intercept_only:
                inf = _curve.infer('t', stat, df2, fwhm, alpha, two_tailed=True)
                kind = 't'
            else:
                df1 = float(g['df1'].iloc[0])
                inf = _curve.infer('F', stat, (df1, df2), fwhm, alpha)
                kind = 'F'
            inf.update(stat=kind, values=stat, df1=float(g['df1'].iloc[0]), df2=df2,
                       df2_range=(float(g['df2'].min()), float(g['df2'].max())))
            terms[str(term)] = describe(inf, stat)

        posthoc = []
        if len(ph):
            fields = list(ph.groupby(['var', 'cell', 'k'], sort=False))
            alpha_each = 1 - (1 - alpha) ** (1 / len(fields))
            for (var, cell, k), g in fields:
                g = g.sort_values('node')
                levels = list(full[var].cat.categories) if hasattr(full[var], 'cat') \
                    else sorted(full[var].astype(str).unique())
                pair = list(itertools.combinations(levels, 2))[int(k) - 1]
                t = g['t'].to_numpy(dtype=float)
                inf = _curve.infer('t', t, float(g['df'].min()), fwhm, alpha_each,
                                   two_tailed=True)
                inf.update(var=var, cell=cell, pair=pair, values=t, diff=g['diff'].to_numpy(),
                           df=float(g['df'].min()), alpha=alpha_each)
                posthoc.append(describe(inf, t))

        self.curve_result = {
            'column': self._curve_col(), 'positions': positions, 'step': step,
            'n_curves': n_curves, 'n_points': Q, 'fwhm': fwhm,
            'resels': _curve.resel_counts(Q, fwhm), 'formula': formula,
            'use_lmer': use_lmer, 'df_method': method, 'singular': singular,
            'terms': terms, 'posthoc': posthoc, 'n_posthoc': len(posthoc),
            'emm': emm, 'factors': factors, 'intercept_only': intercept_only,
            'positions_source': getattr(self, '_curve_positions_source', None),
        }
        # 'Clusters', 'Points' and 'Means', as saved in Curve.xlsx.
        self.curve_result['tables'] = self._curve_tables_of(self.curve_result)
        self._curve_figures()

    def _curve_compare_parts(self, entry, factors):
        """(factor, conditioning factors) for one posthoc_compare entry: by
        default the other factors of x, as kbstatpy's post-hoc does."""
        from .kbstat import _compare_parts
        var, by = _compare_parts(entry)
        if var not in factors:
            return None, []
        if by is None:
            by = [f for f in factors if f != var]
        return var, list(by)

    # --- report -----------------------------------------------------------------

    def _curve_label(self, inf, term=None):
        names = self._display_names
        if term is not None:
            return ':'.join(names.get(p, p) for p in term.split(':'))
        a, b = inf['pair']
        lab = f"{self._disp(inf['var'])}: {a} vs {b}"
        if inf['cell']:
            cell = ', '.join(f"{self._disp(p.split(' = ')[0])} = {p.split(' = ', 1)[1]}"
                             for p in inf['cell'].split(', '))
            lab += f' ({cell})'
        return lab

    def _curve_summary_text(self):
        from kbstatpy import __version__
        cr = self.curve_result
        col = self._disp(cr['column'])
        unit = ' %' if cr.get('positions_source') == 'positions 0 to 100 %' else ''
        sep = '=' * 70
        L = [sep, f'kbstatpy {__version__} — Curve Analysis Summary', sep, '',
             'FORMULA (fitted at every point of the curve)', '-' * 44, cr['formula'], '',
             'CURVES', '------',
             f"  Curve column           : {col} (options.curve = {self.options.curve!r})",
             f"  Curves                 : {cr['n_curves']}",
             f"  Points per curve       : {cr['n_points']}, {col} = "
             f"{cr['positions'][0]:g} to {cr['positions'][-1]:g}{unit} in steps of {cr['step']:g}",
             f"  Model at each point    : {'LMM (lme4::lmer, REML)' if cr['use_lmer'] else 'LM'}"
             + (f", df {cr['df_method']}" if cr['df_method'] else ''),
             f"  Smoothness (FWHM)      : {cr['fwhm']:.2f} points "
             f"({cr['fwhm'] * cr['step']:.3g}{unit} of {col})",
             f"  Resels                 : {cr['resels'][1]:.2f} "
             "(the curve's length in units of its smoothness)",
             f"  Threshold              : random field theory, alpha = {self.options.alpha:g} "
             'over the whole curve']
        if cr['singular']:
            L.append(f"  Singular fits          : at {cr['singular']} of {cr['n_points']} points "
                     "(a variance component estimated as 0)")
        L.append('')

        def cluster_lines(inf, stat):
            if not inf['clusters']:
                return ['  no clusters: the statistic stays below the threshold everywhere']
            pair = inf.get('pair')
            out = [f"  {'from':>9} {'to':>9} {'peak at':>9} {'peak ' + stat:>10} {'p':>10}"
                   + ('   higher' if pair else '')]
            for c in inf['clusters']:
                out.append(f"  {c['from']:9.2f} {c['to']:9.2f} {c['peak_at']:9.2f} "
                           f"{c['peak_value']:10.3f} {_fmt_p(c['p']):>10}"
                           + (f"   {c['higher']}" if pair else ''))
            return out

        L += ['TERMS', '-----']
        for term, inf in cr['terms'].items():
            label = self._curve_label(None, term)
            if inf['stat'] == 'F':
                df = f"F({inf['df1']:g}, {inf['df2']:.4g})"
            else:
                tv = self.options.test_value
                df = f"t({inf['df2']:.4g}), mean against {tv if tv is not None else 0:g}"
            L.append(f"  {label}: {df}, threshold {inf['threshold']:.3f}")
            lo, hi = inf['df2_range']
            if hi - lo > 1e-6 * max(1, hi):
                L.append(f"    (denominator df ranges from {lo:.4g} to {hi:.4g} over the "
                         "curve; the smallest is used, which is conservative)")
            L += ['  ' + s for s in cluster_lines(inf, inf['stat'])] + ['']

        if cr['posthoc']:
            n = cr['n_posthoc']
            a = cr['posthoc'][0]['alpha']
            L += ['POST-HOC COMPARISONS', '--------------------',
                  ] + textwrap.wrap(
                      f"Each pair is a t curve, tested two-sided at alpha = {a:.5g}: the "
                      f"Sidak correction of {self.options.alpha:g} over the {n} comparison "
                      f"curve{'s' if n > 1 else ''}, within which random field theory "
                      "controls the false-positive rate over the points.",
                      width=72, initial_indent='  ', subsequent_indent='  ') + ['']
            for inf in cr['posthoc']:
                L.append(f"  {self._curve_label(inf)}: t({inf['df']:.4g}), "
                         f"threshold +/-{inf['threshold']:.3f}")
                L += ['  ' + s for s in cluster_lines(inf, 't')]
                L.append('')

        L += ['NOTES', '-----',
              '  A cluster is a stretch of the curve where the statistic exceeds the',
              '  threshold; its p is the chance of a cluster at least that wide if',
              '  nothing were going on. from/to are interpolated to where the curve',
              '  crosses the threshold. The threshold and the cluster p come from',
              '  random field theory (Worsley et al. 1996; Friston et al. 1994), as in',
              '  SPM1D (Pataky 2016), with the smoothness estimated from the residual',
              '  curves of the model. Curve.xlsx holds every point.', sep]
        return '\n'.join(L)

    def _curve_figures(self):
        """CurveSPM: the statistic curve of each term with its threshold and
        clusters. CurveMeans: the estimated mean curves with bands at 1 - alpha, the
        clusters of the pairwise comparisons marked under them."""
        import matplotlib.pyplot as plt
        cr = self.curve_result
        x = cr['positions']
        col = self._disp(cr['column'])
        unit = ' [%]' if cr.get('positions_source') == 'positions 0 to 100 %' else ''

        panels = [(self._curve_label(None, t), inf) for t, inf in cr['terms'].items()]
        panels += [(self._curve_label(inf), inf) for inf in cr['posthoc']]
        n = len(panels)
        ncol = min(3, n)
        nrow = int(np.ceil(n / ncol))
        fig, axes = plt.subplots(nrow, ncol, figsize=(4.6 * ncol, 3.2 * nrow), squeeze=False)
        for ax, (label, inf) in zip(axes.flat, panels):
            z = inf['values']
            ax.plot(x, z, color='k', lw=1.4)
            u = inf['threshold']
            two = inf['stat'] == 't' if 'stat' in inf else True
            ax.axhline(u, color='#C0392B', ls='--', lw=1)
            if two:
                ax.axhline(-u, color='#C0392B', ls='--', lw=1)
                ax.axhline(0, color='#9AA3AA', lw=0.6)
            for c in inf['clusters']:
                ax.fill_between(x, z, c['sign'] * u,
                                where=(np.arange(len(x)) >= c['first']) & (np.arange(len(x)) <= c['last']),
                                color='#E59866', alpha=0.6, interpolate=True)
                # Fragments of a few points are listed in Summary.txt and
                # Curve.xlsx; labelled here they pile up into an unreadable heap.
                if c['extent'] >= 0.03 * (len(x) - 1):
                    ax.text(c['peak_at'], z[c['peak']], f" p = {_fmt_p(c['p'])}", fontsize=8,
                            va='bottom' if c['sign'] > 0 else 'top', color='#6B757C')
            stat = 'F' if inf.get('stat') == 'F' else 't'
            ax.set_title(label, fontsize=9)
            ax.set_ylabel(stat)
            ax.set_xlabel(f'{col}{unit}')
        for ax in list(axes.flat)[n:]:
            ax.set_visible(False)
        fig.tight_layout()
        self.fig_curve_spm = fig
        self._show_fig(fig)

        emm = cr['emm']
        factors = cr['factors']
        units = self.options.y_units
        units = (units[0] if units else '') if isinstance(units, (list, tuple)) else units
        y_label = self._disp(self.options.y) + (f' [{units}]' if units else '')
        first = factors[0] if factors else None
        others = factors[1:]
        cells = ([()] if not others else
                 list(emm[others].drop_duplicates().itertuples(index=False, name=None)))
        ncol = min(3, len(cells))
        nrow = int(np.ceil(len(cells) / ncol))
        fig2, axes2 = plt.subplots(nrow, ncol, figsize=(4.8 * ncol, 3.6 * nrow),
                                   squeeze=False, sharey=True)
        palette = plt.rcParams['axes.prop_cycle'].by_key()['color']
        # One colour per level for the whole figure, so a level keeps its
        # colour in every panel, on its curve and in the comparison bars.
        colour = ({str(lev): palette[i % len(palette)]
                   for i, lev in enumerate(dict.fromkeys(emm[first]))} if first else {})
        bars_per_cell = []
        for ax, cell in zip(axes2.flat, cells):
            sub = emm
            for f, v in zip(others, cell):
                sub = sub[sub[f] == v]
            groups = (list(dict.fromkeys(sub[first])) if first else [None])
            for lev in groups:
                g = sub if lev is None else sub[sub[first] == lev]
                g = g.sort_values('node')
                xx = x[g['node'].astype(int).to_numpy()]
                line_colour = colour.get(str(lev), palette[0])
                ax.plot(xx, g['emmean'], color=line_colour, lw=1.6,
                        label=str(lev) if lev is not None else 'mean')
                ax.fill_between(xx, g['lower'], g['upper'], color=line_colour, alpha=0.2, lw=0)
            cell_str = ', '.join(f'{f} = {v}' for f, v in zip(others, cell))
            bars_per_cell.append([inf for inf in cr['posthoc']
                                  if inf['cell'] == cell_str and inf['clusters']])
            if cell_str:
                ax.set_title(', '.join(f'{self._disp(f)} = {v}' for f, v in zip(others, cell)),
                             fontsize=9)
            ax.set_xlabel(f'{col}{unit}')
            ax.set_ylabel(y_label)
            if first:
                ax.legend(title=self._disp(first), fontsize=8, title_fontsize=8,
                          frameon=False, loc='best')
        # One y range for all panels (they share the axis), with a strip below
        # the curves for the clusters of each pairwise comparison.
        used = list(axes2.flat)[:len(cells)]
        ylo = min(a.get_ylim()[0] for a in used)
        yhi = max(a.get_ylim()[1] for a in used)
        span = yhi - ylo
        n_bars = max((len(b) for b in bars_per_cell), default=0)
        row = 0.08 * span
        for ax, bars in zip(used, bars_per_cell):
            for bi, inf in enumerate(bars):
                yb = ylo - row * (bi + 0.7)
                # Two parallel strokes in the colours of the two levels
                # compared, so a bar is matched to its curves at a glance.
                for c in inf['clusters']:
                    for lev, dy in zip(inf['pair'], (0.09, -0.09)):
                        ax.plot([c['from'], c['to']], [yb + dy * row] * 2,
                                color=colour.get(str(lev), 'k'), lw=2.2,
                                solid_capstyle='butt')
                ax.text(x[0], yb + row * 0.18, f"{inf['pair'][0]} vs {inf['pair'][1]}",
                        fontsize=7, va='bottom', ha='left', color='#6B757C')
        for ax in used:
            ax.set_ylim(ylo - row * (n_bars + 0.3) if n_bars else ylo, yhi)
        for ax in list(axes2.flat)[len(cells):]:
            ax.set_visible(False)
        fig2.tight_layout()
        self.fig_curve_means = fig2
        self._show_fig(fig2)

    def _curve_tables_of(self, cr):
        """Sheets of Curve.xlsx: the clusters, and every point of every curve."""
        x = cr['positions']
        rows, points = [], []
        for term, inf in cr['terms'].items():
            label = self._curve_label(None, term)
            for c in inf['clusters']:
                rows.append({'test': label, 'statistic': inf['stat'], 'from': c['from'],
                             'to': c['to'], 'peak at': c['peak_at'], 'peak': c['peak_value'],
                             'threshold': inf['threshold'], 'p': c['p']})
            for q, v in enumerate(inf['values']):
                points.append({'test': label, cr['column']: x[q], inf['stat']: v,
                               'threshold': inf['threshold']})
        for inf in cr['posthoc']:
            label = self._curve_label(inf)
            for c in inf['clusters']:
                rows.append({'test': label, 'statistic': 't', 'from': c['from'], 'to': c['to'],
                             'peak at': c['peak_at'], 'peak': c['peak_value'],
                             'threshold': inf['threshold'], 'p': c['p'],
                             'higher': c.get('higher', '')})
            for q, v in enumerate(inf['values']):
                points.append({'test': label, cr['column']: x[q], 't': v,
                               'diff': inf['diff'][q], 'threshold': inf['threshold']})
        emm = cr['emm'].copy()
        emm.insert(0, cr['column'], x[emm['node'].astype(int).to_numpy()])
        emm = emm.drop(columns='node')
        return {'Clusters': pd.DataFrame(rows), 'Points': pd.DataFrame(points), 'Means': emm}


def _fmt_p(p):
    if p == 0:
        return '<1e-308'          # below the smallest double
    if p < 1e-4:
        return f'{p:.2e}'
    return f'{p:.4f}'
