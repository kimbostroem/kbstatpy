#!/usr/bin/env python3
"""Tests for `options.offset`.

An offset enters the linear predictor with its coefficient fixed at 1; with
offset = 'log(duration)' a Poisson model of a count becomes one of the rate,
count per unit of duration, which is how counts over trials of unequal length
are compared. The guarded failure mode: there was no way to write one. An
offset(log(duration)) term in options.formula was cut at its first ')' by the
term parser, which then reported a factor called 'eyes)' and failed in R.
Also guarded: the offset reaching the model (the rate ratio must match a
direct glmmTMB fit, and differ from the fit without it), the two spellings
agreeing, per-y offsets reaching only their own y, and the bare-column
mistake under a log link being pointed out.

Needs R + glmmTMB.

Run:  python3 tests/test_offset.py
"""
import os
import shutil
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd
import rpy2.robjects as ro
from rpy2.robjects import pandas2ri
from rpy2.robjects.conversion import localconverter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy._terms import split_offsets          # noqa: E402
from kbstatpy.kbstat import Kbstat                 # noqa: E402
from kbstatpy.options import KbstatOptions         # noqa: E402

OUT = '/tmp/kbstatpy_offset'


def toy(n_subj=20, n_rep=4, seed=5):
    """Group B has twice the rate of A, and its trials are mostly the short
    ones, so the raw counts understate the difference."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        u = rng.normal(scale=0.2)
        for grp, rate, p_short in (('A', 0.05, 0.2), ('B', 0.10, 0.8)):
            for _ in range(n_rep):
                dur = 20.0 if rng.random() < p_short else 60.0
                rows.append({'count': rng.poisson(dur * rate * np.exp(u)),
                             'amp': rng.normal(1 + (grp == 'B')),
                             'duration': dur, 'grp': grp, 'subject': f's{s}'})
    return pd.DataFrame(rows)


def run(**kw):
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    csv = os.path.join(OUT, 'toy.csv')
    toy().to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file, o.out_dir, o.figure_display = csv, OUT, 'save_only'
    o.y, o.x, o.id = 'count', 'grp', 'subject'
    o.distribution = 'poisson'
    for k, v in kw.items():
        setattr(o, k, v)
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    return k


def ratio(k, y='count'):
    res = next(r for r in k.output.results if r.y == y)
    return float(res.posthoc['grp']['ratio'].iloc[0])


def direct_ratio():
    """A / B rate ratio from glmmTMB + emmeans, without kbstatpy."""
    with localconverter(ro.default_converter + pandas2ri.converter):
        ro.globalenv['kb_offset_toy'] = toy()
    return float(ro.r("""
        local({
          m <- glmmTMB::glmmTMB(count ~ grp + offset(log(duration)) + (1 | subject),
                                family = poisson, data = kb_offset_toy)
          summary(pairs(emmeans::emmeans(m, ~ grp, type = 'response')))$ratio
        })""")[0])


def test_split_offsets():
    assert split_offsets('y ~ a*b + offset(log(t)) + (1|s)') == ('y ~ a*b + (1|s)', 'log(t)')
    assert split_offsets('y ~ offset(log(t))') == ('y ~ 1', 'log(t)')
    assert split_offsets('y ~ a + offset(log(t)) + offset(log(n))') == ('y ~ a', 'log(t) + log(n)')
    assert split_offsets('y ~ a + log(t)') == ('y ~ a + log(t)', '')


def test_the_offset_reaches_the_model():
    with_offset, without = ratio(run(offset='log(duration)')), ratio(run())
    expected = direct_ratio()
    assert abs(with_offset - expected) < 1e-3, (with_offset, expected)
    # True ratio 0.5; ignoring the shorter B trials hides most of it.
    assert abs(with_offset - 0.5) < 0.15, with_offset
    assert without > 0.75, f'without the offset the ratio should be near 1, got {without}'


def test_formula_offset_is_the_same_model():
    """The spelling that used to fail in the term parser."""
    k = run(x='', id='', formula='count ~ grp + offset(log(duration)) + (1 | subject)')
    assert abs(ratio(k) - ratio(run(offset='log(duration)'))) < 1e-6
    assert k.options.offset == 'log(duration)', k.options.offset
    assert k.options.x == ['grp'], f'factors read from the formula: {k.options.x}'


def test_summary_states_the_reference_exposure():
    k = run(offset='log(duration)')
    summary = k.output.results[0].summary
    line = next(l for l in summary.splitlines() if 'Reference offset' in l)
    ref = float(line.split('duration =')[1])
    # emmeans holds a covariate at its mean, but one with only two values (20
    # and 60 here) is treated as a factor and averaged over on the link scale:
    # the geometric mean of the two, not the mean. The note must report the
    # value emmeans used, whichever it was.
    assert abs(ref - np.sqrt(20 * 60)) < 1e-2, (ref, np.sqrt(20 * 60))


def test_per_y_offset_reaches_only_its_y():
    k = run(y='count, amp', distribution='poisson, normal',
            offset=['log(duration)', ''])
    f = {r.y: r.formula for r in k.output.results}
    assert 'offset(log(duration))' in f['count'] and 'offset' not in f['amp'], f


def test_bare_column_under_log_link_warns():
    o = KbstatOptions()
    csv = os.path.join(OUT, 'toy.csv')
    os.makedirs(OUT, exist_ok=True)
    toy().to_csv(csv, index=False)
    o.in_file, o.out_dir, o.figure_display = csv, OUT, 'save_only'
    o.y, o.x, o.id, o.distribution, o.offset = 'count', 'grp', 'subject', 'poisson', 'duration'
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        Kbstat(o).run()
    assert any("log(duration)" in str(x.message) for x in w), [str(x.message) for x in w]


def test_unknown_column_and_double_offset_are_errors():
    for kw, word in (({'offset': 'log(durration)'}, 'durration'),
                     ({'x': '', 'id': '', 'offset': 'log(duration)',
                       'formula': 'count ~ grp + offset(log(2*duration)) + (1 | subject)'},
                      'one place')):
        try:
            run(**kw)
        except ValueError as e:
            assert word in str(e), e
        else:
            raise AssertionError(f'{kw} must be rejected')


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
