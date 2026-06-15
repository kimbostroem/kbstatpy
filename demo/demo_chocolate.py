"""Demo: chocolate dataset.

Two between-subject factors (Chocolate, Gender), continuous outcome (jump distance in m).
Mirrors kbstat_demo_chocolate.m from the MATLAB kbstat library.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file = os.path.join(os.path.dirname(__file__), 'Chocolate.csv')
options.out_dir = os.path.join(os.path.dirname(__file__), 'Results_chocolate')
# options.y = 'Distance'
# options.x = ['Chocolate', 'Gender']
# options.id = 'Subject'
options.distribution = 'gamma'
options.link = 'log'
options.fit_method = 'MPL'
options.formula = 'Distance ~ Chocolate * Gender + (1 | Subject)'

kb = Kbstat(options)
kb.run()

print('\n--- ANOVA ---')
print(kb.anova())

print('\n--- Post-hoc ---')
print(kb.posthoc())

kb.save()
