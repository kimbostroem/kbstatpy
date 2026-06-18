"""Demo 8 — GLMM with gamma distribution

Strictly positive, right-skewed outcomes can also be modelled directly with a
distribution that fits, instead of being forced into a normal model. This demo
shows that on the `Oats` dataset (nlme; Yates 1935), a split-plot field trial:
oat yield for three varieties under four nitrogen levels across six blocks
(72 plots).

It fits a generalised linear mixed model with a gamma distribution and log link,
with a random intercept per block:

    yield ~ Variety * Nitrogen + (1 | Block)

There is no classical counterpart: a gamma GLMM captures the mean–variance
relationship of skewed positive data directly (a constant coefficient of
variation), and the log link keeps fitted yields positive — which a t-test or
ANOVA cannot. Compare with demo 7, which targets the same data by log-transforming
a normal model instead.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

HERE = os.path.dirname(os.path.abspath(__file__))

options = KbstatOptions()
options.in_file      = os.path.join(HERE, '../data/oats.csv')                     # input data file
options.out_dir      = os.path.join(HERE, 'results/demo_08_glmm_gamma')        # output folder
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
kb.run_save()

