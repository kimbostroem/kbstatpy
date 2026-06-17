"""Demo 10: Outlier removal before and after fitting.

The stackloss dataset (Brownlee, 1965) records the percentage of ammonia
lost (stack.loss) during an industrial oxidation process across 21 plant
runs. Observations 1, 3, 4, and 21 are well-documented influential outliers
widely used as a benchmark in robust regression literature.

This demo runs the same linear model twice to show the effect of outlier
removal on the estimated marginal means and significance:

  run_default:  no outlier removal (standard LM)
  run_clean:    pre-fit IQR removal + post-fit residual removal, then refit

The x-axis factor is Air.Flow binned into three operating regimes so that
the violin / data plot is meaningful. The numeric covariates Water.Temp and
Acid.Conc are included in the model.

Model: `stack.loss ~ Air.Flow + Water.Temp + Acid.Conc.` (fit with and without outlier removal)

Dataset: stackloss (R base / Brownlee, 1965). 21 observations, 4 variables.
"""

from kbstatpy import Kbstat, KbstatOptions

def make_options(out_dir, remove_pre=False, remove_post=False):
    options = KbstatOptions()
    options.in_file     = '../data/stackloss.csv'
    options.out_dir     = out_dir
    options.y           = 'stack.loss'
    options.y_units     = '%'
    options.x           = 'Air.Flow'
    options.covariate   = 'Water.Temp, Acid.Conc.'
    options.rename      = ('stack.loss -> StackLoss; '
                           'Air.Flow -> AirFlow; '
                           'Water.Temp -> WaterTemp; '
                           'Acid.Conc. -> AcidConc')
    options.remove_outliers_prefit  = remove_pre
    options.remove_outliers_postfit = remove_post
    return options

print("=== Run 1: no outlier removal ===")
kb_default = Kbstat(make_options('results/demo_10_outliers/default'))
kb_default.run()

print("\n=== Run 2: pre-fit IQR + post-fit residual removal ===")
kb_clean = Kbstat(make_options('results/demo_10_outliers/clean',
                               remove_pre=True, remove_post=True))
kb_clean.run()
