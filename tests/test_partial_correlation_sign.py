#!/usr/bin/env python3
"""Regression tests for the sign of `correlate()`'s partial correlations.

History: up to 1.11.3 each variable was residualised on *all the others*, i.e.
with its eventual partner still in the predictor set. For a pair (i, j) that
returns corr(resid_i | all others, resid_j | all others), which is identically
MINUS the partial correlation, by the precision-matrix identity

    partial_r(i, j) = -P_ij / sqrt(P_ii * P_jj),   P = inv(cov)

so every partial coefficient (and every partial scatter slope) came out with the
wrong sign. The magnitudes were correct, which is what made it easy to miss.

Run directly:   python3 tests/test_partial_correlation_sign.py
or under pytest: pytest tests/test_partial_correlation_sign.py
"""
import itertools
import os
import sys

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

TOL = 1e-6


def partial_from_precision(df, cols):
    """Reference partial correlations: -P_ij / sqrt(P_ii * P_jj) with P = inv(cov)."""
    P = np.linalg.inv(np.cov(df[cols].to_numpy(dtype=float), rowvar=False))
    out = {}
    for i, j in itertools.combinations(range(len(cols)), 2):
        out[(cols[i], cols[j])] = -P[i, j] / np.sqrt(P[i, i] * P[j, j])
    return out


def run_correlate(data, cols, control=''):
    o = KbstatOptions()
    o.correlation = list(cols)
    o.correlation_control = control
    k = Kbstat(o)
    k.data = data.copy()
    return k.correlate()          # CorrelationResult


def all_axes(fig):
    """Every axes in the figure, including inset axes (which do not appear in
    fig.axes; the scatter cells are created with ax.inset_axes)."""
    out, stack = [], list(fig.axes)
    while stack:
        ax = stack.pop()
        out.append(ax)
        stack.extend(list(getattr(ax, 'child_axes', []) or []))
    return out


def lookup(table, a, b):
    m = table[((table.var_1 == a) & (table.var_2 == b)) |
              ((table.var_1 == b) & (table.var_2 == a))]
    assert len(m) == 1, f'{a} ~ {b} not found exactly once'
    return float(m.r.iloc[0])


def _toy(n=400, seed=0):
    """Four correlated variables, no special structure needed: the precision-matrix
    reference is exact for whatever the sample covariance happens to be."""
    rng = np.random.default_rng(seed)
    a = rng.normal(size=n)
    b = 0.8 * a + rng.normal(scale=0.6, size=n)
    c = 0.5 * a - 0.4 * b + rng.normal(scale=0.7, size=n)
    d = 0.3 * b + 0.6 * c + rng.normal(scale=0.5, size=n)
    return pd.DataFrame({'a': a, 'b': b, 'c': c, 'd': d})


def test_partial_matches_precision_matrix():
    """Every partial coefficient equals the precision-matrix definition, sign included."""
    cols = ['a', 'b', 'c', 'd']
    data = _toy()
    res = run_correlate(data, cols)
    ref = partial_from_precision(data, cols)
    for (v1, v2), expected in ref.items():
        got = lookup(res.partial_table, v1, v2)
        assert abs(got - expected) < 1e-3, (
            f'{v1} ~ {v2}: kbstatpy {got:+.4f} vs precision-matrix {expected:+.4f}')
        assert np.sign(got) == np.sign(expected) or abs(expected) < 1e-3, (
            f'{v1} ~ {v2}: SIGN INVERTED ({got:+.4f} vs {expected:+.4f})')


