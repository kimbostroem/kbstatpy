import pandas as pd
import polars as pl
from pymer4.models import lmer as Lmer
from pymer4.models import glmer as Glmer

from .options import KbstatOptions


class Kbstat:
    """Generalized linear mixed model analysis with post-hoc pairwise comparisons."""

    def __init__(self, options: KbstatOptions):
        self.options = options
        self.data: pd.DataFrame = None
        self.model = None
        self.anova_table: pd.DataFrame = None
        self.posthoc_table: pd.DataFrame = None

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
        """Extract the ANOVA table from the fitted model."""
        if self.model is None:
            raise RuntimeError('Call fit() before anova()')
        self.model.anova()
        self.anova_table = self.model.result_anova
        return self.anova_table

    def posthoc(self):
        """Perform post-hoc pairwise comparisons."""
        if self.model is None:
            raise RuntimeError('Call fit() before posthoc()')
        factors = self.options.x if self.options.x else []
        if not factors:
            return None
        self.model.set_factors(factors)
        self.posthoc_table = self.model.emmeans(
            marginal_var=factors[0],
            p_adjust=self.options.posthoc_correction,
        )
        return self.posthoc_table

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
