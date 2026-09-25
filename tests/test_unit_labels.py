#!/usr/bin/env python3
"""Tests for `y_units` / `x_units`, which are matched to variables by position.

The guarded failure mode: both were split with the same helper as `x` and
`slope`, which discards empty entries. That is right for a list of names, where
a stray comma should not invent a blank variable, and wrong here, where an
entry's position is what ties it to a variable. `x_units = ', mg'` therefore
became `['mg']` and labelled the FIRST factor with mg instead of the second, an
axis mislabelled with no warning anywhere.

`'1'` was the documented way round it -- a placeholder occupying a position
without printing a unit -- and it still works. An empty entry now does too,
which is what the Python list form has always accepted, so the string and list
spellings finally agree.

Needs R + glmmTMB (importing kbstatpy starts R).

Run:  python3 tests/test_unit_labels.py
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402
from kbstatpy.options import KbstatOptions    # noqa: E402

FACTORS = ['group', 'limb', 'eyes']


def units(spec, attr='x_units'):
    o = KbstatOptions()
    o.y, o.x, o.id = 'y', list(FACTORS), 'subj'
    setattr(o, attr, spec)
    k = Kbstat(o)
    k._normalize_options()
    return getattr(k.options, attr)


def label(us, i):
    """The rule the plotting code applies: '' and '1' both mean no unit."""
    return (f'{FACTORS[i]} [{us[i]}]'
            if len(us) > i and us[i] and us[i] != '1' else FACTORS[i])


def test_empty_entry_holds_its_position():
    assert units(', mg, s') == ['', 'mg', 's'], units(', mg, s')


def test_empty_and_one_label_identically():
    a = units(', mg, s')
    b = units('1, mg, s')
    assert [label(a, i) for i in range(3)] == [label(b, i) for i in range(3)], \
        f'{a} and {b} must label the same'
    assert [label(a, i) for i in range(3)] == \
        ['group', 'limb [mg]', 'eyes [s]'], [label(a, i) for i in range(3)]


def test_the_string_and_list_spellings_agree():
    assert units(', mg, s') == units(['', 'mg', 's'])
    assert units('1, mg, s') == units(['1', 'mg', 's'])


def test_a_wholly_empty_spec_means_no_units():
    for spec in ('', '  ', ' , , '):
        assert units(spec) == [], f'{spec!r} -> {units(spec)!r}'


def test_y_units_is_positional_too():
    """Same helper, same failure: y_units is matched to the dependent variables
    of a multi-y run in order."""
    o = KbstatOptions()
    o.y, o.x, o.id = ['a', 'b', 'c'], list(FACTORS), 'subj'
    o.y_units = ', mg, s'
    k = Kbstat(o)
    k._normalize_options()
    assert k.options.y_units == ['', 'mg', 's'], k.options.y_units


def test_name_lists_still_drop_stray_entries():
    """The positional rule must not leak into the options that name things,
    where a trailing comma should not invent a blank variable."""
    o = KbstatOptions()
    o.y, o.id = 'y', 'subj'
    o.x, o.slope, o.covariate = 'group, limb,', 'limb, ', 'age,,'
    k = Kbstat(o)
    k._normalize_options()
    assert k.options.x == ['group', 'limb'], k.options.x
    assert k.options.slope == ['limb'], k.options.slope
    assert k.options.covariate == ['age'], k.options.covariate


def _plotted_ylabels(y_units):
    """The y labels kbstat actually draws in its data plot."""
    import warnings
    import numpy as np
    import pandas as pd
    out = '/tmp/kbstatpy_unit_labels'
    os.makedirs(out, exist_ok=True)
    rng = np.random.default_rng(3)
    df = pd.DataFrame({'y': rng.normal(size=40), 'group': ['A', 'B'] * 20,
                       'subj': [f's{i // 2}' for i in range(40)]})
    df.to_csv(os.path.join(out, 'toy.csv'), index=False)
    o = KbstatOptions()
    o.in_file, o.out_dir, o.figure_display = os.path.join(out, 'toy.csv'), out, 'save_only'
    o.y, o.x, o.id, o.y_units = 'y', 'group', 'subj', y_units
    k = Kbstat(o)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        k.run_save()
    fig = k.output.results[0].fig_data
    fig = fig if not isinstance(fig, dict) else next(iter(fig.values()))
    return [ax.get_ylabel() for ax in fig.axes if ax.get_ylabel()]


def test_the_plotted_y_label_shows_no_unit_for_one():
    """'1' means no unit on the y axis as well, not a literal '[1]'."""
    labels = _plotted_ylabels('1')
    assert labels and not any('[' in t for t in labels), labels
    assert any('[mm]' in t for t in _plotted_ylabels('mm')), 'a real unit must still show'


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
