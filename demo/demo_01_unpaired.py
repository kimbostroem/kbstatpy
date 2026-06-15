"""Demo 1: Unpaired t-test equivalent.

Two independent groups (drug 1 vs drug 2), continuous outcome (extra sleep hours).
No repeated measures — plain linear model, equivalent to an unpaired t-test.

Dataset: sleep (R base), Cushny & Peebles (1905) / Student (1908).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file  = os.path.join(os.path.dirname(__file__), 'data', 'sleep.csv')
options.out_dir  = os.path.join(os.path.dirname(__file__), 'results', 'demo_01_unpaired')
options.formula  = 'extra ~ group'
options.y        = 'extra'
options.x        = ['group']
options.distribution = 'normal'

kb = Kbstat(options)
kb.fit()

print('\n--- ANOVA ---')
print(kb.anova())

print('\n--- Post-hoc ---')
print(kb.posthoc())

kb.plot_diagnostics()
kb.save()
