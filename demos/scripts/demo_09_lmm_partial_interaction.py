"""Demo 9: LMM with a partial interaction (three fixed-effect factors, one interaction).

Three binary treatment factors applied to pea plots: nitrogen (N), phosphate (P),
and potassium (K). Plots are grouped in 6 blocks — a random intercept per block
accounts for spatial variation.

The model tests the main effect of N and the P×K interaction separately, without
assuming that N interacts with either:

    yield ~ N + P*K + (1 | block)

This contrasts with demo 7 (oats), where all pairwise terms from a two-factor
interaction were of interest. Here only one of the three possible interactions is
hypothesised, illustrating the `interaction` option with three fixed-effect factors.

Dataset: npk (R base). Nitrogen, phosphate and potassium effects on pea yield
(pounds per plot). 24 plots in 6 complete blocks (Venables & Ripley, 2002).
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
kb.run()

# run() is equivalent to calling the following steps individually:
# kb.fit()               # fit the model
# kb.anova()             # compute Type III ANOVA table
# kb.posthoc()           # pairwise post-hoc comparisons
# kb.plot_diagnostics()  # show diagnostic plots (saved to out_dir when save() is called)
# kb.plot_data()         # show data plot (saved to out_dir when save() is called)
# kb.save()              # save all result tables, figures, and Summary.txt to out_dir
