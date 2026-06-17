"""Demo 4 — One-way repeated-measures ANOVA (LMM)

This demo uses the `ergoStool` dataset (nlme; Wretenberg, Arborelius & Lindberg
1993), in which 9 subjects each rated the perceived effort (on the Borg scale) of
rising from four different stool types — one rating per subject per stool, a
balanced design with no replication. It asks whether the stool type affects the
effort required.

A random intercept per subject captures individual baseline differences:

    effort ~ Type + (1 | Subject)

Because the design is balanced and the four stools have no natural ordering, this
is an exact one-way repeated-measures ANOVA: the Type III F-test matches
`aov(effort ~ Type + Error(Subject/Type))`, with the random intercept reproducing
the compound-symmetry covariance that RM-ANOVA assumes. A four-level
within-subject factor is also a more honest RM-ANOVA than a two-level one, which
would merely be the paired t-test of demo 2.
"""

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = '../data/ergostool.csv'               # input data file
options.out_dir      = 'results/demo_04_lmm'              # output folder
options.y            = 'effort'          # dependent variable
options.y_units      = 'Borg'           # unit label for y-axis
options.x            = 'Type'            # fixed-effect factor(s)
options.id           = 'Subject'         # random-effect grouping variable (subject ID)
options.rename       = 'effort -> Effort; Type -> Stool type'
# options.formula    = 'effort ~ Type + (1 | Subject)'  # alternative: Wilkinson formula (overrides y, x, id above)

kb = Kbstat(options)
kb.run()

# run() is equivalent to calling the following steps individually:
# kb.fit()               # fit the model
# kb.anova()             # compute Type III ANOVA table
# kb.posthoc()           # pairwise post-hoc comparisons
# kb.plot_diagnostics()  # show diagnostic plots (saved to out_dir when save() is called)
# kb.plot_data()         # show data plot (saved to out_dir when save() is called)
# kb.save()              # save all result tables, figures, and Summary.txt to out_dir
