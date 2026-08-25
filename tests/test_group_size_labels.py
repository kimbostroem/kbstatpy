#!/usr/bin/env python3
"""Tests for `options.show_group_size`, the 'n=' label on each plotted group.

The counts used to be drawn unconditionally in bar style, from inside the panel
loop, and the significance brackets knew nothing about them: the brackets are
anchored above the tallest thing a panel has *rendered*, which was computed from
the collections, patches and lines only. A label therefore ended up drawn through
the lowest bracket whenever a group's CI top came close to it — the reason the
option exists at all.

So these tests check both halves:
  * the option switches the labels on and off, in violin style as well as bar
    style, and is off by default in both — the counts used to be drawn in bar
    style unconditionally, so the default is a deliberate change of behaviour
  * every bracket sits above every label of its panel *by a visible margin*, in
    both styles — the collision guard. A margin, not just "above": the bracket
    spacing is derived from the y-range as it stood before the stack expanded the
    axis, so a gap that the layout reserved in data units silently collapsed to
    under a pixel once a three-bracket stack had stretched the axis by ~40 %,
    which is why the violins grazed their labels while the bar plots, with pinned
    limits, looked fine
  * the labels stay inside the axis when there are no brackets at all, since then
    nothing else expands the y-limits and the top label would be clipped by the
    frame
  * the counts are the real per-group observation counts, not the panel's or the
    whole sample's

Needs R + lme4/emmeans, like the rest of kbstatpy.

Run:  python3 tests/test_group_size_labels.py
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


def violin_data(n_subj=18, n_trial=4, seed=0):
    """Three groups x two regions with an interaction, continuous outcome, and
    group effects large enough that the post-hoc brackets actually appear."""
    rng = np.random.default_rng(seed)
    groups = ['TD', 'Med', 'Unmed']
    regions = ['Ankle', 'Hip']
    base = {'Ankle': 10.0, 'Hip': 30.0}
    gain = {('TD', 'Ankle'): 1.0, ('Med', 'Ankle'): 1.4, ('Unmed', 'Ankle'): 1.2,
            ('TD', 'Hip'): 1.3, ('Med', 'Hip'): 1.0, ('Unmed', 'Hip'): 1.15}
    rows = []
    for s in range(n_subj):
        g = groups[s % 3]
        subj_re = rng.normal(scale=1.0)
        for r in regions:
            for t in range(n_trial):
                rows.append({'Subject': f'S{s:02d}', 'Group': g, 'Region': r,
                             'Y': base[r] * gain[(g, r)] + subj_re + rng.normal(scale=1.5)})
    return pd.DataFrame(rows)


def binary_data(n_subj=24, n_trial=8, seed=1):
    """Binary outcome, so plot_style='auto' resolves to bar style."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        g = ['A', 'B', 'C'][s % 3]
        p = {'A': 0.3, 'B': 0.6, 'C': 0.45}[g]
        for t in range(n_trial):
            rows.append({'Subject': f'S{s:02d}', 'Group': g,
                         'Y': int(rng.random() < p)})
    return pd.DataFrame(rows)


def fit(show_group_size, style='violin', posthoc='auto', out=None):
    o = KbstatOptions()
    o.y = 'Y'
    o.id = 'Subject'
    o.show_group_size = show_group_size
    o.posthoc_compare = posthoc
    o.figure_display = 'save_only'
    o.out_dir = out or f'/tmp/kbstatpy_groupsize_{style}'
    if style == 'bar':
        o.x = ['Group']
        o.distribution = 'binomial'
        data = binary_data()
    else:
        o.x = ['Group', 'Region']
        o.interaction = ['Group', 'Region']
        o.posthoc_compare = 'Group' if posthoc == 'auto' else posthoc
        data = violin_data()
    k = Kbstat(o)
    k.data = data
    k._normalize_options()
    k.fit()
    k.anova()
    k.posthoc()
    k.plot_data()
    return k


def _figure(k):
    return k.fig_data if not isinstance(k.fig_data, dict) else list(k.fig_data.values())[0]


def _panel_axes(fig):
    return [ax for ax in fig.axes if ax.collections or ax.patches]


def _labels(ax):
    return [t for t in ax.texts if t.get_text().startswith('n=')]


def _label_tops(fig, ax):
    """Data-space top edge of each 'n=' label, as the bracket code sees it."""
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    out = []
    for t in _labels(ax):
        bb = t.get_window_extent(renderer=rend)
        out.append(float(ax.transData.inverted().transform((bb.x0, bb.y1))[1]))
    return out


