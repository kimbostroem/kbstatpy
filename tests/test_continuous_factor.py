#!/usr/bin/env python3
"""Measurements in options.x stop with a message; interaction='all' and an
order cross the covariates.

The guarded failure modes, both met in one notebook on a JupyterHub:

1. Three continuous measurements (54, 72 and 72 distinct values in 72 rows)
   were placed in options.x with an interaction among them. options.x makes
   every variable a factor with one level per value, so the model asked for
   about 280 000 cells. The Jupyter kernel died of memory before R could
   object, with nothing to say why. A numeric x with more than ten values,
   most of them distinct, now raises ContinuousFactor before any fitting.
   Coded numeric factors (speed 13/25, a numeric subject id) repeat their
   levels and must still pass.

2. Moved to options.covariate with interaction='all', the same variables
   entered additively without a word: 'all' and an integer order crossed the
   factors in options.x only. They now cross the covariates too. The default
   'auto' keeps covariates additive (the ANCOVA convention), and generated
   columns such as a^2's stay additive under every keyword.

Needs R.

Run:  python3 tests/test_continuous_factor.py
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

from kbstatpy.kbstat import Kbstat, ContinuousFactor   # noqa: E402
from kbstatpy.options import KbstatOptions             # noqa: E402

OUT = '/tmp/kbstatpy_continuous_factor'
os.makedirs(OUT, exist_ok=True)
FAILED = []


def check(name, cond, detail=''):
    print(('PASS' if cond else 'FAIL'), name, detail)
    if not cond:
        FAILED.append(name)


# 12 subjects x 3 conditions x 2 speeds, like the notebook's pretest table.
rng = np.random.default_rng(3)
rows = []
for s in range(12):
    for cond in ('ws', 'ps', 'bs'):
        for speed in (13, 25):
            a, b = rng.normal(5, 1), rng.normal(0, 2)
            rows.append(dict(subject=s + 1, condition=cond, speed=speed, a=a, b=b,
                             y=10 + 0.5 * a + 0.3 * b + 0.2 * a * b + rng.normal()))
PATH = os.path.join(OUT, 'data.csv')
pd.DataFrame(rows).to_csv(PATH, index=False)


def run(sub, **opts):
    """Run the analysis, returning (exception or None, warning texts, fit)."""
    o = KbstatOptions()
    o.in_file, o.out_dir, o.y, o.id = PATH, os.path.join(OUT, sub), 'y', 'subject'
    for k, v in opts.items():
        setattr(o, k, v)
    k = Kbstat(o)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                k.run()
                err = None
            except Exception as e:      # noqa: BLE001 -- the type is what is tested
                err = e
    return err, [str(x.message) for x in w], k


# 1. A measurement in x stops before any fitting, with a usable message.
err, _, _ = run('measurement_in_x', x='a, b', interaction='a, b')
check('measurement in x: ContinuousFactor', isinstance(err, ContinuousFactor), repr(err)[:120])
check('measurement in x: still a ValueError', isinstance(err, ValueError))
msg = str(err)
check('measurement in x: names the variable and the remedy',
      "'a'" in msg and '72 different values' in msg and 'options.covariate' in msg, msg[:160])

# Coded numeric factors pass: speed (2 values) and a numeric subject id.
err, _, k = run('coded_factors', x='condition, speed')
check('numeric coded factor: fits', err is None, repr(err)[:120])

# 2. Covariates and the interaction modes.
def fitted(sub, **opts):
    err, _, k = run(sub, **opts)
    return err, (k.output.results[0].formula if err is None else '')


err, f = fitted('cov_all', x='condition', covariate='a, b', interaction='all')
check("interaction='all': fits", err is None, repr(err)[:120])
check("interaction='all': crosses factor and covariates",
      'condition:a:b' in f and 'a:b' in f, f)

err, f = fitted('cov_order', x='condition', covariate='a, b', interaction=2)
check('interaction=2: fits', err is None, repr(err)[:120])
check('interaction=2: two-way terms with covariates, no three-way',
      'condition:a' in f and 'a:b' in f and 'condition:a:b' not in f, f)

err, f = fitted('cov_covariates_only', covariate='a, b', interaction='all')
check("interaction='all', covariates only: crossed", err is None and 'a:b' in f, f)

err, f = fitted('cov_auto', x='condition', covariate='a, b')
check("interaction='auto': covariates stay additive",
      err is None and ':a' not in f and 'a:' not in f, f)

err, f = fitted('cov_power', x='condition', covariate='a^2, b', interaction='all')
check("interaction='all': the generated a^2 column stays additive",
      err is None and 'a_pow2' in f and not any(
          ':' in term and 'a_pow2' in term for term in f.split(' + ')), f)

err, f = fitted('cov_named', covariate='a, b', interaction='a, b')
check('named terms: crossed', err is None and 'a * b' in f, f)

print()
if FAILED:
    print(f'{len(FAILED)} FAILED:', ', '.join(FAILED))
    sys.exit(1)
print('All tests passed.')
