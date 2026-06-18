"""Demo 10 — Outlier removal (before and after fitting)

This demo uses the `stackloss` dataset (R base; Brownlee 1965), which records the
percentage of ammonia lost during an industrial oxidation process over 21 plant
runs; observations 1, 3, 4, and 21 are textbook influential outliers used
throughout the robust-regression literature. It asks how much those points sway
the conclusions.

The same linear model is fitted twice — once untouched, once after pre-fit IQR and
post-fit residual outlier removal:

    stack.loss ~ Air.Flow + Water.Temp + Acid.Conc.

Air.Flow is binned into three operating regimes for the plot, while Water.Temp and
Acid.Conc. enter as numeric covariates. Comparing the two runs shows how
kbstatpy's two-pass, principled outlier handling shifts the estimates, while
keeping the excluded points visible and the analysis valid under the resulting
imbalance.
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
kb_default.run_save()

print("\n=== Run 2: pre-fit IQR + post-fit residual removal ===")
kb_clean = Kbstat(make_options('results/demo_10_outliers/clean',
                               remove_pre=True, remove_post=True))
kb_clean.run_save()
