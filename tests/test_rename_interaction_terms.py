#!/usr/bin/env python3
"""Display names from options.rename inside interaction terms.

With rename = 'dose -> Dose', the ANOVA table showed the main effect as 'Dose'
but the interaction as 'Treatment:dose': terms were looked up whole, and an
interaction term is never a display-name key. Nobody had looked at a renamed
factor inside an interaction closely enough to notice; demo 19 shows one.
Guarded here: every part of a term is mapped, and other values pass unchanged.

Summary.txt had three more places showing the column name: the fixed
effects and the variance components, whose random-slope terms R names by coded column ('Period1' for
factor Period), and the column headers of the post-hoc table ('Period_1').

Needs R (kbstatpy starts it on import; the fit test uses lme4/emmeans).

Run:  python3 tests/test_rename_interaction_terms.py
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat                 # noqa: E402
from kbstatpy.options import KbstatOptions         # noqa: E402


def test_interaction_terms_use_display_names():
    k = Kbstat(KbstatOptions())
    k._display_names = {'dose': 'Dose', 'supp': 'Supplement'}
    df = pd.DataFrame({'Term': ['Treatment', 'dose', 'Treatment:dose',
                                'dose:supp', '(Intercept)']})
    out = list(k._disp_vals(df, 'Term')['Term'])
    assert out == ['Treatment', 'Dose', 'Treatment:Dose', 'Dose:Supplement',
                   '(Intercept)'], out



def test_coded_terms_use_display_names():
    k = Kbstat(KbstatOptions())
    k._display_names = {'Period': 'Day', 'Days': 'Time', 'a': 'A', 'subj': 'Subject'}
    k.data = pd.DataFrame({'Period': ['rested', 'deprived']})
    got = [k._disp_term(t) for t in
           ['Period1', 'Periodrested', 'Days', '(Intercept)', 'Period1:a2', 'subj.1',
            'ab1', 'Periodic', '']]
    assert got == ['Day1', 'Dayrested', 'Time', '(Intercept)', 'Day1:A2', 'Subject.1',
                   'ab1', 'Periodic', ''], got


def test_summary_variance_terms_and_posthoc_headers_renamed():
    rng = np.random.default_rng(1)
    n = 12
    d = pd.DataFrame({'subj': np.repeat(np.arange(n), 6),
                      'cond': np.tile(['a', 'b'], 3 * n)})
    d['y'] = (rng.normal(0, 1, n)[d['subj']] + (d['cond'] == 'b')
              * (1 + rng.normal(0, 0.5, n)[d['subj']]) + rng.normal(0, 0.5, len(d)))
    path = '/tmp/kbstatpy_rename_terms.csv'
    d.to_csv(path, index=False)
    o = KbstatOptions()
    o.in_file, o.figure_display = path, 'save_only'
    o.y, o.x, o.id, o.slope = 'y', 'cond', 'subj', 'cond'
    o.rename = 'cond -> Condition; subj -> Subject'
    k = Kbstat(o)
    with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter('ignore')
        k.run()
    s = k.output.results[0].summary
    fe = s[s.index('FIXED EFFECTS'):s.index('ANOVA')] if 'FIXED EFFECTS' in s else ''
    assert 'cond' not in fe, fe
    vc = s[s.index('VARIANCE COMPONENTS'):s.index('POST-HOC')]
    ph = s[s.index('POST-HOC'):]
    # depending on the fit, R names the slope terms by coded column (cond1)
    # or by level (conda, condb), and the group subj or subj.1
    assert 'Condition' in vc and 'cond' not in vc and 'subj' not in vc, vc
    assert 'Condition_1' in ph and 'cond_1' not in ph, ph[:1500]


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
