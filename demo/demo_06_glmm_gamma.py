"""Demo 6: Generalised linear mixed model (GLMM) with gamma distribution.

Two crossed fixed-effect factors (Variety × Nitrogen), random intercept per
block. Oat yield is positive and right-skewed — gamma distribution with log
link is more appropriate than a normal LMM.

Dataset: Oats (nlme). Split-plot experiment on oat varieties and nitrogen
fertilisation (Yates, 1935). 3 varieties × 4 nitrogen levels × 6 blocks,
72 observations total.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file  = os.path.join(os.path.dirname(__file__), 'data', 'oats.csv')
options.out_dir  = os.path.join(os.path.dirname(__file__), 'results', 'demo_06_glmm_gamma')
options.formula  = 'yield ~ Variety * Nitrogen + (1 | Block)'
options.y        = 'yield'
options.x        = ['Variety', 'Nitrogen']
options.id       = 'Block'
options.distribution = 'gamma'
options.link     = 'log'

kb = Kbstat(options)
kb.run()

# run() is equivalent to calling the following steps individually:
# kb.fit()               # fit the model
# kb.anova()             # compute Type III ANOVA table
# kb.posthoc()           # pairwise post-hoc comparisons
# kb.plot_diagnostics()  # show diagnostic plots (saved to out_dir when save() is called)
# kb.plot_data()         # show data plot (saved to out_dir when save() is called)
# kb.save()              # save all result tables, figures, and Summary.txt to out_dir
