#!/usr/bin/env python3
"""Tests that a large Gaussian LMM still gets the df method it reports.

emmeans stops computing finite-sample df once a fit exceeds pbkrtest.limit /
lmerTest.limit -- both 3000 observations by default -- and quietly returns
asymptotic df = Inf instead. kbstatpy never raised those caps, so every LMM
past 3000 rows was tested by Wald z while Summary.txt claimed Kenward-Roger,
and the post-hoc effect sizes fell through to a fallback that counted the
fixed-effect columns off `model.coefs` -- an attribute only the glmmTMB wrapper
has, so on the LMM path it counted 0 and every SMD / etaSqp came out NaN.

Both were invisible below 3000 rows, which is why the demos never caught them.
These tests therefore run either side of the cap.

Needs R + lme4/lmerTest/emmeans, like the rest of kbstatpy.

Run:  python3 tests/test_large_lmm_df.py
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

EMM_CAP = 3000          # emmeans' default pbkrtest.limit / lmerTest.limit


def toy_data(n_rep, seed=0, n_subj=12):
    """A balanced within-subject design whose size is set by n_rep alone, so the
    same model can be fitted either side of emmeans' observation cap."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        subj_re = rng.normal(scale=0.5)
        for cond in ('a', 'b', 'c'):
            for _ in range(n_rep):
                rows.append({'subject': f'S{s:02d}', 'cond': cond,
                             'Y': 1.0 + subj_re + 0.3 * (cond == 'a')
                                  + rng.normal(scale=0.2)})
    return pd.DataFrame(rows)


def fit(n_rep, **opts):
    o = KbstatOptions()
    o.y = 'Y'
    o.x = 'cond'
    o.id = 'subject'
    o.distribution = 'normal'
    o.figure_display = 'save_only'
    for k, v in opts.items():
        setattr(o, k, v)
    k = Kbstat(o)
    k.data = toy_data(n_rep)
    k._normalize_options()
    k.fit()
    k.anova()
    k.posthoc_table = k.posthoc()
    return k


def small():
    """Below the cap: 12 x 3 x 50 = 1800 rows."""
    return fit(50)


def large(**opts):
    """Above emmeans' cap: 12 x 3 x 120 = 4320 rows. kr_max_obs is pinned below
    that so the fit takes the Satterthwaite route -- the one Andrea's data took,
    and the one the default kr_max_obs sends every really large fit down --
    rather than depending on whatever the shipped default happens to be."""
    return fit(120, kr_max_obs=2000, **opts)


def test_small_fit_has_finite_df():
    """Baseline — under the cap emmeans was always well behaved."""
    k = small()
    assert k.n_obs_fit < EMM_CAP, f'n={k.n_obs_fit} is not below the cap, test is vacuous'
    df2 = k.anova_table['DF2'].astype(float).to_numpy()
    assert np.all(np.isfinite(df2)), f'expected finite df below the cap, got {df2}'


def test_large_fit_keeps_finite_df():
    """The regression guard: past 3000 rows the df must still be finite."""
    k = large()
    assert k.n_obs_fit > EMM_CAP, f'n={k.n_obs_fit} is not above the cap, test is vacuous'
    df2 = k.anova_table['DF2'].astype(float).to_numpy()
    assert np.all(np.isfinite(df2)), (
        f'df2={df2} — emmeans fell back to asymptotic inference, so the '
        'observation caps were not raised')
    assert 'Chisq' not in k.anova_table.columns, (
        'a Chisq column means the Wald test ran instead of the F test')


def test_large_fit_reports_the_method_it_used():
    """The label and the table must agree: finite df are never 'asymptotic',
    and asymptotic df are never named after a finite-sample method."""
    k = large()
    label = k._df_method_label()
    assert 'asymptotic' not in label, f'finite df reported as {label!r}'
    assert label == 'Satterthwaite', f'unexpected label {label!r}'


def test_large_fit_has_numeric_posthoc_effect_sizes():
    """The NaN that started this: SMD / etaSqp must be real numbers."""
    k = large()
    for col in ('SMD', 'etaSqp'):
        vals = pd.to_numeric(k.posthoc_table[col], errors='coerce').to_numpy(dtype=float)
        assert np.all(np.isfinite(vals)), f'{col} came back non-finite: {vals}'
        assert np.all(vals > 0), f'{col} came back non-positive: {vals}'
    assert (k.posthoc_table['effectSize'].astype(str).str.len() > 0).all(), \
        'effect-size labels are empty'


def test_auto_drops_kenward_roger_on_large_fits():
    """'auto' pays for Kenward-Roger only where it is affordable; past
    kr_max_obs it uses Satterthwaite, and says so."""
    assert small()._df_method_label() == 'Kenward-Roger', \
        'a small fit should still get KR under auto (is pbkrtest installed?)'
    assert large()._df_method_label() == 'Satterthwaite', \
        'a fit past kr_max_obs should degrade to Satterthwaite under auto'
    assert fit(120, kr_max_obs=99999)._df_method_label() == 'Kenward-Roger', \
        'the same fit under a cap it does not exceed should keep KR'


def test_explicit_kenward_roger_is_honoured_past_the_cap():
    """The cap governs 'auto' only — an explicit request still gets KR, and
    with the pbkrtest limit raised so it actually applies."""
    k = fit(120, df_method='kenward-roger')
    assert k._df_method_label() == 'Kenward-Roger', \
        f'explicit KR was not honoured: {k._df_method_label()!r}'
    df2 = k.anova_table['DF2'].astype(float).to_numpy()
    assert np.all(np.isfinite(df2)), f'KR reported but df2={df2}'


def test_kr_max_obs_zero_lifts_the_cap():
    """kr_max_obs=0 means no cap, so 'auto' keeps KR at any size."""
    k = fit(120, kr_max_obs=0)
    assert k._df_method_label() == 'Kenward-Roger', \
        f'kr_max_obs=0 should leave auto on KR, got {k._df_method_label()!r}'


def test_fixed_param_count_comes_from_the_model():
    """The count behind the effect-size fallback must be the real number of
    fixed-effect columns, not the 0 that reading it off `model.coefs` gave."""
    k = small()
    assert not hasattr(k.model, 'coefs'), \
        "pymer4's lmer grew a .coefs attribute — the comment in _n_fixed_params is stale"
    # Y ~ cond with effects coding: intercept + 2 contrast columns
    assert k._n_fixed_params(k.model.r_model) == 3, \
        f'expected 3 fixed-effect columns, got {k._n_fixed_params(k.model.r_model)}'


def test_underflowed_p_prints_as_a_bound():
    """A p-value too small for a double arrives as 0; printing '0' reads as a
    defect in the test, so the summary states the bound instead."""
    from kbstatpy.kbstat import _bounded_p_table
    at = pd.DataFrame({'Term': ['a', 'b'], 'p': [0.0, 1.5e-9]})
    shown = _bounded_p_table(at)['p'].tolist()
    assert shown[0] == '<1e-308', f'underflow rendered as {shown[0]!r}'
    assert shown[1] == '1.500000e-09', f'ordinary p rendered as {shown[1]!r}'
    untouched = _bounded_p_table(pd.DataFrame({'p': [0.04, 0.5]}))['p'].tolist()
    assert untouched == [0.04, 0.5], f'a table without underflow was altered: {untouched}'


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
