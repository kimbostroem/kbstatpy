"""Demo 3: Two-way ANOVA equivalent.

Two between-subject factors (supplement type × dose), no repeated measures.
Plain linear model — equivalent to a classical two-way ANOVA.

Dataset: ToothGrowth (R base). Guinea pig tooth length (mm) after vitamin C
supplementation by two delivery methods (OJ = orange juice, VC = ascorbic acid)
at three dose levels (low / medium / high).
"""

import sys, os
DEMO_DIR = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(DEMO_DIR, '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = os.path.join(DEMO_DIR, 'data', 'toothgrowth.csv')  # input data file
options.out_dir      = os.path.join(DEMO_DIR, 'results', 'demo_03_twoway')  # output folder
options.y            = 'len'             # dependent variable
options.y_units      = 'mm'             # unit label for y-axis
options.x            = 'supp, dose'      # fixed-effect factors
options.interaction  = 'supp, dose'      # test the supp × dose interaction
# options.formula    = 'len ~ supp * dose'  # alternative: Wilkinson formula (overrides y, x, interaction above)

kb = Kbstat(options)
kb.run()

# run() is equivalent to calling the following steps individually:
# kb.fit()               # fit the model
# kb.anova()             # compute Type III ANOVA table
# kb.posthoc()           # pairwise post-hoc comparisons
# kb.plot_diagnostics()  # show diagnostic plots (saved to out_dir when save() is called)
# kb.plot_data()         # show data plot (saved to out_dir when save() is called)
# kb.save()              # save all result tables, figures, and Summary.txt to out_dir
