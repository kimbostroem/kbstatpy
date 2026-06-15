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
    y: object = ''            # str for a single dependent variable, or list[str] to iterate
    y_units: object = ''      # unit label(s) for the y-axis, e.g. 'ms' or 'kg, N, m' for multi-y
    x_units: object = ''      # unit label(s) for x factors, e.g. '1, mg' — '1' means no units
    y_transform: str = ''     # optional transform expression using 'y' as placeholder, e.g. 'log(y)'
    x: list = field(default_factory=list)
    id: str = ''
    slope: list = field(default_factory=list)
    interaction: list = field(default_factory=list)

    # GLM settings
    distribution: str = 'normal'
    link: str = 'auto'
    fit_method: str = 'MPL'

    remove_outliers: bool = False

    # Covariates: included in model and ANOVA, excluded from plots and post-hoc
    covariate: list = field(default_factory=list)

    # Plot settings
    colors: str = 'Set1'

    # Post-hoc settings
    posthoc_method: str = 'emm'
    posthoc_correction: str = 'holm'
