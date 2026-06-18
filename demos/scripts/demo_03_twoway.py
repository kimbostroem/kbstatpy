"""Demo 3 — Two-way ANOVA equivalent

This demo uses the `ToothGrowth` dataset (R base), in which the tooth
(odontoblast) length of 60 guinea pigs was measured after vitamin C
supplementation given by two delivery methods — orange juice (`OJ`) and ascorbic
acid (`VC`) — at three dose levels (low, medium, high), with 10 animals in each of
the six cells. It asks whether length depends on the supplement, the dose, and
their interaction.

Both factors enter as crossed between-subject effects:

    len ~ supp * dose

With effects coding, Type III sums of squares, and a balanced design, the result
is numerically identical to a classical two-way factorial ANOVA, including the
interaction term.
"""

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = '../data/toothgrowth.csv'              # input data file
options.out_dir      = 'results/demo_03_twoway'            # output folder
options.y            = 'len'             # dependent variable
options.y_units      = 'mm'             # unit label for y-axis
options.x            = 'supp, dose'      # fixed-effect factors
options.interaction  = 'supp, dose'      # test the supp × dose interaction
options.rename       = 'len -> ToothLength; supp -> Supplement; dose -> Dose; supp: OJ -> orange_juice, VC -> vitamin_c'
options.x_order      = 'dose: low, medium, high'
# options.formula    = 'len ~ supp * dose'  # alternative: Wilkinson formula (overrides y, x, interaction above)

kb = Kbstat(options)
kb.run_save()

