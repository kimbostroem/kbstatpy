"""Demo 16 — Level-wise profile analysis (profile_across)

When one factor is an ordered series of levels, the interesting question is often
not "is there an effect at some level?" but "how does another factor's effect
change *across* the ordered levels?" — the pattern is the finding. This demo shows
that on the `ToothGrowth` dataset (R base): odontoblast length of 60 guinea pigs
given vitamin C as orange juice (`OJ`) or ascorbic acid (`VC`) at three ordered
doses (low, medium, high).

The model is the same crossed two-way as Demo 3:

    len ~ supp * dose

Setting `profile_across = 'dose'` adds a level-wise profile of the *supp* effect
across the ordered dose levels:

  Layer 1 (per level) — the OJ-vs-VC contrast computed within each dose level.
  Layer 2 (trend)     — the supp x dose interaction as a focused 1-df LINEAR TREND
                        across the ordered dose positions, reported next to the
                        factor-omnibus supp:dose already in the ANOVA.

The classic ToothGrowth finding falls straight out: OJ's advantage over VC is
large at low and medium dose but vanishes at high dose — a monotone attenuation
that the linear trend captures directly. `x_order` fixes the dose ordering so the
trend runs low -> medium -> high; the profile plot (LevelProfile.png) shows both
supp curves across dose, and LevelProfile.xlsx holds the per-level and trend tables.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file        = os.path.join(options.demo_dir, 'data/toothgrowth.csv')  # input data file
options.out_dir        = 'results/demo_16_profile'      # output folder
options.y              = 'len'            # dependent variable
options.y_units        = 'mm'             # unit label for y-axis
options.x              = 'supp, dose'     # fixed-effect factors
options.interaction    = 'supp, dose'     # supp × dose interaction (needed for a non-flat profile)
options.x_order        = 'dose: low, medium, high'   # meaningful order for the trend
options.profile_across = 'dose'           # level-wise profile of supp across the dose levels

kb = Kbstat(options)
kb.run_save()
