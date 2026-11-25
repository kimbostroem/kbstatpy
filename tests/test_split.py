#!/usr/bin/env python3
"""Tests for `options.split` and `options.split_correction`.

`split` fits the same model once per level of a column (e.g. one model per task,
when each task is its own set of trials). `split_correction` then corrects every
post-hoc contrast across those levels: the same contrast in each level forms one
family. The guarded failure modes: the correction reaching the tables but not the
plot brackets (the plots are drawn before any correction is known unless they
wait for it), a family built from the wrong rows, and results of different levels
overwriting each other on disk.

Needs R + lme4/emmeans.

Run:  python3 tests/test_split.py
"""
import os
import shutil
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat, _adjust_pvalues, _sig_stars   # noqa: E402
from kbstatpy.options import KbstatOptions                        # noqa: E402

OUT = '/tmp/kbstatpy_split'
EFFECT = {'t1': 1.2, 't2': 0.35, 't3': 0.0}          # cond B - A; t2: p < 0.05 alone, not after correction


def toy(n_subj=14, n_rep=3, seed=11):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subj):
        u = rng.normal(scale=0.6)
        for task, eff in EFFECT.items():
            for cond in ('A', 'B'):
                for _ in range(n_rep):
                    mu = 2.0 + u + (eff if cond == 'B' else 0.0)
                    rows.append({'y': mu + rng.normal(scale=0.8),
                                 'y2': 0.5 * mu + rng.normal(scale=0.8),
                                 'cond': cond, 'task': task, 'subject': f's{s}'})
    return pd.DataFrame(rows)


def run(**kw):
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    csv = os.path.join(OUT, 'toy.csv')
    toy().to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file, o.out_dir, o.figure_display = csv, OUT, 'save_only'
    o.y, o.x, o.id = 'y', 'cond', 'subject'
    o.posthoc_correction = 'none'
    for k, v in kw.items():
        setattr(o, k, v)
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run_save()
    return k


def posthoc(res, var='cond'):
    return res.posthoc[var]


def test_one_result_per_level_in_x_order():
    k = run(split='task', x_order={'task': ['t3', 't1', 't2']})
    assert [r.split for r in k.output.results] == ['t3', 't1', 't2'], \
        [r.split for r in k.output.results]
    for r in k.output.results:
        assert set(r.data['task']) == {r.split}, f'{r.split}: fitted on {set(r.data["task"])}'


def test_psplit_is_the_correction_across_levels():
    k = run(split='task', split_correction='FDR')
    p = [float(posthoc(r)['p'].iloc[0]) for r in k.output.results]
    expected = _adjust_pvalues(p, 'fdr')
    got = [float(posthoc(r)['pSplit'].iloc[0]) for r in k.output.results]
    # save() rounds the p columns to 4 decimals, so compare at that precision.
    assert np.allclose(got, expected, atol=1e-4), f'pSplit {got} != BH of {p} = {expected}'
    for r in k.output.results:
        ph = posthoc(r)
        assert ph['significance'].tolist() == [_sig_stars(v) for v in ph['pSplit']], \
            'significance must follow pSplit'


def test_the_plot_brackets_follow_psplit():
    """The point of the feature: a contrast that is significant on its own but not
    after the correction must not get a bracket."""
    k = run(split='task', split_correction='bonferroni')
    lost = [r.split for r in k.output.results
            if float(posthoc(r)['p'].iloc[0]) < 0.05 <= float(posthoc(r)['pSplit'].iloc[0])]
    assert lost, 'toy data must contain a contrast that the correction makes non-significant'
    for r in k.output.results:
        n_sig = int((posthoc(r)['pSplit'] < 0.05).sum())
        fig = r.fig_data if not isinstance(r.fig_data, dict) else next(iter(r.fig_data.values()))
        stars = [t for ax in fig.axes for t in ax.texts if set(t.get_text()) == {'*'}]
        assert len(stars) == n_sig, f'{r.split}: {len(stars)} bracket(s), {n_sig} significant pSplit'


def test_files_are_written_per_level():
    run(split='task', split_correction='FDR')
    for lvl in EFFECT:
        d = os.path.join(OUT, 'y', lvl)
        assert os.path.isfile(os.path.join(d, 'Posthoc_cond.xlsx')), f'missing {d}/Posthoc_cond.xlsx'
        assert os.path.isfile(os.path.join(d, 'Anova.xlsx')), f'missing {d}/Anova.xlsx'
        assert 'pSplit' in pd.read_excel(os.path.join(d, 'Posthoc_cond.xlsx')).columns
    sc = pd.read_excel(os.path.join(OUT, 'y', 'SplitCorrection.xlsx'))
    assert set(sc['kind']) == {'posthoc', 'anova'}, set(sc['kind'])
    assert set(sc['task']) == set(EFFECT), set(sc['task'])


def test_without_correction_nothing_is_added():
    k = run(split='task')
    assert all('pSplit' not in posthoc(r).columns for r in k.output.results)
    assert not k.output.split_corrections
    assert not os.path.isfile(os.path.join(OUT, 'y', 'SplitCorrection.xlsx'))


def test_split_correction_needs_split():
    try:
        run(split_correction='FDR')
    except ValueError as e:
        assert 'split' in str(e), e
    else:
        raise AssertionError('split_correction without split must be rejected')


def test_works_with_a_formula_and_several_outcomes():
    k = run(y='y, y2', x='', id='', formula='y ~ cond + (1 | subject)',
            split='task', split_correction='FDR')
    assert [(r.y, r.split) for r in k.output.results] == \
        [(y, t) for y in ('y', 'y2') for t in EFFECT], [(r.y, r.split) for r in k.output.results]
    assert set(k.output.split_corrections) == {'y', 'y2'}, set(k.output.split_corrections)


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
