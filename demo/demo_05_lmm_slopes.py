"""Demo 5: LMM with random intercepts and random slopes.

Same as demo 4 but each subject is now allowed their own slope for Period,
i.e. subjects differ not only in baseline reaction time but also in how strongly
sleep deprivation affects them.

Compare the random-effects variance table with demo 4 to see the additional
slope variance and intercept-slope correlation estimated by the model.

Dataset: sleepstudy (lme4), same as demo 4.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file  = os.path.join(os.path.dirname(__file__), 'data', 'sleepstudy.csv')
options.out_dir  = os.path.join(os.path.dirname(__file__), 'results', 'demo_05_lmm_slopes')
options.formula  = 'Reaction ~ Period + (1 + Period | Subject)'
options.y        = 'Reaction'
options.x        = ['Period']
options.id       = 'Subject'
options.slope    = ['Period']
options.distribution = 'normal'

kb = Kbstat(options)
kb.fit()

print('\n--- ANOVA ---')
print(kb.anova())

print('\n--- Post-hoc ---')
print(kb.posthoc())

kb.save()
