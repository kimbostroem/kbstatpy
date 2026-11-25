#!/usr/bin/env python3
"""Tests for how the fixed-effect structure is chosen, reported and compared.

`options.x = 'a, b, c'` builds an additive model, which asserts that each
factor's effect is the same at every level of the others. The post-hoc contrast
is then identical in every cell by construction -- five rows of the same
numbers, which reads as several tests that happen to agree exactly rather than
one test shown several times. These tests pin the three things that follow: the
structure is named, the repeats are blanked in the summary but kept in the
exported table, and the optional comparison table reports alternatives without
selecting between them.

Also guards the information criteria. lmer fits by REML, whose likelihood is not
comparable across fixed-effect structures, so AIC/BIC/logLik come from an ML
refit while everything else stays REML.

Run:  python3 tests/test_model_structure.py
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat, _blank_repeated_contrasts   # noqa: E402
from kbstatpy.options import KbstatOptions                      # noqa: E402


def toy_data(seed=0, n_subj=16, n_rep=4, interaction=0.0):
    """Three crossed two-level factors. Additive in truth unless `interaction`
    plants a grp:limb effect."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        re_ = rng.normal(scale=0.3)
        for a in ('ctrl', 'test'):
            for b in ('open', 'closed'):
                for c in ('sl', 'wl'):
                    for _ in range(n_rep):
                        y = (1 + 0.4 * (a == 'ctrl') + 0.3 * (b == 'open')
                             + 0.2 * (c == 'sl')
                             + interaction * (a == 'ctrl') * (c == 'sl')
                             + re_ + rng.normal(scale=0.4))
                        rows.append({'subject': f'S{s:02d}', 'grp': a,
                                     'eyes': b, 'limb': c, 'Y': y})
    return pd.DataFrame(rows)


def fit(plant_interaction=0.0, **opts):
    """`plant_interaction` sizes a real grp:limb effect in the generated data.
    Not to be confused with the kbstatpy option `interaction`, which goes
    through **opts and changes the model rather than the truth."""
    o = KbstatOptions()
    o.y = 'Y'; o.x = 'grp, eyes, limb'; o.id = 'subject'
    o.distribution = 'normal'
    o.figure_display = 'save_only'
    for k, v in opts.items():
        setattr(o, k, v)
    k = Kbstat(o)
    k.data = toy_data(interaction=plant_interaction)
    # These tests were written when '' (additive) was the default structure. It
    # is 'auto' now, so the additive baseline has to be requested explicitly.
    if 'interaction' not in opts:
        k.options.interaction = ''
    k._normalize_options()
    k.fit()
    k.anova()
    k.posthoc_table = k.posthoc()
    return k


def test_structure_is_named_in_the_summary():
    """The additive default is an assumption, so it has to be on the page."""
    assert 'additive' in fit()._model_structure_label()
    assert fit(interaction='grp, eyes, limb')._model_structure_label() == 'full factorial'


def test_additive_model_repeats_the_contrast():
    """Not a defect: with no interaction the contrast cannot vary by cell. If
    this ever stops holding, the blanking below is wrong too."""
    ph = fit().posthoc_table
    assert len(ph) > 1, 'no stratified rows, test is vacuous'
    for col in ('t', 'p'):
        assert ph[col].nunique() == 1, f'{col} varies in an additive model'


def test_summary_blanks_the_repeats_and_says_why():
    k = fit()
    shown, n = _blank_repeated_contrasts(k.posthoc_table, 'grp')
    assert n > 0, 'nothing was blanked'
    assert (shown['t'].astype(str) == '').sum() == len(shown) - 1, \
        'the test statistic should survive exactly once'
    txt = k._summary_text()
    assert 'no interaction' in txt and 'options.interaction' in txt, \
        'the summary does not explain the repeated rows'


def test_exported_table_keeps_every_number():
    """Blanking is a reading aid. The xlsx is data, and blanks there would
    propagate as NaN into whatever is built on it."""
    ph = fit().posthoc_table
    for col in ('t', 'df', 'p'):
        assert ph[col].notna().all(), f'{col} has holes in the exported table'
        assert pd.api.types.is_numeric_dtype(ph[col]), f'{col} is no longer numeric'


