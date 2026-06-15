from dataclasses import dataclass, field


@dataclass
class KbstatOptions:
    """Configuration for a kbstat analysis run."""

    # Data input / output
    in_file: str = ''
    out_dir: str = ''

    # constraints
    constraints: str = ''

    # Model specification
    formula: str = ''
    y: str = ''
    x: list = field(default_factory=list)
    id: str = ''
    slope: list = field(default_factory=list)

    # GLM settings
    distribution: str = 'normal'
    link: str = 'auto'
    fit_method: str = 'MPL'

    remove_outliers: bool = False

    # Covariates: included in model and ANOVA, excluded from plots and post-hoc
    covariate: list = field(default_factory=list)

    # Plot settings
    colors: str = 'Set2'

    # Post-hoc settings
    posthoc_method: str = 'emm'
    posthoc_correction: str = 'holm'
