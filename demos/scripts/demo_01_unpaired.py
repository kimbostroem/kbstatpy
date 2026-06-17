"""Demo 1 — Unpaired t-test equivalent

This demo uses the classic `sleep` dataset (R base; Cushny & Peebles 1905, later
made famous by Student 1908), which records the extra hours of sleep gained by 10
patients under two different soporific drugs. Treating the two drug groups as
independent, it asks whether the average sleep gain differs between them.

The model is a plain linear model with no random effects:

    extra ~ group

With a two-level factor and effects coding this is algebraically identical to an
independent-samples (Student) t-test — the ANOVA F equals t², the degrees of
freedom are n − 2, and the p-value matches exactly — so it reproduces the
classical result while using the same machinery as every other demo.
"""

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file      = '../data/sleep.csv'                    # input data file
options.out_dir      = 'results/demo_01_unpaired'          # output folder
options.y            = 'extra'           # dependent variable
options.y_units      = 'h'              # unit label for y-axis
options.x            = 'group'           # fixed-effect factor(s)
options.rename       = 'extra -> ExtraSleep; group -> DrugGroup'
# options.formula    = 'extra ~ group'   # alternative: Wilkinson formula (overrides y, x, id above)

kb = Kbstat(options)
kb.run()
kb.save()

