"""Demo 11: Generalised linear mixed model (GLMM) with binomial distribution.

Binary outcome (bacteria present / absent), repeated measures per child.
Treatment (placebo / drug / drug+) and week are fixed-effect factors;
random intercept per child accounts for the within-subject correlation.

A gaussian model cannot be used here: the outcome is binary (0/1), so the
mean is a probability bounded between 0 and 1. A binomial GLMM with logit
link models this correctly without any transformation.

Dataset: bacteria (MASS). Presence/absence of H. influenzae bacteria in
children with otitis media, under three treatments across five time points
(weeks 0, 2, 4, 6, 11). 50 children, 220 observations total.
"""

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = '../data/bacteria.csv'
options.out_dir      = 'results/demo_11_glmm_binomial'
options.y            = 'present'                   # binary outcome: 1 = bacteria present
options.x            = 'trt, week'                 # fixed-effect factors
options.id           = 'ID'                        # random intercept per child
options.distribution = 'binomial'                  # binary outcome
options.link         = 'logit'                     # logit link: maps linear predictor to probability
options.rename       = 'present -> Bacteria present; trt -> Treatment; week -> Week'

kb = Kbstat(options)
kb.run()
