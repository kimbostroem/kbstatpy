#!/usr/bin/env python3
"""Tests for an `x_order` that names only some of a factor's levels.

x_order sets a level order. Naming some levels used to make them the only
categories, so every other level became NaN: R dropped those rows from the
fit without a word, and a constraint excluding one of them (`grp != "B"`)
kept them, NaN not being "B", so emmeans met rows the model never had and
failed with a bare R error. Guarded here: the unnamed levels stay in the
analysis, after the named ones, and a named level that does not occur, a
likely typo, is reported.

Needs R + lme4/emmeans.

Run:  python3 tests/test_x_order_partial.py
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

OUT = '/tmp/kbstatpy_x_order_partial'


def toy(seed=6):
    rng = np.random.default_rng(seed)
    rows = [{'y': rng.normal(i), 'grp': g, 'subject': f'{g}{s}'}
            for i, g in enumerate(('A', 'B', 'C')) for s in range(8) for _ in range(3)]
    return pd.DataFrame(rows)


def run(record=None, **kw):
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    csv = os.path.join(OUT, 'toy.csv')
    toy().to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file, o.out_dir, o.figure_display = csv, OUT, 'save_only'
    o.y, o.x, o.id = 'y', 'grp', 'subject'
    for k, v in kw.items():
        setattr(o, k, v)
    k = Kbstat(o)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        k.run()
    if record is not None:
        record.extend(str(x.message) for x in w)
    return k


def test_unnamed_levels_stay_in_the_analysis():
    k = run(x_order={'grp': ['C', 'A']})
    d = k.output.results[0].data
    assert len(d) == len(toy()) and d['grp'].notna().all(), (len(d), d['grp'].isna().sum())
    assert list(d['grp'].cat.categories) == ['C', 'A', 'B'], list(d['grp'].cat.categories)


def test_constraint_on_an_unnamed_level():
    k = run(x_order={'grp': ['C', 'A']}, constraints='grp != "B"')
    d = k.output.results[0].data
    assert set(d['grp'].astype(str)) == {'C', 'A'}, set(d['grp'].astype(str))
    assert len(k.output.results[0].posthoc['grp']) == 1


def test_a_named_level_absent_from_the_data_is_reported():
    msgs = []
    run(record=msgs, x_order={'grp': ['C', 'A', 'Bee']})
    assert any("'Bee'" in m and 'x_order' in m for m in msgs), msgs


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
