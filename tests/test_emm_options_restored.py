#!/usr/bin/env python3
"""kbstatpy must leave the R session's emmeans options as it found them.

The guarded failure mode: posthoc() sets pbkrtest.limit and lmerTest.limit to the
number of observations of its own model, and pins lmer.df. Left in place, a limit
sized to a small model made a LATER emmeans call on more rows fall back silently
from Kenward-Roger to asymptotic df (different columns, different p-values), in
code outside kbstatpy that happened to run after it.

Needs R + lme4/emmeans.

Run:  python3 tests/test_emm_options_restored.py
"""
import os
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd
import rpy2.robjects as ro

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

OUT = '/tmp/kbstatpy_emm_options'


def emm_opts():
    r = ro.r('function() { o <- getOption("emmeans"); '
             'sapply(c("lmer.df", "pbkrtest.limit", "lmerTest.limit"), '
             'function(k) if (is.null(o[[k]])) "<unset>" else as.character(o[[k]])) }')()
    return dict(zip(r.names, list(r)))


def run(**kw):
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(2)
    rows = [{'y': rng.normal() + (0.5 if c == 'b' else 0), 'cond': c, 'subject': f's{s}'}
            for s in range(10) for c in ('a', 'b') for _ in range(3)]
    csv = os.path.join(OUT, 'toy.csv')
    pd.DataFrame(rows).to_csv(csv, index=False)
    o = KbstatOptions()
    o.in_file, o.out_dir, o.figure_display = csv, OUT, 'save_only'
    o.y, o.x, o.id = 'y', 'cond', 'subject'
    for k, v in kw.items():
        setattr(o, k, v)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        Kbstat(o).run()


def test_defaults_are_left_untouched():
    before = emm_opts()
    run()
    assert emm_opts() == before, f'emmeans options changed: {before} -> {emm_opts()}'


def test_user_settings_survive():
    ro.r('emmeans::emm_options(pbkrtest.limit = 12345, lmerTest.limit = 23456, lmer.df = "satterthwaite")')
    before = emm_opts()
    run()
    assert emm_opts() == before, f'user settings changed: {before} -> {emm_opts()}'


def test_restored_even_when_the_analysis_fails():
    """Fail AFTER posthoc() has set the options, so only the restore can undo them."""
    ro.r('emmeans::emm_options(pbkrtest.limit = 3000, lmerTest.limit = 3000)')
    before = emm_opts()
    original = Kbstat.plot_diagnostics

    def boom(self):
        raise RuntimeError('simulated failure after the post-hoc step')
    Kbstat.plot_diagnostics = boom
    try:
        run()
    except RuntimeError:
        pass
    finally:
        Kbstat.plot_diagnostics = original
    assert emm_opts() == before, f'options changed by a failed run: {before} -> {emm_opts()}'


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
