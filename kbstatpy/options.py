import os
from dataclasses import dataclass, field

# Absolute path to the bundled demo folder (a sibling of this package in the
# source tree). Convenience anchor for the demos; present when running from the
# repo, which is the only place the demos live.
_DEMO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'demos')


@dataclass
class KbstatOptions:
    """Configuration for a kbstat analysis run."""

    # Data input / output
    in_file: str = ''
    out_dir: str = ''

    # Absolute path to the bundled demo folder, for example inputs, e.g.
    #   os.path.join(options.demo_dir, 'data/sleep.csv')
    # (Outputs need no such anchor: a relative out_dir resolves against the
    # current working directory, so out_dir='results/my_run' already lands there.)
    demo_dir: str = field(default_factory=lambda: _DEMO_DIR)

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

    remove_outliers_prefit: bool = False   # IQR-based outlier removal per group before fitting
    remove_outliers_postfit: bool = False  # Pearson-residual outlier removal after fitting (refits model)

    # Covariates: included in model and ANOVA, excluded from plots and post-hoc
    covariate: list = field(default_factory=list)

    # Plot settings
    # Data-plot title prefix. When set, the title becomes '<title> (<DV>)',
    # e.g. title='Static' -> 'Static (Torque Amplitude)'. In a multi-y run each
    # variable still gets its own display name in the parentheses. Empty (default)
    # keeps the plain dependent-variable name as the title.
    title: str = ''
    # Font family for plot titles (suptitles), distinct from the body font.
    # Empty (default) uses a narrow / condensed sans-serif if one is installed
    # (e.g. 'Arial Narrow', 'DejaVu Sans Condensed'), falling back to the regular
    # sans-serif font, so titles take less horizontal space. Set a family name
    # (or list of names) to override.
    title_font: object = ''
    color_scheme: str = 'Set1'
    color_sat: float = 0.9
    color_alpha: float = 0.5
    font: str = ''
    plot_style: str = 'auto'   # 'auto' | 'violin' | 'bar'
    # How the x-axis of the data plot labels the first factor's levels:
    #   'variable_below_levels' (default) level names as tick labels, with the
    #                           variable name as the axis label below them
    #   'variable_equals_level' each tick reads '<variable> = <level>'
    #                           (e.g. 'State = normal'); no separate axis label
    #   'levels'                only the level names; the variable name is hidden
    #   'none'                  no x-axis labelling at all (neither level ticks
    #                           nor variable name)
    x_label: str = 'variable_below_levels'
    # How the y-axis of the data plot is labelled:
    #   'variable_with_units' (default) variable name plus '[units]' when units are set
    #   'variable_only'                 variable name only, no units
    #   'none'                          no y-axis label at all
    y_label: str = 'variable_with_units'
    # How outliers (flagged by remove_outliers_prefit/postfit) appear in the data
    # plot. With 'none'/'text' the outlier points are not drawn, so the y-axis
    # autoscales to the non-outlier data — useful when extreme outliers otherwise
    # squash the plot.
    #   'plot'   (default) draw each outlier as a red X marker
    #   'none'   omit outliers entirely
    #   'text'   omit the points but annotate the count and percentage of
    #            outliers as text at the bottom (south) of each panel
    show_outliers: str = 'plot'
    figure_display: str = 'show_close'   # 'save_only' | 'show_close' | 'show_keep'; all save files.
    #                                      In notebooks show_close/show_keep both render inline once.

    # Post-hoc settings
    posthoc_method: str = 'emm'
    posthoc_correction: str = 'holm'

    # Multiple-comparison correction applied ACROSS the dependent variables of a
    # multi-y run (one family per model term). Distinct from posthoc_correction,
    # which corrects pairwise comparisons within a single model. Results are
    # written to MultipleComparisons.xlsx. Only acts when y has >1 component.
    #   'none' (default) | 'bonferroni' | 'holm' | 'FDR' (Benjamini-Hochberg)
    #   | 'FDR_correlated' (Benjamini-Yekutieli, valid under dependence)
    # Case-insensitive.
    y_correction: str = 'none'
