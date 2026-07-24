"""Demo 17 — Per-group dispersion for the glmmTMB families (dispersion / dispformula)

A Gamma (or inverse-Gaussian) GLM assumes a constant coefficient of variation: the
scatter scales with the mean through a single dispersion parameter. When groups
differ not only in level but in *relative* scatter, that one dispersion is a poor
compromise, and the standard errors (hence p-values and CIs) it produces are
mis-scaled.

`options.dispersion` sets the right-hand side of glmmTMB's `dispformula`, so the
dispersion may vary by a factor instead of the default constant `~ 1`. This demo
shows it on `ToothGrowth` (R base): odontoblast length of 60 guinea pigs given
vitamin C as orange juice (`OJ`) or ascorbic acid (`VC`) at three ordered doses
(low, medium, high). The doses differ markedly in relative scatter (coefficient of
variation about 0.42 at low dose but only about 0.15 at high dose), so a single
dispersion cannot fit all three well.

The model is the crossed two-way `len ~ supp * dose`, fitted twice:

  1. default, one constant dispersion  (dispformula = ~ 1)
  2. dispersion varying by dose         (dispersion = 'dose'  ->  dispformula = ~ dose)

The demo prints both models' AIC: letting the dispersion vary by dose lowers it by
roughly 14 here (a clearly better fit), and the group standard errors and
confidence intervals shift accordingly. The mean structure (and the reported EMMs)
is unchanged; only the dispersion model, and therefore the inference, differs.
`dispersion` is ignored for gaussian (LM/LMM) models, which estimate their own
residual variance.
"""

import os

from kbstatpy import Kbstat, KbstatOptions


def base_options():
    """The crossed two-way Gamma model shared by both fits."""
    o = KbstatOptions()
    o.in_file      = os.path.join(o.demo_dir, 'data/toothgrowth.csv')  # input data file
    o.y            = 'len'              # dependent variable
    o.y_units      = 'mm'              # unit label for y-axis
    o.x            = 'supp, dose'       # fixed-effect factors
    o.interaction  = 'supp, dose'       # supp × dose interaction
    o.x_order      = 'dose: low, medium, high'
    o.distribution = 'gamma'            # positive, right-skewed outcome
    o.link         = 'log'
    return o


# 1) Default: a single, constant dispersion (dispformula = ~ 1).
shared = base_options()
shared.out_dir = 'results/demo_17_dispersion/shared'
kb_shared = Kbstat(shared)
kb_shared.run_save()

# 2) Dispersion varying by dose (dispformula = ~ dose) — the better-fitting model.
by_dose = base_options()
by_dose.dispersion = 'dose'            # -> glmmTMB dispformula = ~ dose
by_dose.out_dir    = 'results/demo_17_dispersion/by_dose'
kb_by_dose = Kbstat(by_dose)
kb_by_dose.run_save()

# Fit comparison: allowing the dispersion to vary by dose fits clearly better.
aic_shared  = float(kb_shared.model.fit_stats['AIC'].iloc[0])
aic_by_dose = float(kb_by_dose.model.fit_stats['AIC'].iloc[0])
print(f'\nAIC  shared dispersion (~ 1)     : {aic_shared:.1f}')
print(f'AIC  dispersion by dose (~ dose) : {aic_by_dose:.1f}')
print(f'delta AIC (negative favours ~ dose): {aic_by_dose - aic_shared:+.1f}')
