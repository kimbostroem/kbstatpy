#!/usr/bin/env python3
"""Tests that the list-valued options agree on how they spell "empty".

The guarded failure mode: these eight options are all documented in one breath
as accepting "either a Python list or a comma-separated string", but four were
declared `list = field(default_factory=list)` and four `object = ''`. Nothing
distinguished the two groups; it was drift. The visible consequence was in the
README, whose default column faithfully reported `[]` for some and `''` for
others, so two options that behave identically looked as though they did not.

They now all default to ''. Both spellings still work and normalise to the same
list, which is what makes the defaults interchangeable in the first place -- so
that equivalence is asserted here rather than assumed, since it is the whole
reason the unification is safe. correlation_control was the last holdout: its
splitting was done inline in correlate() rather than in _normalize_options, so
it alone kept the spelling it was given.

Also checked: the README's default column still matches the code. That is the
column that was wrong before, and nothing else would catch it drifting again.

Metadata and normalisation only, but importing kbstatpy starts R.

Run:  python3 tests/test_option_defaults.py
"""
import dataclasses
import os
import re
import sys

import matplotlib
matplotlib.use('Agg')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Every option documented as "list or comma-separated string".
LIST_VALUED = ('x', 'slope', 'interaction', 'covariate',
               'y_units', 'x_units', 'correlation', 'correlation_control')

# interaction takes the same spellings as the rest, but its default is the
# structure keyword 'auto' rather than "nothing" -- an additive model is a
# choice, not an absence, so it is one the caller makes explicitly.
EMPTY_BY_DEFAULT = tuple(o for o in LIST_VALUED if o != 'interaction')



def test_all_list_valued_options_default_to_empty_string():
    fields = {f.name: f for f in dataclasses.fields(KbstatOptions)}
    wrong = {n: fields[n].default for n in EMPTY_BY_DEFAULT
             if fields[n].default != ''}
    assert not wrong, f'these should default to \'\': {wrong}'
    assert fields['interaction'].default == 'auto', \
        f"interaction should default to 'auto', got {fields['interaction'].default!r}"


def test_no_list_valued_option_uses_a_default_factory():
    fields = {f.name: f for f in dataclasses.fields(KbstatOptions)}
    factories = [n for n in LIST_VALUED
                 if fields[n].default_factory is not dataclasses.MISSING]
    assert not factories, f'still declared with a default_factory: {factories}'


def test_string_and_list_spellings_normalise_alike():
    """The equivalence that makes the shared default safe."""
    for name in LIST_VALUED:
        a, b = Kbstat(KbstatOptions()), Kbstat(KbstatOptions())
        setattr(a.options, name, 'alpha, beta')
        setattr(b.options, name, ['alpha', 'beta'])
        a._normalize_options(); b._normalize_options()
        va, vb = getattr(a.options, name), getattr(b.options, name)
        assert va == vb == ['alpha', 'beta'], f'{name}: {va!r} vs {vb!r}'


def test_the_empty_default_normalises_to_an_empty_list():
    for name in EMPTY_BY_DEFAULT:
        k = Kbstat(KbstatOptions())
        k._normalize_options()
        assert getattr(k.options, name) == [], \
            f'{name} came out {getattr(k.options, name)!r}, not []'


def test_readme_default_column_matches_the_code():
    """The README column that was wrong before; nothing else would catch it."""
    readme = open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read()
    fields = {f.name: f for f in dataclasses.fields(KbstatOptions)}
    bad = []
    for name in LIST_VALUED:
        m = re.search(r'^\| `%s` \| [^|]*\| `([^|`]*)` \|' % name, readme, re.M)
        assert m, f'{name} has no row in the README option table'
        if m.group(1) != repr(fields[name].default):
            bad.append((name, m.group(1), repr(fields[name].default)))
    assert not bad, f'README default disagrees with the code: {bad}'


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
