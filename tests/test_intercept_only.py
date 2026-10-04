#!/usr/bin/env python3
"""Intercept-only models: y ~ 1 and y ~ 1 + (1 | id).

The guarded failure mode: a model with no factor and no covariate could not be
run at all. The fit succeeded, but the ANOVA is built by emmeans::joint_tests,
which has nothing to test without a factor and stopped with "There are no
factors to test". With options.x left empty the formula came out as 'y ~ ',
and an explicit `y ~ 1` had its '1' read as a factor ("Detected independent
variables: 1"), which also broke `y ~ 1 + group`, a legitimate way to write
`y ~ group`. Nobody noticed because every demo has a factor; the model only
matters once the course starts from the bottom of the ladder, with the mean as
a model, the one-sample t-test and the ICC.

Checked against the classical tests: `y ~ 1` is the one-sample t-test, and on
balanced data `y ~ 1 + (1 | id)` is the one-sample t-test on the per-unit
means. The ICC is checked against lme4's own variance components.

Needs R.

Run:  python3 tests/test_intercept_only.py
"""
import contextlib
import io
import os
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

OUT = '/tmp/kbstatpy_intercept_only'
os.makedirs(OUT, exist_ok=True)
FAILED = []


def check(name, cond, detail=''):
    print(('PASS' if cond else 'FAIL'), name, detail)
    if not cond:
        FAILED.append(name)


def data(n_subj=10, n_rep=3, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        u = rng.normal(scale=1.5)
        for r in range(n_rep):
            rows.append({'y': 2.0 + u + rng.normal(scale=1.0), 'subject': f's{s}',
                         'group': 'a' if r % 2 else 'b'})
    df = pd.DataFrame(rows)
    path = os.path.join(OUT, 'data.csv')
    df.to_csv(path, index=False)
    return df, path


def fit(path, **kw):
    o = KbstatOptions()
    o.in_file = path
    o.figure_display = 'save_only'
    for k, v in kw.items():
        setattr(o, k, v)
    kb = Kbstat(o)
    with contextlib.redirect_stdout(io.StringIO()):
        kb.run()
    return kb


df, path = data()

# --- y ~ 1 is the one-sample t-test, against 0 and against test_value ---
for tv in (None, 2.5):
    kb = fit(path, formula='y ~ 1', test_value=tv)
    it = kb.intercept_test
    ref = stats.ttest_1samp(df['y'], 0.0 if tv is None else tv)
    check(f'one-sample t-test, test_value={tv}',
          np.isclose(it['t'], ref.statistic) and np.isclose(it['p'], ref.pvalue)
          and np.isclose(it['df'], len(df) - 1),
          f"t={it['t']:.4f} vs {ref.statistic:.4f}, p={it['p']:.4g} vs {ref.pvalue:.4g}")
    check(f'mean is the sample mean, test_value={tv}', np.isclose(it['mean'], df['y'].mean()))
    d_ref = (df['y'].mean() - (0.0 if tv is None else tv)) / df['y'].std(ddof=1)
    check(f"Cohen's d, test_value={tv}", np.isclose(it['d'], d_ref),
          f"{it['d']:.4f} vs {d_ref:.4f}")

# --- the options route: x empty gives y ~ 1, with id the random intercept ---
kb = fit(path, y='y', x='', id='subject')
check('x empty builds y ~ 1 + (1 | subject)',
      kb._build_formula() == 'y ~ 1 + (1 | subject)', kb._build_formula())
means = df.groupby('subject')['y'].mean()
ref = stats.ttest_1samp(means, 0.0)
it = kb.intercept_test
check('random intercept, balanced = t-test on unit means',
      np.isclose(it['t'], ref.statistic, rtol=1e-4) and np.isclose(it['df'], len(means) - 1, rtol=1e-4),
      f"t={it['t']:.4f} vs {ref.statistic:.4f}, df={it['df']:.3f}")
check('one-row ANOVA table with F = t^2',
      len(kb.anova_table) == 1 and np.isclose(kb.anova_table['F'].iloc[0], it['t'] ** 2))
check('data plot drawn', kb.fig_data is not None)
check('statistics table has one row', kb.statistics_table is not None and len(kb.statistics_table) == 1)

# --- ICC from the variance components ---
vc = kb._variance_components()
total = sum(v for _, _, v in vc)
icc = dict((g, v) for g, _, v in vc)['subject'] / total
summary = kb._summary_text()
check('ICC reported from VarCorr', f'ICC (subject) : {icc:.3f}' in summary, f'{icc:.3f}')
check('summary names the model', 'TEST OF THE MEAN' in summary and 'ANOVA (Type III)' not in summary)

# --- the 1 in an explicit formula is not a factor ---
kb1 = fit(path, formula='y ~ 1 + group + (1 | subject)')
kb2 = fit(path, formula='y ~ group + (1 | subject)')
check("'1 + group' parses as group", kb1.options.x == ['group'], str(kb1.options.x))
check("'1 + group' fits the same model as 'group'",
      np.isclose(kb1.anova_table['p'].iloc[0], kb2.anova_table['p'].iloc[0]))
check('adjusted ICC labelled as such', 'adjusted' in kb2._summary_text())

# --- test_value: ignored with a factor, and validated ---
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter('always')
    fit(path, y='y', x='group', test_value=1)
check('test_value with a factor warns',
      any('test_value' in str(m.message) for m in w))
try:
    fit(path, formula='y ~ 1', test_value='abc')
    check('non-numeric test_value raises', False)
except ValueError:
    check('non-numeric test_value raises', True)

if FAILED:
    print(f'\n{len(FAILED)} FAILED: {FAILED}')
    sys.exit(1)
print('\nall passed')
