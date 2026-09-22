#!/usr/bin/env python3
"""Tests for the MODEL INFORMATION link line and the fit-statistics filter.

Two failures are guarded, both of them in the block a reader consults first to
learn what was fitted.

`options.link` defaults to 'auto', and the summary echoed the option instead of
the link: every model that did not set it explicitly printed
'Link function : default'. That names no link at all, so nothing in the summary
said whether effects were additive or multiplicative -- the reader had to know
each family's default by heart. It is worst for exactly the families where it
matters, since gaussian's default is the identity and the positive-continuous
ones bring a log.

And a statistic the family does not define was printed as 'deviance : nan'.
glmmTMB returns NA for the tweedie deviance, which is a quantity that does not
exist rather than one that failed to converge, but 'nan' among the fit
statistics reads as a broken fit.

Needs R + glmmTMB.

Run:  python3 tests/test_link_reporting.py
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

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

OUT = '/tmp/kbstatpy_link_reporting'


def toy(power=1.4, n_subj=18, seed=0):
    """Positive outcome whose variance grows like mean**power.

    The power must sit strictly inside (1, 2). Gamma data looks like the
    obvious choice for a positive outcome and is the worst one available:
    gamma IS tweedie at power exactly 2, and glmmTMB estimates the power as
    1 + plogis(theta), so power 2 needs theta -> +infinity. The optimiser
    then runs the full max_iterations against a series-expansion density and
    takes minutes to not converge. Same at power 1. Stay in the interior.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        re_ = rng.normal(scale=0.25)
        for g in ('g1', 'g2'):
            for _ in range(8):
                mu = np.exp(-1.0 + re_ + (0.4 if g == 'g2' else 0.0))
                sd = 0.35 * mu ** (power / 2)
                rows.append({'y': max(1e-4, mu + rng.normal(scale=sd)),
                             'grp': g, 'subj': f's{s}'})
    return pd.DataFrame(rows)


def summary(**kw):
    os.makedirs(OUT, exist_ok=True)
    csv = os.path.join(OUT, 'toy.csv')
    toy().to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file = csv
    o.y, o.x, o.id = 'y', 'grp', 'subj'
    o.out_dir, o.figure_display = OUT, 'save_only'
    for k, v in kw.items():
        setattr(o, k, v)
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    return k._summary_text()


def field(text, label):
    m = re.search(rf'^\s*{re.escape(label)}\s*:\s*(.+)$', text, re.M)
    assert m, f'no {label!r} line in the summary'
    return m.group(1).strip()


def test_auto_link_names_the_identity_link_of_a_gaussian_fit():
    got = field(summary(), 'Link function')
    assert got == 'identity', f"expected 'identity', got {got!r}"


def test_auto_link_names_the_link_kbstatpy_resolved_to():
    """'auto' must print the resolved link, never the word 'default'.

    This test asserted 'inverse' until 1.29.0, because 'auto' then deferred to
    R's canonical link for Gamma(). Reporting the resolved link is what made
    that visible, and 'auto' now means the link kbstatpy recommends, so gamma
    resolves to a log. The assertion is kept here rather than deleted: it is
    the one that would catch 'auto' silently falling back to R's canonical
    choice again. tests/test_gamma_link_and_scale.py owns the reasoning.
    """
    got = field(summary(distribution='gamma'), 'Link function')
    assert got == 'log', f"expected 'log', got {got!r}"


def test_auto_link_names_the_log_link_under_tweedie():
    got = field(summary(distribution='tweedie'), 'Link function')
    assert got == 'log', f"expected 'log', got {got!r}"


def test_an_explicitly_asked_link_stays_visible_beside_the_fitted_one():
    """Naming the link explicitly must not hide what was actually fitted.

    Asked for the link the family would have chosen anyway: the branch under
    test is 'asked is not auto', and pairing a family with a link it cannot
    support only buys an unconverged fit. gamma with an identity link on a
    log-scale outcome sends the linear predictor non-positive and glmmTMB
    grinds against the iteration ceiling for minutes.
    """
    got = field(summary(distribution='gamma', link='log'), 'Link function')
    assert got.startswith('log') and "options.link='log'" in got, got


def test_a_statistic_the_family_does_not_define_is_omitted_not_nan():
    text = summary(distribution='tweedie')
    stats = text.split('FIT STATISTICS')[1].split('\n\n')[0]
    assert 'nan' not in stats.lower(), f'nan among the fit statistics:\n{stats}'
    assert 'AIC' in stats, f'the surviving statistics went missing too:\n{stats}'


def test_the_estimated_variance_power_is_reported():
    got = field(summary(distribution='tweedie'), 'Tweedie power')
    p = float(got.split()[0])
    assert 1.0 < p < 2.0, f'power outside the admissible interval: {got}'


def test_an_explicit_link_survives_a_refit():
    """The summary's link label must never be fed back to R as a link name.

    The label carries the asked-for value alongside the fitted one, e.g.
    "log (options.link='log')". That is a display string; R's make.link()
    rejects it. It only shows on a refit -- post-fit outlier removal fits a
    second time -- because before the first fit there is no model to ask, so
    the label falls back to a value R happens to accept. Every other test here
    fits once and so cannot see it.
    """
    text = summary(distribution='gamma', link='log',
                   remove_outliers_postfit=True)
    assert field(text, 'Link function').startswith('log')


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
