#!/usr/bin/env python3
"""Tests that the enumerated options agree on case and on bad values.

The guarded failure mode: they did not. Some lower-cased their value and raised
on an unknown one; others took whatever string they were given and quietly fell
back, so the same mistake was loud in one option and invisible in another.

Two of those were harmful rather than merely untidy. `plot_style = 'Bar'` drew
violins, because the consuming test is `style == 'bar'`. And a mistyped
`distribution` fitted a Gaussian LMM without a word, because the family lookup
ends in `.get(name, 'gaussian')` -- a typo silently changed the model family and
every number that came out of it.

They now share one table, one lower-casing and one validation. Deliberately
outside it: `posthoc_correction`, whose value reaches R, where method names are
case-sensitive ('BH', 'BY'); `df_method`, which has its own alias table and
warns; `link`, lower-cased but not enumerated because the valid set depends on
the family; and the free-text options.

Needs R + glmmTMB (importing kbstatpy starts R).

Run:  python3 tests/test_option_validation.py
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat, _ENUM_OPTIONS       # noqa: E402
from kbstatpy.options import KbstatOptions              # noqa: E402


def norm(**kw):
    o = KbstatOptions()
    o.y, o.x, o.id = 'y', 'A, B', 'subj'
    for k, v in kw.items():
        setattr(o, k, v)
    k = Kbstat(o)
    k._normalize_options()
    return k.options


def test_every_enumerated_option_is_case_insensitive():
    for name, allowed in _ENUM_OPTIONS.items():
        for value in allowed:
            got = getattr(norm(**{name: value.upper()}), name)
            assert got == value, f'{name}={value.upper()!r} -> {got!r}'


def test_every_enumerated_option_rejects_an_unknown_value():
    for name in _ENUM_OPTIONS:
        try:
            norm(**{name: 'definitely-not-a-value'})
        except ValueError as e:
            assert name in str(e), f'{name}: message should name the option: {e}'
        else:
            raise AssertionError(f'{name} accepted an unknown value')


def test_the_table_only_lists_real_options():
    fields = {f.name for f in __import__('dataclasses').fields(KbstatOptions)}
    unknown = sorted(set(_ENUM_OPTIONS) - fields)
    assert not unknown, f'_ENUM_OPTIONS names options that do not exist: {unknown}'


def test_each_default_is_one_of_its_own_allowed_values():
    """A default outside its own allowed set would raise on an untouched run."""
    d = KbstatOptions()
    bad = {n: getattr(d, n) for n, allowed in _ENUM_OPTIONS.items()
           if str(getattr(d, n)).strip().lower() not in allowed}
    assert not bad, f'defaults outside their allowed set: {bad}'


def test_a_capitalised_plot_style_is_honoured():
    """The concrete trap: `'Bar'` used to fall through to violins."""
    assert norm(plot_style='Bar').plot_style == 'bar'


def test_a_mistyped_distribution_is_refused():
    """The dangerous trap: it used to fit a Gaussian and say nothing."""
    try:
        norm(distribution='gama')
    except ValueError as e:
        assert 'distribution' in str(e) and 'gamma' in str(e), str(e)
    else:
        raise AssertionError('a mistyped distribution must not be accepted')


def test_data_outliers_keeps_its_aliases_but_refuses_the_rest():
    for alias in ('hide', 'off', 'NONE'):
        assert norm(data_outliers=alias).data_outliers == 'none', alias
    assert norm(data_outliers='PLOT').data_outliers == 'plot'
    try:
        norm(data_outliers='bogus')
    except ValueError as e:
        assert 'data_outliers' in str(e)
    else:
        raise AssertionError('data_outliers accepted an unknown value')


def test_an_empty_value_is_left_to_mean_the_default():
    for name in ('x_label', 'y_label'):
        assert getattr(norm(**{name: ''}), name) == ''


def test_posthoc_correction_is_left_case_sensitive():
    """It reaches R, where 'BH' and 'BY' are not the same as 'bh' and 'by'."""
    assert norm(posthoc_correction='BH').posthoc_correction == 'BH'


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
