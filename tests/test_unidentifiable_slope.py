#!/usr/bin/env python3
"""A random slope with one value per subject and condition: a plain error.

The guarded failure mode: `options.slope` on a paired design with one value
per subject and condition (Student's sleep data, the course's running
example) asks lme4 for as many random effects as there are observations. lme4
refuses, which is right, but the refusal reached the user as a raw R error
inside an rpy2 traceback ("RRuntimeError: Fehler: number of observations
(=20) <= number of random effects (=20) for term (0 + pill | subject) ..."),
and with slope_correlated='auto' only after a warning that kbstatpy was
refitting with an uncorrelated structure, which cannot help: the diagonal
structure has at least as many random effects as the correlated one. Nobody
saw it because every demo with slopes has several values per subject and
condition; it surfaced when the course showed the random slope as an outlook
on paired data, where the error is the point of the exercise and has to be
readable by students.

Checks: the error is a ValueError subclass with a message that names the
slope, the grouping factor and what the data lack; no R error is chained to
it; no auto-refit warning precedes it; and with two values per cell the same
model still fits.

Needs R.

Run:  python3 tests/test_unidentifiable_slope.py
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

from kbstatpy.kbstat import Kbstat, UnidentifiableRandomEffects   # noqa: E402
from kbstatpy.options import KbstatOptions                        # noqa: E402

OUT = '/tmp/kbstatpy_unidentifiable_slope'
os.makedirs(OUT, exist_ok=True)
FAILED = []

# Student's sleep data (Cushny & Peebles 1905), long format.
PILL1 = [0.7, -1.6, -0.2, -1.2, -0.1, 3.4, 3.7, 0.8, 0.0, 2.0]
PILL2 = [1.9, 0.8, 1.1, 0.1, -0.1, 4.4, 5.5, 1.6, 4.6, 3.4]


def check(name, cond, detail=''):
    print(('PASS' if cond else 'FAIL'), name, detail)
    if not cond:
        FAILED.append(name)


def write(df, name):
    path = os.path.join(OUT, name)
    df.to_csv(path, index=False)
    return path


def options(path, sub):
    o = KbstatOptions()
    o.in_file = path
    o.out_dir = os.path.join(OUT, sub)
    o.y, o.x, o.id, o.slope = 'extra', 'pill', 'subject', 'pill'
    return o


def run(o):
    """Fit, returning (exception or None, warning texts)."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                Kbstat(o).fit()
                err = None
            except Exception as e:      # noqa: BLE001 -- the type is what is tested
                err = e
    return err, [str(x.message) for x in w]


rows = [{'subject': f'S{i + 1:02d}', 'pill': p, 'extra': v}
        for i in range(10) for p, v in (('Pill 1', PILL1[i]), ('Pill 2', PILL2[i]))]
paired = write(pd.DataFrame(rows), 'sleep.csv')

for mode in ('auto', True, False):
    o = options(paired, f'paired_{mode}')
    o.slope_correlated = mode
    err, warns = run(o)
    check(f'slope_correlated={mode!r}: UnidentifiableRandomEffects',
          isinstance(err, UnidentifiableRandomEffects), repr(type(err)))
    check(f'slope_correlated={mode!r}: still a ValueError', isinstance(err, ValueError))
    msg = str(err)
    check(f'slope_correlated={mode!r}: names slope, group and what is missing',
          "'pill'" in msg and "'subject'" in msg and 'only one value per level' in msg, msg[:120])
    check(f'slope_correlated={mode!r}: no R error chained',
          err is not None and err.__cause__ is None and err.__suppress_context__)
    check(f'slope_correlated={mode!r}: no refit warning first',
          not any('refitting' in t for t in warns), [t[:60] for t in warns if 'refit' in t])

# Two values per subject and condition: the same model is estimable.
rng = np.random.default_rng(1)
rep = pd.DataFrame([dict(r, extra=r['extra'] + rng.normal(scale=0.3)) for r in rows for _ in range(2)])
err, _ = run(options(write(rep, 'sleep_rep.csv'), 'repeated'))
check('two values per cell: fits', err is None, repr(err))

print()
if FAILED:
    print(f'{len(FAILED)} FAILED:', ', '.join(FAILED))
    sys.exit(1)
print('All tests passed.')
