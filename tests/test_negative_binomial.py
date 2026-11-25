#!/usr/bin/env python3
"""Tests for `distribution = 'negative_binomial'` (glmmTMB's nbinom2).

Counts whose variance exceeds the mean were Poisson or nothing: Poisson ties
the variance to the mean, so on overdispersed counts its standard errors are
too small and its p-values too small with them. The guarded failure modes: the
family not reaching the model (estimates, theta and the rate ratio must match
a direct glmmTMB nbinom2 fit, the standard errors must exceed Poisson's on
overdispersed data), the offset and the per-y form not composing with it, and
theta, the reason to choose the family, going unreported.

Needs R + glmmTMB.

Run:  python3 tests/test_negative_binomial.py
"""
import os
import re
import shutil
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd
import rpy2.robjects as ro
from rpy2.robjects import pandas2ri
from rpy2.robjects.conversion import localconverter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat                 # noqa: E402
from kbstatpy.options import KbstatOptions         # noqa: E402

OUT = '/tmp/kbstatpy_nbinom'
THETA = 1.5


def toy(n_subj=20, n_rep=6, seed=9):
    """Overdispersed counts: negative binomial with theta = 1.5, group B at
    1.6 times the rate of A, trials of 30 or 60 s."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        u = rng.normal(scale=0.3)
        for grp, rate in (('A', 0.05), ('B', 0.08)):
            for _ in range(n_rep):
                dur = 30.0 if rng.random() < 0.3 else 60.0
                mu = dur * rate * np.exp(u)
                rows.append({'count': rng.negative_binomial(THETA, THETA / (THETA + mu)),
                             'amp': rng.normal(1.0), 'duration': dur,
                             'grp': grp, 'subject': f's{s}'})
    return pd.DataFrame(rows)


def run(**kw):
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    csv = os.path.join(OUT, 'toy.csv')
    toy().to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file, o.out_dir, o.figure_display = csv, OUT, 'save_only'
    o.y, o.x, o.id = 'count', 'grp', 'subject'
    o.distribution = 'negative_binomial'
    for k, v in kw.items():
        setattr(o, k, v)
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    return k


def direct(offset=''):
    """(A / B ratio, its z, theta) from glmmTMB nbinom2 + emmeans."""
    with localconverter(ro.default_converter + pandas2ri.converter):
        ro.globalenv['kb_nb_toy'] = toy()
    off = f' + offset({offset})' if offset else ''
    out = ro.r(f"""
        local({{
          m <- glmmTMB::glmmTMB(count ~ grp{off} + (1 | subject),
                                family = glmmTMB::nbinom2, data = kb_nb_toy)
          p <- summary(pairs(emmeans::emmeans(m, ~ grp, type = 'response')))
          c(p$ratio, p$z.ratio, sigma(m))
        }})""")
    return tuple(float(v) for v in out)


def posthoc(k, y='count'):
    res = next(r for r in k.output.results if r.y == y)
    return res.posthoc['grp'].iloc[0]


def theta_line(k):
    m = re.search(r'Negative binomial theta: ([0-9.eE+-]+)', k.output.results[0].summary)
    return float(m.group(1)) if m else None


def test_matches_a_direct_nbinom2_fit():
    k = run(offset='log(duration)')
    ratio, z, theta = direct('log(duration)')
    row = posthoc(k)
    assert abs(float(row['ratio']) - ratio) < 1e-3, (float(row['ratio']), ratio)
    assert abs(float(row['t']) - z) < 1e-3, (float(row['t']), z)
    got = theta_line(k)
    assert got is not None and abs(got - theta) / theta < 1e-3, (got, theta)


def test_theta_is_near_the_simulated_one():
    got = theta_line(run(offset='log(duration)'))
    assert 0.8 < got < 3.0, f'theta {got} far from the simulated {THETA}'


def test_wider_intervals_than_poisson_on_overdispersed_counts():
    nb = posthoc(run(offset='log(duration)'))
    po = posthoc(run(offset='log(duration)', distribution='poisson'))
    assert abs(float(nb['t'])) < abs(float(po['t'])), (nb['t'], po['t'])


def test_summary_names_the_family_and_poisson_has_no_theta():
    k = run()
    assert 'Distribution           : negative_binomial' in k.output.results[0].summary
    assert theta_line(run(distribution='poisson')) is None


def test_per_y_alongside_other_families():
    k = run(y='count, amp', distribution='negative_binomial, normal',
            offset=['log(duration)', ''])
    s = {r.y: r.summary for r in k.output.results}
    assert 'Negative binomial theta' in s['count'] and 'Negative binomial theta' not in s['amp']


def test_bare_offset_column_warns_under_negative_binomial():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        o = KbstatOptions()
        os.makedirs(OUT, exist_ok=True)
        csv = os.path.join(OUT, 'toy.csv')
        toy().to_csv(csv, index=False)
        o.in_file, o.out_dir, o.figure_display = csv, OUT, 'save_only'
        o.y, o.x, o.id = 'count', 'grp', 'subject'
        o.distribution, o.offset = 'negative_binomial', 'duration'
        Kbstat(o).run()
    assert any('log(duration)' in str(x.message) for x in w), [str(x.message) for x in w]


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
    if failures:
        print(f'\n{failures} test(s) FAILED')
        sys.exit(1)
    print('\nall tests passed')
