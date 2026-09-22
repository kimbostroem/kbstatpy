#!/usr/bin/env python3
"""Tests for the residual spread ratio on the Residuals vs Fitted panel.

Mean |residual| in the top third of fitted values over the same in the bottom
third: a number for the fan that the panel already shows. It exists because
comparing two fits by eye, across two figures, is exactly where a real
heteroscedasticity was nearly missed on one plane of a gait dataset while two
others looked fine.

It is descriptive and must stay that way. There is no null distribution behind
it, so it is never starred and never called significant.

It goes on Residuals vs Fitted rather than Scale-Location because the latter is
only drawn when the model has no random effect, which is the minority case and
not the one where the question arises.

Failure modes guarded: a ratio computed from too few observations, or from
fitted values that barely vary, would be noise presented as a measurement; and
a constant-variance fit must not be made to look fanned.

Needs R.

Run:  python3 tests/test_spread_ratio.py
"""
import os
import re
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

OUT = '/tmp/kbstatpy_spread_ratio'


def toy(fanned, n_subj=14, seed=0):
    """`fanned=True` gives spread growing with the mean; False keeps it flat."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        re_ = rng.normal(scale=0.20)
        for g, shift in (('g1', 0.0), ('g2', 1.6)):
            for _ in range(8):
                mu = 2.0 + re_ + shift
                sd = 0.25 * mu if fanned else 0.25
                rows.append({'y': mu + rng.normal(scale=sd),
                             'grp': g, 'subj': f's{s}'})
    return pd.DataFrame(rows)


def fit(fanned, **kw):
    os.makedirs(OUT, exist_ok=True)
    csv = os.path.join(OUT, f'{fanned}.csv')
    toy(fanned).to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file = csv
    o.y, o.x, o.id = 'y', 'grp', 'subj'
    o.out_dir, o.figure_display = OUT, 'save_only'
    for k_, v in kw.items():
        setattr(o, k_, v)
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    return k


def test_a_flat_fit_sits_near_one():
    """Constant variance must not be made to look like a fan."""
    r = fit(False)._spread_ratio_value
    assert r is not None
    assert 0.7 < r < 1.4, f'flat data reported a ratio of {r:.2f}'


def test_a_fanned_fit_is_clearly_above_one():
    """The case it exists for."""
    r = fit(True)._spread_ratio_value
    assert r is not None
    assert r > 1.4, f'fanned data reported only {r:.2f}'


def test_the_two_are_ordered():
    """Whatever the exact values, fanned must exceed flat."""
    assert fit(True)._spread_ratio_value > fit(False)._spread_ratio_value


def test_it_reaches_the_summary_with_its_meaning():
    """A bare number in the text would invite reading it as a test statistic."""
    text = fit(True)._summary_text()
    m = re.search(r'Residual spread ratio[^:]*:\s*([0-9.]+)', text)
    assert m, text.split('DIAGNOSTICS')[-1][:400]
    assert float(m.group(1)) > 1.4
    assert 'constant spread' in text
    assert '***' not in text.split('DIAGNOSTICS')[-1].split('SIGNIFICANCE')[0]


def test_too_few_observations_give_no_ratio():
    """Three points a side is noise; it must decline rather than guess."""
    k = fit(True)
    small = np.linspace(0.0, 1.0, k._SPREAD_RATIO_MIN_N - 1)
    assert k._spread_ratio(small, small) is None


def test_fitted_values_that_do_not_vary_give_no_ratio():
    """With no spread in the fitted values the tertiles do not separate."""
    k = fit(True)
    n = k._SPREAD_RATIO_MIN_N + 10
    flat = np.ones(n)
    assert k._spread_ratio(flat, np.random.default_rng(0).normal(size=n)) is None


def test_a_zero_spread_lower_third_gives_no_ratio():
    """Dividing by zero would report inf as though it were a measurement."""
    k = fit(True)
    n = k._SPREAD_RATIO_MIN_N + 30
    fitted = np.arange(n, dtype=float)
    resid = np.where(fitted <= np.quantile(fitted, 1 / 3), 0.0, 1.0)
    assert k._spread_ratio(fitted, resid) is None


if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print(f'PASS  {name}', flush=True)
            except AssertionError as e:
                failures += 1
                print(f'FAIL  {name}\n      {e}', flush=True)
            except Exception as e:                      # noqa: BLE001
                failures += 1
                print(f'ERROR {name}\n      {type(e).__name__}: {e}', flush=True)
    print(f'\n{"all tests passed" if not failures else f"{failures} test(s) FAILED"}')
    sys.exit(1 if failures else 0)
