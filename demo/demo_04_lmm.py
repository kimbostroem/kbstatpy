"""Demo 4: Linear mixed model (LMM) with random intercepts.

One within-subject factor (Period: rested vs deprived), random intercept per
subject to account for individual baseline differences in reaction time.

Dataset: sleepstudy (lme4). Reaction times (ms) of 18 subjects over 10 days of
sleep deprivation (Belenky et al., 2003). Days 0-4 are labelled 'rested',
days 5-9 are labelled 'deprived'.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file  = os.path.join(os.path.dirname(__file__), 'data', 'sleepstudy.csv')
options.out_dir  = os.path.join(os.path.dirname(__file__), 'results', 'demo_04_lmm')
options.formula  = 'Reaction ~ Period + (1 | Subject)'
options.y        = 'Reaction'
options.x        = ['Period']
options.id       = 'Subject'
options.distribution = 'normal'

kb = Kbstat(options)
kb.fit()

print('\n--- ANOVA ---')
print(kb.anova())

print('\n--- Post-hoc ---')
print(kb.posthoc())

kb.save()
