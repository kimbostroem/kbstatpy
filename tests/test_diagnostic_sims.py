#!/usr/bin/env python3
"""Tests for the DHARMa simulation count behind the diagnostic residuals.

A DHARMa quantile residual is the observation's position in the empirical CDF
of n_sim simulated datasets, so it can only take the values k/n_sim. The most
extreme value expressible is qnorm(1/n_sim), and everything beyond it is capped
at z = +/-7. At DHARMa's default of 250 that limit is z = +/-2.65: observations
past it collapse onto that one value, which draws horizontal rows at the ends
of the Q-Q plot, and the capped count is inflated by the same mechanism (one
real fit reported 1.44% capped at 250 simulations and 0.20% at 3028).

options.diagnostic_sims scales the count with the data instead. These tests
pin the rule, including the memory budget that keeps DHARMa's n_obs x n_sim
matrix from running away on a large fit.

Run:  python3 tests/test_diagnostic_sims.py
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')

import numpy as np
import scipy.stats as stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

DHARMA_DEFAULT = 250        # what the library used unconditionally before 1.17.0


def sims_for(n_obs, **opts):
    k = Kbstat(KbstatOptions())
    for key, v in opts.items():
        setattr(k.options, key, v)
    k.n_obs_fit = n_obs
    return k._diagnostic_sims()


def test_never_below_the_old_hardcoded_default():
    """Whatever the rule decides, it may not under-resolve relative to what the
    library already did — that would be a regression in every panel."""
    for n in (10, 100, 1000, 7061, 18589, 60000, 500000):
        assert sims_for(n) >= DHARMA_DEFAULT, f'n_obs={n} got {sims_for(n)} simulations'


def test_small_fits_get_the_floor():
    """Below the floor, 2 x n_obs would be uselessly coarse."""
    assert sims_for(100) == 1000, sims_for(100)
    assert sims_for(500) == 1000, sims_for(500)


def test_mid_size_fits_get_full_tail_resolution():
    """2 x n_obs resolves the most extreme order statistic, whose tail
    probability is about 1/(2 n_obs), instead of collapsing it onto the grid."""
    n = 2000
    ns = sims_for(n)
    assert ns >= 2 * n, f'expected at least {2 * n} simulations, got {ns}'
    # the grid must reach past the most extreme quantile the sample can show
    assert stats.norm.ppf(1 / ns) <= stats.norm.ppf(1 / (2 * n)), \
        'the grid does not reach the extreme order statistic'


def test_the_target_is_capped():
    """Without a ceiling, 2 x n_obs would keep growing with no benefit."""
    assert sims_for(50000) <= 5000, sims_for(50000)


def test_memory_budget_holds_on_large_fits():
    """DHARMa keeps an n_obs x n_sim matrix: 18 589 rows x 5000 simulations is
    some 750 MB. The product is what has to be bounded, not the count."""
    for n in (7061, 12000, 18589):
        cells = n * sims_for(n)
        assert cells <= Kbstat._SIM_CELL_BUDGET * 1.01, \
            f'n_obs={n} would allocate {cells * 8 / 1e6:.0f} MB'


def test_huge_fits_degrade_to_the_old_behaviour():
    """The floor wins over the budget past a point, so a very large fit behaves
    as it always did rather than failing."""
    assert sims_for(500000) == DHARMA_DEFAULT, sims_for(500000)


def test_resolution_beats_the_old_default_where_it_matters():
    """The whole point: on the sizes this library is used at, the extreme
    expressible z must reach further than DHARMa's default z = +/-2.65."""
    old_limit = stats.norm.ppf(1 / DHARMA_DEFAULT)
    for n in (500, 2500, 7061, 18589):
        assert stats.norm.ppf(1 / sims_for(n)) < old_limit - 0.2, \
            f'n_obs={n} resolves no further than the old default'


def test_an_explicit_count_is_honoured():
    """The option pins the count regardless of the rule."""
    assert sims_for(18589, diagnostic_sims=4000) == 4000
    assert sims_for(100, diagnostic_sims=250) == 250
    assert sims_for(7061, diagnostic_sims='auto') == sims_for(7061)


def test_a_nonsense_count_warns_and_falls_back():
    """A typo must not silently become a 2-simulation run."""
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        got = sims_for(7061, diagnostic_sims='lots')
    assert got == sims_for(7061), f'expected the auto value, got {got}'
    assert any('diagnostic_sims' in str(x.message) for x in w), 'no warning issued'


# ------------------------------------------------------------------
# Randomised residuals, and the capped points that are never drawn
# ------------------------------------------------------------------

