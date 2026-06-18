"""Demo 11 — GLMM with binomial distribution

A binary outcome has a mean that is a probability bounded between 0 and 1, so a
gaussian model is invalid — a binomial GLMM with a logit link is the right tool.
This demo shows that on the `bacteria` dataset (MASS): presence or absence of
H. influenzae in 50 children with otitis media, measured at five time points
(weeks 0, 2, 4, 6, 11) under three treatments (placebo, drug, drug+) — 220
observations in all.

With a random intercept per child for the repeated measures:

    present ~ trt + week + (1 | ID)

The log-odds are estimated on the logit scale and the estimated marginal means are
back-transformed to probabilities — exactly the kind of binary outcome that
classical t-tests and ANOVA cannot handle at all.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

HERE = os.path.dirname(os.path.abspath(__file__))

options = KbstatOptions()
options.in_file      = os.path.join(HERE, '../data/bacteria.csv')
options.out_dir      = os.path.join(HERE, 'results/demo_11_glmm_binomial')
options.y            = 'present'                   # binary outcome: 1 = bacteria present
options.x            = 'trt, week'                 # fixed-effect factors
options.id           = 'ID'                        # random intercept per child
options.distribution = 'binomial'                  # binary outcome
options.link         = 'logit'                     # logit link: maps linear predictor to probability
options.rename       = 'present -> Bacteria present; trt -> Treatment; week -> Week'

kb = Kbstat(options)
kb.run_save()
