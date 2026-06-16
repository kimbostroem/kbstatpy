"""Demo 4: Linear mixed model (LMM) as a one-way repeated-measures ANOVA.

One within-subject factor (stool Type, 4 levels) with a random intercept per
subject to account for individual baseline differences. Because the design is
balanced with exactly one observation per subject per level and no within-cell
trend, the model is an exact equivalent of a classical one-way repeated-measures
ANOVA: the Type III F-test for Type matches the RM-ANOVA F, and the random
intercept reproduces the compound-symmetry covariance that RM-ANOVA assumes.

Dataset: ergoStool (nlme). Perceived effort (Borg scale) required for 9 subjects
to arise from each of 4 stool types (Wretenberg, Arborelius & Lindberg, 1993).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = 'data/ergostool.csv'               # input data file
options.out_dir      = 'results/demo_04_lmm'              # output folder
options.y            = 'effort'          # dependent variable
options.y_units      = 'Borg'           # unit label for y-axis
options.x            = 'Type'            # fixed-effect factor(s)
options.id           = 'Subject'         # random-effect grouping variable (subject ID)
options.rename       = 'effort -> Effort; Type -> Stool type'
# options.formula    = 'effort ~ Type + (1 | Subject)'  # alternative: Wilkinson formula (overrides y, x, id above)

kb = Kbstat(options)
kb.run()

# run() is equivalent to calling the following steps individually:
# kb.fit()               # fit the model
# kb.anova()             # compute Type III ANOVA table
# kb.posthoc()           # pairwise post-hoc comparisons
# kb.plot_diagnostics()  # show diagnostic plots (saved to out_dir when save() is called)
# kb.plot_data()         # show data plot (saved to out_dir when save() is called)
# kb.save()              # save all result tables, figures, and Summary.txt to out_dir
