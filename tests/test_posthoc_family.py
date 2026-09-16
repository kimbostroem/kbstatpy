#!/usr/bin/env python3
"""Tests for `posthoc_family`, the scope of the post-hoc correction family.

The guarded failure mode: with a two-level factor compared within each cell of
the conditioning factors, every emmeans family holds exactly ONE contrast, so
Holm is the identity and `pCorr` comes out equal to `p` in every row. That is
correct for the family kbstatpy defined, but it is indistinguishable from a
correction that is simply not running, and it went unnoticed because nothing in
`Summary.txt` said how large the families were -- the header just said `holm`.
A user reported it as a bug.

`posthoc_family` makes the family explicit and offers the two wider ones:
  'pooled' -- all cells as one family, corrected in one pass;
  'cross'  -- corrected within each cell, then Bonferroni across the cells.

The dominance asserted below (pooled <= cross with one contrast per cell) holds
only at that size: with two or more contrasts per cell neither dominates, which
is why the advisory warning is gated on the family size rather than the method.

Needs R + glmmTMB.

Run:  python3 tests/test_posthoc_family.py
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

OUT = '/tmp/kbstatpy_posthoc_family'


def toy(n_subj=24, seed=0):
    """Two groups x two limbs x two eye conditions, one random intercept.

    The group effect is made to vary by cell so the four conditional contrasts
    are genuinely different tests -- otherwise the comparison between family
    scopes would be vacuous.
    """
    rng = np.random.default_rng(seed)
    effect = {('sl', 'open'): 0.9, ('sl', 'closed'): 1.8,
              ('wl', 'open'): 0.4, ('wl', 'closed'): 2.4}
    rows = []
    for s in range(n_subj):
        g = 'CAI_1' if s % 2 else 'CAI_4'
        re_ = rng.normal(scale=0.8)
        for limb in ('sl', 'wl'):
            for eyes in ('open', 'closed'):
                for _ in range(3):
                    mu = 4.0 + (effect[(limb, eyes)] if g == 'CAI_1' else 0.0)
                    mu += 2.5 if eyes == 'closed' else 0.0
                    rows.append({'y': mu + re_ + rng.normal(scale=1.4),
                                 'group': g, 'limb': limb, 'eyes': eyes,
                                 'subject': f's{s}'})
    return pd.DataFrame(rows)


def fit(df, family='cell', correction='holm', out=OUT, **kw):
    o = KbstatOptions()
    o.y, o.x, o.id = 'y', 'group, limb, eyes', 'subject'
    o.interaction = 'group, limb, eyes'
    o.posthoc_family, o.posthoc_correction = family, correction
    o.out_dir, o.figure_display = out, 'save_only'
    for k, v in kw.items():
        setattr(o, k, v)
    k = Kbstat(o)
    k.data = df.copy()
    k._normalize_options()
    k.fit(); k.anova(); k.posthoc()
    return k


def cells(k):
    """The four conditional rows, i.e. the posthoc table without its marginal
    ('any') block, which is the ANOVA term and belongs to no family."""
    ph = k.posthoc_table
    ph = ph.to_pandas() if hasattr(ph, 'to_pandas') else ph
    return ph[(ph['limb'] != 'any') & (ph['eyes'] != 'any')]


DF = toy()


def test_cell_is_an_identity_for_a_two_level_factor():
    c = cells(fit(DF, 'cell'))
    assert len(c) == 4, f'expected 4 conditional rows, got {len(c)}'
    assert np.allclose(c['p'].astype(float), c['pCorr'].astype(float)), \
        'a family of one must leave the p-value untouched'


def test_pooled_corrects_the_cells_as_one_family():
    c = cells(fit(DF, 'pooled'))
    p, pc = c['p'].astype(float).to_numpy(), c['pCorr'].astype(float).to_numpy()
    assert (pc >= p - 1e-12).all(), 'pooled must not shrink a p-value'
    assert (pc > p + 1e-12).any(), 'pooled changed nothing; test is vacuous'
    # Holm over the four raw values, computed independently of the library.
    n, order = len(p), np.argsort(p)
    want, run = np.empty(n), 0.0
    for rank, i in enumerate(order):
        run = max(run, (n - rank) * p[i])
        want[i] = min(run, 1.0)
    assert np.allclose(pc, want), f'expected Holm over 4\n  got {pc}\n  want {want}'


def test_cross_is_bonferroni_over_the_cells_at_one_contrast_each():
    c = cells(fit(DF, 'cross'))
    p, pc = c['p'].astype(float).to_numpy(), c['pCorr'].astype(float).to_numpy()
    assert np.allclose(pc, np.minimum(1.0, 4 * p)), \
        f'expected Bonferroni x 4\n  got {pc}\n  want {np.minimum(1.0, 4 * p)}'


def test_pooled_dominates_cross_at_one_contrast_per_cell():
    # The claim the warning makes; it is only true at this family size.
    a = cells(fit(DF, 'pooled'))['pCorr'].astype(float).to_numpy()
    b = cells(fit(DF, 'cross'))['pCorr'].astype(float).to_numpy()
    assert (a <= b + 1e-12).all(), f'pooled must not exceed cross\n  {a}\n  {b}'


def test_marginal_row_is_excluded_from_every_family():
    ph = {}
    for fam in ('cell', 'pooled', 'cross'):
        t = fit(DF, fam).posthoc_table
        t = t.to_pandas() if hasattr(t, 'to_pandas') else t
        marg = t[(t['limb'] == 'any') & (t['eyes'] == 'any')]
        assert len(marg) == 1, f'{fam}: expected one marginal row'
        ph[fam] = (float(marg['p'].iloc[0]), float(marg['pCorr'].iloc[0]))
    for fam, (p, pc) in ph.items():
        assert p == pc, f'{fam}: the marginal row must stay uncorrected'
    assert len({v for v in ph.values()}) == 1, \
        f'the marginal row must not depend on posthoc_family: {ph}'


def test_summary_states_the_family_size():
    txt = fit(DF, 'cell')._summary_text()
    assert "posthoc_family='cell'" in txt, 'Summary must name the family'
    assert '4 families of 1 comparison each' in txt, \
        'Summary must state how many comparisons each family held'
    assert 'pCorr equals p' in txt, \
        'Summary must say outright that the correction could not act'
    pooled = fit(DF, 'pooled')._summary_text()
    assert '1 family of 4 comparisons' in pooled
    assert 'pCorr equals p' not in pooled, \
        'the no-op note must not appear when the correction did act'


def test_exact_method_falls_back_to_cross_with_a_warning():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        k = fit(DF, 'pooled', correction='tukey')
    assert k.options.posthoc_family == 'cross', \
        f"tukey cannot be pooled; expected a fallback, got {k.options.posthoc_family!r}"
    assert any('no pooled form' in str(m.message) for m in w), \
        f'expected a fallback warning, got {[str(m.message) for m in w]}'


def test_cross_advises_pooled_when_it_is_provably_dominated():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        fit(DF, 'cross', correction='holm')
    assert any("posthoc_family='pooled'" in str(m.message) for m in w), \
        f'expected the dominance advice, got {[str(m.message) for m in w]}'
    # ... and not when the choice is a genuine one.
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        fit(DF, 'cross', correction='tukey')
    assert not any("posthoc_family='pooled'" in str(m.message) for m in w), \
        'no advice is possible for an exact within-family method'


def test_invalid_family_is_rejected():
    try:
        fit(DF, 'nested')
    except ValueError as e:
        assert 'posthoc_family' in str(e)
    else:
        raise AssertionError('an unknown posthoc_family must raise')


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
