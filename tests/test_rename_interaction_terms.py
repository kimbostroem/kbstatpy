#!/usr/bin/env python3
"""Display names from options.rename inside interaction terms.

With rename = 'dose -> Dose', the ANOVA table showed the main effect as 'Dose'
but the interaction as 'Treatment:dose': terms were looked up whole, and an
interaction term is never a display-name key. Nobody had looked at a renamed
factor inside an interaction closely enough to notice; demo 19 shows one.
Guarded here: every part of a term is mapped, and other values pass unchanged.

Needs R (kbstatpy starts it on import).

Run:  python3 tests/test_rename_interaction_terms.py
"""
import os
import sys

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
