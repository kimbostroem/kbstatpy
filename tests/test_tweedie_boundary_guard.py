#!/usr/bin/env python3
"""Tests for the Tweedie boundary warning and the DHARMa simulation guard.

Failure mode guarded: a tweedie fit whose estimated power pins at the upper
bound made the diagnostics hang for over ten minutes on a 120-row dataset,
with no message, and then not converge.

The cost is not in the fit -- glmmTMB fits that data in 0.1 s -- but in
DHARMa. A compound Poisson-gamma draw is N ~ Poisson(lambda) gamma variates
summed, with lambda = mu^(2-p) / (phi * (2-p)). As p -> 2 that denominator
goes to zero: measured at p = 1.99999499, lambda reached 1.7e6, so DHARMa's
simulation needed ~2e11 gamma draws.

The guard has to be predictive. R's setTimeLimit does not help: the cost sits
inside the compiled rpois/rgamma loop and control never returns to the
interpreter to check the limit, so a fit ran past a 30 s limit for more than
ten minutes. So the simulation is priced first and declined, and the existing
deviance/Pearson fallback carries the panels.

Gamma data is used deliberately: gamma IS tweedie at power exactly 2, the
bound glmmTMB cannot reach, so it drives the estimate into the wall.

Needs R + glmmTMB.

Run:  python3 tests/test_tweedie_boundary_guard.py
"""
import os
import re
import sys
import time
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

OUT = '/tmp/kbstatpy_tweedie_boundary'
BUDGET_S = 180      # the unguarded fit ran >10 min; generous but decisive


def toy(kind, n_subj=10, seed=0):
    """`kind='boundary'` sits at power 2 exactly; `'interior'` near 1.4."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        re_ = rng.normal(scale=0.25)
        for g in ('g1', 'g2'):
            for _ in range(6):
                mu = np.exp(-1.0 + re_ + (0.4 if g == 'g2' else 0.0))
                y = (rng.gamma(9.0, mu / 9.0) if kind == 'boundary'
                     else mu + rng.normal(scale=0.35 * mu ** 0.7))
                rows.append({'y': max(1e-4, y), 'grp': g, 'subj': f's{s}'})
    return pd.DataFrame(rows)


def fit(kind, **kw):
    os.makedirs(OUT, exist_ok=True)
    csv = os.path.join(OUT, f'{kind}.csv')
    toy(kind).to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file = csv
    o.y, o.x, o.id = 'y', 'grp', 'subj'
    o.out_dir, o.figure_display = OUT, 'save_only'
    o.distribution = 'tweedie'
    for k_, v in kw.items():
        setattr(o, k_, v)
    k = Kbstat(o)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        k.run()
    return k, [str(w.message) for w in caught]


def test_a_boundary_fit_finishes_instead_of_hanging():
    """The whole point: it must return, and quickly."""
    t = time.time()
    fit('boundary')
    took = time.time() - t
    assert took < BUDGET_S, f'boundary fit took {took:.0f}s (budget {BUDGET_S}s)'


def test_the_boundary_fit_warns_and_names_the_right_family():
    """A power at the wall is not an estimate, and gamma is what the data want."""
    k, msgs = fit('boundary')
    note = k._tweedie_boundary_note()
    assert note is not None, f'no boundary note at p = {k._tweedie_power()}'
    assert "'gamma'" in note, note
    assert any('Tweedie' in m and 'gamma' in m for m in msgs), msgs


def test_the_simulation_is_declined_and_the_summary_says_so():
    """Skipping DHARMa silently would leave the panels quietly less trustworthy."""
    k, _ = fit('boundary')
    assert k._dharma_skip_reason() is not None
    txt = k._summary_text()
    assert 'were skipped' in txt, txt.split('DIAGNOSTICS')[-1][:400]
    assert 'DHARMa quantile residuals.' not in txt


def test_the_declined_fit_still_produces_usable_residuals():
    """The fallback has to actually carry the panels, not leave them empty."""
    k, _ = fit('boundary')
    r = np.asarray(k.model.residuals, dtype=float)
    assert r.size and np.isfinite(r).any(), 'no finite residuals after the skip'


def test_an_interior_fit_is_untouched():
    """The guard must not cost a well-posed tweedie fit its DHARMa residuals."""
    k, msgs = fit('interior')
    p = k._tweedie_power()
    assert 1.0 + 0.01 < p < 2.0 - 0.01, f'toy is not interior: p = {p}'
    assert k._tweedie_boundary_note() is None
    assert k._dharma_skip_reason() is None
    assert 'DHARMa quantile residuals' in k._summary_text()
    assert not any('pinned' in m for m in msgs), msgs


def test_the_simulation_rate_matches_the_closed_form():
    """The guard's arithmetic is the documented lambda, not a fudge factor."""
    k, _ = fit('boundary')
    import rpy2.robjects as ro
    r_obj = getattr(k.model, 'r_model', None)
    p = k._tweedie_power()
    phi = float(np.asarray(ro.r('sigma')(r_obj))[0])
    mu = float(np.nanmean(np.asarray(ro.r('fitted')(r_obj), dtype=float)))
    expected = mu ** (2.0 - p) / (phi * (2.0 - p))
    got = k._tweedie_sim_rate()
    assert np.isclose(got, expected, rtol=1e-6), f'{got} != {expected}'
    assert got > k._DHARMA_MAX_POISSON_RATE, got


if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print(f'PASS  {name}', flush=True)
            except AssertionError as e:
                failures += 1
                print(f'FAIL  {name}\n      {e}', flush=True)
            except Exception as e:                      # noqa: BLE001
                failures += 1
                print(f'ERROR {name}\n      {type(e).__name__}: {e}', flush=True)
    print(f'\n{"all tests passed" if not failures else f"{failures} test(s) FAILED"}')
    sys.exit(1 if failures else 0)
