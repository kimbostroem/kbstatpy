#!/usr/bin/env python3
"""Tests for the repeat-blanking of the post-hoc table in `Summary.txt`.

Where the compared factor does not interact with the factors the table is split
by, emmeans returns literally the same test in every cell, and printing it once
per cell reads as several tests that happen to agree exactly. The repeats are
therefore blanked (1.18.0).

The guarded failure mode: that blanking was decided per COLUMN, against the
first row of each level pair. Cells with genuinely different tests still share a
`significance` of '***' or an `effectSize` of 'small' most of the time, so those
values were emptied out of `Summary.txt` while `Posthoc_<var>.xlsx` and the plot
showed them -- reported as missing values by a user. It also fired the
explanatory note ("the model has no interaction between ...") under a full
factorial model, where it is simply false.

A row now counts as a repeat only if its TEST repeats -- t, df and p together --
and only then are its other columns blanked where they match.

Needs R + glmmTMB.

Run:  python3 tests/test_blank_repeated_contrasts.py
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


def toy(n_subj=24, seed=3):
    """Group effect varying by cell, so the four conditional tests differ."""
    rng = np.random.default_rng(seed)
    effect = {('sl', 'open'): 0.9, ('sl', 'closed'): 1.8,
              ('wl', 'open'): 0.4, ('wl', 'closed'): 2.4}
    rows = []
    for s in range(n_subj):
        g = 'A' if s % 2 else 'B'
        re_ = rng.normal(scale=0.8)
        for limb in ('sl', 'wl'):
            for eyes in ('open', 'closed'):
                for _ in range(3):
                    mu = 4.0 + (effect[(limb, eyes)] if g == 'A' else 0.0)
                    mu += 2.5 if eyes == 'closed' else 0.0
                    rows.append({'y': mu + re_ + rng.normal(scale=1.4), 'group': g,
                                 'limb': limb, 'eyes': eyes, 'subject': f's{s}'})
    return pd.DataFrame(rows)


def fit(df, interaction=True):
    o = KbstatOptions()
    o.y, o.x, o.id = 'y', 'group, limb, eyes', 'subject'
    # Explicit either way: the default is 'auto' (every estimable interaction),
    # so the additive model is now something a test has to ask for.
    o.interaction = 'group, limb, eyes' if interaction else ''
    o.out_dir, o.figure_display = '/tmp/kbstatpy_blank', 'save_only'
    k = Kbstat(o)
    k.data = df.copy()
    k._normalize_options()
    k.fit(); k.anova(); k.posthoc()
    return k


DF = toy()


def test_distinct_tests_keep_every_column():
    """A full factorial: the four cells are different tests and must print whole."""
    k = fit(DF, interaction=True)
    shown, n_blanked = _blank_repeated_contrasts(k.posthoc_table, 'group')
    assert n_blanked == 0, f'{n_blanked} row(s) blanked although the tests differ'
    for col in ('significance', 'effectSize', 't', 'p', 'pCorr'):
        assert (shown[col].astype(str) != '').all(), \
            f'{col} lost a value:\n{shown[["limb", "eyes", col]]}'


def test_coincident_significance_is_not_blanked():
    """The reported symptom: cells agreeing on '***' by coincidence, not by
    construction. Guards the per-column comparison specifically."""
    k = fit(DF, interaction=True)
    ph = k.posthoc_table
    ph = ph.to_pandas() if hasattr(ph, 'to_pandas') else ph
    sig = ph['significance'].astype(str)
    assert (sig == sig.iloc[0]).sum() >= 2, \
        'test is vacuous: no two rows share a significance label'
    assert ph['t'].nunique() == len(ph), 'test is vacuous: the tests are not distinct'
    shown, _ = _blank_repeated_contrasts(ph, 'group')
    assert (shown['significance'].astype(str) != '').all(), \
        'a coincidental significance match was blanked'


def test_no_interaction_still_blanks_the_repeats():
    """The case the feature exists for must keep working."""
    k = fit(DF, interaction=False)
    ph = k.posthoc_table
    ph = ph.to_pandas() if hasattr(ph, 'to_pandas') else ph
    cells = ph[(ph['limb'] != 'any') & (ph['eyes'] != 'any')]
    assert cells['t'].nunique() == 1, \
        'additive model should give one identical contrast in every cell'
    shown, n_blanked = _blank_repeated_contrasts(ph, 'group')
    assert n_blanked == len(ph) - 1, \
        f'expected {len(ph) - 1} blanked rows, got {n_blanked}'
    assert (shown['t'].astype(str).iloc[1:] == '').all(), \
        'identical tests should print once'


def test_summary_note_only_appears_when_something_was_blanked():
    full = fit(DF, interaction=True)._summary_text()
    assert 'has no interaction' not in full, \
        'the no-interaction note must not appear under a full factorial model'
    add = fit(DF, interaction=False)._summary_text()
    assert 'has no interaction' in add, \
        'the note must appear when the contrast really is constant across cells'


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
