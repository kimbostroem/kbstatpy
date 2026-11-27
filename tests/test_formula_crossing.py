#!/usr/bin/env python3
"""Bracketed fixed terms in a formula: R's crossing operators.

`(a + b + c)^2` is R's "every term up to order 2". The formula parser used to
strip every bracket group as if it were a random term, so `(vision + stance)^2`
left the "variable" '^2' behind and the run failed at the post-hoc step with
'"^2" not found'. Only groups with a bar are random terms; the others are now
written out as R reads them. A power of one numeric variable, `z^2`, is not a
crossing and keeps its kbstatpy meaning (the polynomial, see test_covariate_terms).

Run:  python3 tests/test_formula_crossing.py
"""
import os
import shutil
import sys
import tempfile

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat        # noqa: E402
from kbstatpy.options import KbstatOptions  # noqa: E402

TMP = tempfile.mkdtemp(prefix='kbstatpy_formula_crossing_')


def parse(f):
    r = Kbstat._parse_formula(None, f)
    return r['x'], sorted(sorted(i) for i in r['interactions']), r['id']


def test_power_of_a_sum_is_every_term_up_to_that_order():
    x, ia, gid = parse('y ~ (a + b + c)^2 + (1|subject)')
    assert x == ['a', 'b', 'c'], x
    assert ia == [['a', 'b'], ['a', 'c'], ['b', 'c']], ia
    assert gid == 'subject'
    x, ia, _ = parse('y ~ (a+b+c)^3')
    assert ['a', 'b', 'c'] in ia and len(ia) == 4, ia


def test_bracketed_products_are_distributed():
    assert parse('y ~ (a + b)*c') == (['a', 'b', 'c'], [['a', 'c'], ['b', 'c']], '')
    assert parse('y ~ d + (a + b):c')[1] == [['a', 'c'], ['b', 'c']]


def test_random_terms_are_still_recognised():
    x, _, gid = parse('y ~ a * b + diag(1 + a | s) + (1|s/t)')
    assert x == ['a', 'b'] and gid == 's, s/t', (x, gid)


def test_plain_formulas_parse_as_before():
    assert parse('y ~ a*b*c + (1|s)') == (['a', 'b', 'c'], [['a', 'b', 'c']], 's')
    assert parse('y ~ 1 + a + b') == (['a', 'b'], [], '')


def data(seed=2):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(12):
        u = rng.normal()
        for a in ('a1', 'a2'):
            for b in ('b1', 'b2'):
                for c in ('c1', 'c2'):
                    y = 5 + (a == 'a2') + 0.5 * (b == 'b2') + 0.8 * (a == 'a2') * (c == 'c2') \
                        + u + rng.normal(scale=0.7)
                    rows.append({'subject': f'S{s:02d}', 'a': a, 'b': b, 'c': c, 'y': y})
    path = os.path.join(TMP, 'abc.csv')
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_power_of_a_sum_runs_and_is_the_two_way_rung():
    o = KbstatOptions()
    o.in_file = data()
    o.out_dir = os.path.join(TMP, 'sq')
    o.figure_display = 'save_only'
    o.model_comparison = True
    o.formula = 'y ~ (a + b + c)^2 + (1|subject)'
    k = Kbstat(o)
    k.run()
    terms = set(k.anova_table['Term'])
    assert terms == {'a', 'b', 'c', 'a:b', 'a:c', 'b:c'}, terms
    mc = k.model_comparison_table
    fitted = mc.loc[mc['fitted'] != '', 'Structure'].tolist()
    assert fitted == ['all two-way'], mc


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
