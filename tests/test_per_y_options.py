#!/usr/bin/env python3
"""Tests for per-y `distribution`, `link` and `constraints`.

In a multi-y run these may take one entry per dependent variable, matched to y
by position as y_units is: a count, a binary and a continuous outcome in one
run, the count on its own subset of rows. The guarded failure mode: they could
not. A list for distribution was rejected as one unknown name, and a list for
constraints reached pandas.query and failed there, so the only way was one
Kbstat per outcome. Also guarded: an entry reaching the wrong y (the reason
the match is by position, and a length mismatch an error), and a per-y
constraint missed by the split-level probe, which reads the rows separately.

Needs R + glmmTMB.

Run:  python3 tests/test_per_y_options.py
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

OUT = '/tmp/kbstatpy_per_y'


def toy(n_subj=16, n_rep=4, seed=3):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        u = rng.normal(scale=0.3)
        for cond in ('A', 'B'):
            for task in ('t1', 't2'):
                for _ in range(n_rep):
                    eta = 0.5 + u + (0.6 if cond == 'B' else 0.0)
                    rows.append({'count': rng.poisson(np.exp(eta)),
                                 'stable': int(rng.random() < 1 / (1 + np.exp(-eta))),
                                 'amp': eta + rng.normal(scale=0.5),
                                 'duration': 60 if rng.random() < 0.8 else 55,
                                 'cond': cond, 'task': task, 'subject': f's{s}'})
    return pd.DataFrame(rows)


def options(**kw):
    o = KbstatOptions()
    o.y, o.x, o.id = 'count, stable, amp', 'cond', 'subject'
    for k, v in kw.items():
        setattr(o, k, v)
    return o


def normalized(**kw):
    k = Kbstat(options(**kw))
    k._normalize_options()
    return k.options


def run(**kw):
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    csv = os.path.join(OUT, 'toy.csv')
    toy().to_csv(csv, index=False)
    o = options(in_file=csv, out_dir=OUT, figure_display='save_only', **kw)
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    return k


def distribution_line(res):
    return next(line for line in res.summary.splitlines()
                if line.strip().startswith('Distribution')).split(':', 1)[1].strip()


def test_comma_separated_string_is_per_y():
    o = normalized(distribution='Poisson, binomial, normal', link='log, logit, auto')
    assert o.distribution == ['poisson', 'binomial', 'normal'], o.distribution
    assert o.link == ['log', 'logit', 'auto'], o.link


def test_one_value_or_identical_values_stay_scalar():
    assert normalized(distribution=['poisson']).distribution == 'poisson'
    assert normalized(distribution='normal, normal, normal').distribution == 'normal'
    assert normalized(constraints=['a > 1'] * 3).constraints == 'a > 1'


def test_a_constraint_string_with_a_comma_is_one_constraint():
    c = 'task in ["t1", "t2"]'
    assert normalized(constraints=c).constraints == c


def test_wrong_number_of_entries_is_an_error():
    for kw in ({'distribution': 'poisson, binomial'},
               {'constraints': ['duration > 59', '']}):
        try:
            normalized(**kw)
        except ValueError as e:
            assert 'entries' in str(e), e
        else:
            raise AssertionError(f'{kw}: two entries for three y must be rejected')


def test_each_entry_is_validated():
    try:
        normalized(distribution='poisson, binomal, normal')
    except ValueError as e:
        assert 'binomal' in str(e), e
    else:
        raise AssertionError('a mistyped entry must be rejected')


def test_per_y_constraints_with_correlation_is_an_error():
    try:
        normalized(constraints=['duration > 59', '', ''], correlation='count, amp')
    except ValueError as e:
        assert 'correlation' in str(e), e
    else:
        raise AssertionError('per-y constraints leave the correlation rows undefined')


def test_each_y_gets_its_own_family_and_rows():
    k = run(distribution='poisson, binomial, normal',
            constraints=['duration > 59', '', ''])
    got = {r.y: distribution_line(r) for r in k.output.results}
    assert got == {'count': 'poisson', 'stable': 'binomial', 'amp': 'normal'}, got
    n = {r.y: len(r.data) for r in k.output.results}
    n_all = len(toy())
    n_long = int((toy()['duration'] > 59).sum())
    assert n == {'count': n_long, 'stable': n_all, 'amp': n_all}, (n, n_long, n_all)


def test_split_levels_use_the_y_constraint():
    """The split-level probe reads the data on its own; with a per-y
    constraint excluding a level, that level must not be fitted for that y."""
    k = run(distribution='poisson, binomial, normal',
            constraints=['task == "t1"', '', ''], split='task')
    got = [(r.y, r.split) for r in k.output.results]
    assert got == [('count', 't1'), ('stable', 't1'), ('stable', 't2'),
                   ('amp', 't1'), ('amp', 't2')], got


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