def test_collider_partial_is_negative():
    """x and y independent, z = x + y. Raw corr(x, y) ~ 0 but partialling on z
    must give a clearly NEGATIVE partial. A global negation would flip this."""
    rng = np.random.default_rng(7)
    n = 500
    x = rng.normal(size=n)
    y = rng.normal(size=n)
    z = x + y + rng.normal(scale=0.1, size=n)
    w = rng.normal(size=n)                      # noise, keeps k >= 3
    data = pd.DataFrame({'x': x, 'y': y, 'z': z, 'w': w})
    res = run_correlate(data, ['x', 'y', 'z', 'w'])
    raw = lookup(res.correlation_table, 'x', 'y')
    par = lookup(res.partial_table, 'x', 'y')
    assert abs(raw) < 0.15, f'raw corr(x, y) should be ~0, got {raw:+.3f}'
    assert par < -0.7, f'partial corr(x, y | z) should be strongly negative, got {par:+.3f}'


def test_redundancy_partial_stays_positive():
    """Two near-duplicate measures of the same quantity keep a POSITIVE partial
    once an unrelated third variable is conditioned on. This is the case that the
    pre-1.11.4 bug turned into a strong significant negative."""
    rng = np.random.default_rng(11)
    n = 500
    t = rng.normal(size=n)
    m1 = t + rng.normal(scale=0.3, size=n)
    m2 = t + rng.normal(scale=0.3, size=n)
    u = rng.normal(size=n)                      # unrelated
    data = pd.DataFrame({'m1': m1, 'm2': m2, 'u': u})
    res = run_correlate(data, ['m1', 'm2', 'u'])
    raw = lookup(res.correlation_table, 'm1', 'm2')
    par = lookup(res.partial_table, 'm1', 'm2')
    assert raw > 0.7, f'raw corr should be strongly positive, got {raw:+.3f}'
    assert par > 0.7, f'partial corr should stay positive, got {par:+.3f}'


def test_partial_with_control_variable():
    """correlation_control must not disturb the sign either: the reference is the
    precision matrix over the metrics AND the control variable."""
    cols = ['a', 'b', 'c', 'd']
    data = _toy(seed=3)
    data['Age'] = 0.4 * data['a'] + np.random.default_rng(5).normal(scale=0.8,
                                                                   size=len(data))
    res = run_correlate(data, cols, control='Age')
    ref = partial_from_precision(data, cols + ['Age'])
    for (v1, v2), expected in ref.items():
        if 'Age' in (v1, v2):
            continue          # control variables are deliberately kept out of the matrix
        got = lookup(res.partial_table, v1, v2)
        assert abs(got - expected) < 1e-3, (
            f'{v1} ~ {v2} (control=Age): kbstatpy {got:+.4f} vs reference {expected:+.4f}')


def test_partial_scatter_slope_matches_coefficient():
    """The partial scatter grid must plot the same relationship it labels: the
    per-pair residual slope has to share the sign of the reported coefficient.

    Note this test PASSES on the pre-1.11.4 code, because there the table and the
    plot were consistently wrong together. It guards a different failure mode: a
    sign-only patch to `r` that leaves the plotted residuals inverted."""
    cols = ['a', 'b', 'c', 'd']
    data = _toy(seed=21)
    res = run_correlate(data, cols)
    tbl = res.partial_table
    fig = res.fig_partial_scatter
    assert fig is not None, 'no partial scatter figure produced'
    slopes = []
    for ax in all_axes(fig):
        for line in ax.get_lines():                       # the red regression line
            xd, yd = line.get_xdata(), line.get_ydata()
            if len(xd) == 2 and xd[1] != xd[0]:
                slopes.append((yd[1] - yd[0]) / (xd[1] - xd[0]))
    assert len(slopes) >= len(tbl), (
        f'expected >= {len(tbl)} regression lines, found {len(slopes)}')
    n_pos_r = int((tbl.r > 0).sum())
    n_pos_slope = sum(1 for s in slopes if s > 0)
    assert n_pos_slope == n_pos_r, (
        f'{n_pos_slope} positive slopes but {n_pos_r} positive coefficients: the '
        'scatter grid and the table disagree in sign')


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
    print(f'\n{"all tests passed" if not failures else f"{failures} test(s) FAILED"}')
    sys.exit(1 if failures else 0)
