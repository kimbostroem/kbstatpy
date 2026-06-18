"""Demo 6 — LMM with random intercepts and random slopes

This demo uses the `sleepstudy` dataset (lme4; Belenky et al. 2003), reaction
times measured on 18 subjects across a period of sleep deprivation (here
contrasting a rested block with a deprived one). It asks not just whether
deprivation slows reactions on average, but whether subjects differ in how
strongly it affects them.

Allowing each subject their own slope as well as their own intercept gives:

    Reaction ~ Period + (1 + Period | Subject)

This has no classical equivalent — repeated-measures ANOVA assumes a single shared
time effect. The random-effects table now carries an additional slope variance and
an intercept–slope correlation.
"""

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = '../data/sleepstudy.csv'               # input data file
options.out_dir      = 'results/demo_06_lmm_slopes'        # output folder
options.y            = 'Reaction'        # dependent variable
options.y_units      = 'ms'             # unit label for y-axis
options.x            = 'Period'          # fixed-effect factor(s)
options.id           = 'Subject'         # random-effect grouping variable (subject ID)
options.slope        = 'Period'          # random slope(s): each subject gets their own Period slope
options.rename       = 'Reaction -> ReactionTime; Period -> Day'
# options.formula    = 'Reaction ~ Period + (1 + Period | Subject)'  # alternative: Wilkinson formula (overrides y, x, id, slope above)

kb = Kbstat(options)
kb.run_save()

