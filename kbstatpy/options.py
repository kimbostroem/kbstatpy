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

    # GLM settings
    distribution: str = 'normal'
    link: str = 'auto'
    fit_method: str = 'MPL'

    remove_outliers: bool = True

    # Post-hoc settings
    posthoc_method: str = 'emm'
    posthoc_correction: str = 'holm'
