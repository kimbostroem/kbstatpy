#!/usr/bin/env python3
"""Tests for options.wide2long, which reshapes wide data to long on reading.

`time = (pre, post)` stacks the columns pre and post into options.y and a new
factor time. The ways this goes wrong quietly, and what guards each here:

- The units lose their grouping: each wide row becomes several long rows, and
  without a random effect for it the levels are fitted as independent
  observations, with standard errors that are too small. options.id defaults
  to 'wide_row', created as the wide row number. Not 'id': a column of that
  name in the data, meaning something else, would be grouped by silently;
  an existing 'wide_row' therefore stops the run.
- The reshape runs after rename or x_order, which then refer to levels that do
  not exist yet and silently do nothing.
- A single spec with several y stacks the same columns for every y, so each
  "dependent variable" is the same analysis under another name.
- With several factors, 'side = (L, R); time = (pre, post)' lists LEVELS and
  the columns are their combinations (L_pre, ...). Read as column lists, the
  spec finds nothing; that, and a missing combination, must be reported, and
  the levels must come from the spec, not from splitting names at '_'.

The reference is the same data written long by hand: the fit must agree.

Needs R + glmmTMB/emmeans.

Run:  python3 tests/test_wide2long.py
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

OUT = '/tmp/kbstatpy_wide2long'


def wide(seed=3, n=12):
    rng = np.random.default_rng(seed)
    unit = rng.normal(0, 1, n)
    grp = ['A' if i % 2 else 'B' for i in range(n)]
    return pd.DataFrame({
        'grp': grp,
        'pre': 10 + unit + rng.normal(0, 0.5, n),
        'mid': 11 + unit + rng.normal(0, 0.5, n),
        'post': 12 + unit + rng.normal(0, 0.5, n) + (np.array(grp) == 'A'),
        'b_pre': 5 + rng.normal(0, 1, n),
        'b_post': 6 + rng.normal(0, 1, n),
    })


def opts(df, name='wide.csv', **kw):
    os.makedirs(OUT, exist_ok=True)
    csv = os.path.join(OUT, name)
    df.to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file, o.out_dir, o.figure_display = csv, os.path.join(OUT, 'out'), 'save_only'
    o.y, o.x = 'score', 'time, grp'
    o.wide2long = 'time = (pre, mid, post)'
    for k, v in kw.items():
        setattr(o, k, v)
    return o


def run(o):
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    return k


def raises(o, text):
    try:
        run(o)
    except ValueError as e:
        assert text in str(e), str(e)
        return
    raise AssertionError(f'no ValueError mentioning {text!r}')


def test_reshape_creates_id_and_matches_hand_written_long_data():
    w = wide()
    k = run(opts(w))
    assert k.options.id == 'wide_row', k.options.id
    assert '(1 | wide_row)' in k._build_formula().replace('(1|wide_row)', '(1 | wide_row)'), k._build_formula()
    d = k.output.results[0].data
    assert len(d) == 3 * len(w), len(d)
    # Unit by unit, levels in the order listed.
    assert list(d['time'].astype(str)[:3]) == ['pre', 'mid', 'post'], list(d['time'][:3])
    assert list(d['wide_row'].astype(str)[:3]) == ['1', '1', '1'], list(d['wide_row'][:3])
    assert list(d['time'].cat.categories) == ['pre', 'mid', 'post']

    long = w.assign(wide_row=range(1, len(w) + 1)).melt(
        id_vars=['wide_row', 'grp'], value_vars=['pre', 'mid', 'post'],
        var_name='time', value_name='score')
    ref = run(opts(long, 'long.csv', wide2long='', id='wide_row'))
    a, b = k.output.results[0].anova, ref.output.results[0].anova
    num = a.select_dtypes('number').columns
    assert np.allclose(a[num].to_numpy(float), b[num].to_numpy(float), equal_nan=True), (a, b)


def test_existing_id_column_is_used():
    w = wide().assign(subject=[f's{i}' for i in range(12)])
    k = run(opts(w, id='subject'))
    d = k.output.results[0].data
    assert 'wide_row' not in d.columns and d['subject'].nunique() == 12


def test_unrelated_id_column_is_not_used():
    # A column 'id' that does not identify the wide rows (two units per id).
    w = wide().assign(id=[f'site{i // 2}' for i in range(12)])
    k = run(opts(w))
    d = k.output.results[0].data
    assert k.options.id == 'wide_row' and d['wide_row'].nunique() == 12, k.options.id


def test_existing_wide_row_column_stops_the_run():
    raises(opts(wide().assign(wide_row=range(12))), 'Set options.id')


def test_rename_and_x_order_apply_to_the_new_levels():
    k = run(opts(wide(), rename='time: pre -> Before, post -> After',
                 x_order='time: After, mid, Before'))
    d = k.output.results[0].data
    assert list(d['time'].cat.categories) == ['After', 'mid', 'Before'], \
        list(d['time'].cat.categories)


def test_constraint_on_the_new_factor():
    k = run(opts(wide(), constraints='time != "mid"'))
    d = k.output.results[0].data
    assert set(d['time'].astype(str)) == {'pre', 'post'}, set(d['time'].astype(str))


def test_one_spec_per_y():
    o = opts(wide(), y='a, b', x='time',
             wide2long=['time = (pre, post)', 'time = b_pre, b_post'])
    k = run(o)
    w = wide()
    r = {res.y: res.data for res in k.output.results}
    assert np.allclose(sorted(r['a']['a']), sorted(pd.concat([w['pre'], w['post']])))
    assert np.allclose(sorted(r['b']['b']), sorted(pd.concat([w['b_pre'], w['b_post']])))


def wide2x2(seed=4, n=12):
    rng = np.random.default_rng(seed)
    unit = rng.normal(0, 1, n)
    d = {'grp': ['A' if i % 2 else 'B' for i in range(n)]}
    for side, s_eff in (('Left_knee', 0), ('Right_knee', 1)):
        for time, t_eff in (('pre', 0), ('post', 2)):
            d[f'{side}_{time}'] = 10 + unit + s_eff + t_eff + rng.normal(0, 0.5, n)
    return pd.DataFrame(d)


def test_two_factors_match_hand_written_long_data():
    w = wide2x2()
    spec = 'side = (Left_knee, Right_knee); time = (pre, post)'
    k = run(opts(w, x='side, time', interaction='side, time', wide2long=spec))
    d = k.output.results[0].data
    assert len(d) == 4 * len(w), len(d)
    # Levels from the spec: 'Left_knee', not split at every '_'.
    assert list(d['side'].astype(str)[:4]) == ['Left_knee'] * 2 + ['Right_knee'] * 2
    assert list(d['time'].astype(str)[:4]) == ['pre', 'post'] * 2
    assert list(d['time'].cat.categories) == ['pre', 'post']

    rows = []
    for i, r in w.iterrows():
        for side in ('Left_knee', 'Right_knee'):
            for time in ('pre', 'post'):
                rows.append({'wide_row': i + 1, 'grp': r['grp'], 'side': side,
                             'time': time, 'score': r[f'{side}_{time}']})
    ref = run(opts(pd.DataFrame(rows), 'long2.csv', wide2long='', id='wide_row',
                   x='side, time', interaction='side, time'))
    a, b = k.output.results[0].anova, ref.output.results[0].anova
    assert list(a.index) == list(b.index) and len(a) == 3, (a, b)
    num = a.select_dtypes('number').columns
    assert np.allclose(a[num].to_numpy(float), b[num].to_numpy(float), equal_nan=True), (a, b)


def test_entry_order_follows_the_column_names():
    w = wide2x2().rename(columns=lambda c: '_'.join(reversed(c.rsplit('_', 1)))
                         if c != 'grp' else c)        # pre_Left_knee, ...
    k = run(opts(w, x='side, time',
                 wide2long='time = (pre, post); side = (Left_knee, Right_knee)'))
    d = k.output.results[0].data
    assert len(d) == 48 and set(d['side'].astype(str)) == {'Left_knee', 'Right_knee'}


def test_missing_combination_is_reported():
    w = wide2x2().drop(columns='Right_knee_post')
    msgs = []
    o = opts(w, x='side, time', wide2long='side = (Left_knee, Right_knee); time = (pre, post)')
    k = Kbstat(o)
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter('always')
        k.run()
    msgs = [str(x.message) for x in rec]
    assert any('Right_knee_post' in m and 'incomplete' in m for m in msgs), msgs
    assert len(k.output.results[0].data) == 36


def test_listed_level_order_survives_a_missing_combination():
    # Without Left_knee_pre, the first unit's rows run post, pre, post, so the
    # order of first appearance would put post first.
    w = wide2x2().drop(columns='Left_knee_pre')
    spec = 'side = (Left_knee, Right_knee); time = (pre, post)'
    k = run(opts(w, x='side, time', wide2long=spec))
    assert list(k.output.results[0].data['time'].cat.categories) == ['pre', 'post']
    # Under rename, by the renamed labels, and without an "absent level" warning.
    o = opts(w, x='side, time', wide2long=spec, rename='time: pre -> Before')
    k = Kbstat(o)
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter('always')
        k.run()
    assert list(k.output.results[0].data['time'].cat.categories) == ['Before', 'post']
    assert not any('x_order' in str(x.message) for x in rec), [str(x.message) for x in rec]
    # x_order still wins.
    k = run(opts(w, x='side, time', wide2long=spec, x_order='time: post, pre'))
    assert list(k.output.results[0].data['time'].cat.categories) == ['post', 'pre']


def test_errors():
    raises(opts(wide(), y='a, b'), 'single spec')
    raises(opts(wide(), wide2long='time = (pre, later)'), "['later']")
    raises(opts(wide(), y='pre', wide2long='time = (mid, post)'), "'pre'")
    raises(opts(wide(), wide2long='time = (pre)'), 'at least two')
    raises(opts(wide(), wide2long='pre, post'), 'newVar')
    # Column names where levels belong: every combination is absent.
    raises(opts(wide2x2(), x='side, time',
                wide2long='side = (Left_knee_pre, Left_knee_post); '
                          'time = (Right_knee_pre, Right_knee_post)'), 'LEVELS')
    raises(opts(wide2x2(), x='side', wide2long='side = (a, b); side = (c, d)'), 'twice')
    raises(opts(wide2x2(), x='grp', wide2long='grp = (Left_knee, Right_knee); '
                                               'time = (pre, post)'), "'grp'")


if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            if os.path.isdir(OUT):
                shutil.rmtree(OUT)
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
