#!/usr/bin/env python3
"""A formula and options.y are two halves of one slot.

`options.formula` overrides the fields it covers, so it ought to be usable
instead of them rather than alongside them.

`options.formula` overrides the fields it covers, so it ought to be usable
instead of them rather than alongside them. It was not: with only a formula
set, `options.y` stayed empty, run() iterated over an empty list of dependent
variables, and the analysis simply did not happen. No model, no tables, no
files, no warning -- the call returned successfully having done nothing, which
is the worst way for it to fail.

The rule is now symmetric. A formula's left-hand side is either the
placeholder `y` (case-insensitive), in which case options.y says what to put
there and may list several, or a real column name, in which case it pins that
one outcome -- which is how you look at a single model without editing
options.y. With neither, y is taken from the formula.

Before this, options.y and an explicit formula were mutually exclusive: the
run raised on the mismatch, or with options.y unset did nothing at all,
silently, having fitted no model and written no files.

Needs R.

Run:  python3 tests/test_formula_only.py
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

OUT = '/tmp/kbstatpy_formula_only'
FORMULA = 'score ~ group * condition + (1 | subject)'


def toy(n_subj=12, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        re_ = rng.normal(scale=0.3)
        for g in ('a', 'b'):
            for c in ('x', 'y'):
                for _ in range(4):
                    mu = 2 + re_ + (0.5 if g == 'b' else 0) + (0.3 if c == 'y' else 0)
                    rows.append({'score': mu + rng.normal(scale=0.4), 'group': g,
                                 'condition': c, 'subject': f's{s}'})
    return pd.DataFrame(rows)


def fit(**kw):
    os.makedirs(OUT, exist_ok=True)
    csv = os.path.join(OUT, 'toy.csv')
    toy().to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file = csv
    o.out_dir, o.figure_display = OUT, 'save_only'
    for k_, v in kw.items():
        setattr(o, k_, v)
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    return k


def frame(t):
    return None if t is None else (t.to_pandas() if hasattr(t, 'to_pandas') else t)


def test_a_formula_alone_fits_a_model():
    """The guard against the silent no-op: it must actually analyse."""
    k = fit(formula=FORMULA)
    assert k.model is not None, 'no model was fitted from the formula alone'
    a = frame(k.anova_table)
    assert a is not None and len(a) > 0, 'formula alone produced no ANOVA'


def test_it_matches_naming_the_fields_instead():
    """Two spellings of one model, so they must give one answer."""
    a = frame(fit(formula=FORMULA).anova_table)
    b = frame(fit(y='score', x='group, condition', id='subject').anova_table)
    assert list(a['Term']) == list(b['Term']), (list(a['Term']), list(b['Term']))
    assert np.allclose(np.asarray(a['p'], dtype=float),
                       np.asarray(b['p'], dtype=float))


def test_the_dependent_variable_is_taken_from_the_formula():
    """y is derived, not left empty, so everything keyed on it still works."""
    k = fit(formula=FORMULA)
    assert k.options.y == 'score', k.options.y


def test_an_explicit_y_still_wins():
    """Deriving must not overwrite what the user actually asked for."""
    k = fit(formula=FORMULA, y='score')
    assert k.options.y == 'score'
    assert frame(k.anova_table) is not None


def test_the_posthoc_still_runs_from_a_formula_alone():
    """Post-hoc keys off the fitted model, and must not need options.x."""
    k = fit(formula=FORMULA)
    assert k.posthoc_table is not None, 'no post-hoc from the formula alone'


MULTI = 'y ~ x1 + (1 | subject)'


def toy_multi(n_subj=12, seed=0):
    """Two outcomes sharing one right-hand side."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        r = rng.normal(scale=0.3)
        for g in ('a', 'b'):
            for _ in range(6):
                rows.append({'y1': 2 + r + (0.6 if g == 'b' else 0) + rng.normal(scale=.4),
                             'y2': 5 + r - (0.9 if g == 'b' else 0) + rng.normal(scale=.4),
                             'x1': g, 'subject': f's{s}'})
    return pd.DataFrame(rows)


def fit_multi(**kw):
    os.makedirs(OUT, exist_ok=True)
    csv = os.path.join(OUT, 'multi.csv')
    toy_multi().to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file = csv
    o.out_dir, o.figure_display = OUT, 'save_only'
    for k_, v in kw.items():
        setattr(o, k_, v)
    k = Kbstat(o)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        out = k.run()
    msgs = [str(w.message) for w in caught if 'unclosed' not in str(w.message)]
    return [r.formula for r in out.results], msgs


def test_the_placeholder_iterates_over_every_y():
    """The case this was built for: one right-hand side, several outcomes."""
    formulas, _ = fit_multi(y='y1, y2', formula=MULTI)
    assert formulas == ['y1 ~ x1 + (1 | subject)',
                        'y2 ~ x1 + (1 | subject)'], formulas


def test_it_matches_the_field_based_multi_y_path():
    """Two spellings of one batch, so they must fit the same models."""
    a, _ = fit_multi(y='y1, y2', formula=MULTI)
    b, _ = fit_multi(y='y1, y2', x='x1', id='subject')
    assert a == b, (a, b)


def test_an_uppercase_placeholder_is_the_same_placeholder():
    """'Y ~ ...' reads as 'y ~ ...'."""
    formulas, _ = fit_multi(y='y1, y2', formula='Y ~ x1 + (1 | subject)')
    assert formulas == ['y1 ~ x1 + (1 | subject)',
                        'y2 ~ x1 + (1 | subject)'], formulas


def test_a_real_name_on_the_left_pins_one_outcome():
    """The debugging affordance: fit one of them without editing options.y.

    Substituting here would fit the same model once per entry in options.y,
    under labels that name outcomes it never touched.
    """
    formulas, msgs = fit_multi(y='y1, y2', formula='y1 ~ x1 + (1 | subject)')
    assert formulas == ['y1 ~ x1 + (1 | subject)'], formulas
    assert any('is ignored' in m and 'y1' in m for m in msgs), msgs


def test_pinning_says_so_rather_than_ignoring_y_silently():
    """options.y was set deliberately; dropping it quietly would be worse."""
    _, msgs = fit_multi(y='y1, y2', formula='y1 ~ x1 + (1 | subject)')
    assert any("'y ~" in m for m in msgs), (
        'the warning should name the placeholder as the way to iterate', msgs)


def test_a_transform_on_the_left_keeps_its_shape():
    """log(y) must become log(y1), not y1: the transform is not the variable."""
    got = Kbstat._formula_with_y('log(y) ~ x1', 'y1')
    assert got == 'log(y1) ~ x1', got
    assert Kbstat._formula_with_y('LOG(Y) ~ x1', 'y2') == 'LOG(y2) ~ x1'


def test_an_ambiguous_left_side_is_left_alone():
    """Two names, so there is nothing to substitute without guessing."""
    assert Kbstat._formula_with_y('y1 + y2 ~ x1', 'y3') == 'y1 + y2 ~ x1'


def test_a_missing_dependent_variable_names_the_reason():
    """The placeholder with no options.y used to die inside R, naming the
    column but not why it was being looked for."""
    try:
        fit_multi(formula=MULTI)      # placeholder, no options.y, no column 'y'
    except ValueError as e:
        assert 'not a column' in str(e), e
        assert 'placeholder' in str(e), e
    else:
        raise AssertionError('no error for a dependent variable that does not exist')


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
