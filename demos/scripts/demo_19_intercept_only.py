"""Demo 19 — Intercept-only models: the mean, the one-sample t-test and the ICC

The simplest model has no predictor at all: every value is one common number
plus a deviation,

    Reaction ~ 1                      y = b0 + e

and its only coefficient, b0, is the mean. Testing it against a reference value
(options.test_value) is the one-sample t-test. This demo uses the two baseline
days of the `sleepstudy` data (lme4; Belenky et al. 2003): 18 subjects, reaction
time measured twice each before the sleep restriction started, and asks whether
the mean baseline reaction time differs from 250 ms.

The first model treats the 36 rows as 36 independent observations. They are
not: they are 18 persons measured twice, and two values of the same person are
more alike than two values of different persons. The second model says so with
a random intercept per subject,

    Reaction ~ 1 + (1 | Subject)      y = b0 + u_subject + e

The mean is the same, but the test now counts 18 subjects instead of 36 rows,
so the CI widens and the p-value grows: the first model's df were inflated by
pseudo-replication. The same model splits the variance into the part between
subjects and the part within them, and Summary.txt reports their ratio, the ICC:
here the test-retest reliability of a single baseline measurement.
"""

import os

from kbstatpy import Kbstat, KbstatOptions


def options(out_dir, id_var):
    o = KbstatOptions()
    o.in_file     = os.path.join(o.demo_dir, 'data/sleepstudy.csv')   # input data file
    o.out_dir     = out_dir                       # output folder
    o.constraints = 'Days <= 1'                   # the two baseline days only
    o.y           = 'Reaction'                    # dependent variable
    o.y_units     = 'ms'                          # unit label for y-axis
    o.x           = ''                            # no factor: the intercept-only model, y ~ 1
    o.id          = id_var                        # '' = no random effect
    o.test_value  = 250                           # test the mean against 250 ms
    return o


# 1. Every row counted as independent: the one-sample t-test, t(35).
# options.formula = 'Reaction ~ 1'               # alternative: Wilkinson formula
Kbstat(options('results/demo_19_intercept_only/one_sample', '')).run_save()

# 2. A random intercept per subject: t(17), and the ICC in Summary.txt.
# options.formula = 'Reaction ~ 1 + (1 | Subject)'
Kbstat(options('results/demo_19_intercept_only/random_intercept', 'Subject')).run_save()
