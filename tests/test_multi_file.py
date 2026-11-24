#!/usr/bin/env python3
"""Tests for options.in_file naming several files: folders, patterns, ';' lists.

The files are stacked row by row, with a column 'file' naming each row's
source. What goes wrong quietly without the guards tested here:

- The file name is often the only record of the subject or session (s01.csv),
  and stacking without a source column loses it.
- The order in which the system lists a folder differs between machines, and
  with it the row order and every first-appearance level order; matches are
  sorted naturally (s2 before s10) instead.
- Excel's lock file (~$data.xlsx, present while the file is open) and hidden
  files sit in data folders and break the read.
- A file lacking a column gets NaN there, and its rows drop out of the fit
  without a word; the gap is named in a warning.
- Two files with the same name in different folders must not share a label.
- A single plain path behaves exactly as before: no 'file' column.

Needs R (kbstatpy starts it on import; the fit tests use glmmTMB/emmeans).

Run:  python3 tests/test_multi_file.py
"""
import contextlib
import io
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

OUT = '/tmp/kbstatpy_multi_file'


def table(seed, n=6, **extra):
    rng = np.random.default_rng(seed)
    d = pd.DataFrame({'cond': ['a', 'b'] * (n // 2), 'y': rng.normal(seed, 1, n)})
    for k, v in extra.items():
        d[k] = v
    return d


def write(rel, df):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if path.endswith('.csv'):
        df.to_csv(path, index=False)
    else:
        df.to_excel(path, index=False)
    return path


def load(in_file, record=None, **kw):
    o = KbstatOptions()
    o.in_file, o.base_dir, o.figure_display = in_file, OUT, 'save_only'
    o.y, o.x = 'y', 'cond'
    for k, v in kw.items():
        setattr(o, k, v)
    k = Kbstat(o)
    k._normalize_options()
    with warnings.catch_warnings(record=True) as w, contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter('always')
        k._load_data()
    if record is not None:
        record.extend(str(x.message) for x in w)
    return k


def raises(in_file, text):
    try:
        load(in_file)
    except ValueError as e:
        assert text in str(e), str(e)
        return
    raise AssertionError(f'no ValueError mentioning {text!r}')


def test_folder_natural_order_mixed_formats_and_skipped_files():
    write('d/s1.csv', table(1))
    write('d/s10.xlsx', table(10))
    write('d/s2.csv', table(2))
    write('d/.hidden.csv', table(99))
    write('d/~$s10.xlsx', table(98))
    with open(os.path.join(OUT, 'd/notes.txt'), 'w') as f:
        f.write('not data')
    d = load('d').data
    assert list(d.columns) == ['file', 'cond', 'y'], list(d.columns)
    assert list(pd.unique(d['file'])) == ['s1', 's2', 's10'], list(pd.unique(d['file']))
    assert len(d) == 18


def test_semicolon_list_pattern_and_list_form():
    write('d/s1.csv', table(1))
    write('d/s2.csv', table(2))
    write('e/sub/t1.csv', table(3))
    d = load('d/s2.csv; e/**/*.csv').data
    assert list(pd.unique(d['file'])) == ['s2', 't1'], list(pd.unique(d['file']))
    d = load(['d/s1.csv', 'd/s1.csv', 'd/s2.csv']).data      # a file named twice: once
    assert list(pd.unique(d['file'])) == ['s1', 's2'] and len(d) == 12


def test_same_name_in_two_folders_gets_two_labels():
    write('a/s1.csv', table(1))
    write('b/s1.csv', table(2))
    d = load('a/s1.csv; b/s1.csv').data
    assert list(pd.unique(d['file'])) == ['a/s1', 'b/s1'], list(pd.unique(d['file']))


def test_missing_column_is_named():
    write('d/s1.csv', table(1, age=30))
    write('d/s2.csv', table(2))
    msgs = []
    d = load('d', record=msgs).data
    assert d['age'].isna().sum() == 6
    assert any('s2: age' in m for m in msgs), msgs


def test_single_plain_file_is_unchanged():
    write('d/s1.csv', table(1))
    d = load('d/s1.csv').data
    assert 'file' not in d.columns and len(d) == 6


def test_errors():
    write('d/s1.csv', table(1, file='x'))
    write('d/s2.csv', table(2))
    raises('d', "column 'file'")
    raises('d/*.xlsx', 'no data file matches')
    os.makedirs(os.path.join(OUT, 'empty'), exist_ok=True)
    raises('empty', 'holds no data file')


def test_fit_with_file_as_id_and_summary():
    for i in range(1, 7):
        write(f'd/s{i}.csv', table(i))
    o = KbstatOptions()
    o.in_file, o.base_dir, o.figure_display = 'd', OUT, 'save_only'
    o.y, o.x, o.id = 'y', 'cond', 'file'
    k = Kbstat(o)
    with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter('ignore')
        k.run()
    r = k.output.results[0]
    assert r.data['file'].nunique() == 6 and len(r.data) == 36
    assert 'Input files            : 6' in r.summary and 's6 (6)' in r.summary, r.summary[:800]


def test_wide2long_across_files_keeps_units_apart():
    write('w/a.csv', pd.DataFrame({'pre': [1.0, 2.0], 'post': [2.0, 3.0]}))
    write('w/b.csv', pd.DataFrame({'pre': [1.5, 2.5], 'post': [2.5, 3.5]}))
    k = load('w', wide2long='time = (pre, post)', x='time', id='')
    d = k.data
    assert d['wide_row'].nunique() == 4 and len(d) == 8, d
    assert list(d['file'][:4]) == ['a'] * 4


if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            if os.path.isdir(OUT):
                shutil.rmtree(OUT)
            os.makedirs(OUT)
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
