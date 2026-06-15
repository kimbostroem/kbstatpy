"""Demo 4: Linear mixed model (LMM) with random intercepts.

One within-subject factor (Period: rested vs deprived), random intercept per
subject to account for individual baseline differences in reaction time.

Dataset: sleepstudy (lme4). Reaction times (ms) of 18 subjects over 10 days of
sleep deprivation (Belenky et al., 2003). Days 0-4 are labelled 'rested',
days 5-9 are labelled 'deprived'.
"""

from init import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = 'data/sleepstudy.csv'               # input data file
options.out_dir      = 'results/demo_04_lmm'               # output folder
options.y            = 'Reaction'        # dependent variable
options.y_units      = 'ms'             # unit label for y-axis
options.x            = 'Period'          # fixed-effect factor(s)
options.id           = 'Subject'         # random-effect grouping variable (subject ID)
# options.formula    = 'Reaction ~ Period + (1 | Subject)'  # alternative: Wilkinson formula (overrides y, x, id above)

kb = Kbstat(options)
kb.run()

# run() is equivalent to calling the following steps individually:
# kb.fit()               # fit the model
# kb.anova()             # compute Type III ANOVA table
# kb.posthoc()           # pairwise post-hoc comparisons
# kb.plot_diagnostics()  # show diagnostic plots (saved to out_dir when save() is called)
# kb.plot_data()         # show data plot (saved to out_dir when save() is called)
# kb.save()              # save all result tables, figures, and Summary.txt to out_dir
