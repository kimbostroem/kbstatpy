"""Demo 2: Paired t-test equivalent.

Same data as demo 1 but now accounting for the fact that both drugs were tested
on the same 10 patients. A random intercept per patient captures between-subject
baseline differences, equivalent to a paired t-test.

Compare the post-hoc p-value with demo 1 to see how pairing increases power.

Dataset: sleep (R base), Cushny & Peebles (1905) / Student (1908).
"""

import sys, os
DEMO_DIR = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(DEMO_DIR, '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = os.path.join(DEMO_DIR, 'data', 'sleep.csv')  # input data file
options.out_dir      = os.path.join(DEMO_DIR, 'results', 'demo_02_paired')  # output folder
options.formula      = 'extra ~ group + (1 | ID)'  # Wilkinson formula (overrides y, x, id below)
options.y            = 'extra'           # dependent variable
options.x            = ['group']         # fixed-effect factor(s)
options.id           = 'ID'              # random-effect grouping variable (subject ID)
options.distribution = 'normal'          # gaussian LMM

kb = Kbstat(options)
kb.run()

# run() is equivalent to calling the following steps individually:
# kb.fit()               # fit the model
# kb.anova()             # compute Type III ANOVA table
# kb.posthoc()           # pairwise post-hoc comparisons
# kb.plot_diagnostics()  # show diagnostic plots (saved to out_dir when save() is called)
# kb.plot_data()         # show data plot (saved to out_dir when save() is called)
# kb.save()              # save all result tables, figures, and Summary.txt to out_dir
