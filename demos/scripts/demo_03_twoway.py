"""Demo 3 — Two-way ANOVA equivalent

Two crossed factors and their interaction are the classic two-way ANOVA, which a
linear model reproduces exactly on a balanced design. This demo shows that on the
`ToothGrowth` dataset (R base): the tooth (odontoblast) length of 60 guinea pigs
given vitamin C by two delivery methods — orange juice (`OJ`) and ascorbic acid
(`VC`) — at three dose levels (low, medium, high), 10 animals per cell.

Both factors enter as crossed between-subject effects:

    len ~ supp * dose

With effects coding, Type III sums of squares, and the balanced design, the
result is numerically identical to a classical two-way factorial ANOVA, including
the interaction term.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

HERE = os.path.dirname(os.path.abspath(__file__))

options = KbstatOptions()
options.in_file      = os.path.join(HERE, '../data/toothgrowth.csv')              # input data file
options.out_dir      = os.path.join(HERE, 'results/demo_03_twoway')            # output folder
options.y            = 'len'             # dependent variable
options.y_units      = 'mm'             # unit label for y-axis
options.x            = 'supp, dose'      # fixed-effect factors
options.interaction  = 'supp, dose'      # test the supp × dose interaction
options.rename       = 'len -> ToothLength; supp -> Supplement; dose -> Dose; supp: OJ -> orange_juice, VC -> vitamin_c'
options.x_order      = 'dose: low, medium, high'
# options.formula    = 'len ~ supp * dose'  # alternative: Wilkinson formula (overrides y, x, interaction above)

kb = Kbstat(options)
kb.run_save()