def _fitted(**opts):
    """A gamma GLMM with planted extremes, so some observations land outside the
    simulated envelope and the capped path is exercised."""
    import pandas as pd
    rng = np.random.default_rng(0)
    rows = []
    for sub in range(12):
        re_ = rng.normal(scale=0.15)
        for ci, c in enumerate(('a', 'b', 'c')):
            for _ in range(14):
                mu = (10.0 + 4.0 * ci) * np.exp(re_)
                rows.append({'subject': f'S{sub:02d}', 'cond': c,
                             'Y': rng.gamma(shape=25.0, scale=mu / 25.0)})
    df = pd.DataFrame(rows)
    for i in (0, 50, 100, 200, 300):
        df.at[i, 'Y'] = df['Y'].max() * 12.0
    o = KbstatOptions()
    o.y = 'Y'; o.x = 'cond'; o.id = 'subject'
    o.distribution = 'gamma'; o.link = 'log'
    o.figure_display = 'save_only'
    for key, v in opts.items():
        setattr(o, key, v)
    k = Kbstat(o)
    k.data = df
    k._normalize_options()
    k.fit()
    return k


def test_residuals_are_not_snapped_to_the_simulation_grid():
    """The regression guard for the horizontal rows: without randomisation the
    residuals take only n_sim distinct values and pile up in ties at the ends."""
    k = _fitted()
    k.plot_diagnostics()
    res = np.asarray(k.model.residuals, float)
    cap = np.asarray(k._resid_capped, bool)
    inner = res[np.isfinite(res) & ~cap]
    assert inner.size > 100, 'too few interior residuals, test is vacuous'
    n_distinct = len(np.unique(np.round(inner, 9)))
    assert n_distinct >= 0.99 * inner.size, (
        f'{n_distinct} distinct values among {inner.size} residuals: they are '
        'snapping onto the simulation grid')
    _, counts = np.unique(np.round(inner, 9), return_counts=True)
    assert counts.max() <= 2, f'largest tie is {counts.max()} points'


def test_randomisation_is_reproducible():
    """Seeded, so the same fit gives the same figure twice."""
    a = _fitted(); a.plot_diagnostics()
    b = _fitted(); b.plot_diagnostics()
    assert np.allclose(np.asarray(a.model.residuals, float),
                       np.asarray(b.model.residuals, float), equal_nan=True), \
        'two identical runs produced different residuals'


def test_capped_points_are_never_drawn():
    """z = +/-7 is a placeholder for an undefined value, so nothing is plotted
    there -- the panels must not stretch out to the placeholder."""
    import matplotlib.pyplot as plt
    k = _fitted()
    k.plot_diagnostics()
    fig = plt.gcf()
    assert int(np.asarray(k._resid_capped, bool).sum()) > 0, \
        'no capped residuals, test is vacuous'
    for idx, panel in ((0, 'histogram'), (1, 'Q-Q')):
        lo, hi = fig.axes[idx].get_xlim() if idx == 0 else fig.axes[idx].get_ylim()
        assert max(abs(lo), abs(hi)) < 6.0, \
            f'{panel} axis reaches {lo:.1f}..{hi:.1f}, so a capped point was drawn'
    plt.close('all')


def test_the_figure_carries_no_capped_annotation():
    """The count is bookkeeping about the plot, not a diagnostic: it barely
    separates a sound model from a broken one, it moves with the simulation
    count and with which rows are in the frame, and the Q-Q says more about the
    tails than it does. It belongs in the text, and it used to be stamped on
    both panels."""
    import matplotlib.pyplot as plt
    k = _fitted()
    k.plot_diagnostics()
    notes = [t.get_text() for ax in plt.gcf().axes for t in ax.texts
             if 'capped' in t.get_text().lower()]
    plt.close('all')
    assert not notes, f'the figure still annotates the capped count: {notes}'


def test_summary_reports_the_capped_count():
    """What the Q-Q cannot convey is that some observations are missing from it,
    so the summary has to say so."""
    k = _fitted()
    k.plot_diagnostics()
    k.anova()
    n_cap = int(np.asarray(k._resid_capped, bool).sum())
    assert n_cap > 0, 'no capped residuals, test is vacuous'
    txt = k._summary_text()
    assert 'outside the range simulated' in txt, \
        'the summary does not say why the observations were dropped'
    assert str(n_cap) in txt, f'the count {n_cap} is missing from the summary'
    assert 'left out of' in txt, \
        'the summary does not say they are left out of the two panels'


def test_summary_records_the_simulation_count():
    """The count is chosen adaptively, so nothing else in the output records what
    a given run actually used -- and the capped count below depends on it."""
    k = _fitted()
    k.plot_diagnostics()
    k.anova()
    assert f'{k._resid_nsim} simulations' in k._summary_text(), \
        'the summary does not record the simulation count'


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
