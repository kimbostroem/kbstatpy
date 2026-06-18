"""Demo 13 — LM with mixed predictors and VIF

Strongly correlated predictors inflate standard errors and destabilise
coefficients; the Variance Inflation Factor flags this before it bites. This demo
shows that on the `mtcars` dataset (R base; Henderson & Velleman 1981),
performance figures for 32 car models: fuel economy (`mpg`) modelled from engine
power (`hp`) and weight (`wt`) — two strongly correlated predictors — plus the
number of cylinders (`cyl`) as a categorical factor.

The fitted model combines the categorical and numeric predictors:

    mpg ~ cyl + hp + wt

Because `options.x` contains numeric predictors, kbstatpy automatically reports
their Variance Inflation Factors (thresholds: < 5 OK, 5–10 concerning, > 10
severe), flagging the collinearity between power and weight that would otherwise
inflate standard errors and destabilise the coefficients. A correlation scatter
grid with VIF on the diagonal visualises it.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

HERE = os.path.dirname(os.path.abspath(__file__))

options = KbstatOptions()
options.in_file     = os.path.join(HERE, '../data/mtcars.csv')                    # input data file
options.out_dir     = os.path.join(HERE, 'results/demo_13_lm_vif')             # output folder
options.y           = 'mpg'              # dependent variable
options.y_units     = 'mpg'             # unit label for y-axis
options.x           = 'cyl'             # categorical predictor — shown in violin plot
options.rename      = 'mpg -> Consumption; cyl -> Cylinders; hp -> Horsepower; wt -> Weight'
options.x_order     = 'cyl: 4, 6, 8'                               # ascending order
options.covariate   = 'hp, wt'          # continuous covariates — included in model, excluded from plots
options.correlation = 'hp, wt'          # correlate the numeric covariates — VIF computed automatically

kb = Kbstat(options)
kb.run_save()
