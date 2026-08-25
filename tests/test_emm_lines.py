#!/usr/bin/env python3
"""Tests for `options.show_emm_lines` on the data plots.

`show_emm_lines` extends every plotted group's EMM across the whole panel as a
horizontal line, so a group's level can be read off against the other groups'
distributions instead of comparing dot heights by eye. Two things make that
silently useless if they break:

  * the line must sit at the EMM the panel's own white dot marks. The EMM grid is
    looked up per panel (filtered by the facet/row factor levels), so a lookup
    that loses the facet filter would draw the first panel's means in every
    panel — a plot that still looks plausible but is wrong.
  * the line must span the full panel width. A line stopping at its own group's
    violin would carry no more information than the dot already does.

The option doubles as the line style (False | True | a matplotlib line style),
so it is also checked that a requested style reaches the line, and that the
default when switched on with a bare True is dotted.

Also guards that the feature is off by default, since a horizontal line per
group is heavy ink to add to every plot unasked.

Needs R + lme4/emmeans, like the rest of kbstatpy.

Run:  python3 tests/test_show_emm_lines.py
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


def toy_data(n_subj=18, n_trial=4, seed=0):
    """Three groups x two regions, with a group x region interaction so the
    per-panel EMMs genuinely differ between the facets."""
    rng = np.random.default_rng(seed)
    groups = ['TD', 'Med', 'Unmed']
    regions = ['Ankle', 'Hip']
    base = {'Ankle': 10.0, 'Hip': 30.0}
    # interaction: the group effect reverses between the regions
    gain = {('TD', 'Ankle'): 1.0, ('Med', 'Ankle'): 1.4, ('Unmed', 'Ankle'): 1.2,
            ('TD', 'Hip'): 1.3, ('Med', 'Hip'): 1.0, ('Unmed', 'Hip'): 1.15}
    rows = []
    for s in range(n_subj):
        g = groups[s % 3]
        subj_re = rng.normal(scale=1.0)
        for r in regions:
            for t in range(n_trial):
                mu = base[r] * gain[(g, r)] + subj_re
                rows.append({'Subject': f'S{s:02d}', 'Group': g, 'Region': r,
                             'Y': mu + rng.normal(scale=1.5)})
    return pd.DataFrame(rows)


def fit(show_emm_lines, out=None):
    o = KbstatOptions()
    o.y = 'Y'
    o.x = ['Group', 'Region']
    o.interaction = ['Group', 'Region']
    o.id = 'Subject'
    o.posthoc_compare = 'Group'
    o.show_emm_lines = show_emm_lines
    o.figure_display = 'save_only'
    o.out_dir = out or '/tmp/kbstatpy_emm_lines_test'
    k = Kbstat(o)
    k.data = toy_data()
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


def _emm_lines(ax):
    """The horizontal EMM reference lines of one panel, identified by geometry
    rather than style (the style is what the option varies): two points, constant
    in y, spanning the axes in x (axhline's xdata is (0, 1) in axes coords). The
    CI bars are vertical, the brackets are 4-point polylines, and a subject
    connecting line has two different y values, so none of them match."""
    out = []
    for line in ax.get_lines():
        yd = np.asarray(line.get_ydata(), dtype=float)
        xd = np.asarray(line.get_xdata(), dtype=float)
        if len(yd) == 2 and yd[0] == yd[1] and tuple(xd) == (0.0, 1.0):
            out.append((line, tuple(xd), float(yd[0])))
    return out


def _emm_dots(ax):
    """y positions of the white EMM markers of one panel."""
    ys = []
    for coll in ax.collections:
        fc = coll.get_facecolor()
        if len(fc) and tuple(np.round(fc[0][:3], 3)) == (1.0, 1.0, 1.0):
            off = np.asarray(coll.get_offsets())
            ys.extend(off[:, 1].tolist())
    return sorted(ys)


def test_off_by_default():
    assert KbstatOptions().show_emm_lines is False, 'show_emm_lines must default to False'
    k = fit(False)
    for ax in _panel_axes(_figure(k)):
        assert not _emm_lines(ax), 'no EMM lines may be drawn when show_emm_lines is off'


def test_one_line_per_group_at_the_emm_height():
    """The regression guard: the lines must match THIS panel's EMM dots. A lookup
    that dropped the facet filter would repeat the first panel's means."""
    k = fit(True)
    fig = _figure(k)
    panels = _panel_axes(fig)
    assert len(panels) >= 2, 'test needs a faceted figure to be meaningful'
    seen = []
    for ax in panels:
        lines = _emm_lines(ax)
        dots = _emm_dots(ax)
        assert dots, 'panel has no EMM markers, test is vacuous'
        assert len(lines) == len(dots), (
            f'expected one EMM line per group ({len(dots)}), got {len(lines)}')
        ys = sorted(y for _, _, y in lines)
        assert np.allclose(ys, dots, rtol=1e-9, atol=1e-9), (
            f'EMM lines at {ys} do not match this panel\'s EMM dots at {dots}')
        seen.append(tuple(np.round(ys, 6)))
    assert len(set(seen)) == len(seen), (
        f'every panel drew the same EMM heights {seen} — the per-panel EMM '
        'lookup is not being applied')


def test_lines_span_the_full_panel_width():
    k = fit(True)
    n_checked = 0
    for ax in _panel_axes(_figure(k)):
        for line, xd, y in _emm_lines(ax):
            n_checked += 1
            assert xd == (0.0, 1.0), (
                f'EMM line at y={y:.4g} spans x={xd}, not the full panel width')
    assert n_checked > 0, 'no EMM lines were drawn, test is vacuous'


def test_line_colour_matches_its_group():
    """Without the group's own colour the lines cannot be attributed to a group.
    The violins are drawn desaturated (options.color_sat), so the line colours are
    checked against the palette itself and, loosely, against the violin hues."""
    import seaborn as sns
    k = fit(True)
    o = k.options
    expected = [tuple(np.round(c, 3))
                for c in sns.color_palette(o.color_scheme, 3)]   # three groups
    for ax in _panel_axes(_figure(k)):
        violins = [np.array(c.get_facecolor()[0][:3])
                   for c in ax.collections
                   if isinstance(c, matplotlib.collections.PolyCollection)
                   and len(c.get_facecolor())]
        assert len(violins) == 3, f'expected three violins, found {len(violins)}'
        got = [tuple(np.round(matplotlib.colors.to_rgb(line.get_color()), 3))
               for line, _, _ in _emm_lines(ax)]
        assert len(set(got)) == len(got), \
            f'EMM lines share colours ({got}) and cannot be told apart'
        assert sorted(got) == sorted(expected), \
            f'EMM line colours {got} are not the group palette {expected}'
        for c in got:
            assert min(np.abs(np.array(c) - v).max() for v in violins) < 0.1, \
                f'EMM line colour {c} is far from every violin hue'


def test_string_spellings_are_accepted():
    """The flag may arrive as text -- from a config file, a command line, a
    spreadsheet cell -- so the string forms must resolve, and a typo must not."""
    def norm(v):
        o = KbstatOptions()
        o.show_emm_lines = v
        k = Kbstat(o)
        k._normalize_options()
        return k.options.show_emm_lines

    for on in (True, 'true', 'True', ' on ', 'yes', '1'):
        assert norm(on) == ':', f'{on!r} must give the default dotted style'
    for off in (False, 'false', 'off', 'no', '0', 'none', ''):
        assert norm(off) is False, f'{off!r} must switch the lines off'
    for bad in ('sometimes', 'offf', 'dashes'):
        try:
            norm(bad)
        except ValueError:
            continue
        raise AssertionError(
            f'{bad!r} must raise, not be read as truthy: a rejected typo is a '
            'visible mistake, a truthy one silently draws lines nobody asked for')


def test_line_style_can_be_chosen():
    """The option doubles as the style, so a requested style must reach the line
    -- both the matplotlib symbol and the matplotlib name for it."""
    for requested, expected in (('--', '--'), ('dashed', '--'),
                                (':', ':'), ('dotted', ':'),
                                ('-.', '-.'), ('dashdot', '-.'),
                                ('solid', '-'), (True, ':')):
        o = KbstatOptions()
        o.show_emm_lines = requested
        k = Kbstat(o)
        k._normalize_options()
        assert k.options.show_emm_lines == expected, (
            f'show_emm_lines={requested!r} normalised to '
            f'{k.options.show_emm_lines!r}, expected {expected!r}')


def test_requested_style_reaches_the_drawn_line():
    """Normalisation alone is not enough: the plot must draw with that style."""
    for requested, expected in ((True, ':'), ('--', '--'), ('-', '-')):
        k = fit(requested, out=f'/tmp/kbstatpy_emm_lines_style_{expected!r}')
        n_checked = 0
        for ax in _panel_axes(_figure(k)):
            for line, _, y in _emm_lines(ax):
                assert line.get_linestyle() == expected, (
                    f'show_emm_lines={requested!r}: line at y={y:.4g} drawn with '
                    f'{line.get_linestyle()!r}, expected {expected!r}')
                n_checked += 1
        assert n_checked > 0, f'show_emm_lines={requested!r} drew no lines'


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
