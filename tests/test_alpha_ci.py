#!/usr/bin/env python3
"""Confidence intervals at 1 - alpha (options.alpha).

Every interval kbstatpy reports follows alpha: the EMM CIs, diffCI/ratioCI of
the post-hoc table, the raw-mean CI of Statistics.xlsx, the curve bands. With
the intervals fixed at 95 % while alpha was 0.10, a comparison could be marked
significant ('+') next to a CI that includes 0. What is guarded:

- at alpha = 0.10 the CI is 90 %: on ToothGrowth (supp, p = 0.060) it then
  excludes 0, as the test says; at 0.05 and 0.01 it includes 0;
- the Statistics.xlsx columns are named by the level (mean_CI95_* at the
  default, unchanged), and Summary.txt names the level;
- the level is an R session setting (emmeans' summary level), which a
  step-by-step fit() leaves set: a later analysis with the default alpha
  must get 95 % again.

Needs R (kbstatpy starts it on import).

Run:  python3 tests/test_alpha_ci.py
"""
import contextlib
import io
import os
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat                 # noqa: E402
from kbstatpy.options import KbstatOptions         # noqa: E402


def run(alpha):
    o = KbstatOptions()
    o.in_file = os.path.join(o.demo_dir, 'data/toothgrowth.csv')
    o.out_dir, o.figure_display = '', 'save_only'
    o.y, o.x, o.alpha = 'len', 'supp', alpha
    k = Kbstat(o)
    with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    r = k.output.results[0]
    row = r.posthoc['supp'].iloc[0]
    lo, hi = (float(v) for v in row['diffCI'].strip('()').split(','))
    return r, row, lo, hi


def test_the_ci_level_follows_alpha():
    _, row, lo, hi = run(0.10)
    assert 0.05 < row['p'] < 0.10, row['p']
    assert hi < 0, f'90 % CI ({lo}, {hi}) should exclude 0 at p = {row["p"]:.3f}'
    assert row['significance'] == '+', row['significance']
    for a in (0.05, 0.01):
        _, row, lo, hi = run(a)
        assert lo < 0 < hi, f'alpha = {a}: CI ({lo}, {hi}) should include 0'
    _, _, lo99, hi99 = run(0.01)
    _, _, lo95, hi95 = run(0.05)
    assert lo99 < lo95 and hi95 < hi99, 'the 99 % CI is the wider one'


def test_names_and_texts_carry_the_level():
    r, *_ = run(0.10)
    cols = list(r.statistics.columns)
    assert 'mean_CI90_lower' in cols and 'emm_CI90_upper' in cols, cols
    assert 'unadjusted 90% CI' in r.summary
    r, *_ = run(0.05)
    assert 'mean_CI95_lower' in r.statistics.columns, 'the default names are unchanged'


def test_a_later_default_run_is_back_at_95():
    # run() restores R's emmeans options afterwards, but a step-by-step fit()
    # does not, and leaves its level set in the R session.
    o = KbstatOptions()
    o.in_file = os.path.join(o.demo_dir, 'data/toothgrowth.csv')
    o.out_dir, o.figure_display = '', 'save_only'
    o.y, o.x, o.alpha = 'len', 'supp', 0.01
    with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
        warnings.simplefilter('ignore')
        Kbstat(o).fit()
    _, _, lo, hi = run(0.05)
    # The 95 % CI of OJ - VC on ToothGrowth, as emmeans gives it by default.
    assert (round(lo, 3), round(hi, 3)) == (-7.567, 0.167), (lo, hi)


if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print(f'PASS  {name}')
            except AssertionError as e:
                failures += 1
                print(f'FAIL  {name}\n      {e}')
            except Exception as e:                      # noqa: BLE001
                failures += 1
                print(f'ERROR {name}\n      {type(e).__name__}: {e}')
    if failures:
        print(f'\n{failures} test(s) FAILED')
        sys.exit(1)
    print('\nall tests passed')