def test_interaction_model_lets_the_contrast_vary():
    ph = fit(interaction='grp, eyes, limb').posthoc_table
    assert ph['t'].nunique() > 1, 'contrasts still identical with interactions present'


def test_information_criteria_come_from_an_ml_refit():
    """REML AIC is not comparable across fixed effects; ML is. The two structures
    must not differ by the tens of units the REML values would show."""
    add, full = fit(), fit(interaction='grp, eyes, limb')
    assert add.ic_refit_ml and full.ic_refit_ml, 'the ML refit did not happen'
    assert abs(add.AIC - full.AIC) < 25, (
        f'AIC {add.AIC:.1f} vs {full.AIC:.1f}: this looks like the REML gap, '
        'not a maximum-likelihood comparison')
    assert 'ML refit' in add._summary_text(), 'the summary does not flag the refit'


def test_comparison_table_reports_without_selecting():
    k = fit(model_comparison=True)
    mc = k._compare_model_structures()
    assert mc is not None and len(mc) >= 2, 'no comparison table produced'
    assert set(mc['Structure']) >= {'additive', 'full factorial'}
    assert mc['dAIC'].min() == 0 and (mc['dAIC'] >= 0).all()
    # the fitted structure is marked, and it is the one the options asked for
    assert (mc['fitted'] != '').sum() == 1, 'exactly one row should be marked fitted'
    assert mc.loc[mc['fitted'] != '', 'Structure'].iloc[0] == 'additive'
    # and the analysis itself is unchanged by the table existing
    assert k._model_structure_label().startswith('additive')


def test_comparison_is_skipped_when_there_is_nothing_to_compare():
    """One factor admits no interaction; an explicit formula is the caller's."""
    k = fit(); k.options.x = ['grp']
    assert k._compare_model_structures() is None
    k2 = fit(); k2.options.formula = 'Y ~ grp + eyes + (1|subject)'
    assert k2._compare_model_structures() is None


def test_comparison_is_off_by_default():
    assert KbstatOptions().model_comparison is False


def test_verdict_keeps_the_fitted_structure_when_nothing_beats_it():
    """On additive data the additive fit is both best and smallest, so the
    verdict must not invent a reason to change."""
    k = fit(model_comparison=True)
    mc = k._compare_model_structures()
    verdict = ' '.join(k._model_comparison_verdict(mc))
    assert 'nothing here argues for changing it' in verdict, verdict
    assert 'your decision' not in verdict, 'warned about a change it did not recommend'


def test_verdict_names_a_better_structure_when_one_exists():
    """With a planted interaction the additive fit is badly beaten, and the
    verdict has to say so -- and carry the post-selection caveat."""
    k = fit(plant_interaction=0.9, model_comparison=True)
    mc = k._compare_model_structures()
    assert mc.loc[mc['Structure'] == 'additive', 'dAIC'].iloc[0] > 10, \
        'the planted interaction did not separate the structures, test is vacuous'
    verdict = ' '.join(k._model_comparison_verdict(mc))
    assert 'additive' not in verdict.split('against the fitted')[0], verdict
    assert 'your decision' in verdict and 'optimistic' in verdict, \
        'recommended a change without the post-selection caveat'


def test_verdict_refuses_to_choose_inside_the_indifference_band():
    """A gap of a fraction of an AIC unit is not a result. Structures within the
    band must be reported as indistinguishable however the AIC column sorts."""
    k = fit(model_comparison=True)
    mc = k._compare_model_structures().copy()
    mc['AIC'] = [100.0, 99.0, 99.5]          # best is NOT the fitted row
    mc['dAIC'] = mc['AIC'] - mc['AIC'].min()
    verdict = ' '.join(k._model_comparison_verdict(mc))
    assert 'do not' in verdict and 'choose between them' in verdict, verdict
    # parsimony breaks the tie towards the fitted (smallest) structure
    assert 'nothing here argues for changing it' in verdict, verdict


def test_indifference_band_is_the_conventional_two_units():
    assert Kbstat._AIC_INDIFFERENCE == 2.0


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
