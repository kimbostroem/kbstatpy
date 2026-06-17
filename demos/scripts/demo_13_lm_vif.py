"""Demo 13 — LM with mixed predictors and VIF

This demo uses the `mtcars` dataset (R base; Henderson & Velleman 1981),
performance figures for 32 car models. Fuel economy (`mpg`) is modelled from
engine power (`hp`) and weight (`wt`) — two strongly correlated predictors —
together with the number of cylinders (`cyl`) as a categorical factor.

The fitted model combines the categorical and numeric predictors:

    mpg ~ cyl + hp + wt

Because `options.x` contains numeric predictors, kbstatpy automatically reports
their Variance Inflation Factors (thresholds: < 5 OK, 5–10 concerning, > 10
severe), flagging the collinearity between power and weight that would otherwise
inflate standard errors and destabilise the coefficients. A correlation scatter
grid with VIF on the diagonal visualises it.
"""

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file     = '../data/mtcars.csv'                    # input data file
options.out_dir     = 'results/demo_13_lm_vif'             # output folder
options.y           = 'mpg'              # dependent variable
options.y_units     = 'mpg'             # unit label for y-axis
options.x           = 'cyl'             # categorical predictor — shown in violin plot
options.rename      = 'mpg -> Consumption; cyl -> Cylinders; hp -> Horsepower; wt -> Weight'
options.x_order     = 'cyl: 4, 6, 8'                               # ascending order
options.covariate   = 'hp, wt'          # continuous covariates — included in model, excluded from plots
options.correlation = 'hp, wt'          # correlate the numeric covariates — VIF computed automatically

kb = Kbstat(options)
kb.run()
kb.save()
