"""Demo 1 — Unpaired t-test equivalent

The simplest equivalence: a linear model with a single two-level factor
reproduces the classical independent-samples t-test exactly. This demo shows that
on the classic `sleep` dataset (R base; Cushny & Peebles 1905, later made famous
by Student 1908) — the extra hours of sleep gained by 10 patients under two
soporific drugs, with the two groups treated as independent.

The model is a plain linear model with no random effects:

    extra ~ group

With effects coding the ANOVA F equals t², the degrees of freedom are n − 2, and
the p-value matches a Student t-test exactly — reproducing the classical result
with the same machinery as every other demo.
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
kb.run_save()

