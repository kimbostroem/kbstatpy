#!/usr/bin/env python3
r"""Tests that variable names and factor levels are safe to use in output paths.

`save()` builds paths out of data, not out of literals: the per-DV subdirectory
is named after the dependent variable, post-hoc tables become
`Posthoc_<factor>.xlsx`, and a 4th+ factor splits the data figure into
`DataPlots_<var>_<level>_<level>.*`. Those levels are ordinary data cells, so
`5 mg/kg`, `50%` and `pre:post` are all realistic values.

Windows forbids `< > : " / \ | ? *` in a path component, refuses the reserved
DOS device names (`NUL`, `CON`, `COM1`, ...) whatever the extension, and
silently strips trailing dots and spaces. This went unnoticed because the
library was developed and used on macOS, where only `/` is special -- and there
it does not raise either: `os.path.join(out_dir, 'Force/BW')` quietly nests a
directory, so the results tree differs from the one the user asked for without
any error, and the same run produces a different layout per operating system.

Checks that the sanitiser neutralises every such class, and -- as importantly --
that a name which is already safe is returned untouched, so existing output
paths do not move.

Exercises the sanitiser directly, but still needs R with emmeans like every
other test here: importing kbstatpy starts R.

Run:  python3 tests/test_path_sanitising.py
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kbstatpy.kbstat import Kbstat            # noqa: E402

safe = Kbstat._safe_path_component

WINDOWS_FORBIDDEN = '<>:"/\\|?*'


def test_already_safe_names_are_untouched():
    """The common case must not move existing output folders."""
    for name in ('score', 'Force_BW', 'Subject', 'condition a', 'y2',
                 '50%', 'x-y', 'a.b', 'Trial#3', 'delta+', 'v(1)'):
        assert safe(name) == name, f'{name!r} was rewritten to {safe(name)!r}'


def test_every_windows_forbidden_character_is_replaced():
    for ch in WINDOWS_FORBIDDEN:
        out = safe(f'a{ch}b')
        assert ch not in out, f'{ch!r} survived sanitising: {out!r}'
        assert out == 'a_b', f'{ch!r} gave {out!r}, expected "a_b"'


def test_realistic_level_values():
    """The values that actually turn up in a factor column."""
    assert safe('Force/BW') == 'Force_BW'
    assert safe('5 mg/kg') == '5 mg_kg'
    assert safe('pre:post') == 'pre_post'
    assert safe('1.5 m/s') == '1.5 m_s'


def test_control_characters_are_replaced():
    assert safe('a\x01b') == 'a_b'
    assert safe('a\tb') == 'a_b'


def test_reserved_device_names_are_defused():
    """Windows refuses these whatever the extension, so 'NUL.xlsx' fails too."""
    for name in ('NUL', 'nul', 'CON', 'PRN', 'AUX', 'COM1', 'LPT9'):
        out = safe(name)
        assert out.upper() not in Kbstat._PATH_RESERVED, f'{name!r} -> {out!r}'
        assert out.upper().startswith(name.upper()), f'{name!r} -> {out!r}'
    # A reserved name is only reserved on its own; these must stay put.
    for name in ('CONDITION', 'NULL', 'COMPARISON', 'AUXILIARY'):
        assert safe(name) == name, f'{name!r} was rewritten to {safe(name)!r}'


def test_trailing_dots_and_spaces_are_stripped():
    """Windows drops them when creating the file, so a path written as 'x ' is
    afterwards not found under 'x '."""
    assert safe('trail.') == 'trail'
    assert safe('trail ') == 'trail'
    assert safe('trail. .') == 'trail'
    assert safe('  padded  ') == 'padded'


def test_a_name_that_sanitises_to_nothing_gets_a_fallback():
    """Without this, os.path.join(out_dir, '') silently returns out_dir and
    the per-DV results overwrite each other in the parent folder."""
    # Nothing left at all -> the fallback name.
    for name in ('', '   ', '...', '. .'):
        assert safe(name) == 'unnamed', f'{name!r} -> {safe(name)!r}'
    # Something left, even if only underscores -> a usable component, and in
    # particular not the empty string.
    for name in ('/', '///', ':', '?'):
        out = safe(name)
        assert out, f'{name!r} sanitised to an empty component'
        assert out == '_' * len(name), f'{name!r} -> {out!r}'


def test_result_is_usable_as_a_real_path_component():
    """The end-to-end property the sanitiser exists for: one component in, one
    component out -- never a nested path."""
    import tempfile
    for name in ('Force/BW', '5 mg/kg', 'pre:post', 'NUL', 'trail. ', '?'):
        component = safe(name)
        assert os.sep not in component, f'{name!r} -> {component!r} nests'
        assert '/' not in component and '\\' not in component
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, component)
            os.makedirs(target)
            assert os.path.isdir(target)
            # Exactly one level deep, i.e. os.path.join did not split it.
            assert os.path.dirname(target) == tmp, f'{name!r} nested into {target!r}'


def test_non_string_names_do_not_crash():
    """Factor levels arrive from a dataframe, so they may be numbers."""
    assert safe(3) == '3'
    assert safe(2.5) == '2.5'


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
