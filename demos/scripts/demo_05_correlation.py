"""Demo 5: Standalone pairwise correlation analysis.

Computes Pearson correlations for all pairs of selected variables and displays
a scatter plot grid. No model is fitted — this is purely exploratory.

The Longley dataset is a classic econometrics dataset specifically designed to
demonstrate high multicollinearity. Five macroeconomic variables from 1947–1962
are selected here; their pairwise correlations are expected to be very high,
reflecting that GNP, population, and year all trend together over time.

options.constraints filters rows before the analysis — here restricted to the
post-war growth period (Year > 1950). Python comparison operators apply:
== != < > <= >= and & or | for combining conditions.

Model: none — pairwise correlation only (no model fitted)

Dataset: longley (R base / Longley, 1967). 16 annual observations, 7 variables.
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
