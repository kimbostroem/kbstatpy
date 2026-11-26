#!/usr/bin/env python3
"""Demo 21 — Curves: an ANOVA at every point (`curve`, SPM1D-style)

Many outcomes are curves rather than single numbers: a knee angle over the gait
cycle, a force over stance, a temperature over the year. `options.curve` fits
the model at every point of the curve, tests each model term with an F curve
and each pairwise comparison with a t curve, and sets one threshold for the
whole curve. This is Statistical Parametric Mapping in one dimension (SPM1D;
Pataky 2016), with kbstatpy's models at each point, so mixed models, repeated
trials and unbalanced designs work too.

The data are `CanadianWeather` (fda; Ramsay & Silverman 2005): the daily mean
temperature, averaged over 1960-1994, at 35 weather stations in four climate
regions. The file has one row per station and one column per day, day_1 to
day_365, so the curve is given as a range of columns:

    curve = 'Day = (day_1 : day_365)'

The columns are stacked into a column Day, whose values are the numbers the
column names end with (1 ... 365; names without numbers would give 0 to 100 %).
At every day the model is the one-way ANOVA

    Temperature ~ Region

Testing 365 days at alpha = 0.05 each would find "differences" on some days by
chance alone. Random field theory uses the smoothness of the residual curves
(FWHM, Summary.txt) to set a threshold so that, if the regions did not differ,
the F curve would exceed it anywhere only with probability 0.05. A stretch above
the threshold is a cluster, reported with its days, its peak and its p. The six
pairwise comparisons are t curves, each tested at the Sidak level 0.0085, so the
six together keep 0.05.

Result: the F curve exceeds its threshold (F = 7.2) on every day of the year,
so the regions differ all year round. The comparisons say how:

- Atlantic stations are warmer than Arctic ones all year, and the Pacific ones
  are warmer than the Arctic ones except around midsummer.
- Pacific stations are warmer than Continental ones in winter only (to day 94
  and from day 306); in summer the two do not differ. Atlantic stations are
  warmer than Continental ones in winter too, mainly from November to January.
- Continental stations are warmer than Arctic ones from spring to autumn (about
  days 54 to 311), not in midwinter, when both are very cold.
- Atlantic and Pacific stations hardly differ: only a few days in February.

Several comparisons break into many short clusters. The daily means still carry
day-to-day weather, so a t curve that hovers near its threshold crosses it many
times. The long clusters carry the result; CurveMeans.png marks all of them.
"""

import os

from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file  = os.path.join(options.demo_dir, 'data/canadian_weather.csv')  # one row per station
options.out_dir  = 'results/demo_21_curves'     # output folder
options.y        = 'Temperature'                # name for the stacked values
options.y_units  = '°C'
options.x        = 'Region'
options.x_order  = {'Region': ['Atlantic', 'Continental', 'Pacific', 'Arctic']}
options.curve    = 'Day = (day_1 : day_365)'    # wide columns: one per day

kb = Kbstat(options)
kb.run_save()
