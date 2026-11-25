#!/usr/bin/env python3
"""Tests that a correlation grid's title fits inside its canvas.

The canvas of both correlation grids is sized from the matrix and its diagonal
labels, which for few variables is much narrower than the title: a 5-variable
partial-correlation table came out under 3 in wide while its subtitle,
"(residuals after removing all other variables)", needs about 5 in at 13 pt.
The PNG hid this because it is saved with bbox_inches='tight', but the PDF
canvas is fixed, so the title was cut off at both ends.

These tests measure the rendered title against the figure width, for a small
and a large grid, and check that the subtitle is set smaller than the title
proper.

Layout only — no model is fitted, so this needs neither R nor glmmTMB.

Run:  python3 tests/test_correlation_title_fits.py
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

TITLE = ('Pearson Partial Correlations (adjusted for Age)\n'
         '(residuals after removing all other variables)')
LINES = TITLE.split('\n')


def toy_corr(k, seed=0, n=60):
    """(vars, data frame, correlation table) for a k-variable grid."""
    vars_ = [f'variable_{i}' for i in range(k)]
    rng = np.random.default_rng(seed)
    data = pd.DataFrame({v: rng.normal(size=n) for v in vars_})
    rows = []
    for a, b in itertools.combinations(vars_, 2):
        r = float(np.corrcoef(data[a], data[b])[0, 1])
        p = 0.001 if abs(r) > 0.22 else 0.5
        rows.append({'var_1': a, 'var_2': b, 'r': r, 'p': p,
                     'significance': '***' if p < 0.05 else 'n.s.'})
    return vars_, data, pd.DataFrame(rows)


def grids(k, title=TITLE):
    """Both correlation figures for a k-variable set, keyed by kind."""
    vars_, data, corr = toy_corr(k)
    kb = Kbstat(KbstatOptions())
    arrays = {v: data[v].to_numpy() for v in vars_}
    return {'table': kb._plot_corr_table(corr, vars_, title),
            'scatter': kb._plot_corr_scatter(corr, vars_, arrays, title)}


def title_texts(fig, title=TITLE):
    """The Text artists carrying the title. One per line as drawn now, but a
    single artist holding the whole string is accepted too, so the width tests
    below still measure a title that regressed to one block of type."""
    lines = title.split('\n')
    return [t for ax in fig.axes for t in ax.texts
            if t.get_text() in lines or t.get_text() == title]


def overflow_in(fig):
    """How far the widest title line sticks out of the canvas, in inches."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    texts = title_texts(fig)
    assert texts, 'no title found on the figure, test is vacuous'
    over = 0.0
    for t in texts:
        bb = t.get_window_extent(renderer=r)
        over = max(over, (-bb.x0) / fig.dpi,
                   (bb.x1 - fig.bbox.width) / fig.dpi)
    return over


def test_small_grid_title_is_not_clipped():
    """The regression guard: k = 5 is where the title outgrew the canvas."""
    for kind, fig in grids(5).items():
        over = overflow_in(fig)
        assert over <= 0.02, (
            f'{kind}: title overflows the {fig.get_size_inches()[0]:.2f} in '
            f'canvas by {over:.2f} in, so the PDF cuts it off')


def test_large_grid_title_is_not_clipped():
    for kind, fig in grids(16).items():
        over = overflow_in(fig)
        assert over <= 0.02, f'{kind}: title overflows by {over:.2f} in'


def test_large_grid_canvas_is_not_widened_for_the_title():
    """A wide grid already has room, so nothing should change there — the fix
    must not pad out figures that were fine."""
    for kind, fig in grids(16).items():
        w = fig.get_size_inches()[0]
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        widest = max(t.get_window_extent(renderer=r).width
                     for t in title_texts(fig)) / fig.dpi
        assert w > widest + 0.5, (
            f'{kind}: canvas {w:.2f} in is barely wider than the title '
            f'{widest:.2f} in, suggesting it was padded to fit')


def test_subtitle_is_smaller_than_the_title():
    for kind, fig in grids(5).items():
        texts = title_texts(fig)
        assert len(texts) == len(LINES), (
            f'{kind}: expected the title split into {len(LINES)} lines so they '
            f'can be sized separately, found {len(texts)}')
        sizes = {t.get_text(): t.get_fontsize() for t in texts}
        assert sizes[LINES[1]] < sizes[LINES[0]], (
            f'{kind}: subtitle ({sizes[LINES[1]]:.1f} pt) should be set '
            f'smaller than the title ({sizes[LINES[0]]:.1f} pt)')


def test_single_line_title_still_works():
    one = LINES[0]
    vars_, data, corr = toy_corr(5)
    kb = Kbstat(KbstatOptions())
    for kind, fig in (('table', kb._plot_corr_table(corr, vars_, one)),
                      ('scatter', kb._plot_corr_scatter(
                          corr, vars_, {v: data[v].to_numpy() for v in vars_}, one))):
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        t = [t for ax in fig.axes for t in ax.texts if t.get_text() == one]
        assert len(t) == 1, f'{kind}: expected one title line, found {len(t)}'
        bb = t[0].get_window_extent(renderer=r)
        assert bb.x0 >= -0.02 * fig.dpi and bb.x1 <= fig.bbox.width + 0.02 * fig.dpi, \
            f'{kind}: single-line title is clipped'


def test_title_sits_above_the_matrix():
    """Shrinking and restacking the lines must not drop them onto the cells."""
    for kind, fig in grids(5).items():
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        ax = fig.axes[0]
        title_bottom = min(t.get_window_extent(renderer=r).y0
                           for t in title_texts(fig))
        # cells are Rectangles on the table grid, inset axes on the scatter one
        boxes = ([p.get_window_extent() for p in ax.patches]
                 + [a.get_window_extent(r) for a in ax.child_axes])
        assert boxes, f'{kind}: no matrix cells drawn, test is vacuous'
        content_top = max(b.y1 for b in boxes)
        assert title_bottom >= content_top - 1.0, (
            f'{kind}: title overlaps the matrix '
            f'(title bottom {title_bottom:.0f} px, content top {content_top:.0f} px)')


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
