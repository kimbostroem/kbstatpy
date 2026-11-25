#!/usr/bin/env python3
"""Tests for the "starting R" message on import.

What it guards: the first `import kbstatpy` starts R and loads its packages,
seconds on a laptop but up to a minute on a small JupyterHub or Colab share.
In a notebook the cell then sat there without a word, and the first students
to try it on a hub took it for a hang. kbstatpy now says so before R starts,
and says when it is ready.

Two failures are guarded. The message must appear in a notebook kernel, and it
must be printed *before* R starts (otherwise it arrives together with the wait
it is meant to explain). And it must not appear anywhere else: scripts keep
their output as it was, because tools and tests read it, and KBSTATPY_QUIET
silences it in a notebook too.

A notebook is recognised by ipykernel being loaded; the test stands one in
with an empty module of that name, which is all the check looks at.

Needs R (each case imports the package in a fresh interpreter).

Run:  python3 tests/test_import_message.py
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAKE_KERNEL = "import sys, types; sys.modules['ipykernel'] = types.ModuleType('ipykernel')\n"
# Whether R is already running when the first message is out: rpy2's embedded
# R is initialised by then if the message came too late.
PROBE = ("import builtins, sys\n"
         "_print = builtins.print\n"
         "def _spy(*a, **k):\n"
         "    if a and str(a[0]).startswith('kbstatpy: starting R'):\n"
         "        _print('R_ALREADY_UP=' + str('rpy2.rinterface' in sys.modules))\n"
         "    _print(*a, **k)\n"
         "builtins.print = _spy\n")


def _import(prefix='', quiet=False):
    env = dict(os.environ)
    env.pop('KBSTATPY_QUIET', None)
    if quiet:
        env['KBSTATPY_QUIET'] = '1'
    code = ('import sys\nsys.path.insert(0, ' + repr(ROOT) + ')\n' + prefix
            + 'import kbstatpy\n')
    out = subprocess.run([sys.executable, '-c', code], capture_output=True,
                         text=True, env=env, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout


def test_a_notebook_is_told_that_r_is_starting_and_when_it_is_ready():
    out = _import(FAKE_KERNEL)
    assert 'kbstatpy: starting R' in out, out
    assert ' ready (' in out, out
    assert out.index('starting R') < out.index(' ready ('), out


def test_the_message_comes_before_r_starts():
    out = _import(FAKE_KERNEL + PROBE)
    assert 'R_ALREADY_UP=False' in out, out


def test_a_script_prints_nothing_new():
    out = _import()
    assert 'starting R' not in out and ' ready (' not in out, out


def test_kbstatpy_quiet_silences_it_in_a_notebook():
    out = _import(FAKE_KERNEL, quiet=True)
    assert 'starting R' not in out and ' ready (' not in out, out


if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print('PASS  ' + name)
            except AssertionError as e:
                failures += 1
                print('FAIL  ' + name + '\n      ' + str(e)[:500])
            except Exception as e:
                failures += 1
                print('ERROR ' + name + '\n      ' + type(e).__name__ + ': ' + str(e)[:500])
    print('\n' + ('all tests passed' if not failures
                  else str(failures) + ' test(s) FAILED'))
    sys.exit(1 if failures else 0)
