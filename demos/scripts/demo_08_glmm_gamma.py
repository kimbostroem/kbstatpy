"""Demo 8 — GLMM with gamma distribution

This demo uses the `Oats` dataset (nlme; Yates 1935), a split-plot field trial in
which oat yield was measured for three varieties grown under four nitrogen levels
across six blocks (72 plots). Yield is strictly positive and right-skewed, so
rather than force it into a normal model the demo models it directly.

It fits a generalised linear mixed model with a gamma distribution and log link,
with a random intercept per block:

    yield ~ Variety * Nitrogen + (1 | Block)

There is no classical counterpart here: a gamma GLMM captures the mean–variance
relationship of skewed positive data directly (a constant coefficient of
variation), and the log link keeps fitted yields positive — something a t-test or
ANOVA cannot do. Compare it with demo 7, which targets the same kind of data by
log-transforming the response of a normal model instead.
"""

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = '../data/oats.csv'                     # input data file
options.out_dir      = 'results/demo_08_glmm_gamma'        # output folder
options.y            = 'yield'                    # dependent variable
options.y_units      = 'qt/plot'                  # unit label for y-axis (quarter-pounds per plot)
options.x            = 'Variety, Nitrogen'         # fixed-effect factors
options.id           = 'Block'                     # random-effect grouping variable
options.interaction  = 'Variety, Nitrogen'         # test the Variety × Nitrogen interaction
options.distribution = 'gamma'                    # gamma GLMM (positive, right-skewed outcome)
options.link         = 'log'                      # log link function
options.x_units      = '1, cwt/acre'
options.x_order      = 'Nitrogen: 0.0, 0.2, 0.4, 0.6'
options.rename       = 'yield -> CropYield; Variety: Golden.rain -> golden_rain'
# options.formula    = 'yield ~ Variety * Nitrogen + (1 | Block)'  # alternative: Wilkinson formula (overrides y, x, id, interaction above)

kb = Kbstat(options)
kb.run()

# run() is equivalent to calling the following steps individually:
# kb.fit()               # fit the model
# kb.anova()             # compute Type III ANOVA table
# kb.posthoc()           # pairwise post-hoc comparisons
# kb.plot_diagnostics()  # show diagnostic plots (saved to out_dir when save() is called)
# kb.plot_data()         # show data plot (saved to out_dir when save() is called)
# kb.save()              # save all result tables, figures, and Summary.txt to out_dir
