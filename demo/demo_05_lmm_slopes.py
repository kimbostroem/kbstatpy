"""Demo 5: LMM with random intercepts and random slopes.

Same as demo 4 but each subject is now allowed their own slope for Period,
i.e. subjects differ not only in baseline reaction time but also in how strongly
sleep deprivation affects them.

Compare the random-effects variance table with demo 4 to see the additional
slope variance and intercept-slope correlation estimated by the model.

Dataset: sleepstudy (lme4), same as demo 4.
"""

import sys, os
DEMO_DIR = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(DEMO_DIR, '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = os.path.join(DEMO_DIR, 'data', 'sleepstudy.csv')  # input data file
options.out_dir      = os.path.join(DEMO_DIR, 'results', 'demo_05_lmm_slopes')  # output folder
options.formula      = 'Reaction ~ Period + (1 + Period | Subject)'  # Wilkinson formula (overrides y, x, id, slope below)
options.y            = 'Reaction'        # dependent variable
options.x            = ['Period']        # fixed-effect factor(s)
options.id           = 'Subject'         # random-effect grouping variable (subject ID)
options.slope        = ['Period']        # random slope(s): each subject gets their own Period slope
options.distribution = 'normal'          # gaussian LMM with random intercepts and slopes

kb = Kbstat(options)
kb.run()

# run() is equivalent to calling the following steps individually:
# kb.fit()               # fit the model
# kb.anova()             # compute Type III ANOVA table
# kb.posthoc()           # pairwise post-hoc comparisons
# kb.plot_diagnostics()  # show diagnostic plots (saved to out_dir when save() is called)
# kb.plot_data()         # show data plot (saved to out_dir when save() is called)
# kb.save()              # save all result tables, figures, and Summary.txt to out_dir
