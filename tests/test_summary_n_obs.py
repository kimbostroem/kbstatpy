#!/usr/bin/env python3
"""Tests for the `Number of observations` line in Summary.txt.

The number a reader needs is the one the model was fitted on. Two things shrink
it behind the reader's back: outlier removal (`remove_outliers_prefit` /
`remove_outliers_postfit` flag rows that the fit then excludes) and missing
values (R drops incomplete rows itself). Reporting the input-table row count
instead overstates n, and since MATLAB kbstat reports the post-removal count it
also made the two libraries look like they disagreed on the data when they
agreed on the model.

Checks that the reported count equals the count the fit used, and that whatever
was held out is named rather than silently absorbed.

Needs R + glmmTMB, like the rest of kbstatpy.

Run:  python3 tests/test_summary_n_obs.py
"""
import os
import re
import sys

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

N_ROWS = 144           # 12 subjects x 3 conditions x 4 repeats


def toy_data(seed=0, n_subj=12, n_rep=4):
    """A balanced gamma-ish design with a handful of planted extremes, so the IQR
    rule has something to flag."""
    rng = np.random.default_rng(seed)
    conds = ['a', 'b', 'c']
    rows = []
    for s in range(n_subj):
        subj_re = rng.normal(scale=0.15)
        for c in conds:
            for _ in range(n_rep):
                mu = (10.0 + 4.0 * conds.index(c)) * np.exp(subj_re)
                rows.append({'subject': f'S{s:02d}', 'cond': c,
                             'Y': rng.gamma(shape=25.0, scale=mu / 25.0)})
    df = pd.DataFrame(rows)
    # planted outliers: one extreme per condition, far outside its group's IQR
    for c in conds:
        idx = df.index[df['cond'] == c][0]
        df.at[idx, 'Y'] = df.loc[df['cond'] == c, 'Y'].max() * 6.0
    return df


def fit(data=None, **opts):
    o = KbstatOptions()
    o.y = 'Y'
    o.x = 'cond'
    o.id = 'subject'
    o.distribution = 'gamma'
    o.link = 'log'
    o.figure_display = 'save_only'
    for k, v in opts.items():
        setattr(o, k, v)
    k = Kbstat(o)
    k.data = toy_data() if data is None else data
    k._normalize_options()
    if o.remove_outliers_prefit:
        k.remove_outliers_pre()
    k.fit()
    if o.remove_outliers_postfit:
        k.remove_outliers_post()
        k.fit()
    k.anova()
    return k


def reported_n(k):
    """The count and the parenthesised breakdown from the summary line."""
    line = next(l for l in k._summary_text().splitlines()
                if 'Number of observations' in l)
    value = line.split(':', 1)[1].strip()
    m = re.match(r'^(\d+)(?:\s*\((.*)\))?$', value)
    assert m, f'unparseable observation line: {line!r}'
    return int(m.group(1)), (m.group(2) or '')


def test_clean_data_reports_the_plain_count():
    """Nothing held out: a bare number, with no breakdown to explain away."""
    k = fit()
    n, extra = reported_n(k)
    assert n == N_ROWS, f'expected {N_ROWS}, got {n}'
    assert extra == '', f'nothing was excluded, so no breakdown belongs here: {extra!r}'


def test_prefit_outliers_are_excluded_from_the_count():
    """The regression guard: the reported n must drop by the number flagged."""
    k = fit(remove_outliers_prefit=True)
    n_flagged = int(k.data['is_outlier'].sum())
    assert n_flagged > 0, 'no outliers flagged, test is vacuous'
    n, extra = reported_n(k)
    assert n == N_ROWS - n_flagged, (
        f'reported {n}, but the fit used {N_ROWS - n_flagged} '
        f'({n_flagged} of {N_ROWS} flagged)')
    assert f'{n_flagged} excluded as outliers' in extra, (
        f'the {n_flagged} excluded rows must be named: {extra!r}')


def test_reported_count_matches_the_model():
    """Tied to the fitted object, not recomputed from the frame — so a future
    change to the exclusion path cannot drift the two apart."""
    k = fit(remove_outliers_prefit=True)
    n, _ = reported_n(k)
    assert n == k.n_obs_fit, f'summary says {n}, model used {k.n_obs_fit}'


def test_missing_values_are_named_too():
    """R silently drops incomplete rows; the summary must account for them."""
    data = toy_data()
    n_missing = 7
    data.loc[data.index[:n_missing], 'Y'] = np.nan
    k = fit(data=data)
    n, extra = reported_n(k)
    assert n == N_ROWS - n_missing, f'expected {N_ROWS - n_missing}, got {n}'
    assert f'{n_missing} with missing values' in extra, (
        f'the {n_missing} dropped rows must be named: {extra!r}')


def test_outliers_and_missing_are_reported_separately():
    """Both causes at once: the two must not be merged or double-counted."""
    data = toy_data()
    n_missing = 5
    # blank out rows that the IQR rule will not also flag, so the counts are disjoint
    data.loc[data.index[-n_missing:], 'Y'] = np.nan
    k = fit(data=data, remove_outliers_prefit=True)
    n_flagged = int(k.data['is_outlier'].sum())
    assert n_flagged > 0, 'no outliers flagged, test is vacuous'
    n, extra = reported_n(k)
    assert n == N_ROWS - n_flagged - n_missing, (
        f'reported {n}, expected {N_ROWS - n_flagged - n_missing} '
        f'({n_flagged} outliers + {n_missing} missing of {N_ROWS})')
    assert f'{n_flagged} excluded as outliers' in extra and \
           f'{n_missing} with missing values' in extra, \
        f'both causes must appear separately: {extra!r}'


def test_postfit_removal_updates_the_count():
    """Post-fit removal refits on fewer rows; the summary follows the refit."""
    k = fit(remove_outliers_postfit=True)
    n_flagged = int(k.data['is_outlier'].sum())
    n, extra = reported_n(k)
    assert n == N_ROWS - n_flagged, f'reported {n}, fit used {N_ROWS - n_flagged}'
    if n_flagged:
        assert f'{n_flagged} excluded as outliers' in extra, (
            f'the {n_flagged} post-fit exclusions must be named: {extra!r}')


def test_effect_sizes_use_the_same_count():
    """etaSqp/SMD substitute n for an infinite df2, so they must not be computed
    on a larger n than the fit saw. Needs missing values to discriminate: with
    complete data the outlier-excluded frame and the fit agree on n anyway."""
    data = toy_data()
    data.loc[data.index[-5:], 'Y'] = np.nan
    k = fit(data=data, remove_outliers_prefit=True)
    assert k.n_obs_fit < len(k.data[~k.data['is_outlier']]), \
        'missing rows did not shrink n further, test is vacuous'
    row = k.anova_table.iloc[0]
    from kbstatpy.kbstat import _f2eta_sq_p
    expected = _f2eta_sq_p(pd.Series([row['F']]), pd.Series([row['DF1']]),
                           pd.Series([row['DF2']]), k.n_obs_fit).iloc[0]
    assert np.isclose(row['etaSqp'], expected), (
        f"etaSqp {row['etaSqp']:.6g} was not computed on n={k.n_obs_fit} "
        f'(expected {expected:.6g})')


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
