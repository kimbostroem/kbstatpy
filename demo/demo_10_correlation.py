"""Demo 10: Standalone pairwise correlation analysis.

Computes Pearson correlations for all pairs of selected variables and displays
a scatter plot grid. No model is fitted — this is purely exploratory.

The Longley dataset is a classic econometrics dataset specifically designed to
demonstrate high multicollinearity. Five macroeconomic variables from 1947–1962
are selected here; their pairwise correlations are expected to be very high,
reflecting that GNP, population, and year all trend together over time.

Dataset: longley (R base / Longley, 1967). 16 annual observations, 7 variables.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file     = 'data/longley.csv'                   # input data file
options.out_dir     = 'results/demo_10_correlation'        # output folder
options.correlation = 'GNP.deflator, GNP, Unemployed, Population, Year'         # variables to correlate (must be numerical)
options.rename      = 'GNP.deflator -> GNP_Deflator; Unemployed -> Unemployment'

kb = Kbstat(options)
kb.run()
