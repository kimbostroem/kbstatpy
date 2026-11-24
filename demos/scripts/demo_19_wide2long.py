"""Demo 19 — Wide data with two within-subject factors (`wide2long`)

Data entered by hand or exported from a lab spreadsheet often arrive in wide
format: one row per subject, one column per condition. kbstatpy fits long data,
one row per observation, and `options.wide2long` does the reshape on reading.

The dataset is `PBG` (nlme; Ludbrook 1994, analysed in Pinheiro & Bates 2000):
five rabbits each received six doses of phenylbiguanide (6.25 to 200 µg), once
after a placebo and once after MDL 72222, a 5-HT3 antagonist. The outcome is the
rise in blood pressure (mmHg). Both treatment and dose vary *within* each rabbit,
so `pbg_wide.csv` has one row per rabbit and twelve columns, one per
treatment × dose: `Placebo_6.25`, ..., `MDL_200`.

    wide2long = 'Treatment = (Placebo, MDL); dose = (6.25, 12.5, 25, 50, 100, 200)'

Each entry lists one factor's LEVELS; the columns are their combinations joined
by `_`, in the order of the entries (`Placebo_6.25`, ...). The twelve columns
become sixty rows with the values in `options.y` and two new factors, Treatment
and dose, whose levels keep the order listed. The reshape runs first, so
`rename`, `x_order` and `constraints` already see the long data.

The rabbit is the unit measured twelve times, so it enters as random intercept:

    deltaBP ~ Treatment * dose + (1|Rabbit)

The wide file has a Rabbit column, used as `options.id`. Without one, kbstatpy
would create `wide_row`, the row number of the wide file, and use that.

Result: the blood pressure rises steeply with dose (F(5, 44) = 81), and MDL 72222
damps that rise at 50 and 100 µg only, by 13 and 11 mmHg; at the three lowest
doses and at 200 µg the treatments do not differ. The Treatment × dose interaction
(F(5, 44) = 5.7) is this shift of the dose-response curve to the right, the
antagonist's signature. The grey lines join each rabbit's two treatments. The
spread grows with the mean (spread ratio about 3.6), so a log transform or a
gamma model (demos 7 and 8) would be worth comparing.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = os.path.join(options.demo_dir, 'data/pbg_wide.csv')  # wide input file
options.out_dir      = 'results/demo_19_wide2long'      # output folder
options.wide2long    = 'Treatment = (Placebo, MDL); dose = (6.25, 12.5, 25, 50, 100, 200)'
options.y            = 'deltaBP'          # the stacked values land in this column
options.y_units      = 'mmHg'
options.x            = 'Treatment, dose'  # Treatment on the x-axis, one panel per dose
options.x_units      = ', µg'
options.interaction  = 'Treatment, dose'
options.id           = 'Rabbit'           # the unit of the wide rows
options.rename       = 'deltaBP -> Blood pressure rise; dose -> Dose'

kb = Kbstat(options)
kb.run_save()
