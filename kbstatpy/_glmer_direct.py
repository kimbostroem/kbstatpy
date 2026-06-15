"""
Direct lme4/emmeans wrapper for GLMMs with random slopes.

pymer4 0.9.x crashes in its broom.tidy() result-parsing layer when a GLMM has
random slopes (more than one random-effect term per grouping factor). lme4 itself
handles random slopes correctly. This class calls lme4 and emmeans directly via
rpy2 and exposes the same interface that kbstat.py expects from a Glmer object.
"""

import numpy as np
import pandas as pd
import rpy2.robjects as ro
from rpy2.robjects import pandas2ri, default_converter
from rpy2.robjects.conversion import localconverter

# Fixed R variable names — safe for single-threaded use
_R_DATA  = '.__kbstat_data__'
_R_MODEL = '.__kbstat_model__'


class GlmerDirect:
    """Drop-in replacement for pymer4 Glmer when random slopes are present."""

    def __init__(self, formula: str, data: pd.DataFrame, family: str, link: str = 'default'):
        self.formula = formula
        self._pd_data = data
        self.family = family
        self.link = link
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
    # Public interface (mirrors pymer4 Glmer)
    # ------------------------------------------------------------------

    def fit(self, summarize=False):
        """Fit the GLMM via lme4::glmer and extract residuals, fits, and summaries."""
        self._push_data()

        family_expr = self._family_expr()
        ro.r(f'''
        suppressMessages(library(lme4))
        {_R_MODEL} <- glmer(
            {self.formula},
            data   = {_R_DATA},
            family = {family_expr}
        )
        ''')
        self.r_model = ro.r(_R_MODEL)

        self.residuals = np.array(ro.r(f'residuals({_R_MODEL}, type="pearson")'))
        self.fits      = np.array(ro.r(f'fitted({_R_MODEL})'))

        self._extract_coefs()
        self._extract_fit_stats()

    def anova(self, jointtest_kwargs=None, **kwargs):
        """Type III ANOVA table via emmeans::joint_tests()."""
        ro.r('suppressMessages(library(emmeans))')
        ro.r(f'.__kbstat_jt__ <- as.data.frame(joint_tests({_R_MODEL}))')

        with localconverter(default_converter + pandas2ri.converter):
            df = ro.conversion.rpy2py(ro.r('.__kbstat_jt__'))

        # Rename to the column names kbstat.py expects before its own rename step
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

    def _extract_coefs(self):
        ro.r(f'''
        .__kbstat_coefs__ <- as.data.frame(summary({_R_MODEL})$coefficients)
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
            deviance = deviance({_R_MODEL})
        )
        ''')
        with localconverter(default_converter + pandas2ri.converter):
            self.result_fit_stats = ro.conversion.rpy2py(ro.r('.__kbstat_fs__'))
        self.fit_stats = self.result_fit_stats
