#!/usr/bin/env python3
"""Keeps analysis_template.py honest.

It is the first file a new user copies, and nothing checked it: it is never
imported, never run by the demos, and a rename elsewhere in the package left
it silently wrong until somebody tried the line. That happened with
`chdir_to_script`, renamed one release after it was added.

Three things are checked, all cheap: that the file still parses, that every
option it sets really exists, and that every option it *mentions* in a
commented-out line exists too. The last is the one that matters, since the
template is mostly commented lines and those are exactly what a user
uncomments.

Needs R only because KbstatOptions is imported from the package.

Run:  python3 tests/test_analysis_template.py
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TEMPLATE = os.path.join(ROOT, 'analysis_template.py')

from kbstatpy.options import KbstatOptions    # noqa: E402


def source():
    return open(TEMPLATE, encoding='utf-8').read()


def known_fields():
    o = KbstatOptions()
    return {f for f in vars(o)} | set(getattr(KbstatOptions, '__annotations__', {}))


def test_the_template_parses():
    """A template that does not compile is worse than none."""
    ast.parse(source(), filename=TEMPLATE)


def test_every_option_it_sets_exists():
    """An active line is one a user runs as-is."""
    tree = ast.parse(source())
    used = {t.attr for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            for t in node.targets
            if isinstance(t, ast.Attribute)
            and isinstance(t.value, ast.Name) and t.value.id == 'options'}
    unknown = sorted(used - known_fields())
    assert not unknown, f'template sets options that do not exist: {unknown}'


def test_every_option_it_mentions_exists():
    """The commented lines are the bulk of the template and the part users
    uncomment, so a stale name there is the likeliest way it goes wrong."""
    mentioned = set(re.findall(r'^\s*#\s*options\.([A-Za-z_][A-Za-z0-9_]*)\s*=',
                               source(), re.M))
    unknown = sorted(mentioned - known_fields())
    assert not unknown, f'template mentions options that do not exist: {unknown}'


def test_the_names_it_calls_on_kbstat_exist():
    """Catches a renamed helper, which is what prompted this file."""
    import kbstatpy
    called = set(re.findall(r'Kbstat\.([A-Za-z_][A-Za-z0-9_]*)\s*\(', source()))
    missing = sorted(n for n in called if not hasattr(kbstatpy.Kbstat, n))
    assert not missing, f'template calls Kbstat methods that do not exist: {missing}'


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
