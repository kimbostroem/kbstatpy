"""Demo 2: Paired t-test equivalent.

Same data as demo 1 but now accounting for the fact that both drugs were tested
on the same 10 patients. A random intercept per patient captures between-subject
baseline differences, equivalent to a paired t-test.

Compare the post-hoc p-value with demo 1 to see how pairing increases power.

Dataset: sleep (R base), Cushny & Peebles (1905) / Student (1908).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file  = os.path.join(os.path.dirname(__file__), 'data', 'sleep.csv')
options.out_dir  = os.path.join(os.path.dirname(__file__), 'results', 'demo_02_paired')
options.formula  = 'extra ~ group + (1 | ID)'
options.y        = 'extra'
options.x        = ['group']
options.id       = 'ID'
options.distribution = 'normal'

kb = Kbstat(options)
kb.fit()

print('\n--- ANOVA ---')
print(kb.anova())

print('\n--- Post-hoc ---')
print(kb.posthoc())

kb.save()
