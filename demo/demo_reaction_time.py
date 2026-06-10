"""Demo: reaction time dataset.

Two within-subject factors A and B, continuous outcome (reaction time in ms).
Mirrors kbstat_demo_reactionTime.m from the MATLAB kbstat library.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file = os.path.join(os.path.dirname(__file__), 'reaction_time.csv')
options.out_dir = os.path.join(os.path.dirname(__file__), 'Results_rt')
options.y = 'rt'
options.x = ['A', 'B']
options.id = 'id'
options.distribution = 'gamma'
options.link = 'log'
options.fit_method = 'MPL'
options.formula = 'rt ~ A * B + (A + B | id)'

kb = Kbstat(options)
kb.fit()

print('\n--- ANOVA ---')
print(kb.anova())

print('\n--- Post-hoc ---')
print(kb.posthoc())
