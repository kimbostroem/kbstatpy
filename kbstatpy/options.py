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
    correlation: object = ''  # variables for pairwise correlation analysis (list or comma-separated)
    y_transform: str = ''     # optional transform expression using 'y' as placeholder, e.g. 'log(y)'
    x: list = field(default_factory=list)
    x_order: object = None   # dict {var: [level, ...]} or list (applied to x[0]) to reorder factor levels
    rename: object = None    # str 'var: old -> new, old -> new; var2: ...' or dict {var: {old: new}} — applies to any column
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
    color_scheme: str = 'Set1'
    color_sat: float = 0.9
    color_alpha: float = 0.5

    # Post-hoc settings
    posthoc_method: str = 'emm'
    posthoc_correction: str = 'holm'
