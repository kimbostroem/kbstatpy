"""Demo 7 — LMM with log-transformed dependent variable

This demo uses the `sleepstudy` dataset (lme4), the same reaction-time data as
demo 6. Reaction times are strictly positive and right-skewed, which strains the
constant-variance assumption of an ordinary linear model, so the response is
modelled on the log scale instead.

    log(Reaction) ~ Period + (1 | Subject)

The model is fitted in log space and the estimated marginal means, confidence
intervals, and pairwise differences are back-transformed to milliseconds
automatically. Note that the back-transformed mean is a geometric mean
(median-like), which contrasts instructively with the gamma GLMM of demo 8.
"""

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = '../data/sleepstudy.csv'               # input data file
options.out_dir      = 'results/demo_07_lmm_transform'     # output folder
options.y            = 'Reaction'        # dependent variable
options.y_units      = 'ms'             # unit label for y-axis
options.y_transform  = 'log(y)'         # log-transform before fitting; back-transformed for plots and tables
options.x            = 'Period'          # fixed-effect factor(s)
options.id           = 'Subject'         # random-effect grouping variable (subject ID)
options.rename       = 'Reaction -> ReactionTime; Period -> Day'
# options.formula    = 'log(Reaction) ~ Period + (1 | Subject)'  # alternative: Wilkinson formula (overrides y, x, id above)

kb = Kbstat(options)
kb.run()

# run() is equivalent to calling the following steps individually:
# kb.fit()               # fit the model
# kb.anova()             # compute Type III ANOVA table
# kb.posthoc()           # pairwise post-hoc comparisons
# kb.plot_diagnostics()  # show diagnostic plots (saved to out_dir when save() is called)
# kb.plot_data()         # show data plot (saved to out_dir when save() is called)
# kb.save()              # save all result tables, figures, and Summary.txt to out_dir
