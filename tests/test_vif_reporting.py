#!/usr/bin/env python3
"""Tests that collinearity among the fixed effects is reported at all.

The guarded failure mode: VIF was computed inside `correlate()`, which returns
immediately unless `options.correlation` is set. A model whose covariates were
severely collinear therefore reported nothing -- no table, no warning, no line
in `Summary.txt` -- unless its author happened to also want an unrelated
correlation analysis. A real dataset went through with VIFs above 30 and gave no
hint of it.

Collinearity is silent in a way most problems are not: the coefficients stay
unbiased and the fit is unaffected, so the output looks healthy while the
standard errors of the collinear terms are inflated several-fold. Pairwise
correlations do not reveal it either, which is the point of VIF -- a variable
can be nearly determined by two others while correlating only moderately with
each.

VIF is now computed with the model, whatever `correlation` says, and reported
three ways: a warning when severe, a `Summary.txt` section when any term is
concerning or worse, and `VIF.xlsx` beside the other tables.

Needs R + glmmTMB.

Run:  python3 tests/test_vif_reporting.py
"""
import os
import re
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import (Kbstat, _wrap_footer,   # noqa: E402
                             _VIF_FLAG)
from kbstatpy.options import KbstatOptions    # noqa: E402

OUT = '/tmp/kbstatpy_vif'


