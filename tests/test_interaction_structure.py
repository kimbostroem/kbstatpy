#!/usr/bin/env python3
"""Tests for `interaction` as a structure: 'auto', 'all', and an integer order.

Before these existed, `interaction` could only name its terms, so a full
factorial meant retyping every factor in `x`, and a design with an empty cell
failed in a way nobody could act on: lme4 silently dropped the rank-deficient
column ("fixed-effect model matrix is rank deficient so dropping 1 column"),
`fit()` succeeded, and `anova()` then died inside R with a `rbind` error about
mismatched column counts, naming neither the term nor the cells at fault.

The structure keywords resolve against the DESIGN MATRIX only -- which cells
were observed -- never against the response. That is what separates this from
model selection: a term whose cells are missing cannot be estimated whatever the
data say, so dropping it is forced rather than chosen, and no p-value is
influenced by the choice. `options.model_comparison` is the other case, where the
likelihood is consulted and kbstatpy therefore reports instead of choosing.

The distinction the tests below guard most carefully is whole-term versus
partial estimability. A 3x3 with one empty cell leaves an interaction with 3 of
its 4 degrees of freedom estimable; dropping the term there would discard real
contrasts, so only wholly unestimable terms (0 df) are removed.

Needs R + glmmTMB.

Run:  python3 tests/test_interaction_structure.py
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

OUT = '/tmp/kbstatpy_interaction'


def toy(levels, drop=(), n_subj=24, seed=1):
    """A crossed design over `levels` ({factor: [level, ...]}), with the cells in
    `drop` never observed."""
    import itertools
    rng = np.random.default_rng(seed)
    names = list(levels)
    rows = []
    for s in range(n_subj):
        re_ = rng.normal(scale=0.5)
        for combo in itertools.product(*(levels[n] for n in names)):
            if combo in drop:
                continue
            for _ in range(2):
                row = dict(zip(names, combo))
                row.update(y=5.0 + re_ + rng.normal(), subj=f's{s}')
                rows.append(row)
    return pd.DataFrame(rows)


def fit(df, interaction, factors='A, B', steps=('fit',)):
    o = KbstatOptions()
    o.y, o.x, o.id = 'y', factors, 'subj'
    o.interaction = interaction
    o.out_dir, o.figure_display = OUT, 'save_only'
    k = Kbstat(o)
    k.data = df.copy()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k._normalize_options(); k._apply_categorical()
        for step in steps:
            getattr(k, step)()
    return k


AB = {'A': ['a1', 'a2'], 'B': ['b1', 'b2']}
ABC = {'A': ['a1', 'a2'], 'B': ['b1', 'b2'], 'C': ['c1', 'c2']}
A3B3 = {'A': ['a1', 'a2', 'a3'], 'B': ['b1', 'b2', 'b3']}

FULL_ABC = toy(ABC)
GAP_AB = toy(AB, drop={('a2', 'b2')})
GAP_ABC = toy(ABC, drop={('a2', 'b2', 'c1'), ('a2', 'b2', 'c2')})
GAP_3x3 = toy(A3B3, drop={('a3', 'b3')})


def terms_of(k):
    return [':'.join(t) for t in (k._resolve_interaction()[0] or [])]


def test_integer_order_selects_up_to_that_order():
    assert terms_of(fit(FULL_ABC, 2, 'A, B, C')) == ['A:B', 'A:C', 'B:C']
    assert terms_of(fit(FULL_ABC, 3, 'A, B, C')) == \
        ['A:B', 'A:C', 'B:C', 'A:B:C']


def test_order_one_is_the_additive_model():
    k = fit(FULL_ABC, 1, 'A, B, C')
    assert terms_of(k) == []
    assert ':' not in k._build_formula(), k._build_formula()


def test_order_above_the_factor_count_is_the_full_factorial():
    assert terms_of(fit(FULL_ABC, 9, 'A, B, C')) == \
        terms_of(fit(FULL_ABC, 'all', 'A, B, C'))


def test_all_and_auto_agree_when_everything_is_estimable():
    assert terms_of(fit(FULL_ABC, 'all', 'A, B, C')) == \
        terms_of(fit(FULL_ABC, 'auto', 'A, B, C'))


def test_auto_drops_a_wholly_unestimable_term_and_reports_it():
    k = fit(GAP_AB, 'auto')
    terms, dropped = k._resolve_interaction()
    assert terms == [], f'A:B is unestimable here, got {terms}'
    assert [t for t, _ in dropped] == [('A', 'B')], dropped
    assert dropped[0][1] == [('a2', 'b2')], f'wrong empty cell: {dropped[0][1]}'


def test_auto_gets_all_the_way_through_anova():
    """The guarded crash: fit() used to succeed and anova() then die in R."""
    k = fit(GAP_AB, 'auto', steps=('fit', 'anova', 'posthoc'))
    a = k.anova_table
    a = a.to_pandas() if hasattr(a, 'to_pandas') else a
    assert list(a['Term']) == ['A', 'B'], list(a['Term'])
    assert np.isfinite(a['p'].astype(float)).all()


def test_auto_keeps_the_estimable_terms_around_a_dropped_one():
    k = fit(GAP_ABC, 'auto', 'A, B, C')
    terms, dropped = k._resolve_interaction()
    assert [':'.join(t) for t in terms] == ['A:C', 'B:C'], terms
    assert {':'.join(t) for t, _ in dropped} == {'A:B', 'A:B:C'}, dropped


def test_partially_estimable_terms_are_kept():
    """3x3 with one empty cell: A:B keeps 3 of its 4 df, so removing the whole
    term would discard estimable contrasts that nothing forces us to lose."""
    for spec in ('auto', 'all', 2):
        k = fit(GAP_3x3, spec)
        terms, dropped = k._resolve_interaction()
        assert [':'.join(t) for t in terms] == ['A:B'], f'{spec}: {terms}'
        assert dropped == [], f'{spec}: partial estimability must not drop: {dropped}'


def test_all_raises_instead_of_dropping():
    for spec in ('all', 2):
        try:
            fit(GAP_AB, spec)
        except ValueError as e:
            assert 'not estimable' in str(e), str(e)
            assert 'A:B' in str(e), f'the term must be named: {e}'
            assert 'a2/b2' in str(e), f'the empty cell must be named: {e}'
            assert "interaction='auto'" in str(e), f'offer the way out: {e}'
        else:
            raise AssertionError(f'interaction={spec!r} should raise on an '
                                 'unestimable term')


def test_summary_states_requested_fitted_and_dropped():
    k = fit(GAP_ABC, 'auto', 'A, B, C', steps=('fit', 'anova', 'posthoc'))
    txt = k._summary_text()
    assert 'INTERACTION STRUCTURE' in txt
    assert "options.interaction='auto'" in txt
    assert 'Fitted   : A:C, B:C' in txt, txt[txt.find('INTERACTION'):][:300]
    assert 'A:B  -- empty: a2/b2' in txt, txt[txt.find('INTERACTION'):][:400]


def test_estimability_markers_are_explained():
    """emmeans::joint_tests marks a reduced term with 'e' and collects the
    unattributable df in a row called '(confounded)'. Its own one-line legend
    does not survive into kbstatpy's table, so both arrive unexplained -- in the
    one situation where a reader most needs them explained."""
    k = fit(GAP_3x3, 'auto', steps=('fit', 'anova', 'posthoc'))
    a = k.anova_table
    a = a.to_pandas() if hasattr(a, 'to_pandas') else a
    assert '(confounded)' in list(a['Term'].astype(str)), \
        f'test is vacuous, no confounded row: {list(a["Term"])}'
    txt = k._summary_text()
    assert 'estimability markers' in txt, 'the markers go unexplained'
    assert 'belong to no one' in txt, 'the (confounded) row must be explained'
    assert 'df1 was REDUCED' in txt, "the 'e' marker must be explained"
    assert 'joint_tests' in txt, 'say where the markers come from'


def test_the_marker_note_stays_away_when_nothing_is_confounded():
    k = fit(FULL_ABC, 'auto', 'A, B, C', steps=('fit', 'anova', 'posthoc'))
    assert 'estimability markers' not in k._summary_text(), \
        'a complete design must not carry the note'


def test_interaction_structure_precedes_the_results():
    """It describes the model, so it belongs with MODEL INFORMATION -- and the
    marker note points at it as being 'above'."""
    txt = fit(GAP_3x3, 'auto', steps=('fit', 'anova', 'posthoc'))._summary_text()
    assert txt.index('MODEL INFORMATION') < txt.index('INTERACTION STRUCTURE') \
        < txt.index('ANOVA (Type III)'), 'structure must come before the results'


def test_explicit_spellings_are_untouched():
    assert fit(FULL_ABC, 'A, B', 'A, B, C')._build_formula() == \
        'y ~ A * B + C + (1 | subj)'
    assert fit(FULL_ABC, [['A', 'B'], ['B', 'C']], 'A, B, C')._build_formula() == \
        'y ~ A * B + B * C + (1 | subj)'
    assert fit(FULL_ABC, '', 'A, B, C')._build_formula() == \
        'y ~ A + B + C + (1 | subj)'


def test_bad_values_are_rejected():
    for bad in (0, -1, True):
        try:
            fit(FULL_ABC, bad, 'A, B, C')
        except ValueError:
            pass
        else:
            raise AssertionError(f'interaction={bad!r} should raise')


def test_auto_and_all_are_reserved_factor_names():
    df = FULL_ABC.rename(columns={'A': 'auto'})
    try:
        fit(df, 'all', 'auto, B, C')
    except ValueError as e:
        assert 'reserved' in str(e), str(e)
    else:
        raise AssertionError('a factor named "auto" must be rejected')


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
