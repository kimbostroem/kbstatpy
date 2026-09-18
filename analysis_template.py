"""kbstatpy analysis template.

Copy this file next to your data, fill in the five required options, uncomment
what you need and delete the rest.

Every commented-out line shows the value kbstatpy uses anyway, so an active line
is always a deliberate departure from the default and a commented one is a
reminder of what happens if you leave it alone.

Full reference: README.md for the option table, STATISTICAL_NOTES.md for the
reasoning behind the defaults.

Run:  python3 my_analysis.py
"""

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()

# ---------------------------------------------------------------------------
# Data in, results out                                              [required]
# ---------------------------------------------------------------------------
options.in_file = 'data/my_data.csv'        # .csv or .xlsx, one row per observation
options.out_dir = 'results/my_analysis'     # created if missing, relative to the working directory

# options.constraints = 'age > 18 & group != "pilot"'   # row filter, applied before everything else

# ---------------------------------------------------------------------------
# The model                                                         [required]
# ---------------------------------------------------------------------------
options.y  = 'my_outcome'                   # dependent variable, comma-separated for several
options.x  = 'group, condition'             # fixed factor(s), the first goes on the x-axis
options.id = 'subject'                      # random grouping factor, '' for no random effect

# options.interaction = 'auto'             # DEFAULT: every interaction the design supports
# options.interaction = ''                 # additive: main effects only, no interactions
# options.interaction = 'group, condition' # just these interact
# options.interaction = 'all'              # the full factorial; raises if not estimable
# options.interaction = 2                  # every factor in x, up to two-way
# options.covariate   = 'age'               # numeric covariates: in the model, out of the plots
# options.slope       = 'condition'         # random slope(s) on options.id, not just an intercept
# options.formula     = 'y ~ group * condition + (1 | subject)'   # overrides everything above

# 'auto' and 'all' fit the same thing when the design is complete. They differ
# only where a term is not estimable because cells are empty: 'auto' leaves it
# out and says so in Summary.txt, 'all' raises. That is judged on which cells
# were observed, never on the response, so it is not model selection.

# Several grouping factors, comma-separated, are CROSSED (one intercept each).
# For a replicate index whose labels recur inside every subject, nest it instead
# with a slash, and check it earns its place: an unsupported block term fits as a
# zero variance and a singular fit, and one grouping factor is then the better model.
# options.id = 'subject, session'           # crossed:  (1 | subject) + (1 | session)
# options.id = 'subject/repetition'         # nested:   (1 | subject) + (1 | subject:repetition)

# ---------------------------------------------------------------------------
# Distribution, only when the outcome is not roughly normal
# ---------------------------------------------------------------------------
# options.distribution = 'normal'           # normal | gamma | binomial | poisson | inverse_gaussian
# options.link         = 'auto'             # canonical link, or 'log', 'logit', ...
# options.y_transform  = 'log(y)'           # transform instead of a GLMM; EMMs are back-transformed
# options.dispersion   = 'group'            # per-group dispersion for the glmmTMB families

# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------
# options.df_method        = 'auto'         # auto | kenward-roger | satterthwaite | asymptotic
# options.model_comparison = False          # AIC/BIC for additive vs two-way vs factorial

# ---------------------------------------------------------------------------
# Post-hoc comparisons
# ---------------------------------------------------------------------------
# options.posthoc_compare    = 'auto'       # factor(s) to compare pairwise, '' or 'none' = off
# options.posthoc_correction = 'holm'       # holm | bonferroni | fdr | tukey | none
# options.posthoc_family     = 'cell'       # what the correction spans: cell | pooled | cross
# options.y_correction       = 'none'       # correction ACROSS several dependent variables

# A two-level factor gives one comparison per cell, and correcting one value does
# nothing, so pCorr equals p. Set posthoc_family='pooled' if the cells should be
# corrected against each other. Summary.txt states which family was used.

# ---------------------------------------------------------------------------
# Outliers
# ---------------------------------------------------------------------------
# options.remove_outliers_prefit  = False   # drop IQR outliers (1.5 x IQR per group) before fitting
# options.remove_outliers_postfit = False   # drop residual outliers (z > 3) and refit
# options.data_outliers = 'text'            # how excluded rows show in the plot: text | plot | none

# ---------------------------------------------------------------------------
# Labels and appearance
# ---------------------------------------------------------------------------
# options.title   = 'Study A'               # title prefix, 'none' suppresses it entirely
# options.y_units = 'Nm'                    # y-axis unit(s), comma-separated for multi-y
# options.x_units = ', mg'                  # unit(s) per x factor, by position; empty = no unit
# options.rename  = 'grp -> Group; grp: c1 -> Control'   # display names for variables and levels
# options.x_order = 'dose: low, medium, high'            # level order on the axis and in the tables

# options.plot_style      = 'auto'          # violin | bar | auto (bar for binary outcomes)
# options.y_scale         = 'linear'        # linear | log
# options.show_group_size = False           # annotate each group with its n
# options.show_emm_lines  = False           # reference line at each group's marginal mean
# options.color_scheme    = 'Set1'          # any matplotlib/seaborn palette name
# options.figure_display  = 'show_close'    # save_only | show_close | show_keep (all of them save)

# ---------------------------------------------------------------------------
# Optional extra analyses
# ---------------------------------------------------------------------------
# options.correlation         = 'a, b, c'   # pairwise correlations between numeric variables
# options.correlation_method  = 'pearson'   # pearson | spearman
# options.correlation_control = 'age'       # partial this out of every correlation
# options.profile_across      = 'dose'      # profile across one ordered factor (>= 3 levels)

# ---------------------------------------------------------------------------
Kbstat(options).run_save()                  # fit, test, plot, and write everything to out_dir
