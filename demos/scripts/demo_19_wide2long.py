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

    deltaBP ~ Treatment * dose + (1|Rabbit),   gamma, log link

The rises are positive and their scatter grows with the dose: the rabbits lie
within 1 mmHg of each other at 6.25 µg and 17 mmHg apart at 100 µg. A normal model assumes one
residual spread for all of them. In a gamma model the SD is proportional to the
mean, and the log link makes the treatment effect a ratio (demo 8).

The wide file has a Rabbit column, used as `options.id`. Without one, kbstatpy
would create `wide_row`, the row number of the wide file, and use that.

Result: the blood pressure rises steeply with dose (chi² = 559, 5 df), and MDL
72222 damps that rise in the middle of the dose range: placebo over MDL is 2.5 at
25 µg, 4.3 at 50 µg and 1.6 at 100 µg, while at 200 µg the two are equal. The
Treatment × dose interaction (chi² = 43, 5 df) is this shift of the dose-response
curve to the right, the antagonist's signature. The grey lines join each
rabbit's two treatments.

Compared with a normal model, the gamma model also finds the difference at
25 µg (3 mmHg, small in absolute terms but 2.5-fold) and weighs the large ones at
100 µg less heavily, where the scatter is largest. At 6.25 µg it reports MDL
above placebo (p = 0.03); a difference of 0.7 mmHg in one of six uncorrected
cells is better read as noise (posthoc_family = 'pooled' corrects across them).
"""

import os

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = os.path.join(options.demo_dir, 'data/pbg_wide.csv')  # wide input file
options.out_dir      = 'results/demo_19_wide2long'      # output folder
options.wide2long    = 'Treatment = (Placebo, MDL); dose = (6.25, 12.5, 25, 50, 100, 200)'
options.y            = 'deltaBP'          # the stacked values land in this column
options.y_units      = 'mmHg'
options.distribution = 'gamma'           # positive, spread grows with the mean (log link)
options.x            = 'Treatment, dose'  # Treatment on the x-axis, one panel per dose
options.x_units      = ', µg'
options.interaction  = 'Treatment, dose'
options.id           = 'Rabbit'           # the unit of the wide rows
options.rename       = 'deltaBP -> Blood pressure rise; dose -> Dose'

kb = Kbstat(options)
kb.run_save()
