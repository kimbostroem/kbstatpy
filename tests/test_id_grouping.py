#!/usr/bin/env python3
"""Tests for `options.id` with more than one random grouping factor.

The guarded failure mode: `options.id` was interpolated straight into the
formula, so `id = 'participant, repetition'` built `(1 | participant,
repetition)` and R rejected it. A user tried exactly that. Several sites also
assumed `options.id` names one column -- the NaN drop before fitting, the
categorical cast (without which a numeric replicate index reaches R as a
covariate), the random-effect diagnostic panel and the subject lines in the data
plot -- so making the formula alone accept a list would have broken those.

Comma means CROSSED, one intercept each. lme4's own operators are honoured
inside a name: `a/b` nests, `a:b` groups by the pair. Slopes attach to the first
factor only.

The crossed reading is a silent disaster for a replicate index whose labels
recur inside every subject, so that shape is detected and warned about rather
than fitted quietly.

Needs R + glmmTMB.

Run:  python3 tests/test_id_grouping.py
"""
import os
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402


def toy(n_subj=16, n_rep=3, seed=5, crossed_site=False):
    """Subjects x conditions x repetitions. `repetition` is a replicate index:
    its labels recur inside every subject and mean nothing across them. With
    `crossed_site`, a genuinely crossed factor is added instead."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        re_ = rng.normal(scale=0.7)
        for cond in ('A', 'B'):
            for rep in range(1, n_rep + 1):
                row = {'y': 3.0 + (1.2 if cond == 'B' else 0.0) + re_
                            + rng.normal(scale=1.0),
                       'cond': cond, 'subject': f's{s}', 'repetition': rep}
                if crossed_site:
                    row['site'] = ['X', 'Y', 'Z'][s % 3]
                rows.append(row)
    return pd.DataFrame(rows)


def build(df, id_spec, slope=None, fit_model=True):
    o = KbstatOptions()
    o.y, o.x, o.id = 'y', 'cond', id_spec
    if slope:
        o.slope = slope
    o.out_dir, o.figure_display = '/tmp/kbstatpy_id_grouping', 'save_only'
    k = Kbstat(o)
    k.data = df.copy()
    k._normalize_options()
    k._apply_categorical()      # same order as _compute_single
    if fit_model:
        k.fit(); k.anova()
    return k


def test_comma_separated_id_is_crossed():
    k = build(toy(crossed_site=True), 'subject, site', fit_model=False)
    assert k._build_formula() == 'y ~ cond + (1 | subject) + (1 | site)', \
        k._build_formula()
    assert k._id_groups() == ['subject', 'site']
    assert k._id_vars() == ['subject', 'site']


def test_slash_nests_and_colon_pairs():
    k = build(toy(), 'subject/repetition', fit_model=False)
    assert k._build_formula() == 'y ~ cond + (1 | subject/repetition)', \
        k._build_formula()
    assert k._id_vars() == ['subject', 'repetition'], k._id_vars()
    k = build(toy(), 'subject:repetition', fit_model=False)
    assert k._build_formula() == 'y ~ cond + (1 | subject:repetition)', \
        k._build_formula()
    assert k._id_vars() == ['subject', 'repetition'], k._id_vars()


def test_slopes_attach_to_the_first_factor_only():
    k = build(toy(crossed_site=True), 'subject, site', slope=['cond'],
              fit_model=False)
    f = k._build_formula()
    assert '(1 + cond || subject)' in f or '(1 + cond | subject)' in f, f
    assert f.endswith('+ (1 | site)'), f
    assert f.count('cond |') == 1, f'slopes must not be repeated on site: {f}'


def test_a_crossed_and_a_nested_id_both_fit():
    for spec in ('subject, site', 'subject/repetition', 'subject:repetition',
                 'subject'):
        df = toy(crossed_site='site' in spec)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            k = build(df, spec)
        assert k.model is not None, f'{spec}: model did not fit'
        a = k.anova_table
        a = a.to_pandas() if hasattr(a, 'to_pandas') else a
        assert np.isfinite(float(a[a.Term == 'cond']['p'].iloc[0])), \
            f'{spec}: no usable p-value'


def test_every_grouping_column_becomes_categorical():
    """A numeric replicate index left numeric is a covariate to R, not a group."""
    k = build(toy(), 'subject, repetition')
    col = k.data['repetition']
    assert not pd.api.types.is_numeric_dtype(col), \
        f'repetition stayed {col.dtype}, so R sees a covariate, not a grouping factor'
    levels = col.cat.categories if hasattr(col, 'cat') else col.unique()
    assert all(isinstance(v, str) for v in levels), \
        f'grouping levels must reach R as characters, got {list(levels)[:3]}'


def test_implicit_nesting_is_warned_about():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        build(toy(), 'subject, repetition')
    msgs = [str(m.message) for m in w]
    assert any('nested inside' in m and "id='subject/repetition'" in m
               for m in msgs), f'expected the nesting advice, got {msgs}'
    # Nesting is not automatically right either: an unsupported block term fits
    # as a zero variance component, so the warning must offer dropping it too.
    assert any('leave' in m and 'singular' in m for m in msgs), \
        f'the warning must also offer leaving the factor out, got {msgs}'


def test_a_genuinely_crossed_factor_is_not_warned_about():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        build(toy(crossed_site=True), 'subject, site')
    assert not any('nested inside' in str(m.message) for m in w), \
        'site varies between subjects; the nesting warning must not fire'


def test_too_few_levels_is_warned_about():
    df = toy(n_rep=2)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        build(df, 'subject, repetition')
    assert any('2 level(s)' in str(m.message) for m in w), \
        f'expected a too-few-levels warning, got {[str(m.message) for m in w]}'


def test_summary_names_every_grouping_factor():
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        txt = build(toy(crossed_site=True), 'subject, site')._summary_text()
    assert 'Random grouping factors: subject, site' in txt, txt[:400]
    assert 'crossed' in txt


def fit_formula(df, formula):
    """Run the full pipeline from an explicit formula alone, as a user would."""
    out = '/tmp/kbstatpy_id_grouping_formula'
    os.makedirs(out, exist_ok=True)
    csv = os.path.join(out, 'toy.csv')
    df.to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file, o.formula = csv, formula
    o.out_dir, o.figure_display = out, 'save_only'
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    return k


def test_a_nested_term_in_an_explicit_formula_fits():
    """`(1 | subject/repetition)` in options.formula used to be rejected as
    inconsistent with the grouping variable it had itself back-filled."""
    k = fit_formula(toy(), 'y ~ cond + (1 | subject/repetition)')
    assert k.model is not None, 'nested formula did not fit'
    assert k._id_groups() == ['subject/repetition'], k._id_groups()
    assert k._id_vars() == ['subject', 'repetition'], k._id_vars()


def test_several_random_terms_in_a_formula_are_all_kept():
    """Only the last random term used to be recorded as the grouping variable."""
    k = build(toy(), 'subject', fit_model=False)
    parsed = k._parse_formula('y ~ cond + (1 + cond | subject) + (1 | subject:repetition)')
    assert parsed['id'] == 'subject, subject:repetition', parsed['id']
    assert parsed['slopes'] == ['cond'], parsed['slopes']
    k = fit_formula(toy(), 'y ~ cond + (1 | subject) + (1 | subject:repetition)')
    assert k.model is not None, 'two-term formula did not fit'
    assert k._id_vars() == ['subject', 'repetition'], k._id_vars()


def test_a_conflicting_id_is_still_rejected():
    k = build(toy(), 'subject', fit_model=False)
    k.options.formula = 'y ~ cond + (1 | subject/repetition)'
    try:
        k._validate_options_vs_formula(k.options.formula)
    except ValueError as e:
        assert 'grouping variable' in str(e), e
    else:
        raise AssertionError("options.id='subject' vs a nested formula term must be rejected")


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
