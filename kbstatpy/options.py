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
    correlation_method: str = 'pearson'  # 'pearson' | 'spearman' — for the raw and partial correlations
    correlation_control: object = ''  # variable(s) to partial out of every correlation, e.g. 'Age' (list or comma-separated); adjusts both the raw and partial tables and is not shown in the matrix
    y_transform: str = ''     # optional transform expression using 'y' as placeholder, e.g. 'log(y)'
    x: list = field(default_factory=list)
    x_order: object = None   # dict {var: [level, ...]} or list (applied to x[0]) to reorder factor levels
    rename: object = None    # str 'var: old -> new, old -> new; var2: ...' or dict {var: {old: new}} — applies to any column
    id: str = ''
    slope: list = field(default_factory=list)
    # Random-effect correlation structure for the slopes. True (default) fits a
    # full covariance among the random intercept and slopes, (1 + s | id). False
    # fits an uncorrelated (diagonal) structure — glmmTMB diag(1 + s | id) for the
    # non-gaussian families, lme4's (1 + s || id) for gaussian LMMs — which drops
    # the correlation parameters and avoids the near-singular fits that a
    # many-level factor slope can otherwise produce.
    slope_correlated: bool = True
    interaction: list = field(default_factory=list)

    # GLM settings
    distribution: str = 'normal'
    link: str = 'auto'
    # Dispersion model for the glmmTMB families (Gamma, inverse Gaussian, etc.):
    # the right-hand side of glmmTMB's dispformula. '' (default) = constant
    # dispersion (~1). Give a factor name, e.g. 'JointGroup', to let the
    # dispersion vary by that factor (dispformula = ~ JointGroup), which is useful
    # when pooled groups differ widely in scale/scatter. Ignored for gaussian
    # (LM/LMM) models.
    dispersion: str = ''
    fit_method: str = 'MPL'
    # Maximum optimizer iterations / function evaluations for the glmmTMB fit
    # (non-Gaussian GLMMs). Large fixed-effect models — e.g. a factor*factor
    # interaction with many levels — can hit the optimizer's default cap and emit
    # a benign "iteration limit reached" convergence warning even when the fit is
    # already at the optimum; raising this lets them converge cleanly. Only
    # affects glmmTMB fits (gamma, binomial, Poisson, ...).
    max_iterations: int = 10000

    # Denominator-df method for the fixed-effect tests (ANOVA F and post-hoc
    # contrasts), used identically for both so the two strata stay consistent:
    #   'auto'          (default) Kenward-Roger for Gaussian LMMs when the R
    #                   package pbkrtest is installed, else Satterthwaite; exact
    #                   residual df for plain LMs; asymptotic (Wald z, df=Inf)
    #                   for GLMMs.
    #   'kenward-roger' force Kenward-Roger (Gaussian LMM + pbkrtest only).
    #   'satterthwaite' force Satterthwaite (Gaussian LMM).
    #   'asymptotic'    force asymptotic Wald z (df=Inf).
    # A request unavailable for the fitted model/dataset warns and falls back
    # (see Kbstat._validate_df_method). Aliases: 'kr', 'satt', 'wald'.
    df_method: str = 'auto'

    remove_outliers_prefit: bool = False   # IQR-based outlier removal per group before fitting
    remove_outliers_postfit: bool = False  # Pearson-residual outlier removal after fitting (refits model)

    # Covariates: included in model and ANOVA, excluded from plots and post-hoc
    covariate: list = field(default_factory=list)

    # Plot settings
    # Data-plot title prefix. When set, the title becomes '<title> (<DV>)',
    # e.g. title='Static' -> 'Static (Torque Amplitude)'. In a multi-y run each
    # variable still gets its own display name in the parentheses. Empty (default)
    # keeps the plain dependent-variable name as the title. title='none' (case-
    # insensitive) suppresses the title entirely -- no text and no vertical space
    # reserved for it -- while leaving the y-axis label untouched (the y-axis
    # label and title both otherwise derive from the same variable display name,
    # so this is the only way to drop the title alone).
    title: str = ''
    # Font family for plot titles (suptitles), distinct from the body font.
    # Empty (default) derives the title font from the body font (see `font`):
    # a condensed/narrow variant when one is installed (e.g. 'Arial' ->
    # 'Arial Narrow', 'DejaVu Sans' -> 'DejaVu Sans Condensed'), otherwise the
    # body font itself. So titles match the body font, using a condensed face
    # only where that exact variant exists. Set a family name (or list of
    # names) to override.
    title_font: object = ''
    color_scheme: str = 'Set1'
    color_sat: float = 0.9
    color_alpha: float = 0.5
    # Matplotlib font family (or ordered fallback chain) for body text on all
    # plots. The default is Helvetica: the real font on macOS/Windows, and the
    # bundled TeX Gyre Heros clone on Linux/Colab, so it renders as Helvetica on
    # every platform with no system font install. kbstatpy also bundles Latin
    # Modern Sans (LaTeX's Computer Modern sans) and TeX Gyre Termes (a Times
    # clone), all registered on import. Override with any family name or
    # comma-separated chain; a request for Helvetica/Arial or Times falls back to
    # its bundled clone where the real font is absent, rather than dropping to the
    # visibly-different DejaVu Sans. Convenient case-insensitive aliases:
    # 'Sans'/'Modern' -> Latin Modern Sans (the LaTeX look), 'Times' -> Times New
    # Roman; any family name is also matched case-insensitively. matplotlib tries
    # each family in order, so a missing one never warns. '' or 'auto' uses
    # matplotlib's own default (DejaVu Sans). The title font derives from this (see
    # title_font). To match this style in a hand-built matplotlib figure that
    # bypasses Kbstat.run_save() entirely, call the public Kbstat.apply_font()
    # before building it.
    font: str = 'Helvetica, DejaVu Sans'
    # Previous default (matplotlib's own, DejaVu Sans) — restore this line to
    # roll back the Helvetica-first chain above:
    # font: str = ''
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
    # Which fixed-effect factor(s) to run pairwise level comparisons on. Each
    # listed factor is plotted as if it were the first x-variable — its levels on
    # the x-axis, the others as facet panels — with significance brackets between
    # its violins. Comparisons are CONDITIONAL (per cell): a factor's levels are
    # compared within each combination of the other factors, so every facet panel
    # gets its own brackets (and its own block of rows in Posthoc_<var>.xlsx, with
    # the conditioning factors as leading columns). Per-cell p-values are corrected
    # within the cell. Posthoc_<var>.xlsx additionally carries a marginal block —
    # every conditioning column set to 'any' — with the comparison averaged over the
    # conditioning factors (table only, not the plot). Comma-separated factor names;
    # '' or 'none' turns comparisons
    # off (violin plots only, no brackets); 'auto' (default) compares the first
    # x-variable. Output files are suffixed with the (original) variable name, e.g.
    # DataPlots_condition.* and Posthoc_condition.xlsx. 'auto' and 'none' are
    # reserved — a factor may not be named either.
    posthoc_compare: str = 'auto'

    # Level-wise profile analysis across an ordered factor. Set to the name of one
    # categorical fixed factor B (must be in x). In addition to the normal
    # analyses, kbstat then profiles how the OTHER factor(s) that interact with B
    # behave across B's ordered levels:
    #   Layer 1 (per-level): each interacting factor A's pairwise contrast computed
    #            within every level of B (marginal over any further factors) — the
    #            level-by-level profile, with per-level estimate, CI, and p.
    #   Layer 2 (trend): the A x B interaction as a 1-df linear trend across B's
    #            ordered positions (emmeans polynomial interaction contrast on the
    #            fitted model), reported alongside the factor-omnibus A:B already in
    #            the ANOVA. Leads with the focused linear trend.
    # Level order = x_order[B] if set, else B's existing (first-appearance) order.
    # The trend uses B's numeric positions: the level labels' numeric values when
    # all parse as numbers (so unequal spacing, e.g. dose 1/2/10, is honoured), else
    # equal-spaced ranks. The trend estimate is the per-unit slope of the profiled
    # contrast across B, and its test reduces to the equal-spaced polynomial trend
    # when spacing is equal. Meaningful only when B interacts with
    # the profiled factor and has >=3 ordered levels (warns otherwise). Writes
    # LevelProfile.xlsx and a profile plot. '' (default) = off.
    profile_across: str = ''

    # Multiple-comparison correction applied ACROSS the dependent variables of a
    # multi-y run (one family per model term). Distinct from posthoc_correction,
    # which corrects pairwise comparisons within a single model. Results are
    # written to MultipleComparisons.xlsx. Only acts when y has >1 component.
    #   'none' (default) | 'bonferroni' | 'holm' | 'FDR' (Benjamini-Hochberg)
    #   | 'FDR_correlated' (Benjamini-Yekutieli, valid under dependence)
    # Case-insensitive.
    y_correction: str = 'none'
