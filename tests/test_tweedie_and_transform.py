#!/usr/bin/env python3
"""Tests for the tweedie family and for '^' in `y_transform`.

Tweedie fills the gap in the family list. The others fix the variance power at
0 (gaussian), 1 (poisson), 2 (gamma) and 3 (inverse gaussian); tweedie
estimates it. A positive continuous outcome whose spread grows faster than the
mean but slower than the mean squared -- a range, an amplitude -- falls between
the fixed rungs and is fitted badly by either neighbour. Found on a real gait
dataset sitting at a power near 1.2.

Two failures are guarded beyond the family itself:

glmmTMB defines no deviance residuals for tweedie and answers with a vector of
NA and a message rather than an error. The residual helpers caught exceptions
only, so the structure panels were handed all-NA, drew nothing, and the plot
code then indexed an empty collection list -- an IndexError from matplotlib
naming neither the family nor the residuals.

And `y_transform = 'y^0.4'` failed with "ufunc 'bitwise_xor' not supported",
because '^' is exponentiation in R, in sympy and in ordinary mathematical
writing, but XOR in Python.

Needs R + glmmTMB.

Run:  python3 tests/test_tweedie_and_transform.py
"""
import os
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

OUT = '/tmp/kbstatpy_tweedie'


def toy(power=1.4, n_subj=18, seed=0):
    """Positive outcome whose variance grows like mean**power, so it sits
    between the Poisson and gamma rungs."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        re_ = rng.normal(scale=0.25)
        for g in ('g1', 'g2'):
            for _ in range(8):
                mu = np.exp(-1.0 + re_ + (0.4 if g == 'g2' else 0.0))
                sd = 0.35 * mu ** (power / 2)
                rows.append({'y': max(1e-4, mu + rng.normal(scale=sd)),
                             'grp': g, 'subj': f's{s}'})
    return pd.DataFrame(rows)


def fit(**kw):
    os.makedirs(OUT, exist_ok=True)
    csv = os.path.join(OUT, 'toy.csv')
    toy().to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file = csv
    o.y, o.x, o.id = 'y', 'grp', 'subj'
    o.out_dir, o.figure_display = OUT, 'save_only'
    for k, v in kw.items():
        setattr(o, k, v)
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    return k


def test_tweedie_is_an_accepted_distribution():
    k = fit(distribution='tweedie', link='log')
    assert k.model is not None
    a = k.anova_table
    a = a.to_pandas() if hasattr(a, 'to_pandas') else a
    assert np.isfinite(a['p'].astype(float)).all(), a


def test_tweedie_is_case_insensitive_like_the_others():
    assert fit(distribution='TWEEDIE', link='log').options.distribution == 'tweedie'


def test_the_estimated_power_is_reported():
    """It is the substance of the choice: a p next to a neighbour says the
    simpler family would have done."""
    k = fit(distribution='tweedie', link='log')
    p = k._tweedie_power()
    assert p is not None, 'the power was not recoverable'
    assert 1.0 < p < 2.0, f'expected a power between Poisson and gamma, got {p}'
    assert 'Tweedie power' in k._summary_text()


def test_other_families_report_no_power():
    assert fit(distribution='gamma', link='log')._tweedie_power() is None
    assert fit()._tweedie_power() is None


def test_the_diagnostics_survive_a_family_without_deviance_residuals():
    """The guarded crash: glmmTMB returns NA rather than raising, so the panels
    were handed nothing and matplotlib raised from an empty collection list."""
    k = fit(distribution='tweedie', link='log')
    assert k.fig_diagnostics is not None, 'no diagnostics figure'
    assert k._struct_resid_label == 'Pearson residuals', k._struct_resid_label
    drawn = [ax for ax in k.fig_diagnostics.axes if ax.collections or ax.lines]
    assert len(drawn) >= 5, f'only {len(drawn)} panels drew anything'


def test_a_caret_means_exponentiation_in_y_transform():
    a = fit(y_transform='y^0.4')
    b = fit(y_transform='y**0.4')
    fa = a.anova_table
    fb = b.anova_table
    fa = fa.to_pandas() if hasattr(fa, 'to_pandas') else fa
    fb = fb.to_pandas() if hasattr(fb, 'to_pandas') else fb
    assert np.allclose(fa['F'].astype(float), fb['F'].astype(float)), \
        "'y^0.4' must mean what 'y**0.4' means"


def test_log_transform_is_unaffected_by_the_caret_handling():
    k = fit(y_transform='log(y)')
    a = k.anova_table
    a = a.to_pandas() if hasattr(a, 'to_pandas') else a
    assert np.isfinite(a['p'].astype(float)).all()


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
    print(f'\n{"all tests passed" if not failures else f"{failures} test(s) FAILED"}')
    sys.exit(1 if failures else 0)
