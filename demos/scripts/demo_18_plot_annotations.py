"""Demo 18 — Plot annotations: EMM reference lines and group sizes

Two options change nothing about the model and everything about how quickly the
figure can be read. Both are off by default, so a plot only carries the ink you
ask for.

`options.show_emm_lines` extends each group's estimated marginal mean across the
whole panel, in that group's own colour. The EMM is already marked by the white
dot, but reading one group's level against the *other* groups meant comparing dot
heights by eye across the panel; the line turns that into a direct read-off. In
the figure below the high-dose line clears the entire medium-dose violin under
ascorbic acid, while under orange juice the two overlap by a wide margin — the
interaction, visible without consulting a table. Each panel uses its own EMMs, so
the lines move between panels.

The option doubles as the line style: `True` gives the default dotted line, which
recedes behind the violins so a line crossing one cannot be mistaken for plotted
data, while `'-'`, `'--'`, `':'` and `'-.'` (or the names `'solid'`, `'dashed'`,
`'dotted'`, `'dashdot'`) pick one explicitly. Solid reads calmest and makes the
colours easiest to attribute, at the cost of looking more like content than like
a guide.

`options.show_group_size` labels each group with the number of observations
behind it, just above the violin (or above the CI bar in bar style). Useful
wherever the cells are unbalanced, or where outlier removal has thinned some
groups more than others — the count is the group's own, after any exclusions.
Note for bar plots: up to version 1.13.6 the counts were drawn there
unconditionally and were unavailable for violins; from 1.14.0 both styles need
this option set.

The significance brackets are stacked above the labels and keep a visible gap
from them, so switching the labels on pushes the brackets up rather than
colliding with them.

The model is the crossed two-way design of Demo 3, with the roles of the two
factors swapped so the ordered dose is on the x-axis and the supplement makes the
panels:

    len ~ dose * supp
"""

import os

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file         = os.path.join(options.demo_dir, 'data/toothgrowth.csv')
options.out_dir         = 'results/demo_18_plot_annotations'
options.y               = 'len'              # dependent variable
options.y_units         = 'mm'               # unit label for y-axis
options.x               = 'dose, supp'       # dose on the x-axis, supp as panels
options.interaction     = 'dose, supp'       # test the dose × supp interaction
options.x_order         = 'dose: low, medium, high'
options.rename          = 'len -> ToothLength; supp -> Supplement; dose -> Dose; supp: OJ -> orange_juice, VC -> vitamin_c'
options.show_emm_lines  = True                # EMM of each group across the panel; True = dotted
# options.show_emm_lines = '--'               # or pick a style: '-', '--', ':', '-.'
options.show_group_size = True                # 'n=10' above each group

kb = Kbstat(options)
kb.run_save()
