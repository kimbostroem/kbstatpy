"""Demo 2 — Paired t-test equivalent

When the same subjects are measured under both conditions, accounting for that
pairing is both more correct and more powerful. This demo shows the paired
t-test equivalent on the `sleep` dataset (R base; Cushny & Peebles 1905 / Student
1908), where both drugs were measured on the same 10 patients.

A random intercept per patient absorbs each person's baseline sleep tendency:

    extra ~ group + (1 | ID)

This is equivalent to a paired t-test (degrees of freedom n − 1); comparing its
p-value with demo 1 shows how accounting for the pairing increases power.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = os.path.join(options.demo_dir, 'data/sleep.csv')                    # input data file
options.out_dir      = 'results/demo_02_paired'            # output folder
options.y            = 'extra'           # dependent variable
options.y_units      = 'h'              # unit label for y-axis
options.x            = 'group'           # fixed-effect factor(s)
options.id           = 'ID'              # random-effect grouping variable (subject ID)
options.rename       = 'extra -> ExtraSleep; group -> DrugGroup'
# options.formula    = 'extra ~ group + (1 | ID)'  # alternative: Wilkinson formula (overrides y, x, id above)

kb = Kbstat(options)
kb.run_save()

