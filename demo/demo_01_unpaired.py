"""Demo 1: Unpaired t-test equivalent.

Two independent groups (drug 1 vs drug 2), continuous outcome (extra sleep hours).
No repeated measures — plain linear model, equivalent to an unpaired t-test.

Dataset: sleep (R base), Cushny & Peebles (1905) / Student (1908).
"""

import sys, os
DEMO_DIR = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(DEMO_DIR, '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file  = os.path.join(DEMO_DIR, 'data', 'sleep.csv')
options.out_dir  = os.path.join(DEMO_DIR, 'results', 'demo_01_unpaired')
options.formula  = 'extra ~ group'
options.y        = 'extra'
options.x        = ['group']
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
