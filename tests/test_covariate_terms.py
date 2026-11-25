#!/usr/bin/env python3
"""Covariate terms that are expressions of one column: z^2, log(w), I(z^2).

Before this, every way of asking for a curved covariate went wrong, two of
them silently:

* `covariate = 'z, z^2'` passed `z^2` into the R formula, where `^` is the
  crossing operator and `z^2` is just `z`: a linear model, reported as such,
  with nothing to say the square had gone.
* `formula = 'y ~ z + I(z^2)'` with z declared a covariate fitted the square,
  but emmeans' joint_tests folds a function of z into z's own row, so the
  ANOVA table showed z alone, and on an inverted-U it read "n.s.".
* Without the covariate declaration the same formula raised "0 (non-NA)
  cases", and `poly(z, 2)` crashed in pymer4.

Now each expression becomes its own column (kbstatpy/_terms.py). The tests
pin what the expressions mean, that the fit matches the same model built by
hand, and that the squared term reaches the ANOVA table under its label.

Run:  python3 tests/test_covariate_terms.py
"""
import os
import sys
import tempfile
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('MPLBACKEND', 'Agg')

import numpy as np                               # noqa: E402
import pandas as pd                              # noqa: E402

from kbstatpy import Kbstat, KbstatOptions       # noqa: E402
from kbstatpy import _terms as T                 # noqa: E402


def _data(tmp):
    """An inverted U in cadence with its vertex at the mean, two sexes."""
    rng = np.random.default_rng(1)
    rows = []
    for s in range(12):
        a = rng.normal(0, 15)
        sex = 'f' if s % 2 else 'm'
        for c in (50, 60, 70, 80, 90, 100, 110, 120):
            rows.append(dict(subject=f'S{s:02d}', sex=sex, cadence=c,
                             w=float(np.exp(rng.normal())),
                             power=300 + a + (20 if sex == 'm' else 0)
                             - 0.06 * (c - 85) ** 2 + rng.normal(0, 8)))
    d = pd.DataFrame(rows)
    path = os.path.join(tmp, 'power.csv')
    d.to_csv(path, index=False)
    return path, d


def _fit(path, **opts):
    o = KbstatOptions()
    o.in_file = path
    o.figure_display = 'save_only'
    o.diagnostic_sims = 50
    for k, v in opts.items():
        setattr(o, k, v)
    kb = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        kb.run()
    return kb


def _anova(kb):
    at = kb._disp_vals(kb.anova_table, 'Term')
    return dict(zip(at['Term'], at['F']))


def test_what_the_expressions_mean():
    labels = lambda e: [p if isinstance(p, str) else (p.label, p.kind)
                        for p in T.parse(e)]
    assert labels('z') == ['z']
    assert labels('z^3') == ['z', ('z^2', 'power'), ('z^3', 'power')]
    assert labels('z**2') == labels('z^2')
    assert labels('I(z^2)') == [('I(z^2)', 'transform')], 'I() must stay literal'
    assert labels('log(w)') == [('log(w)', 'transform')]
    assert labels('z^0.5') == [('z^0.5', 'transform')], 'non-integer power is a transform'
    for bad in ('z*w', 'sin(z)', '2^3'):
        try:
            T.parse(bad)
        except ValueError:
            continue
        raise AssertionError(f'{bad!r} should be refused')


def test_the_formula_rewrite_leaves_r_crossing_alone():
    f, entries, _, caret = T.rewrite_formula('y ~ (a + b)^2 + z^2', {})
    assert f == 'y ~ (a + b)^2 + z + z_pow2', f
    assert caret and entries == ['z', 'z_pow2']
    f, _, _, caret = T.rewrite_formula('y ~ z + I(z^2)', {})
    assert f == 'y ~ z + I_z_pow2' and not caret, (f, caret)
    for bad in ('y ~ group * z^2', 'y ~ poly(z, 2)'):
        try:
            T.rewrite_formula(bad, {})
        except ValueError:
            continue
        raise AssertionError(f'{bad!r} should be refused')


def test_a_squared_covariate_is_fitted_and_reported():
    with tempfile.TemporaryDirectory() as tmp:
        path, d = _fit_data = _data(tmp)
        kb = _fit(path, y='power', id='subject', covariate='cadence^2')
        F = _anova(kb)
        assert set(F) == {'cadence', 'cadence^2'}, F
        assert F['cadence^2'] > 100, f'the inverted U was not fitted: {F}'
        # Same model built by hand: z-scored cadence and its square.
        z = (d.cadence - d.cadence.mean()) / d.cadence.std()
        d2 = d.assign(cz=z, cz2=z ** 2)
        p2 = os.path.join(tmp, 'manual.csv')
        d2.to_csv(p2, index=False)
        ref = _anova(_fit(p2, y='power', id='subject', covariate='cz, cz2',
                          scale_covariates=False))
        assert abs(ref['cz2'] - F['cadence^2']) < 1e-6 * ref['cz2'], (ref, F)
        assert abs(ref['cz'] - F['cadence']) < 1e-6 * max(ref['cz'], 1), (ref, F)


def test_the_formula_spelling_gives_the_same_model_and_warns():
    with tempfile.TemporaryDirectory() as tmp:
        path, _ = _data(tmp)
        via_cov = _anova(_fit(path, y='power', id='subject', covariate='cadence^2'))
        o = KbstatOptions()
        o.in_file, o.figure_display, o.diagnostic_sims = path, 'save_only', 50
        o.formula = 'power ~ cadence^2 + (1 | subject)'
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            kb = Kbstat(o)
            kb.run()
        assert any("does NOT follow R's formula syntax" in str(x.message) for x in w), \
            'no warning that ^ departs from R'
        assert _anova(kb) == via_cov, (_anova(kb), via_cov)


def test_i_of_z_squared_reaches_the_anova_table():
    with tempfile.TemporaryDirectory() as tmp:
        path, _ = _data(tmp)
        F = _anova(_fit(path, formula='power ~ cadence + I(cadence^2) + (1 | subject)'))
        assert 'I(cadence^2)' in F, f'squared term missing from the ANOVA: {F}'


def test_undefined_values_and_factors_are_refused():
    with tempfile.TemporaryDirectory() as tmp:
        path, d = _data(tmp)
        d.assign(w=d.w - 1).to_csv(path, index=False)        # some w <= 0
        for opts, needle in ((dict(covariate='log(w)'), 'undefined'),
                             (dict(x='sex', covariate='sex^2'), 'numeric covariates only')):
            try:
                _fit(path, y='power', **opts)
            except ValueError as e:
                assert needle in str(e), e
            else:
                raise AssertionError(f'{opts} should raise')


def test_several_outcomes_reuse_the_terms():
    """The options are deep-copied per outcome and normalised again; the
    generated columns must survive that rather than be parsed a second time."""
    with tempfile.TemporaryDirectory() as tmp:
        path, d = _data(tmp)
        d.assign(power2=d.power * 2).to_csv(path, index=False)
        o = KbstatOptions()
        o.in_file, o.figure_display, o.diagnostic_sims = path, 'save_only', 50
        o.y, o.id, o.covariate = 'power, power2', 'subject', 'cadence^2, log(w)'
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            out = Kbstat(o).run()
        assert len(out.results) == 2
        for r in out.results:
            assert 'cadence_pow2' in r.formula and 'log_w' in r.formula, r.formula


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
