#!/usr/bin/env python3
"""Tests for `posthoc_compare = 'factor | conditioning factors'`.

A comparison used to be conditional on every other factor, or (in the 'any'
block) on none: with x = group, limb, eyes there was no way to compare group
within each limb, averaged over eyes, short of refitting per limb with split,
which loses the joint model. 'group | limb' is emmeans' `~ group | limb`. The
guarded failure modes: the comparison averaging over the wrong factors (its
estimates must match emmeans' own `~ group | limb`), the table showing EMMs of
one eyes level instead of the average, the plot still faceting by eyes, and
the entry's key reaching code that reads it as a factor name.

Needs R + lme4/emmeans.

Run:  python3 tests/test_posthoc_by.py
"""
import os
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

OUT = '/tmp/kbstatpy_posthoc_by'


def toy(n_subj=12, n_rep=3, seed=7):
    """Group effect 1.0 on the weak limb, 0.2 on the strong one; eyes closed
    adds 0.8 for group B only, so averaging over eyes is not the same as
    holding eyes at either level."""
    rng = np.random.default_rng(seed)
    rows = []
    for grp in ('A', 'B'):
        for s in range(n_subj):
            u = rng.normal(scale=0.4)
            for limb, eff in (('sl', 0.2), ('wl', 1.0)):
                for eyes in ('open', 'closed'):
                    for _ in range(n_rep):
                        mu = (u + (eff if grp == 'B' else 0.0)
                              + (0.8 if grp == 'B' and eyes == 'closed' else 0.0))
                        rows.append({'y': mu + rng.normal(scale=0.5), 'group': grp,
                                     'limb': limb, 'eyes': eyes,
                                     'subject': f'{grp}{s}'})
    return pd.DataFrame(rows)


def run(compare, **kw):
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    csv = os.path.join(OUT, 'toy.csv')
    toy().to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file, o.out_dir, o.figure_display = csv, OUT, 'save_only'
    o.y, o.x, o.id = 'y', 'group, limb, eyes', 'subject'
    o.posthoc_compare = compare
    o.interaction = 'all'          # the model direct() fits
    for k, v in kw.items():
        setattr(o, k, v)
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run_save()
    return k


def direct(formula_rhs):
    """emmeans' own pairs and EMM grid for `formula_rhs`, e.g. '~ group | limb'."""
    with localconverter(ro.default_converter + pandas2ri.converter):
        ro.globalenv['kb_by_toy'] = toy()
        ro.r(f"""
            kb_by_m <- lme4::lmer(y ~ group * limb * eyes + (1 | subject), data = kb_by_toy)
            kb_by_e <- emmeans::emmeans(kb_by_m, {formula_rhs})
            kb_by_p <- as.data.frame(pairs(kb_by_e, adjust = 'none'))
            kb_by_g <- as.data.frame(kb_by_e)
            if (!is.null(kb_by_p$limb)) kb_by_p$limb <- as.character(kb_by_p$limb)
            kb_by_g$limb <- as.character(kb_by_g$limb)
            kb_by_g$group <- as.character(kb_by_g$group)""")
        return ro.r('kb_by_p'), ro.r('kb_by_g')


def table(k, key):
    return k.output.results[0].posthoc[key]


def test_estimates_match_emmeans_group_by_limb():
    ph = table(run('group | limb'), 'group | limb')
    assert list(ph.columns[:3]) == ['limb', 'group_1', 'group_2'], list(ph.columns[:4])
    assert 'eyes' not in ph.columns
    cond = ph[ph['limb'] != 'any'].set_index('limb')
    pairs, _ = direct('~ group | limb')
    for _, r in pairs.iterrows():
        got = float(cond.loc[r['limb'], 'diff'])
        # save() rounds diff to 3 decimals
        assert abs(got - float(r['estimate'])) < 1e-3, (r['limb'], got, float(r['estimate']))


def test_emms_are_averaged_over_eyes():
    ph = table(run('group | limb'), 'group | limb')
    _, grid = direct('~ group * limb')
    row = ph[(ph['limb'] == 'wl')].iloc[0]
    expected = float(grid[(grid['group'] == row['group_1']) & (grid['limb'] == 'wl')]['emmean'].iloc[0])
    got = float(str(row['emm_1']).split()[0])
    assert abs(got - expected) < 1e-3, (got, expected)


def test_files_and_plot_panels():
    k = run('group | limb')
    d = os.path.join(OUT, 'y')
    assert os.path.isfile(os.path.join(d, 'Posthoc_group_by_limb.xlsx')), os.listdir(d)
    assert any(f.startswith('DataPlots_group_by_limb') for f in os.listdir(d)), os.listdir(d)
    fig = k.output.results[0].fig_data['group_by_limb']
    panels = [ax for ax in fig.axes if ax.get_visible() and ax.has_data()]
    assert len(panels) == 2, f'one panel per limb, got {len(panels)}'


def test_plain_and_by_entries_side_by_side():
    k = run('group, group | limb')
    assert set(k.output.results[0].posthoc) == {'group', 'group | limb'}
    assert 'eyes' in table(k, 'group').columns


def test_conditioning_on_all_others_is_the_plain_comparison():
    k = run('group|limb*eyes, group')
    a, b = table(k, 'group | limb * eyes'), table(k, 'group')
    assert np.allclose(a['p'].to_numpy(float), b['p'].to_numpy(float)), (a['p'], b['p'])


def test_summary_names_the_averaged_factor():
    s = run('group | limb').output.results[0].summary
    assert 'averaged over eyes' in s, s[:2000]


def test_bad_entries_are_errors():
    for spec in ('group | group', 'group | foo', 'group |', 'group | limb * limb'):
        try:
            run(spec)
        except ValueError as e:
            assert 'posthoc_compare' in str(e), e
        else:
            raise AssertionError(f'{spec!r} must be rejected')


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