def _bracket_ys(ax):
    """y of each significance bracket: the 4-point [down, up, up, down] polyline."""
    ys = []
    for line in ax.get_lines():
        yd = np.asarray(line.get_ydata(), dtype=float)
        if len(yd) == 4 and yd[1] == yd[2] and yd[0] < yd[1]:
            ys.append(float(yd[1]))
    return ys


def test_off_by_default_in_both_styles():
    """The default is off everywhere, bar style included -- where the counts used
    to be drawn unconditionally."""
    assert KbstatOptions().show_group_size is False
    for style in ('bar', 'violin'):
        panels = _panel_axes(_figure(fit(KbstatOptions().show_group_size, style=style)))
        assert not any(_labels(ax) for ax in panels), \
            f'{style} style must not label groups by default'


def test_true_labels_violins_and_false_unlabels_bars():
    viol = _panel_axes(_figure(fit(True, style='violin')))
    assert all(_labels(ax) for ax in viol), \
        'show_group_size=True must label the violins too'
    bar = _panel_axes(_figure(fit(False, style='bar')))
    assert not any(_labels(ax) for ax in bar), \
        'show_group_size=False must remove the bar labels'


def test_counts_are_the_per_group_counts():
    """A label showing the panel total or the sample size would look plausible."""
    k = fit(True, style='violin')
    data = k.data if k.data is not None else violin_data()
    expected = set()
    for (g, r), sub in data.groupby(['Group', 'Region'], observed=True):
        expected.add(f'n={len(sub)}')
    got = {t.get_text() for ax in _panel_axes(_figure(k)) for t in _labels(ax)}
    assert got <= expected, f'labels {got} are not per-group counts (expected {expected})'
    assert got, 'no labels drawn, test is vacuous'


# Minimum gap demanded between the lowest bracket ink and the highest label, in
# points. Below the 5 pt the figure aims for, to leave room for the rounding of
# the correction pass, but far above the sub-pixel gap the bug produced.
MIN_GAP_PT = 3.5


def _tick_bottoms(ax):
    """y of each bracket's downward ticks — the lowest ink of the bracket, which
    is what actually reaches down towards a label."""
    ys = []
    for line in ax.get_lines():
        yd = np.asarray(line.get_ydata(), dtype=float)
        if len(yd) == 4 and yd[1] == yd[2] and yd[0] < yd[1]:
            ys.append(float(yd[0]))
    return ys


def test_brackets_clear_the_labels():
    """The regression guard: brackets must clear the labels by a visible margin,
    measured in points on the finished figure, not merely be above them in data
    coordinates at the moment they were laid out."""
    n_checked = 0
    for style in ('violin', 'bar'):
        k = fit(True, style=style)
        fig = _figure(k)
        for ax in _panel_axes(fig):
            ticks = _tick_bottoms(ax)
            tops = _label_tops(fig, ax)
            if not ticks or not tops:
                continue
            gap_px = (ax.transData.transform((0, min(ticks)))[1]
                      - max(ax.transData.transform((0, y))[1] for y in tops))
            gap_pt = gap_px / fig.dpi * 72.0
            assert gap_pt >= MIN_GAP_PT, (
                f'{style}: lowest bracket clears the highest label by only '
                f'{gap_pt:.2f} pt (want >= {MIN_GAP_PT} pt)')
            n_checked += 1
    assert n_checked > 0, 'no panel had both brackets and labels, test is vacuous'


def test_labels_are_not_clipped_without_brackets():
    """With posthoc off nothing else expands the y-axis, so the tallest group's
    label has to be what makes room for itself."""
    k = fit(True, style='violin', posthoc='none')
    fig = _figure(k)
    n_checked = 0
    for ax in _panel_axes(fig):
        assert not _bracket_ys(ax), 'posthoc_compare=none must draw no brackets'
        top = ax.get_ylim()[1]
        for y in _label_tops(fig, ax):
            assert y <= top, f'label top {y:.4g} is clipped by the axis top {top:.4g}'
            n_checked += 1
    assert n_checked > 0, 'no labels drawn, test is vacuous'


def test_option_spellings():
    def norm(v):
        o = KbstatOptions()
        o.show_group_size = v
        k = Kbstat(o)
        k._normalize_options()
        return k.options.show_group_size

    for on in (True, 'true', 'True', ' on ', 'yes', '1'):
        assert norm(on) is True, f'{on!r} should switch the labels on'
    for off in (False, 'false', 'off', 'no', '0', 'none', ''):
        assert norm(off) is False, f'{off!r} should switch the labels off'
    for bad in ('auto', 'sometimes', 'offf', 'hide'):
        try:
            norm(bad)
        except ValueError:
            continue
        raise AssertionError(
            f'{bad!r} must raise, not be read as truthy: a rejected typo is a '
            'visible mistake, a truthy one silently switches the labels ON')


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
