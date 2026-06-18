"""Demo 9 — LMM with partial interaction

With three or more factors you often want to test one specific interaction without
assuming the others — a partial interaction. This demo shows that on the `npk`
dataset (R base; Venables & Ripley 2002), a classic agricultural experiment: pea
yield under three binary treatments — nitrogen (N), phosphate (P), potassium (K) —
across six complete blocks (24 plots).

Only the one hypothesised interaction is included:

    yield ~ N + P*K + (1 | block)

Where classical two-way ANOVA tests all pairwise interactions at once, this fits
just the theoretically motivated P×K term, keeping the model parsimonious and
preserving degrees of freedom. A random intercept per block accounts for spatial
variation across the field.
"""

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = '../data/npk.csv'                      # input data file
options.out_dir      = 'results/demo_09_lmm_partial_interaction'  # output folder
options.y            = 'yield'           # dependent variable
options.y_units      = 'lb/plot'        # unit label for y-axis
options.x            = 'N, P, K'         # fixed-effect factors (three binary treatments)
options.id           = 'block'           # random-effect grouping variable (spatial block)
options.interaction  = 'P, K'            # test only the P×K interaction (not N×P or N×K)
options.rename       = ('yield -> CropYield; N -> Nitrogen; P -> Phosphate; K -> Potassium; block -> Block; '
                        'N: 0 -> absent, 1 -> applied; P: 0 -> absent, 1 -> applied; K: 0 -> absent, 1 -> applied')
options.x_order      = 'Nitrogen: absent, applied; Phosphate: absent, applied; Potassium: absent, applied'
# options.formula    = 'yield ~ N + P*K + (1 | block)'  # alternative: Wilkinson formula (overrides y, x, id, interaction above)

kb = Kbstat(options)
kb.run_save()

