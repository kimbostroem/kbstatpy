"""Demo 5 — Standalone pairwise correlation analysis

When several variables all trend together, raw correlations cannot separate direct
association from shared drift — partial correlations can. This demo shows that on
the `longley` dataset (R base; Longley 1967), a classic econometrics benchmark
built to be severely multicollinear: 16 annual US macroeconomic observations
(1947–1962) in which GNP, population, and the calendar year all move together.

No model is fitted — the analysis is purely exploratory. Alongside ordinary
Pearson correlations it computes partial correlations (the association between two
variables after regressing out all the others), separating direct relationships
from shared trends. The `constraints = 'Year > 1950'` filter restricts the
analysis to the post-war growth period, illustrating row filtering.

Reading the two tables together
-------------------------------
It is the *difference* between the raw and partial tables that carries the
message.

  * A high raw correlation that collapses in the partial means the pair is
    largely explained by the other variables. That is what Longley is built to
    show: GNP, population and the calendar year all rise together, so almost any
    two of them correlate near 1.0 while little survives once the rest are held
    fixed. A whole block behaving this way indicates the variables track one
    underlying quantity rather than several distinct ones.
  * A partial that stays high means the pair shares something the other
    variables do not capture — the association worth a second look.
  * A low raw correlation that grows in the partial means the others were
    masking, i.e. suppressing, it.

What conditioning can and cannot tell you
-----------------------------------------
Partial correlation removes whatever is *linearly predictable* from the
conditioning set; it has no notion of cause. The same arithmetic therefore
removes a spurious association when the conditioned variable is a common cause
(confounder), CREATES one when it is a common effect (collider, i.e. both X and Y
influence it), and erases a real effect when it is a mediator on X -> M -> Y.
Longley is the benign case, since calendar time plausibly drives every series.
Note that confounder and mediator give the *same* signature (high raw, near-zero
partial) with opposite meanings, and no amount of data distinguishes them. With
the conditioning set being simply all remaining variables, read the partials as a
statement about redundancy within the variable set, not about mechanism.

See STATISTICAL_NOTES.md, 'Pearson and partial correlation', for the full
treatment.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file     = os.path.join(options.demo_dir, 'data/longley.csv')                   # input data file
options.out_dir     = 'results/demo_05_correlation'        # output folder
options.correlation  = 'GNP.deflator, GNP, Unemployed, Population, Year'         # variables to correlate (must be numerical)
options.constraints  = 'Year > 1950'                                              # restrict to post-war growth period (1951–1962)
options.rename       = 'GNP.deflator -> GNP_Deflator; Unemployed -> Unemployment'

kb = Kbstat(options)
kb.run_save()
