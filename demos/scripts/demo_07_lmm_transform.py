"""Demo 7 — LMM with log-transformed dependent variable

Strictly positive, right-skewed outcomes strain the constant-variance assumption
of an ordinary linear model; one remedy is to model them on the log scale. This
demo shows that on the `sleepstudy` dataset (lme4) — the same reaction-time data
as demo 6, which is positive and right-skewed.

The response is modelled on the log scale:

    log(Reaction) ~ Period + (1 | Subject)

The model is fitted in log space and the estimated marginal means, confidence
intervals, and pairwise differences are back-transformed to milliseconds
automatically. Note that the back-transformed mean is a geometric mean
(median-like), which contrasts instructively with the gamma GLMM of demo 8.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

HERE = os.path.dirname(os.path.abspath(__file__))

options = KbstatOptions()
options.in_file      = os.path.join(HERE, '../data/sleepstudy.csv')               # input data file
options.out_dir      = os.path.join(HERE, 'results/demo_07_lmm_transform')     # output folder
options.y            = 'Reaction'        # dependent variable
options.y_units      = 'ms'             # unit label for y-axis
options.y_transform  = 'log(y)'         # log-transform before fitting; back-transformed for plots and tables
options.x            = 'Period'          # fixed-effect factor(s)
options.id           = 'Subject'         # random-effect grouping variable (subject ID)
options.rename       = 'Reaction -> ReactionTime; Period -> Day'
# options.formula    = 'log(Reaction) ~ Period + (1 | Subject)'  # alternative: Wilkinson formula (overrides y, x, id above)

kb = Kbstat(options)
kb.run_save()

