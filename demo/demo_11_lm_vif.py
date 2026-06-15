"""Demo 11: Linear model with mixed numeric/categorical predictors and automatic VIF.

When options.x contains numerical variables, kbstat automatically computes VIF
(Variance Inflation Factor) to check for multicollinearity among the numeric
predictors. VIF thresholds: < 5 OK, 5–10 concerning, > 10 severe (Cohen, 1988).

Setting options.correlation = options.x produces a pairwise scatter plot grid
for the predictors; numeric predictors also show their VIF on the diagonal.

Here fuel efficiency (mpg) is modelled from two numeric predictors — power (hp)
and weight (wt) — and one categorical predictor — number of cylinders (cyl).
The categorical predictor appears in the violin plot; the numeric predictors
are checked for multicollinearity via VIF and visualised in the correlation plot.

Dataset: mtcars (R base / Henderson & Velleman, 1981). 32 car models, 11 variables.
"""

import sys, os
DEMO_DIR = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(DEMO_DIR, '..'))

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file     = os.path.join(DEMO_DIR, 'data', 'mtcars.csv')          # input data file
options.out_dir     = os.path.join(DEMO_DIR, 'results', 'demo_11_lm_vif')   # output folder
options.y           = 'mpg'              # dependent variable
options.y_units     = 'mpg'             # unit label for y-axis
options.x           = 'cyl'             # categorical predictor — shown in violin plot
options.covariate   = 'hp, wt'          # continuous covariates — included in model, excluded from plots
options.correlation = 'hp, wt'          # correlate the numeric covariates — VIF computed automatically

kb = Kbstat(options)
kb.run()
