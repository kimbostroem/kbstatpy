#!/usr/bin/env python3
"""options.ordered: polynomial trend components of an ordered factor.

A factor with ordered levels -- dose steps, sets, age bands -- keeps its
post-hoc comparisons and plots, and its k-1 degrees of freedom are also split
into linear, quadratic and cubic trend components plus one joint test beyond.
Before, the only ways to ask "does it rise steadily" were to give up the
factor (a numeric covariate has no post-hoc comparisons and no plot panel) or
profile_across, which answers a different question (how another factor's
effect changes across the levels).

Checked against two independent facts rather than against a copy of the
implementation: with equal spacing the tests equal emmeans' own "poly"
contrasts, and with any spacing the orthogonal components add up to the
omnibus F of the factor (sum of t^2 plus df * F of the remainder equals
(k - 1) * F in a balanced additive model).

Run:  python3 tests/test_ordered_trend.py
"""
import os
import sys
import tempfile
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('MPLBACKEND', 'Agg')

import numpy as np                               # noqa: E402
import pandas as pd                              # noqa: E402
import rpy2.robjects as ro                       # noqa: E402

from kbstatpy import Kbstat, KbstatOptions       # noqa: E402

TOOTH = os.path.join(ROOT, 'demos', 'data', 'toothgrowth.csv')


def _run(**opts):
    o = KbstatOptions()
    o.figure_display = 'save_only'
    o.diagnostic_sims = 50
    for k, v in opts.items():
        setattr(o, k, v)
    kb = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        kb.run()
    return kb


def test_equal_spacing_matches_emmeans_poly():
    kb = _run(in_file=TOOTH, y='len', x='dose, supp', ordered='dose',
              x_order='dose: low, medium, high')
    t = kb.trend_results['dose']['table']
    ref = ro.r(f'''local({{
        suppressMessages(library(emmeans))
        d <- read.csv("{TOOTH.replace(os.sep, '/')}")
        d$dose <- factor(d$dose, levels = c("low", "medium", "high"))
        op <- options(contrasts = c("contr.sum", "contr.poly")); on.exit(options(op))
        m <- lm(len ~ dose * supp, d)
        a <- as.data.frame(contrast(emmeans(m, ~ dose), "poly"))
        b <- as.data.frame(contrast(emmeans(m, ~ dose | supp), "poly"))
        c(a$t.ratio, b$t.ratio[b$supp == "OJ"], b$t.ratio[b$supp == "VC"])
    }})''')
    ours = (list(t[t.cell == 'all'].stat) + list(t[t.cell == 'supp = OJ'].stat)
            + list(t[t.cell == 'supp = VC'].stat))
    assert np.allclose(ours, list(ref), atol=1e-6), (ours, list(ref))
    assert kb.trend_results['dose']['partners'] == ['supp']


def test_components_add_up_to_the_omnibus_with_real_spacing():
    """Six unequally spaced numeric doses: positions from the labels, a
    remainder test beyond the cubic, a mixed model, and a slope that the
    linear estimate recovers in the units of the labels."""
    rng = np.random.default_rng(3)
    doses = [0, 1, 2, 5, 10, 20]
    rows = [dict(subject=f'S{s}', dose=d, y=2.0 * d + rng.normal(0, 3) + s % 4)
            for s in range(10) for d in doses]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'dose.csv')
        pd.DataFrame(rows).to_csv(path, index=False)
        kb = _run(in_file=path, y='y', x='dose', id='subject', ordered='dose')
    tr = kb.trend_results['dose']
    assert tr['positions'] == [float(d) for d in doses], tr['positions']
    t = tr['table']
    assert list(t.component) == ['linear', 'quadratic', 'cubic',
                                 'beyond cubic (2 df, joint)'], list(t.component)
    lin = t[t.component == 'linear'].iloc[0]
    assert abs(lin.estimate - 2.0) < 0.15, f'slope per unit of dose: {lin.estimate}'
    F = float(kb.anova_table.set_index('Term').loc['dose', 'F'])
    parts = float((t.stat[:3] ** 2).sum() + 2 * t.stat.iloc[3])
    assert abs(parts - 5 * F) < 1e-5 * 5 * F + 5e-3, (parts, 5 * F)   # F is rounded to 3 places


def test_an_ordered_categorical_covariate():
    rng = np.random.default_rng(4)
    lev = ['low', 'medium', 'high']
    rows = [dict(group=g, fitness=f, y=3 * i + (2 if g == 'B' else 0) + rng.normal())
            for g in 'AB' for i, f in enumerate(lev) for _ in range(8)]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'fit.csv')
        pd.DataFrame(rows).to_csv(path, index=False)
        kb = _run(in_file=path, y='y', x='group', covariate='fitness',
                  ordered='fitness', x_order='fitness: low, medium, high')
    t = kb.trend_results['fitness']['table']
    assert list(t.component) == ['linear', 'quadratic'], list(t.component)
    assert t.iloc[0].p < 1e-10 and abs(t.iloc[0].estimate - 3) < 0.5, t
    assert set(kb.posthoc_by_var) == {'group'}, 'a covariate gets no post-hoc'


def test_refusals_name_the_way_out():
    rng = np.random.default_rng(5)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'd.csv')
        pd.DataFrame(dict(g=list('abc') * 10, z=rng.normal(size=30),
                          y=rng.normal(size=30))).to_csv(path, index=False)
        for opts, needle in ((dict(x='g', ordered='g'), 'x_order'),
                             (dict(x='g', covariate='z', ordered='z'), "'z^2'"),
                             (dict(x='g', ordered='nope'), 'not a column')):
            try:
                _run(in_file=path, y='y', **opts)
            except ValueError as e:
                assert needle in str(e), e
            else:
                raise AssertionError(f'{opts} should raise')


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