def toy(collinear=True, n_subj=20, seed=0):
    """`c` is nearly a + b when collinear, independent otherwise. `d` is always
    independent, so something sits below the reporting threshold."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        re_ = rng.normal(scale=0.4)
        for g in ('g1', 'g2'):
            for _ in range(6):
                a = rng.normal()
                b = rng.normal()
                c = (a + b + rng.normal(scale=0.05)) if collinear else rng.normal()
                rows.append({'y': 2 + re_ + 0.3 * a + rng.normal(),
                             'grp': g, 'a': a, 'b': b, 'c': c,
                             'd': rng.normal(), 'subj': f's{s}'})
    return pd.DataFrame(rows)


def fit(df, correlation='', covariate='a, b, c, d'):
    """Goes through run(), not _compute_vif() directly. The bug was in the
    wiring -- the method always worked, it was simply never reached -- so a test
    that calls it by hand would pass against the broken code."""
    os.makedirs(OUT, exist_ok=True)
    csv = os.path.join(OUT, 'toy.csv')
    df.to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file = csv
    o.y, o.x, o.id = 'y', 'grp', 'subj'
    o.covariate = covariate
    o.correlation = correlation
    o.out_dir, o.figure_display = OUT, 'save_only'
    k = Kbstat(o)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        k.run()
    k._warnings = [str(m.message) for m in w]
    return k


def test_vif_is_computed_without_a_correlation_analysis():
    """The guarded bug: this used to be None unless `correlation` was set."""
    k = fit(toy())
    assert k.vif_table is not None, 'no VIF table without options.correlation'
    assert set(k.vif_table['variable']) == {'a', 'b', 'c', 'd'}, k.vif_table


def test_covariates_count_as_fixed_effects():
    """They are covariates, not in x; they are fixed effects all the same."""
    k = fit(toy())
    assert len(k.vif_table) == 4, k.vif_table


def test_severe_collinearity_warns():
    k = fit(toy(collinear=True))
    assert (k.vif_table['VIF'] >= 10).any(), f'test is vacuous: {k.vif_table}'
    assert any('collinear' in m.lower() for m in k._warnings), k._warnings


def test_an_uncorrelated_design_raises_no_alarm():
    """The table still appears -- its absence would be ambiguous, since it also
    means "fewer than two numeric predictors" -- but nothing is flagged, no
    warning fires, and the interpretive caution stays away."""
    k = fit(toy(collinear=False))
    assert (k.vif_table['VIF'] < _VIF_FLAG).all(), f'test is vacuous: {k.vif_table}'
    assert k._vif_flagged() is None
    assert not any('collinear' in m.lower() for m in k._warnings), k._warnings
    txt = k._summary_text()
    assert 'COLLINEARITY (VIF)' in txt, 'the table is reported either way'
    assert 'should not be read as an effect' not in txt, \
        'a clean model must not carry the caution'


def test_summary_explains_it_when_it_matters():
    k = fit(toy(collinear=True))
    txt = k._summary_text()
    assert 'COLLINEARITY (VIF)' in txt
    assert 'SE x' in txt, 'give the standard-error factor, not only the variance one'
    assert 'unbiased' in txt, 'say what it does NOT mean'
    assert 'together with n' in txt, 'a VIF alone cannot say whether a term is precise'


def test_fewer_than_two_numeric_predictors_gives_nothing():
    """One predictor cannot be collinear with anything."""
    os.makedirs(OUT, exist_ok=True)
    csv = os.path.join(OUT, 'toy_one.csv')
    toy().to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file = csv
    o.y, o.x, o.id, o.covariate = 'y', 'grp', 'subj', 'a'
    o.out_dir, o.figure_display = OUT, 'save_only'
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    assert k.vif_table is None, k.vif_table


def test_the_table_lists_every_predictor():
    """Summary.txt and VIF.xlsx carry the whole column: a reader comparing terms
    wants them all, and a value below the flag is information too. Only the
    crowded diagnostics footer is restricted."""
    k = fit(toy(collinear=True))
    assert (k.vif_table['VIF'] < _VIF_FLAG).any(), 'test is vacuous'
    section = k._summary_text()
    section = section[section.index('COLLINEARITY'):]
    section = section[:section.index('\n\n')]
    listed = set(re.findall(r'^  (\S+)\s+[\d.]+\s', section, re.M))
    assert listed == set(k.vif_table['variable']), \
        f'{listed} vs {set(k.vif_table["variable"])}'


def test_the_footer_names_only_the_flagged_ones():
    k = fit(toy(collinear=True))
    flagged = k._vif_flagged()
    assert flagged is not None and len(flagged) < len(k.vif_table), 'test is vacuous'
    assert (flagged['VIF'] >= _VIF_FLAG).all()


def test_sample_size_is_reported_beside_the_vif():
    """VIF alone cannot say whether a term is precise enough -- the standard
    error depends on the collinearity and the sample size together."""
    k = fit(toy(collinear=True))
    for col in ('n', 'n_indep', 'SE_factor', 'varies'):
        assert col in k.vif_table.columns, f'{col} missing from {list(k.vif_table)}'
    section = k._summary_text()
    section = section[section.index('COLLINEARITY'):]
    assert 'indep.' in section and ' n ' in section, section[:300]


def test_a_between_subject_predictor_counts_subjects_not_rows():
    """The wrinkle that makes the pair honest: a predictor constant within each
    subject is estimated from the subjects, however many rows there are."""
    df = toy(collinear=True)
    df['height'] = df['subj'].map({s: 1.6 + 0.01 * i
                                   for i, s in enumerate(sorted(df['subj'].unique()))})
    df['mass'] = df['height'] * 40 + 1.0        # collinear with height, also per subject
    k = fit(df, covariate='a, b, c, d, height, mass')
    t = k.vif_table.set_index('variable')
    assert t.loc['height', 'n_indep'] == df['subj'].nunique(), t
    assert t.loc['height', 'n'] == len(df), t
    assert 'between' in t.loc['height', 'varies']
    assert t.loc['a', 'n_indep'] == len(df), t
    assert 'within' in t.loc['a', 'varies']


def test_the_footer_wraps_to_fit_the_figure():
    """It was one line, and ran off the page once a model had a few covariates."""
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(12, 7.5), dpi=100)
    long = ('Formula: y ~ ' + ' + '.join(f'covariate_number_{i:02d}' for i in range(14))
            + ' + (1 | subject)')
    wrapped = _wrap_footer(long, fig)
    assert wrapped.count('\n') >= 1, 'a formula this long must wrap'
    r = fig.canvas.get_renderer()
    t = fig.text(0.5, 0.02, wrapped, ha='center', fontsize=10, fontstyle='italic')
    bb = t.get_window_extent(renderer=r)
    t.remove()
    assert bb.x0 >= 0 and bb.x1 <= 1200, f'still out of bounds: {bb.x0}..{bb.x1}'
    plt.close(fig)


def test_wrapping_keeps_random_effect_terms_whole():
    """The bar inside (1 | subj) is not a separator; breaking there strands the
    grouping factor on a line of its own."""
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(6, 4), dpi=100)     # narrow, to force breaks
    for term in ('(1 | subject)', '(1 + Period | subject)'):
        text = ('Formula: y ~ ' + ' + '.join(f'cov_{i:02d}' for i in range(12))
                + f' + {term}')
        for line in _wrap_footer(text, fig).split('\n'):
            assert line.count('(') == line.count(')'), f'split a term: {line!r}'
    plt.close(fig)


def test_the_wrapper_leaves_no_measuring_artists_behind():
    """It measures by drawing throwaway text; a leaked artist would print."""
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(12, 7.5), dpi=100)
    _wrap_footer('Formula: y ~ ' + ' + '.join(f'c{i}' for i in range(30)), fig)
    assert len(fig.texts) == 0, f'{len(fig.texts)} artist(s) left on the figure'
    plt.close(fig)


def test_the_grouping_columns_are_dropped_without_a_grouping_factor():
    """In a plain LM every row is its own unit, so 'indep.' only repeats n and
    'varies' is blank; printing them would be an empty column."""
    os.makedirs(OUT, exist_ok=True)
    csv = os.path.join(OUT, 'toy_lm.csv')
    toy(collinear=True).to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file = csv
    o.y, o.x, o.covariate = 'y', 'grp', 'a, b, c, d'      # no id -> plain LM
    o.out_dir, o.figure_display = OUT, 'save_only'
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    section = k._summary_text()
    section = section[section.index('COLLINEARITY'):]
    header = section.splitlines()[2]
    assert 'indep.' not in header and 'varies' not in header, header
    assert 'VIF' in header and ' n ' in header, header
    # ... and they come back when there is one.
    grouped = fit(toy(collinear=True))._summary_text()
    grouped = grouped[grouped.index('COLLINEARITY'):]
    assert 'indep.' in grouped.splitlines()[2]


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
