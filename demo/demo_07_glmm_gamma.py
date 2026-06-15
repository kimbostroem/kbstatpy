"""Demo 7: Generalised linear mixed model (GLMM) with gamma distribution.

Two crossed fixed-effect factors (Variety × Nitrogen), random intercept per
block. Oat yield is positive and right-skewed — gamma distribution with log
link is more appropriate than a normal LMM.

Compare with demo 6 (sleepstudy, log-transformed LMM): both approaches handle
right-skewed positive outcomes; the gamma GLMM models the variance structure
directly rather than transforming the data.

Dataset: Oats (nlme). Split-plot experiment on oat varieties and nitrogen
fertilisation (Yates, 1935). 3 varieties × 4 nitrogen levels × 6 blocks,
72 observations total.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = 'data/oats.csv'                     # input data file
options.out_dir      = 'results/demo_06_glmm_gamma'        # output folder
options.y            = 'yield'                    # dependent variable
options.y_units      = 'qt/plot'                  # unit label for y-axis (quarter-pounds per plot)
options.x            = 'Variety, Nitrogen'         # fixed-effect factors
options.id           = 'Block'                     # random-effect grouping variable
options.interaction  = 'Variety, Nitrogen'         # test the Variety × Nitrogen interaction
options.distribution = 'gamma'                    # gamma GLMM (positive, right-skewed outcome)
options.link         = 'log'                      # log link function
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
