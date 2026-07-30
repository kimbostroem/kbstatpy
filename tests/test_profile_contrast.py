#!/usr/bin/env python3
"""Tests for the differential profile figure produced by `profile_across`.

`_plot_profile_across` shows absolute EMMs per level of the partner factor. The
trend statistic reported alongside it is a linear trend of the CONTRAST between
those levels, which absolute EMMs do not display, so `_plot_profile_contrast`
plots the contrast itself. These tests check that the figure shows the same
numbers the tables report, and that it does not draw a trend line through a
non-monotone pattern.

Needs R + glmmTMB.

Run:  python3 tests/test_profile_contrast.py
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

REGIONS = ['Ankle', 'Hip', 'Upper']


def toy(gain_by_region=None, n_subj=18, n_trial=4, seed=0, link='log'):
    """Three groups x three ordered regions. `gain_by_region` sets the Med-vs-TD
    ratio per region, which is what the trend is computed over."""
    rng = np.random.default_rng(seed)
    groups = ['TD', 'Med', 'Unmed']
    base = {'Ankle': 12.0, 'Hip': 30.0, 'Upper': 2.0}
    gain = gain_by_region or {'Ankle': 1.0, 'Hip': 1.3, 'Upper': 1.7}   # monotone
    rows = []
    for s in range(n_subj):
        g = groups[s % 3]
        re_ = rng.normal(scale=0.10)
        for r in REGIONS:
            for _ in range(n_trial):
                mult = 1.0 if g == 'TD' else (gain[r] if g == 'Med'
                                              else 1 + (gain[r] - 1) / 2)
                mu = base[r] * mult * np.exp(re_)
                y = rng.gamma(shape=25.0, scale=mu / 25.0)
                rows.append({'Subject': f'S{s:02d}', 'Group': g, 'Region': r,
                             'Age': 9 + (s % 5), 'Y': y})
    return pd.DataFrame(rows)


def fit(data, link='log', out='/tmp/kbstatpy_profile_contrast'):
    o = KbstatOptions()
    o.y = 'Y'
    o.x = ['Group', 'Region']
    o.interaction = ['Group', 'Region']
    o.id = 'Subject'
    o.covariate = 'Age'
    if link == 'log':
        o.distribution, o.link = 'gamma', 'log'
    else:
        o.distribution, o.link = 'normal', 'identity'
    o.posthoc_compare = 'Group'
    o.profile_across = 'Region'
    o.x_order = {'Region': REGIONS}
    o.figure_display = 'save_only'
    o.out_dir = out
    k = Kbstat(o)
    k.data = data
    k._normalize_options()
    k.fit(); k.anova(); k.posthoc(); k.profile_across()
    return k


def fitted_lines(fig):
    """The trend lines are the only 50-point polylines in the figure."""
    out = []
    for ax in fig.axes:
        for ln in ax.get_lines():
            if len(ln.get_xdata()) == 50:
                out.append(ln)
    return out


def test_figure_is_produced_alongside_the_existing_one():
    k = fit(toy())
    assert k.fig_profile_across is not None, 'the original profile plot must remain'
    assert k.fig_profile_contrast is not None, 'no contrast profile figure produced'


def test_trend_rows_carry_real_contrast_labels():
    """With 3+ levels emmeans returns integer codes for this model class; the
    trend table must still name the contrast, or it cannot be joined to it."""
    k = fit(toy())
    trend = k.profile_across_result['trend']
    lin = trend[trend['component'].astype(str).str.startswith('linear')]
    assert len(lin) >= 3, f'expected one trend row per contrast, got {len(lin)}'
    labels = [str(v) for v in lin['contrast']]
    assert all(not lab.replace('.', '').replace('-', '').isdigit() for lab in labels), \
        f'trend contrasts are unlabelled codes: {labels}'
    assert all(' - ' in lab for lab in labels), f'not contrast labels: {labels}'


def test_plotted_points_match_the_emmeans_contrasts():
    """Every marker must equal exp(estimate) from the link-scale contrast table."""
    k = fit(toy())
    res = k.profile_across_result
    ct = res['per_level_link']['Group']
    fig = k.fig_profile_contrast
    plotted = set()
    for ax in fig.axes:
        for ln in ax.get_lines():
            if len(ln.get_xdata()) in (1, 3) and ln.get_marker() not in ('', 'None'):
                for v in np.asarray(ln.get_ydata(), dtype=float):
                    if np.isfinite(v):
                        plotted.add(round(float(v), 6))
    expected = {round(float(np.exp(v)), 6) for v in ct['estimate']}
    missing = [e for e in expected
               if not any(abs(e - p) < 1e-4 for p in plotted)]
    assert not missing, f'contrast estimates absent from the figure: {missing}'


def test_no_trend_line_through_a_non_monotone_pattern():
    """A 1-df linear contrast can be significant on a rise-then-fall pattern.
    The figure must not draw a straight line through that."""
    mono = fit(toy({'Ankle': 1.0, 'Hip': 1.3, 'Upper': 1.7}, seed=1),
               out='/tmp/kbstatpy_pc_mono')
    bumpy = fit(toy({'Ankle': 1.0, 'Hip': 1.8, 'Upper': 1.1}, seed=1),
                out='/tmp/kbstatpy_pc_bumpy')
    n_mono = len(fitted_lines(mono.fig_profile_contrast))
    n_bumpy = len(fitted_lines(bumpy.fig_profile_contrast))
    assert n_mono >= 1, 'a clean monotone gradient should get a fitted line'
    assert n_bumpy < n_mono, (
        f'rise-then-fall drew as many lines as the monotone case '
        f'({n_bumpy} vs {n_mono}); the collinearity guard is not working')


def test_identity_link_shows_differences_on_a_linear_axis():
    k = fit(toy(seed=2), link='identity', out='/tmp/kbstatpy_pc_ident')
    fig = k.fig_profile_contrast
    assert fig is not None
    scales = {ax.get_yscale() for ax in fig.axes if ax.get_ylabel()}
    assert scales == {'linear'}, f'identity link must use a linear axis, got {scales}'
    labels = [ax.get_ylabel() for ax in fig.axes if ax.get_ylabel()]
    assert any('Difference' in lab for lab in labels), \
        f'identity link should plot differences, got {labels!r}'
    assert not any('log scale' in lab for lab in labels)


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
