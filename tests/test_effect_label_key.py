#!/usr/bin/env python3
"""Tests for the effect-size labels: both schemes, Summary.txt, STATISTICAL_NOTES.

The labels (`very small` ... `very large`) are bins centred on Cohen's values,
not cutoffs at them, and their ranges were written down nowhere but the code:
a user had to ask what they meant. Guarded here: the labels change exactly at
the tabulated edges, the STATISTICAL_NOTES table states the edges the code
uses, and Summary.txt carries a key with the measures it actually labels from
(partial eta^2 always, Cohen's d only for a Gaussian post-hoc). Since 1.49
options.effect_labels picks the scheme: 'cohen' (default), Cohen's values as
lower thresholds, as most readers expect them; 'centred', the seven bins
centred on them that were the only scheme before. Both are checked.

Needs R + lme4/glmmTMB (importing kbstatpy starts R).

Run:  python3 tests/test_effect_label_key.py
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from kbstatpy.kbstat import (Kbstat, _cohen_edges, _cohen_label, _cohen_labels,  # noqa: E402
                             _D_ANCHORS, _ETA_ANCHORS, _R_ANCHORS)
from kbstatpy.options import KbstatOptions                                      # noqa: E402

OUT = '/tmp/kbstatpy_effect_label_key'
ANCHORS = {'partial η²': _ETA_ANCHORS, "Cohen's d": _D_ANCHORS, 'r, ρ': _R_ANCHORS}


def run(**kw):
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    rng = np.random.default_rng(1)
    d = pd.DataFrame([{'y': rng.normal(g), 'n': rng.poisson(2 + g), 'grp': f'g{g}',
                       'subject': f's{s}'} for g in (0, 1) for s in range(12) for _ in range(2)])
    csv = os.path.join(OUT, 'toy.csv')
    d.to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file, o.out_dir, o.figure_display = csv, OUT, 'save_only'
    o.y, o.x, o.id = 'y', 'grp', 'subject'
    for k, v in kw.items():
        setattr(o, k, v)
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run()
    return k.output.results[0].summary


def key(summary):
    block = summary.split('EFFECT SIZE LABELS', 1)[1].split('\n\n', 1)[0]
    return block.splitlines()[2:]


SCHEMES = ('cohen', 'centred')


def test_labels_change_exactly_at_the_edges():
    for scheme in SCHEMES:
        labels = _cohen_labels(scheme)
        for anchors in ANCHORS.values():
            edges = _cohen_edges(anchors, scheme)
            assert len(edges) == len(labels) - 1, (scheme, edges)
            for i, e in enumerate(edges):
                assert _cohen_label(e - 1e-9, anchors, scheme) == labels[i], (scheme, anchors, e)
                assert _cohen_label(e, anchors, scheme) == labels[i + 1], (scheme, anchors, e)
                assert _cohen_label(-e, anchors, scheme) == labels[i + 1], 'sign must not matter'


def test_cohen_scheme_uses_the_values_as_thresholds():
    assert [_cohen_label(d, _D_ANCHORS, 'cohen') for d in (0.19, 0.2, 0.49, 0.5, 0.79, 0.8, 2.0)] == \
        ['negligible', 'small', 'small', 'medium', 'medium', 'large', 'large']
    assert _cohen_label(0.45, _D_ANCHORS, 'centred') == 'medium'      # the case users trip over
    assert _cohen_label(0.45, _D_ANCHORS, 'cohen') == 'small'


def test_statistical_notes_tables_match_the_code():
    text = open(os.path.join(ROOT, 'STATISTICAL_NOTES.md'), encoding='utf-8').read()
    body = text.split('#### Effect-size labels', 1)[1].split('\n### ', 1)[0]
    for scheme in SCHEMES:
        part = body.split(f"**`effect_labels = '{scheme}'`**", 1)[1]
        labels = _cohen_labels(scheme)
        rows = [r for r in part.splitlines() if r.startswith('| ') and not r.startswith('| Label')]
        rows = [[c.strip() for c in r.strip('|').split('|')] for r in rows[:len(labels)]]
        assert [r[0] for r in rows] == list(labels), (scheme, [r[0] for r in rows])
        for col, anchors in enumerate(ANCHORS.values(), start=1):
            nums = [float(x) for r in rows for x in re.findall(r'[0-9.]+', r[col])]
            # every edge appears twice, as an upper and as the next lower bound
            expected = [e for e in _cohen_edges(anchors, scheme) for _ in (0, 1)]
            assert np.allclose(nums, expected), (scheme, col, nums, expected)


def test_gaussian_summary_keys_eta_and_d():
    for scheme in SCHEMES:
        lines = key(run(effect_labels=scheme))
        labels = _cohen_labels(scheme)
        assert "partial eta^2" in lines[0] and "Cohen's d" in lines[0], lines[0]
        assert [l.split('  ')[1].strip() for l in lines[1:1 + len(labels)]] == list(labels)
    assert '0.425 to 0.575' in key(run(effect_labels='centred'))[4]
    assert '0.5 to 0.8' in key(run())[3], 'the default is the cohen scheme'


def test_table_labels_follow_the_option():
    for scheme in ('cohen', 'centred', 'Centered'):
        k = Kbstat(KbstatOptions())
        k.options.effect_labels = scheme
        k._normalize_options()
        assert k.options.effect_labels == ('cohen' if scheme == 'cohen' else 'centred')
    s = run(effect_labels='centred')
    assert 'negligible' not in s.split('EFFECT SIZE LABELS')[0]


def test_glmm_summary_keys_eta_only():
    lines = key(run(y='n', distribution='poisson'))
    assert 'partial eta^2' in lines[0] and "Cohen's d" not in lines[0], lines[0]


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
