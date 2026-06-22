"""Demo 13 — Family-wise correction across multiple dependent variables

When you test several outcomes at once, the chance of at least one false positive
grows with the number of tests. `options.y_correction` controls this: after a
multi-y run it adjusts the per-outcome p-values together (one family per model
term) and writes the raw and adjusted values to `MultipleComparisons.xlsx`.

This demo compares six characteristics of the `mtcars` cars (R base; 1974 Motor
Trend) between automatic and manual transmission:

    {mpg, hp, wt, qsec, drat, disp} ~ am

Four outcomes differ clearly by transmission (mpg, wt, drat, disp) and two do
not (hp, qsec) — a realistic family in which correction matters. With six tests,
~0.3 false positives are expected by chance even if nothing were real, so the
`am` p-values are corrected as a family.

`y_correction='FDR'` applies the Benjamini-Hochberg false-discovery-rate
correction. Other choices: 'bonferroni' and 'holm' (control the family-wise
error rate — stricter), 'FDR_correlated' (Benjamini-Yekutieli, valid when the
outcomes are correlated, as these are). Open `MultipleComparisons.xlsx` to see
the raw `p` beside `p_corrected` for each outcome.

Note: this corrects across the dependent variables of a single run. If your
family of tests spans several separate runs (e.g. one per condition), apply the
correction at that outer level instead.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file = os.path.join(options.demo_dir, 'data/mtcars.csv')  # input data file
options.out_dir = 'results/demo_13_family_correction'               # output folder (subfolders per variable)
options.y            = 'mpg, hp, wt, qsec, drat, disp'   # six dependent variables (comma-separated)
options.y_units      = 'mpg, hp, 1000 lb, s, ratio, cu in'  # unit label per variable
options.x            = 'am'                              # fixed-effect factor: transmission
options.rename       = 'am: 0 -> automatic, 1 -> manual'  # readable factor levels
options.x_order      = ['automatic', 'manual']           # reference level first
options.y_correction = 'FDR'  # correct the am p-values across the six outcomes (Benjamini-Hochberg)

kb = Kbstat(options)
kb.run_save()
