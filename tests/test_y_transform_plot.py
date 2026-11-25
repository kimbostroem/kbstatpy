#!/usr/bin/env python3
"""Tests for the data plots under `y_transform`, and per-y `y_transform`.

The plots show y in original units, so under a transform they need the
untransformed values. Those were kept as a copy of the whole frame, taken when
the file was read: before the rename, the categorical cast and the
constraints. A transformed run therefore plotted every row of the file,
excluded levels included and each with its own EMM marker, in data order
rather than x_order, while the model, the ANOVA and the post-hoc table used
the filtered rows. It went unnoticed because the numbers were right and
nothing compared the plot with them. Guarded here: a transformed plot shows
the rows and levels of the untransformed one, and per-y transforms reach only
their own y.

Needs R + lme4/emmeans.

Run:  python3 tests/test_y_transform_plot.py
"""
import os
import shutil
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat                 # noqa: E402
from kbstatpy.options import KbstatOptions         # noqa: E402

OUT = '/tmp/kbstatpy_y_transform_plot'


def toy(n_subj=10, n_rep=3, seed=4):
    rng = np.random.default_rng(seed)
    rows = []
    for grp, shift in (('A', 0.0), ('B', 0.4), ('C', 0.8)):
        for s in range(n_subj):
            u = rng.normal(scale=0.2)
            for cond in ('x', 'y', 'z'):
                for _ in range(n_rep):
                    rows.append({'r': float(np.tanh(0.6 + shift + u + rng.normal(scale=0.3))),
                                 'amp': float(np.exp(rng.normal(1 + shift, 0.3))),
                                 'grp': grp, 'cond': cond, 'subject': f'{grp}{s}'})
    return pd.DataFrame(rows)


def run(**kw):
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    csv = os.path.join(OUT, 'toy.csv')
    toy().to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file, o.out_dir, o.figure_display = csv, OUT, 'save_only'
    o.y, o.x, o.id = 'r', 'grp, cond', 'subject'
    o.constraints = 'grp != "B" & cond != "z"'
    o.x_order = {'grp': ['C', 'A']}
    for k, v in kw.items():
        setattr(o, k, v)
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run_save()
    return k


def figure(k, y='r'):
    res = next(r for r in k.output.results if r.y == y)
    f = res.fig_data
    return next(iter(f.values())) if isinstance(f, dict) else f


def panels(fig):
    return [ax for ax in fig.axes if ax.get_visible() and ax.has_data()]


def ticks(fig):
    return [[t.get_text() for t in ax.get_xticklabels()] for ax in panels(fig)]


def points(fig):
    """The y values of every scatter point in the figure, sorted."""
    ys = []
    for ax in panels(fig):
        for coll in ax.collections:
            off = np.asarray(coll.get_offsets())
            if off.ndim == 2 and len(off) > 1:
                ys.extend(off[:, 1].tolist())
    return np.sort(np.round(ys, 6))


def test_transformed_plot_shows_the_analysed_rows_and_levels():
    plain, tr = figure(run()), figure(run(y_transform='atanh(y)'))
    assert len(panels(tr)) == len(panels(plain)) == 2, (len(panels(tr)), len(panels(plain)))
    assert ticks(tr) == ticks(plain) == [['C', 'A'], ['C', 'A']], (ticks(tr), ticks(plain))


def test_transformed_plot_is_in_original_units():
    plain, tr = points(figure(run())), points(figure(run(y_transform='atanh(y)')))
    assert len(tr) == len(plain) and np.allclose(tr, plain), (len(tr), len(plain))


def test_data_csv_has_no_helper_column():
    run(y_transform='atanh(y)')
    cols = pd.read_csv(os.path.join(OUT, 'r', 'Data.csv') if os.path.isdir(os.path.join(OUT, 'r'))
                       else os.path.join(OUT, 'Data.csv')).columns
    assert '_y_untransformed' not in cols, list(cols)


def test_per_y_transform_reaches_only_its_y():
    k = run(y='r, amp', y_transform=['atanh(y)', 'log(y)'], constraints='')
    s = {r.y: r.summary for r in k.output.results}
    assert 'Transform of y         : atanh(y)' in s['r'], s['r'][:800]
    assert 'Transform of y         : log(y)' in s['amp'], s['amp'][:800]
    k = run(y='r, amp', y_transform=['atanh(y)', ''], constraints='')
    s = {r.y: r.summary for r in k.output.results}
    assert 'Transform of y' in s['r'] and 'Transform of y' not in s['amp']


def test_per_y_transform_length_must_match():
    try:
        run(y='r, amp', y_transform=['atanh(y)', 'log(y)', 'y'])
    except ValueError as e:
        assert 'entries' in str(e), e
    else:
        raise AssertionError('three transforms for two y must be rejected')


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
