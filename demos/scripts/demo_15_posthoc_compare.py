"""Demo 15 — Comparing several factors with posthoc_compare

By default kbstatpy runs the pairwise post-hoc comparisons — and the data plot's
significance brackets — on the *first* x-variable only. `options.posthoc_compare`
lets you pick one or more factors to compare instead. Each listed factor is
plotted as if it were the first variable (its levels on the x-axis, the others as
facet panels), with its own significance brackets, and written to
`DataPlots_<var>.*` and `Posthoc_<var>.xlsx`.

This demo reuses the two-way ToothGrowth model from Demo 3:

    len ~ supp * dose

but compares BOTH factors in a single run, from one model fit — `supp` (orange
juice vs ascorbic acid) and `dose` (low/medium/high). Comparisons are per-cell
(conditional): each factor's levels are compared within every cell of the other
factor, so each facet panel gets its own brackets — e.g. medium-vs-high dose is
highly significant under vitamin C but only marginally so under orange juice.
Each `Posthoc_<var>.xlsx` also carries a marginal block (conditioning column set
to `any`) with the comparison averaged over the other factor — in the table only.

Other settings: `posthoc_compare = 'auto'` (the default) compares just the first
factor (`supp` here); `posthoc_compare = 'none'` (or `''`) switches comparisons
off and draws the violins without brackets.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file         = os.path.join(options.demo_dir, 'data/toothgrowth.csv')  # input data file
options.out_dir         = 'results/demo_15_posthoc_compare'  # output folder
options.y               = 'len'             # dependent variable
options.y_units         = 'mm'             # unit label for y-axis
options.x               = 'supp, dose'      # fixed-effect factors
options.interaction     = 'supp, dose'      # test the supp × dose interaction
options.posthoc_compare = 'supp, dose'      # compare BOTH factors, each plotted as if first
options.rename          = 'len -> ToothLength; supp -> Supplement; dose -> Dose; supp: OJ -> orange_juice, VC -> vitamin_c'
options.x_order         = 'dose: low, medium, high'

kb = Kbstat(options)
kb.run_save()
