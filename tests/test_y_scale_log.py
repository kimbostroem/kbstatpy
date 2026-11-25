#!/usr/bin/env python3
"""Tests for `options.y_scale = 'log'` on the data plots and the profile plot.

Fits a small gamma/log GLMM (so it exercises the real plotting path, brackets and
all) and checks that:
  * the axis really is logarithmic
  * significance brackets stay inside the axis limits and are evenly spaced in
    LOG space, which is the part that silently breaks if the bracket geometry is
    done with linear arithmetic
  * non-positive data downgrades to a linear axis instead of silently dropping
    points, since matplotlib omits y <= 0 on a log axis
  * the profile plot carries no x-axis label (the tick labels are the level names)

Needs R + glmmTMB, like the rest of kbstatpy.

Run:  python3 tests/test_y_scale_log.py
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


def toy_data(n_subj=18, n_trial=4, seed=0):
    """Three groups x three regions, gamma-ish, region means spanning 2 decades so
    a shared linear axis would flatten the smallest region."""
    rng = np.random.default_rng(seed)
    groups = ['TD', 'Med', 'Unmed']
    regions = ['Ankle', 'Hip', 'Upper']
    base = {'Ankle': 12.0, 'Hip': 30.0, 'Upper': 2.0}
    gain = {'TD': 1.0, 'Med': 1.35, 'Unmed': 1.12}
    rows = []
    for s in range(n_subj):
        g = groups[s % 3]
        subj_re = rng.normal(scale=0.12)
        for r in regions:
            for t in range(n_trial):
                mu = base[r] * gain[g] * np.exp(subj_re)
                rows.append({'Subject': f'S{s:02d}', 'Group': g, 'Region': r,
                             'Age': 9 + (s % 5),
                             'Y': rng.gamma(shape=12.0, scale=mu / 12.0)})
    return pd.DataFrame(rows)


def fit(y_scale, data=None, out=None):
    o = KbstatOptions()
    o.y = 'Y'
    o.x = ['Group', 'Region']
    o.interaction = ['Group', 'Region']
    o.id = 'Subject'
    o.covariate = 'Age'
    o.distribution = 'gamma'
    o.link = 'log'
    o.posthoc_compare = 'Group'
    o.profile_across = 'Region'
    o.x_order = {'Region': ['Ankle', 'Hip', 'Upper']}
    o.y_scale = y_scale
    o.figure_display = 'save_only'
    o.out_dir = out or '/tmp/kbstatpy_yscale_test'
    k = Kbstat(o)
    k.data = data if data is not None else toy_data()
    k._normalize_options()
    k.fit()
    k.anova()
    k.posthoc()
    k.plot_data()
    k.profile_across()
    return k


def _panel_axes(fig):
    return [ax for ax in fig.axes if ax.get_ylabel() or ax.collections or ax.patches]


def test_log_axis_is_applied_to_data_plots():
    k = fit('log')
    fig = k.fig_data if not isinstance(k.fig_data, dict) else list(k.fig_data.values())[0]
    scales = {ax.get_yscale() for ax in _panel_axes(fig)}
    assert 'log' in scales, f'expected a log y-axis, got {scales}'


def test_linear_is_the_default():
    k = fit('linear')
    fig = k.fig_data if not isinstance(k.fig_data, dict) else list(k.fig_data.values())[0]
    scales = {ax.get_yscale() for ax in _panel_axes(fig)}
    assert scales == {'linear'}, f'expected only linear axes, got {scales}'


def test_brackets_stay_in_bounds_and_are_even_in_log_space():
    """The regression guard: with linear bracket arithmetic on a log axis the
    stack either escapes the axis or collapses to uneven spacing."""
    k = fit('log')
    fig = k.fig_data if not isinstance(k.fig_data, dict) else list(k.fig_data.values())[0]
    n_checked = 0
    for ax in _panel_axes(fig):
        if ax.get_yscale() != 'log':
            continue
        lo, hi = ax.get_ylim()
        tops = []
        for line in ax.get_lines():
            yd = np.asarray(line.get_ydata(), dtype=float)
            # a bracket is the 4-point [down, up, up, down] polyline
            if len(yd) == 4 and yd[1] == yd[2] and yd[0] < yd[1]:
                assert yd[1] <= hi + 1e-9, (
                    f'bracket at {yd[1]:.4g} escapes the axis top {hi:.4g}')
                assert yd[0] >= lo - 1e-9
                tops.append(yd[1])
                n_checked += 1
        if len(tops) >= 2:
            gaps = np.diff(np.log10(sorted(tops)))
            assert gaps.std() < 0.02 * max(gaps.mean(), 1e-9) + 1e-6, (
                f'bracket gaps uneven in log space: {gaps}')
    assert n_checked > 0, 'no significance brackets were drawn, test is vacuous'


def test_non_positive_data_falls_back_to_linear():
    data = toy_data(seed=4)
    data.loc[data.index[:6], 'Y'] = -1.0     # impossible for gamma, but plot-only here
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        k = Kbstat(KbstatOptions())
        fig, ax = matplotlib.pyplot.subplots()
        ax.plot([1, 2, 3], [1.0, -0.5, 2.0])
        ok = k._log_scale_ok(ax, 'test figure')
    assert ok is False, 'a non-positive value must veto the log axis'
    assert any('non-positive' in str(w.message) for w in caught), \
        'the fallback must warn'


def test_profile_plot_has_no_x_axis_label():
    k = fit('log')
    fig = k.fig_profile_across
    assert fig is not None, 'no profile figure produced'
    labels = [ax.get_xlabel() for ax in fig.axes]
    assert all(not lab for lab in labels), (
        f'profile plot should carry no x-axis label, got {labels!r}')


def test_log_axis_is_marked_on_the_label():
    """The ticks carry untransformed values, so the label must say 'log scale' —
    otherwise only the spacing reveals it. And a linear axis must NOT say it."""
    k = fit('log')
    fig = k.fig_data if not isinstance(k.fig_data, dict) else list(k.fig_data.values())[0]
    labels = [ax.get_ylabel() for ax in _panel_axes(fig) if ax.get_ylabel()]
    assert any('log scale' in lab for lab in labels), \
        f'no log-scale note on any data-plot y-label: {labels!r}'
    prof = [ax.get_ylabel() for ax in k.fig_profile_across.axes if ax.get_ylabel()]
    assert any('log scale' in lab for lab in prof), \
        f'no log-scale note on the profile y-label: {prof!r}'

    lin = fit('linear')
    figl = lin.fig_data if not isinstance(lin.fig_data, dict) else list(lin.fig_data.values())[0]
    lin_labels = ([ax.get_ylabel() for ax in _panel_axes(figl)]
                  + [ax.get_ylabel() for ax in lin.fig_profile_across.axes])
    assert not any('log scale' in lab for lab in lin_labels), \
        f'linear axes must not claim a log scale: {lin_labels!r}'


def test_profile_plot_honours_log_scale():
    k = fit('log')
    scales = {ax.get_yscale() for ax in k.fig_profile_across.axes}
    assert 'log' in scales, f'profile plot y-axis should be log, got {scales}'


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
