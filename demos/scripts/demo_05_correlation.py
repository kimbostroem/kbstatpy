"""Demo 5 — Standalone pairwise correlation analysis

This demo uses the `longley` dataset (R base; Longley 1967), a classic
econometrics benchmark built specifically to be severely multicollinear: it holds
16 annual US macroeconomic observations from 1947–1962 in which GNP, population,
and the calendar year all trend together. It asks how strongly these variables
covary.

No model is fitted — the analysis is purely exploratory. Alongside ordinary
Pearson correlations it computes partial correlations (the association between two
variables after regressing out all the others), which separate direct
relationships from shared trends. The `constraints = 'Year > 1950'` filter
restricts the analysis to the post-war growth period, illustrating row filtering.
"""

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file     = '../data/longley.csv'                   # input data file
options.out_dir     = 'results/demo_05_correlation'        # output folder
options.correlation  = 'GNP.deflator, GNP, Unemployed, Population, Year'         # variables to correlate (must be numerical)
options.constraints  = 'Year > 1950'                                              # restrict to post-war growth period (1951–1962)
options.rename       = 'GNP.deflator -> GNP_Deflator; Unemployed -> Unemployment'

kb = Kbstat(options)
kb.run()
kb.save()
