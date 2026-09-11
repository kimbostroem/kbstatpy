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
    # Random-effect correlation structure for the slopes. Accepts True, False, or
    # 'auto' (the default).
    #   True   fits the full covariance among the random intercept and slopes,
    #          (1 + s | id). If that fit is singular a warning suggests 'auto'/False.
    #   False  fits an uncorrelated (diagonal) structure — glmmTMB diag(1 + s | id)
    #          for the non-gaussian families, lme4's (1 + s || id) for gaussian
    #          LMMs — which drops the correlation parameters and avoids the
    #          near-singular fits a many-level factor slope can otherwise produce.
    #   'auto' fits the correlated structure first and, only if it comes back
    #          singular (non-positive-definite Hessian / boundary correlation /
    #          non-finite likelihood), refits with the uncorrelated (diagonal)
    #          structure. The fallback is reported in Summary.txt and the
    #          diagnostics footer. Ignored when an explicit `formula` is supplied.
    slope_correlated: object = 'auto'
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

    # Observation count above which df_method='auto' stops using Kenward-Roger
    # and uses Satterthwaite instead. A cost threshold, not a statistical one:
    # KR's cost grows as roughly n^2.5 (80 s at n = 18000 against a flat ~0.06 s
    # for Satterthwaite) while the two methods stop differing meaningfully above
    # roughly a thousand observations, so the default sits at the knee of the
    # cost curve with a wide margin above the convergence point. An explicit
    # df_method='kenward-roger' is still honoured at any n (with a warning about
    # the cost); set kr_max_obs=0 to lift the cap for 'auto' as well.
    # STATISTICAL_NOTES.md carries the measured timings and df comparisons.
    kr_max_obs: int = 5000

    # Report ML information criteria for a ladder of fixed-effect structures
    # (additive, all two-way, full factorial) alongside the fitted model, so the
    # cost of the additive default is visible instead of implicit. Off by default.
    #
    # It is a REPORT, never a selection. Choosing a structure by AIC and then
    # quoting the winner's p-values as if it had been fixed in advance inflates
    # them: over 300 simulated datasets containing no interaction at all, a
    # search of this same ladder kept one 30.7% of the time and called it
    # significant in 13.0% of runs, against the 5.0% a pre-specified test gives.
    # The model that is fitted, tested and reported stays the one you asked for.
    # The table is followed by a reading of it: structures within 2 AIC of the best
    # are called indistinguishable and parsimony breaks the tie, so a gap of a
    # fraction of a unit is not presented as a result.
    #
    # Costs one extra fit per rung, with the random-effect structure held fixed;
    # that is about a second per variable on 18 000 rows with a random intercept,
    # more with random slopes, which dominate the cost far more than row count.
    model_comparison: bool = False

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
    # Annotate each plotted group with its observation count ('n=12'), placed
    # just above the group's violin (or its CI bar in bar style). Off by default
    # in both styles; before this option existed the counts were drawn
    # unconditionally in bar style, so bar plots lose them unless this is set.
    # The significance brackets are stacked above the labels and keep a visible
    # gap from them, so switching the labels on pushes the brackets up rather
    # than colliding with them. 'true'/'false', 'on'/'off', 'yes'/'no' and 'none'
    # (= off) are accepted alongside True/False.
    show_group_size: object = False
    # Draw a horizontal reference line across the whole panel at the height of
    # every plotted group's EMM (the marginal mean already marked by the white
    # dot), in that group's own colour. It lets a group's level be read off
    # directly against the other groups' distributions, instead of comparing dot
    # heights by eye across the panel. Applies to the data plots (violin and bar style alike); each panel
    # uses its own EMMs, and where none is available the line follows the same
    # median fallback as the dot.
    #   False (default)  no lines
    #   True             lines in the default style, dotted — it recedes furthest
    #                    behind the violins and brackets, so a line crossing a
    #                    violin cannot be mistaken for plotted data
    #   '-' | '--' | ':' | '-.'  or the matplotlib names 'solid' | 'dashed' |
    #                    'dotted' | 'dashdot' — lines in that style. Solid reads
    #                    calmest and makes the group colours easiest to attribute,
    #                    at the cost of looking more like plotted content.
    # 'true'/'false', 'on'/'off' and 'yes'/'no' are accepted alongside True/False,
    # and 'none' means off (not matplotlib's invisible 'none' style).
    show_emm_lines: object = False
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
    # How data outliers (flagged by remove_outliers_prefit/postfit) appear in the
    # data plot. With 'text'/'hide' the outlier points are not drawn, so the
    # y-axis autoscales to the non-outlier data — useful when extreme outliers
    # otherwise squash the plot.
    #   'plot'   draw each outlier as a red X marker
    #   'text'   (default) omit the points but annotate the count and percentage
    #            of outliers as text at the bottom (south) of each panel
    #   'hide'   omit outliers entirely, no annotation
    # 'plot' marks them with red X markers, 'text' (default) annotates the count
    # and percentage, 'none' hides them silently ('off' / 'hide' also accepted).
    data_outliers: str = 'text'
    # Number of simulated datasets behind the DHARMa quantile residuals used by
    # the diagnostic distribution panels. 'auto' (the default) scales it with the
    # data; give an integer to pin it.
    #
    # The count sets the RESOLUTION of those residuals, which is why it is worth
    # a knob. A quantile residual is the observation's position in the empirical
    # CDF of the simulations, so it can only take the values k/n_sim: the most
    # extreme value expressible is qnorm(1/n_sim), and every observation beyond
    # it lands either on that value or in the capped pile. DHARMa's own default
    # of 250 puts that limit at z = +/-2.65, which on a few thousand rows shows
    # up as horizontal rows of points at the ends of the Q-Q plot -- not ties in
    # the data, just the grid running out. It also inflates the capped count:
    # the same fit reported 1.67% capped at 250 simulations and 0.91% at 1000.
    #
    # 'auto' asks for 2 x n_obs, which is what it takes to resolve the most
    # extreme order statistic of an n_obs sample (its tail probability is about
    # 1/(2 n_obs)), bounded to [1000, 5000] and then held under a memory budget:
    # DHARMa keeps an n_obs x n_sim matrix, which at 18 000 rows and 5000
    # simulations would be some 750 MB. The budget caps the product instead, and
    # never drops below DHARMa's own 250, so a very large fit degrades to
    # today's behaviour rather than exhausting memory.
    diagnostic_sims: object = 'auto'

    # Deprecated alias for data_outliers (the option name up to 1.10.0). None
    # means unset; if given, it overrides data_outliers with a DeprecationWarning.
    show_outliers: object = None
    # y-axis scale for the DATA plots and the profile plot (options.profile_across):
    #   'linear' (default)
    #   'log'    logarithmic y-axis, useful when panels of one figure span orders of
    #            magnitude (e.g. joint torque at ankle vs upper body) and a shared
    #            linear axis flattens the small-valued panels into slivers. It also
    #            suits gamma/log-link models, where a constant ratio becomes a
    #            constant distance. Significance brackets and the y-limit padding
    #            are computed in log space so the spacing stays even.
    #            Requires strictly positive plotted values; if any are <= 0 the
    #            scale falls back to 'linear' with a warning. Diagnostic and
    #            correlation figures are never rescaled.
    y_scale: str = 'linear'
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
