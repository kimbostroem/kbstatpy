#!/usr/bin/env python3
"""Statistics.xlsx: each estimate carries its own 95% CI.

The guarded failure mode: the statistics table had one CI pair, `CI95_lower` /
`CI95_upper`, placed right after the `emm` column, but it was the normal-theory
CI of the raw arithmetic mean (mean +/- 1.96 SE), not the EMM's. A paper copied
emm and CI side by side, and a reviewer found point estimates outside their
own intervals. Nobody noticed earlier because on balanced data without
covariates the raw mean and the EMM nearly coincide, so the pair looked right.

Checked here on data where they do not coincide (a gamma GLMM with a covariate
confounded with the group): `emm_CI95_*` must equal emmeans' own back-
transformed CI, contain the EMM, and sit next to it; `mean_CI95_*` must be the
raw mean's CI and sit next to the mean. Also for a two-factor model (the full
interaction grid) and for y_transform, whose back-transform must reach the
limits too.

Needs R.

Run:  python3 tests/test_statistics_emm_ci.py
"""
import contextlib
import io
import os
import sys

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd
import rpy2.robjects as ro
import rpy2.robjects.pandas2ri as p2ri

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

OUT = '/tmp/kbstatpy_statistics_emm_ci'
os.makedirs(OUT, exist_ok=True)
FAILED = []


def check(name, cond, detail=''):
    print(('PASS' if cond else 'FAIL'), name, detail)
    if not cond:
        FAILED.append(name)


def data(seed=3):
    """Gamma data; the older a group, the larger y, and group b is older."""
    rng = np.random.default_rng(seed)
    rows = []
    for g, age0 in (('a', 8.0), ('b', 12.0), ('c', 10.0)):
        for s in range(8):
            age = age0 + rng.uniform(-1, 1)
            u = rng.normal(scale=0.15)
            for limb in ('L', 'R'):
                for r in range(3):
                    mu = np.exp(0.5 + 0.15 * age + u + (0.2 if limb == 'R' else 0.0))
                    rows.append({'y': rng.gamma(8.0, mu / 8.0), 'group': g, 'limb': limb,
                                 'age': age, 'subject': f'{g}{s}'})
    df = pd.DataFrame(rows)
    path = os.path.join(OUT, 'data.csv')
    df.to_csv(path, index=False)
    return df, path


def fit(path, **kw):
    o = KbstatOptions()
    o.in_file = path
    o.figure_display = 'save_only'
    o.id = 'subject'
    o.covariate = 'age'
    for k, v in kw.items():
        setattr(o, k, v)
    kb = Kbstat(o)
    with contextlib.redirect_stdout(io.StringIO()):
        kb.run()
    return kb


def r_emm(kb, spec):
    """emmeans' own response-scale grid, straight from the fitted model."""
    r_obj = getattr(kb.model, 'r_model', getattr(kb.model, 'model_obj', None))
    ro.globalenv['kbstat_test_model'] = r_obj
    # Factors as text: rpy2 would otherwise hand back their integer codes.
    emm = p2ri.rpy2py(ro.r(f'local({{d <- as.data.frame(emmeans::emmeans(kbstat_test_model, '
                           f'{spec}, type = "response")); '
                           'd[] <- lapply(d, function(v) if (is.factor(v)) as.character(v) else v); d})'))
    lo = next(c for c in ('lower.CL', 'asymp.LCL') if c in emm.columns)
    hi = next(c for c in ('upper.CL', 'asymp.UCL') if c in emm.columns)
    val = next(c for c in ('response', 'emmean', 'rate') if c in emm.columns)
    return emm.rename(columns={val: 'val', lo: 'lo', hi: 'hi'})


def column_order(st, tag):
    cols = list(st.columns)
    check(f'{tag}: no ambiguous CI95_lower column', 'CI95_lower' not in cols)
    i = cols.index('mean')
    check(f'{tag}: mean CI next to mean',
          cols[i + 1:i + 3] == ['mean_CI95_lower', 'mean_CI95_upper'], str(cols))
    i = cols.index('emm')
    check(f'{tag}: emm CI next to emm',
          cols[i + 1:i + 3] == ['emm_CI95_lower', 'emm_CI95_upper'], str(cols))


df, path = data()

# --- one factor + covariate, gamma GLMM ---
kb = fit(path, y='y', x='group', distribution='gamma', link='log')
st = kb.statistics_table
column_order(st, 'one factor')
ref = r_emm(kb, '~ group')
for _, row in st.iterrows():
    r = ref[ref['group'].astype(str) == row['group']].iloc[0]
    check(f"one factor, {row['group']}: emm CI is emmeans' CI",
          np.allclose([row['emm'], row['emm_CI95_lower'], row['emm_CI95_upper']],
                      [r['val'], r['lo'], r['hi']], rtol=1e-6),
          f"{row['emm']:.3f} ({row['emm_CI95_lower']:.3f}, {row['emm_CI95_upper']:.3f})")
    check(f"one factor, {row['group']}: emm inside its CI",
          row['emm_CI95_lower'] < row['emm'] < row['emm_CI95_upper'])
    vals = df.loc[df['group'] == row['group'], 'y']
    ci = 1.96 * vals.sem()
    check(f"one factor, {row['group']}: mean CI is the raw mean's",
          np.allclose([row['mean_CI95_lower'], row['mean_CI95_upper']],
                      [vals.mean() - ci, vals.mean() + ci]))
# The data were built so that the two differ; otherwise this test proves nothing.
b = st[st['group'] == 'b'].iloc[0]
check('discriminates: raw mean of b lies outside its emm CI',
      not (b['emm_CI95_lower'] <= b['mean'] <= b['emm_CI95_upper']),
      f"mean {b['mean']:.3f}, emm CI ({b['emm_CI95_lower']:.3f}, {b['emm_CI95_upper']:.3f})")

# --- two factors: the full interaction grid ---
kb = fit(path, y='y', x=['group', 'limb'], interaction=['group', 'limb'],
         distribution='gamma', link='log')
st = kb.statistics_table
column_order(st, 'two factors')
ref = r_emm(kb, '~ group * limb')
ok = True
for _, row in st.iterrows():
    r = ref[(ref['group'].astype(str) == row['group']) & (ref['limb'].astype(str) == row['limb'])].iloc[0]
    ok &= np.allclose([row['emm'], row['emm_CI95_lower'], row['emm_CI95_upper']],
                      [r['val'], r['lo'], r['hi']], rtol=1e-6)
check("two factors: every cell's emm CI is emmeans' CI", bool(ok))

# --- y_transform: the limits are back-transformed like the EMM ---
kb = fit(path, y='y', x='group', y_transform='log(y)')
st = kb.statistics_table
column_order(st, 'y_transform')
ref = r_emm(kb, '~ group')
ok = True
for _, row in st.iterrows():
    r = ref[ref['group'].astype(str) == row['group']].iloc[0]
    ok &= np.allclose([row['emm'], row['emm_CI95_lower'], row['emm_CI95_upper']],
                      np.exp([r['val'], r['lo'], r['hi']]), rtol=1e-6)
check('y_transform log(y): emm and its CI back-transformed', bool(ok))

if FAILED:
    print(f'\n{len(FAILED)} FAILED')
    sys.exit(1)
print('\nAll passed')
