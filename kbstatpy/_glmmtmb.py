"""
Direct glmmTMB/emmeans wrapper for generalised linear mixed models.

This is the GLMM engine for all non-Gaussian families (binomial, poisson,
Gamma, inverse.gaussian). It replaces lme4::glmer, which produces unreliable
fixed-effect standard errors for the continuous dispersion families (Gamma,
inverse Gaussian): glmer fits the correct point estimates and log-likelihood but
returns a mis-scaled covariance matrix, so every standard-error-derived quantity
(Wald omnibus tests, post-hoc pairwise p-values, EMM confidence intervals)
collapses. glmmTMB estimates the dispersion as an explicit parameter and computes
the covariance from a proper (autodiff) Hessian, so those quantities are correct
and mutually coherent.

glmmTMB also handles random slopes natively, so this single engine covers both
the random-intercept and random-slope cases (lme4 needed the separate direct
wrapper only because pymer4's Glmer crashed on slopes).

The class exposes the same interface that kbstat.py expects from a model object
(fit / anova / emmeans / set_factors / set_contrasts and the r_model, residuals,
fits, result_anova, coefs, fit_stats attributes).
"""

import warnings

import numpy as np
import pandas as pd
import rpy2.robjects as ro
from rpy2.robjects import pandas2ri, default_converter
from rpy2.robjects.conversion import localconverter

# Fixed R variable names — safe for single-threaded use
_R_DATA  = '.__kbstat_data__'
_R_MODEL = '.__kbstat_model__'


class GlmmTMB:
    """GLMM engine backed by glmmTMB (drop-in for the former glmer path)."""

    def __init__(self, formula: str, data: pd.DataFrame, family: str, link: str = 'default',
                 max_iterations: int = 10000):
        self.formula = formula
        self._pd_data = data
        self.family = family
        self.link = link
        self.max_iterations = int(max_iterations)
        # Attributes expected by kbstat.py
        self.r_model = None
        self.residuals = None
        self.fits = None
        self.result_anova = None
        self.result_fit_stats = None
        self.fit_stats = None
        self.coefs = None
        self.ranef_var = None
        self.factors = {}
        self._r_contrasts = {}

    # ------------------------------------------------------------------
    # Public interface (the methods/attributes kbstat.py expects from a model)
    # ------------------------------------------------------------------

    def fit(self, summarize=False):
        """Fit the GLMM via glmmTMB::glmmTMB and extract residuals, fits, summaries."""
        self._push_data()

        family_expr = self._family_expr()
        # Raise the nlminb optimizer's iteration/evaluation caps so large
        # fixed-effect models converge cleanly instead of stopping at the default
        # limit with a benign "iteration limit reached" warning (see max_iterations).
        _maxit = int(self.max_iterations)
        ro.r(f'''
        suppressMessages(library(glmmTMB))
        {_R_MODEL} <- glmmTMB(
            {self.formula},
            data    = {_R_DATA},
            family  = {family_expr},
            control = glmmTMBControl(optCtrl = list(iter.max = {_maxit}, eval.max = {_maxit}))
        )
        ''')
        self.r_model = ro.r(_R_MODEL)

        self._check_convergence()

        self.residuals = np.array(ro.r(f'residuals({_R_MODEL}, type="pearson")'))
        self.fits      = np.array(ro.r(f'fitted({_R_MODEL})'))

        self._extract_coefs()
        self._extract_fit_stats()

    def anova(self, jointtest_kwargs=None, **kwargs):
        """Type III ANOVA table via emmeans::joint_tests().

        With glmmTMB's correctly scaled covariance the Wald joint test is
        trustworthy and coherent with the emmeans post-hoc comparisons.
        """
        ro.r('suppressMessages(library(emmeans))')
        ro.r(f'.__kbstat_jt__ <- as.data.frame(joint_tests({_R_MODEL}))')

        with localconverter(default_converter + pandas2ri.converter):
            df = ro.conversion.rpy2py(ro.r('.__kbstat_jt__'))

        df = df.rename(columns={
            'F.ratio': 'F_ratio',
            'p.value': 'p_value',
        })
        self.result_anova = df

    def emmeans(self, marginal_var: str, by=None, p_adjust: str = 'holm', **kwargs):
        """Marginal means for marginal_var via emmeans::emmeans()."""
        ro.r('suppressMessages(library(emmeans))')
        ro.r(f'''
        .__kbstat_emm__ <- emmeans(
            {_R_MODEL},
            specs  = ~ {marginal_var},
            type   = "response",
            adjust = "{p_adjust}"
        )
        .__kbstat_emm_df__ <- as.data.frame(.__kbstat_emm__)
        ''')
        with localconverter(default_converter + pandas2ri.converter):
            return ro.conversion.rpy2py(ro.r('.__kbstat_emm_df__'))

    def set_factors(self, factors_and_levels):
        """Convert columns to R factors (mirrors pymer4 set_factors)."""
        if isinstance(factors_and_levels, str):
            factors_and_levels = [factors_and_levels]
        if isinstance(factors_and_levels, list):
            factors_and_levels = {f: None for f in factors_and_levels}
        self.factors = dict(factors_and_levels)
        for col in self.factors:
            ro.r(f'{_R_DATA}[["{col}"]] <- as.factor({_R_DATA}[["{col}"]])')

    def set_contrasts(self, contrasts: dict, normalize=False):
        """Apply contrast coding to factors (mirrors pymer4 set_contrasts)."""
        self._r_contrasts = contrasts
        for col, contrast in contrasts.items():
            if isinstance(contrast, str):
                ro.r(f'contrasts({_R_DATA}[["{col}"]]) <- {contrast}(nlevels({_R_DATA}[["{col}"]]))')

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _push_data(self):
        with localconverter(default_converter + pandas2ri.converter):
            ro.globalenv[_R_DATA] = pandas2ri.py2rpy(self._pd_data)

    def _family_expr(self) -> str:
        if self.link and self.link not in ('default', 'auto', ''):
            return f'{self.family}(link="{self.link}")'
        return self.family

    def _check_convergence(self):
        """Warn if glmmTMB did not converge cleanly (so unreliable fits surface)."""
        try:
            code = int(ro.r(f'{_R_MODEL}$fit$convergence')[0])
        except Exception:
            code = 0
        if code != 0:
            warnings.warn(
                f'glmmTMB reported non-convergence (code {code}); '
                f'results for this fit may be unreliable.', stacklevel=2)

    def _extract_coefs(self):
        ro.r(f'''
        .__kbstat_coefs__ <- as.data.frame(summary({_R_MODEL})$coefficients$cond)
        .__kbstat_coefs__$term <- rownames(.__kbstat_coefs__)
        rownames(.__kbstat_coefs__) <- NULL
        ''')
        with localconverter(default_converter + pandas2ri.converter):
            self.coefs = ro.conversion.rpy2py(ro.r('.__kbstat_coefs__'))

    def _extract_fit_stats(self):
        ro.r(f'''
        .__kbstat_fs__ <- data.frame(
            AIC      = AIC({_R_MODEL}),
            BIC      = BIC({_R_MODEL}),
            logLik   = as.numeric(logLik({_R_MODEL})),
            deviance = tryCatch(as.numeric(deviance({_R_MODEL})), error = function(e) NA_real_)
        )
        ''')
        with localconverter(default_converter + pandas2ri.converter):
            self.result_fit_stats = ro.conversion.rpy2py(ro.r('.__kbstat_fs__'))
        self.fit_stats = self.result_fit_stats
