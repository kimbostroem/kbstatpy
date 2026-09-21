#!/usr/bin/env python3
"""Tests for `scale_covariates`, which centres and scales the numeric covariates.

Numerical hygiene rather than a change of model: centring and scaling a
predictor that is not in an interaction divides its coefficient and its standard
error by the same number, so every t, F and p is untouched. The tests below
assert that invariance directly, because it is the whole justification for the
option -- if a p-value moved, the option would be doing something it does not
claim to.

Only `options.covariate` is affected, and that is not a restriction but the
whole numeric surface: `_apply_categorical` casts every `options.x` variable to
a factor, and a random slope must be one of those, so a covariate is the only
place a numeric predictor survives to the fit.

Needs R + glmmTMB.

Run:  python3 tests/test_scale_covariates.py
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

OUT = '/tmp/kbstatpy_scale_cov'


def toy(n_subj=20, seed=0):
    """Covariates on wildly different scales, plus a categorical one and a
    constant one, which must survive untouched."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        re_ = rng.normal(scale=0.4)
        for g in ('g1', 'g2'):
            for _ in range(6):
                rows.append({'y': 0.002 + re_ * 1e-3 + rng.normal(scale=1e-3),
                             'grp': g,
                             'big': rng.normal(loc=700, scale=90),   # newtons
                             'small': rng.normal(scale=0.01),
                             'sex': rng.choice(['f', 'm']),          # categorical
                             'flat': 5.0,                            # constant
                             'subj': f's{s}'})
    return pd.DataFrame(rows)


def fit(scale, covariate='big, small, sex, flat'):
    os.makedirs(OUT, exist_ok=True)
    csv = os.path.join(OUT, 'toy.csv')
    toy().to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file = csv
    o.y, o.x, o.id = 'y', 'grp', 'subj'
    o.covariate = covariate
    o.scale_covariates = scale
    o.out_dir, o.figure_display = OUT, 'save_only'
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    return k


def anova_of(k):
    a = k.anova_table
    a = a.to_pandas() if hasattr(a, 'to_pandas') else a
    return a.set_index('Term')


def test_the_default_is_on():
    """Costs nothing -- every test statistic is identical either way -- and
    conditions the optimisation, so it applies unless switched off."""
    assert KbstatOptions().scale_covariates is True


def test_the_export_keeps_the_original_units_and_shows_the_scaled_ones():
    """Saving only z-scores would replace the measurements with numbers in a
    different unit; saving only originals would hide what the model saw."""
    k = fit(True)
    out = k._data_for_export()
    for c in ('big', 'small'):
        assert f'{c}_scaled' in out.columns, f'{c}_scaled missing'
        assert abs(out[c].mean() - k._covariate_originals[c].mean()) < 1e-9, \
            f'{c} was not restored to its own units'
        assert abs(out[f'{c}_scaled'].mean()) < 1e-9
        assert abs(out[f'{c}_scaled'].std() - 1) < 1e-9
    # the scaled column sits next to the one it came from
    cols = list(out.columns)
    assert cols[cols.index('big') + 1] == 'big_scaled', cols
    # untouched covariates gain no companion
    assert 'sex_scaled' not in cols and 'flat_scaled' not in cols


def test_the_export_is_unchanged_when_scaling_is_off():
    k = fit(False)
    out = k._data_for_export()
    assert not [c for c in out.columns if c.endswith('_scaled')]
    assert list(out.columns) == list(k.data.columns)


def test_numeric_covariates_become_z_scores():
    k = fit(True)
    for c in ('big', 'small'):
        assert abs(k.data[c].mean()) < 1e-9, f'{c} not centred'
        assert abs(k.data[c].std() - 1) < 1e-9, f'{c} not scaled'
    assert set(k._scaled_covariates) == {'big', 'small'}, k._scaled_covariates


def test_a_categorical_covariate_is_left_alone():
    k = fit(True)
    assert 'sex' not in k._scaled_covariates
    assert set(k.data['sex'].unique()) == {'f', 'm'}


def test_a_constant_covariate_is_left_alone():
    """Its SD is zero; scaling it would divide by zero."""
    k = fit(True)
    assert 'flat' not in k._scaled_covariates
    assert (k.data['flat'] == 5.0).all()
    assert np.isfinite(k.data['flat']).all()


def test_the_factors_and_the_grouping_variable_are_untouched():
    k = fit(True)
    assert set(k.data['grp'].unique()) == {'g1', 'g2'}
    assert k.data['subj'].nunique() == 20


def test_no_test_statistic_moves():
    """The justification for the whole option."""
    a, b = anova_of(fit(False)), anova_of(fit(True))
    common = [t for t in a.index if t in b.index]
    assert common, 'no shared terms'
    for col in ('F', 'p'):
        d = (a.loc[common, col].astype(float) - b.loc[common, col].astype(float)).abs().max()
        assert d < 1e-6, f'{col} moved by {d:.2e}; scaling must not change inference'


def test_summary_says_so_only_when_it_applies():
    on, off = fit(True)._summary_text(), fit(False)._summary_text()
    assert 'COVARIATE SCALING' in on, 'the transform must be stated'
    assert 'Scaled covariates' in on, 'name which covariates were scaled'
    assert 'changes no result' in on, 'say what it does not mean'
    assert 'COVARIATE SCALING' not in off
    assert 'Scaled covariates' not in off


def test_nothing_is_claimed_when_no_covariate_is_numeric():
    k = fit(True, covariate='sex')
    assert k._scaled_covariates == []
    assert 'centred and scaled' not in k._summary_text()


def test_the_flag_takes_the_usual_spellings():
    for spelling in (True, 'true', 'on', 'yes'):
        assert fit(spelling)._scaled_covariates, f'{spelling!r} should switch it on'
    for spelling in (False, 'false', 'off', 'none'):
        assert fit(spelling)._scaled_covariates == [], f'{spelling!r} should switch it off'


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
