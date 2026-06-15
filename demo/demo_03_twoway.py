"""Demo 3: Two-way ANOVA equivalent.

Two between-subject factors (supplement type × dose), no repeated measures.
Plain linear model — equivalent to a classical two-way ANOVA.

Dataset: ToothGrowth (R base). Guinea pig tooth length (mm) after vitamin C
supplementation by two delivery methods (OJ = orange juice, VC = ascorbic acid)
at three dose levels (low / medium / high).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file  = os.path.join(os.path.dirname(__file__), 'data', 'toothgrowth.csv')
options.out_dir  = os.path.join(os.path.dirname(__file__), 'results', 'demo_03_twoway')
options.formula  = 'len ~ supp * dose'
options.y        = 'len'
options.x        = ['supp', 'dose']
options.distribution = 'normal'

kb = Kbstat(options)
kb.run()

# run() is equivalent to calling the following steps individually:
# kb.fit()               # fit the model
# kb.anova()             # compute Type III ANOVA table
# kb.posthoc()           # pairwise post-hoc comparisons
# kb.plot_diagnostics()  # show diagnostic plots (saved to out_dir when save() is called)
# kb.plot_data()         # show data plot (saved to out_dir when save() is called)
# kb.save()              # save all result tables, figures, and Summary.txt to out_dir
