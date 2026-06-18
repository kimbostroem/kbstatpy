"""Demo 4 — One-way repeated-measures ANOVA (LMM)

A within-subject factor handled by a random intercept reproduces the one-way
repeated-measures ANOVA. This demo shows that on the `ergoStool` dataset (nlme;
Wretenberg, Arborelius & Lindberg 1993): 9 subjects each rate the perceived
effort (Borg scale) of rising from four stool types — one rating per subject per
stool, balanced and unreplicated.

A random intercept per subject captures individual baseline differences:

    effort ~ Type + (1 | Subject)

Because the design is balanced and the four stools have no natural ordering, this
is an exact one-way repeated-measures ANOVA: the Type III F-test matches
`aov(effort ~ Type + Error(Subject/Type))`, the random intercept reproducing the
compound-symmetry covariance RM-ANOVA assumes. A four-level within-subject factor
is also a more honest RM-ANOVA than a two-level one, which would merely be the
paired t-test of demo 2.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = os.path.join(options.demo_dir, 'data/ergostool.csv')               # input data file
options.out_dir      = 'results/demo_04_lmm'              # output folder
options.y            = 'effort'          # dependent variable
options.y_units      = 'Borg'           # unit label for y-axis
options.x            = 'Type'            # fixed-effect factor(s)
options.id           = 'Subject'         # random-effect grouping variable (subject ID)
options.rename       = 'effort -> Effort; Type -> Stool type'
# options.formula    = 'effort ~ Type + (1 | Subject)'  # alternative: Wilkinson formula (overrides y, x, id above)

kb = Kbstat(options)
kb.run_save()

