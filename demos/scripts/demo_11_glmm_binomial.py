"""Demo 11 — GLMM with binomial distribution

This demo uses the `bacteria` dataset (MASS), which tracks the presence or absence
of H. influenzae in 50 children with otitis media, measured at five time points
(weeks 0, 2, 4, 6, 11) under three treatments (placebo, drug, drug+) — 220
observations in all. It asks whether treatment and time affect the probability
that bacteria are still present.

The outcome is binary, so its mean is a probability bounded between 0 and 1 and a
gaussian model is invalid. A binomial GLMM with a logit link, plus a random
intercept per child for the repeated measures, models it correctly:

    present ~ trt + week + (1 | ID)

The log-odds are estimated on the logit scale and the estimated marginal means are
back-transformed to probabilities — exactly the kind of binary outcome that
classical t-tests and ANOVA cannot handle at all.
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
