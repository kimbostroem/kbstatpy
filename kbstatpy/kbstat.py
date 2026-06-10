import pandas as pd
from pymer4.models import Lmer

from .options import KbstatOptions


class Kbstat:
    """Generalized linear mixed model analysis with post-hoc pairwise comparisons."""

    def __init__(self, options: KbstatOptions):
        self.options = options
        self.data: pd.DataFrame = None
        self.model: Lmer = None
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
        """Load data and fit the GLMM."""
        if self.data is None:
            self._load_data()
        formula = self._build_formula()
        self.model = Lmer(formula, data=self.data, family=self._family())
        self.model.fit(summarize=False)

    def anova(self):
        """Extract the ANOVA table from the fitted model."""
        if self.model is None:
            raise RuntimeError('Call fit() before anova()')
        self.anova_table = self.model.anova()
        return self.anova_table

    def posthoc(self):
        """Perform post-hoc pairwise comparisons."""
        if self.model is None:
            raise RuntimeError('Call fit() before posthoc()')
        factors = self.options.x if self.options.x else []
        if not factors:
            return None
        self.posthoc_table = self.model.post_hoc(
            marginal_vars=factors[0],
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
            self.data = pd.read_csv(path)
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
        """Map options.distribution to the pymer4 family string."""
        mapping = {
            'normal':          'gaussian',
            'binomial':        'binomial',
            'poisson':         'poisson',
            'gamma':           'Gamma',
            'inverse_gaussian': 'inverse.gaussian',
        }
        return mapping.get(self.options.distribution, 'gaussian')
