#!/usr/bin/env python3
"""Post-hoc SMD is Cohen's d for any design, and the difference has a CI.

The guarded failure modes:

1. Every SMD was 2·|t|/sqrt(df), the t-to-d conversion for two independent
   groups of equal size. In a within-subject contrast df is about n - 1, so the
   SMD came out near twice d_z: on Student's sleep data 2.71, labelled "very
   large", where Cohen's d is 0.83 -- the same 0.83 the unpaired analysis of
   the same numbers gives. It went unnoticed because the number looked
   plausible for a strong paired effect and nothing compared it with the
   unpaired one. The ANOVA table carried the same number and no longer shows it.

2. The post-hoc table gave the CI of each mean but none of the difference, so a
   reader had to rebuild diff ± t·SE by hand, although STATISTICAL_NOTES said the
   table provided it.

Under a log or logit link the interval is of the ratio, which must be the
ratio of the back-transformed means.

Needs R.

Run:  python3 tests/test_posthoc_d_and_ci.py
"""
import contextlib
import io
import os
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

OUT = '/tmp/kbstatpy_posthoc_d_and_ci'
os.makedirs(OUT, exist_ok=True)
FAILED = []


def check(name, cond, detail=''):
    print(('PASS' if cond else 'FAIL'), name, detail)
    if not cond:
        FAILED.append(name)


def run(in_file, y, x, id_='', slope='', distribution='normal'):
    o = KbstatOptions()
    o.in_file = in_file
    o.out_dir = OUT
    o.y, o.x, o.id = y, x, id_
    if slope:
        o.slope = slope
    o.distribution = distribution
    o.figure_display = 'save_only'
    k = Kbstat(o)
    with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter('ignore')
        k.fit()
        k.anova()
        k.posthoc()
    return k


def ci_bounds(s):
    lo, hi = str(s).strip('()').split(',')
    return float(lo), float(hi)


SLEEP = os.path.join(KbstatOptions().demo_dir, 'data', 'sleep.csv')
sleep = pd.read_csv(SLEEP)
a = sleep.loc[sleep.group == 1, 'extra'].to_numpy()
b = sleep.loc[sleep.group == 2, 'extra'].to_numpy()
D_POOLED = abs(a.mean() - b.mean()) / np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)


def test_sleep():
    for label, id_ in (('unpaired', ''), ('paired', 'ID')):
        k = run(SLEEP, 'extra', 'group', id_)
        row = k.posthoc_table.iloc[0]
        smd = float(row['SMD'])
        check(f'sleep {label}: SMD is Cohen\'s d with the pooled SD',
              abs(smd - D_POOLED) < 1e-3, f'SMD={smd:.4f}, d={D_POOLED:.4f}')
        check(f'sleep {label}: labelled from d', row['effectSize'] == 'large',
              repr(row['effectSize']))
        check(f'sleep {label}: no SMD in the ANOVA table',
              'SMD' not in k.anova_table.columns)
        # diff ± t_0.975(df)·SE, with SE = diff / t.
        diff, t, df = float(row['diff']), float(row['t']), float(row['df'])
        half = stats.t.ppf(0.975, df) * abs(diff / t)
        lo, hi = ci_bounds(row.get('diffCI', '(nan, nan)'))
        check(f'sleep {label}: diffCI is diff ± t·SE',
              abs(lo - (diff - half)) < 2e-3 and abs(hi - (diff + half)) < 2e-3,
              f'({lo}, {hi}) vs ({diff - half:.3f}, {diff + half:.3f})')


def test_random_slope():
    """Against the marginal variance written out from VarCorr's covariance
    matrix, z_i' Σ z_i + σ², rather than from lme4's Λ factor the code uses."""
    import rpy2.robjects as ro
    k = run(os.path.join(KbstatOptions().demo_dir, 'data', 'sleepstudy.csv'),
            'Reaction', 'Period', 'Subject', slope='Period')
    r_obj = getattr(k.model, 'r_model', getattr(k.model, 'model_obj', None))
    v = float(ro.r('''function(m) {
        S <- kronecker(diag(lme4::ngrps(m)[[1]]), as.matrix(lme4::VarCorr(m)[[1]]))
        Z <- as.matrix(lme4::getME(m, "Z"))
        mean(rowSums((Z %*% S) * Z)) + sigma(m)^2 }''')(r_obj)[0])
    row = k.posthoc_table.iloc[0]
    est = abs(float(row['diff']))
    expect = est / np.sqrt(v)
    check('random slope: SMD = |diff| / marginal SD', abs(float(row['SMD']) - expect) < 1e-6,
          f'SMD={float(row["SMD"]):.4f}, expected {expect:.4f}')


def test_log_link_ratio():
    rng = np.random.default_rng(3)
    df = pd.DataFrame({'g': np.repeat(['a', 'b'], 40),
                       'id': np.tile([f's{i}' for i in range(20)], 4)})
    u = dict(zip(df.id.unique(), rng.normal(scale=0.3, size=20)))
    df['y'] = rng.poisson(np.exp(1.5 + 0.4 * (df.g == 'b') + df.id.map(u)))
    path = os.path.join(OUT, 'pois.csv')
    df.to_csv(path, index=False)
    k = run(path, 'y', 'g', 'id', distribution='poisson')
    row = k.posthoc_table.iloc[0]
    m1, m2 = (float(str(row[c]).split()[0]) for c in ('emm_1', 'emm_2'))
    check('log link: ratio is emm_1 / emm_2', abs(float(row['ratio']) - m1 / m2) < 2e-3,
          f'{row["ratio"]} vs {m1 / m2:.4f}')
    lo, hi = ci_bounds(row['ratioCI'])
    check('log link: ratioCI brackets the ratio', lo < float(row['ratio']) < hi, row['ratioCI'])
    check('log link: no diffCI', 'diffCI' not in k.posthoc_table.columns)
    check('log link: SMD falls back to a finite value', np.isfinite(float(row['SMD'])))


if __name__ == '__main__':
    for fn in (test_sleep, test_random_slope, test_log_link_ratio):
        try:
            fn()
        except Exception as exc:
            check(fn.__name__, False, f'{type(exc).__name__}: {exc}')
    print('\n' + ('ALL PASSED' if not FAILED else f'{len(FAILED)} FAILED: {FAILED}'))
    sys.exit(1 if FAILED else 0)
