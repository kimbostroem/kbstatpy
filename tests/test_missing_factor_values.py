#!/usr/bin/env python3
"""Rows with no value for a factor or the grouping column.

A data file joined from two sources (measurements plus a questionnaire) leaves
the factor empty for subjects missing from one of them. That used to stop the
run in pandas ("Categorical categories cannot be null"), and a NaN level let
through went on to fail in emmeans, since R had dropped those rows from the fit
while the cell means and post-hoc grid still held them. These tests pin that
such rows are left out once, with a warning and a line in Summary.txt, and that
the result equals the one on the file without them.

Run:  python3 tests/test_missing_factor_values.py
"""
import os
import shutil
import sys
import tempfile
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat        # noqa: E402
from kbstatpy.options import KbstatOptions  # noqa: E402

TMP = tempfile.mkdtemp(prefix='kbstatpy_missing_factor_')


def data(seed=1):
    """vision x stance within, gender between; two subjects without gender."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(14):
        g = ('female', 'male')[s % 2] if s < 12 else np.nan
        u = rng.normal(scale=2)
        for v in ('open', 'closed'):
            for st in ('tandem', 'one-leg'):
                y = 15 + 10 * (v == 'closed') + 4 * (st == 'one-leg') + u + rng.normal(scale=3)
                rows.append({'subject': f'S{s:02d}', 'vision': v, 'stance': st,
                             'gender': g, 'sway': y, 'code': s})
    return pd.DataFrame(rows)


def run(df, name, **opts):
    path = os.path.join(TMP, f'{name}.csv')
    df.to_csv(path, index=False)
    o = KbstatOptions()
    o.in_file = path
    o.out_dir = os.path.join(TMP, name)
    o.figure_display = 'save_only'
    for k, v in opts.items():
        setattr(o, k, v)
    k = Kbstat(o)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        k.run()
    return k, [str(x.message) for x in w]


FORMULA = 'sway ~ 1 + vision * stance * gender + (1|subject)'


def test_rows_without_a_factor_value_are_left_out_and_reported():
    k, msgs = run(data(), 'formula', formula=FORMULA)
    assert k.n_obs_fit == 48, k.n_obs_fit
    assert any('8 row(s) left out' in m and 'gender' in m for m in msgs), msgs
    assert 'Rows left out          : 8 (no value for gender)' in k._summary_text()


def test_same_result_as_without_those_rows():
    full, _ = run(data(), 'with_na', formula=FORMULA)
    clean, msgs = run(data().dropna(subset=['gender']), 'without_na', formula=FORMULA)
    assert not any('left out' in m for m in msgs), 'warned on complete data'
    assert 'Rows left out' not in clean._summary_text()
    a, b = full.anova_table, clean.anova_table
    assert np.allclose(a['F'].to_numpy(float), b['F'].to_numpy(float)), (a, b)


def test_per_variable_and_numeric_factor():
    """Same through y, x, id; and a numeric-coded factor keeps NaN missing
    instead of turning it into a level called 'nan'."""
    df = data()
    df['gcode'] = df['gender'].map({'female': 1, 'male': 2})
    k, _ = run(df, 'pervar', y='sway', x='vision, stance, gcode', id='subject')
    assert k.n_obs_fit == 48
    assert 'nan' not in [str(c) for c in k.data['gcode'].cat.categories]


def test_constraint_that_removes_them_leaves_nothing_to_report():
    k, msgs = run(data(), 'constrained', formula=FORMULA, constraints='code < 12')
    assert k.n_obs_fit == 48
    assert not any('left out' in m for m in msgs), msgs


if __name__ == '__main__':
    failures = 0
    try:
        for name, fn in sorted(globals().items()):
            if name.startswith('test_') and callable(fn):
                try:
                    fn()
                    print(f'PASS  {name}')
                except Exception as e:
                    failures += 1
                    print(f'FAIL  {name}: {type(e).__name__}: {e}')
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1 if failures else 0)
