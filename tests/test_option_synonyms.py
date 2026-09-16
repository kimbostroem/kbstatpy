#!/usr/bin/env python3
"""Tests for the alternative spellings of option names.

The guarded failure mode: KbstatOptions is a plain dataclass, so assigning an
unrecognised attribute succeeds and is then ignored. A user who wrote
`options.correlate = 'a, b'` (the verb) or `options.constraint = '...'` (the
singular) got no error, no warning and no analysis -- the option simply appeared
not to work.

`correlate` and `constraint` are now declared synonyms of `correlation` and
`constraints`. They are synonyms, not deprecations: neither spelling is
preferred and neither warns. Setting both spellings of the same option to
different values is a contradiction and raises, because silently picking one
would be the original failure in a new form.

None, not '', is the unset marker: '' is a legitimate value for both canonical
options and means "off".

Needs R + glmmTMB (importing kbstatpy starts R).

Run:  python3 tests/test_option_synonyms.py
"""
import os
import sys
import warnings

import matplotlib
matplotlib.use('Agg')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat, _OPTION_SYNONYMS    # noqa: E402
from kbstatpy.options import KbstatOptions              # noqa: E402


def opts(**kw):
    o = KbstatOptions()
    o.y, o.x, o.id = 'y', 'cond', 'subject'
    for k, v in kw.items():
        setattr(o, k, v)
    return o


def test_every_synonym_is_a_real_field_on_both_sides():
    """A typo in the table would reintroduce the silent-ignore bug."""
    fields = KbstatOptions().__dataclass_fields__
    for alias, canon in _OPTION_SYNONYMS.items():
        assert alias in fields, f'{alias} is not a declared option'
        assert canon in fields, f'{canon} is not a declared option'
        assert fields[alias].default is None, \
            f'{alias} must default to None so "unset" is distinguishable from ""'


def test_synonym_is_copied_onto_the_canonical_option():
    k = Kbstat(opts(correlate='a, b'))
    assert k.options.correlation == 'a, b', k.options.correlation
    k = Kbstat(opts(constraint='Year > 1950'))
    assert k.options.constraints == 'Year > 1950', k.options.constraints


def test_canonical_spelling_still_works():
    k = Kbstat(opts(correlation='a, b', constraints='Year > 1950'))
    assert k.options.correlation == 'a, b'
    assert k.options.constraints == 'Year > 1950'


def test_a_synonym_set_after_construction_is_picked_up():
    k = Kbstat(opts())
    k.options.correlate = 'a, b'
    k._normalize_options()
    # _normalize_options also splits the comma-separated form into a list, so
    # the synonym must arrive before that step, not merely be stored somewhere.
    assert k.options.correlation == ['a', 'b'], k.options.correlation


def test_resolution_is_idempotent():
    """_normalize_options runs on both run() and fit(); the second pass must not
    undo the first by copying a cleared alias back over the canonical value."""
    k = Kbstat(opts(correlate='a, b'))
    for _ in range(3):
        k._normalize_options()
    assert k.options.correlation == ['a', 'b'], k.options.correlation
    assert k.options.correlate is None


def test_neither_spelling_warns():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        Kbstat(opts(correlate='a, b'))
        Kbstat(opts(constraint='Year > 1950'))
    assert not [m for m in w if 'correlate' in str(m.message)
                or 'constraint' in str(m.message)], \
        f'synonyms must not warn, got {[str(m.message) for m in w]}'


def test_an_empty_synonym_does_not_wipe_the_canonical_option():
    """'' means "off" and is a real value, so it must beat an unset canonical
    rather than being mistaken for "not given"."""
    k = Kbstat(opts(correlation='a, b'))
    assert k.options.correlation == 'a, b'
    k = Kbstat(opts(correlate=''))
    assert k.options.correlation == ''


def test_conflicting_spellings_raise():
    for kw in ({'correlate': 'a, b', 'correlation': 'c, d'},
               {'constraint': 'Year > 1950', 'constraints': 'Year > 1960'}):
        try:
            Kbstat(opts(**kw))
        except ValueError as e:
            assert 'only one' in str(e), str(e)
        else:
            raise AssertionError(f'{kw} should raise, the two disagree')


def test_the_same_value_in_both_spellings_is_accepted():
    k = Kbstat(opts(correlate='a, b', correlation='a, b'))
    assert k.options.correlation == 'a, b'


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
