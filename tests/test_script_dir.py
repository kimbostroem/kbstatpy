#!/usr/bin/env python3
"""Tests for chdir_to_script() / script_dir() in kbstatpy/_scriptdir.py.

What they replace: every evaluation script opened with

    script_dir = os.path.dirname(os.path.abspath(__file__))

and then built its paths on top of that, because a plain relative path means
something different depending on where the script was launched from. An IDE's
run button, a cron entry and a double-click each choose a different working
directory, and the failure is silent -- the script reads or writes the wrong
folder rather than reporting anything.

Two failure modes are guarded beyond the happy path.

The script's path is taken from the call stack, so the search must stop at the
first frame outside the package. Continuing up until some frame has a
`__file__` would find the interpreter's own frames, which do: in a notebook
that answers with ipykernel's install directory, and chdir_to_script() would
then move to site-packages.

And a context with no script at all -- a REPL, a notebook cell, exec() of a
string -- must not be guessed at. Moving the working directory somewhere
invented there is worse than not moving it.

The same pair is exposed on the Kbstat class, so a script that already
imports Kbstat needs no second import. Those two tests go through the real
package and so need R; the rest load the module standalone and do not.

Run:  python3 tests/test_script_dir.py
"""
import os
import subprocess
import sys
import tempfile
import textwrap
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import importlib.util                                          # noqa: E402

_spec = importlib.util.spec_from_file_location(
    '_kbstatpy_scriptdir', os.path.join(ROOT, 'kbstatpy', '_scriptdir.py'))
_sd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sd)


def _run_script(body, workdir):
    """Write `body` to a script in its own folder and run it from `workdir`."""
    home = tempfile.mkdtemp()
    path = os.path.join(home, 'analysis.py')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(textwrap.dedent(f'''
            import sys
            sys.path.insert(0, {ROOT!r})
            import importlib.util
            _s = importlib.util.spec_from_file_location(
                'sd', {os.path.join(ROOT, 'kbstatpy', '_scriptdir.py')!r})
            sd = importlib.util.module_from_spec(_s)
            _s.loader.exec_module(sd)
        ''') + textwrap.dedent(body))
    # The child runs from a different directory, so it cannot rely on the
    # parent's import path being reproducible from the environment alone: a
    # relative entry on sys.path resolves somewhere else, and on CI the child
    # lost numpy that way while the parent had it. Hand it the parent's path.
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(
        [p for p in sys.path if p and os.path.isabs(p)]
        + ([env['PYTHONPATH']] if env.get('PYTHONPATH') else []))
    # And drop what R put there. Importing kbstatpy starts R, which rewrites
    # the dynamic loader's search path to its own lib directory. Inherited by
    # a child, that makes the child resolve libpython out of R's directory
    # rather than its own, and its stdlib extensions then fail to load:
    #   _ctypes...so: undefined symbol: _PyErr_SetLocaleString
    # The parent is fine only because it started before R changed anything, so
    # the child is given the same clean start. It re-imports kbstatpy and R
    # sets these again for itself; nothing is lost.
    for var in ('LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH',
                'DYLD_FALLBACK_LIBRARY_PATH'):
        env.pop(var, None)
    out = subprocess.run([sys.executable, path], cwd=workdir, env=env,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, f'script failed:\n{out.stderr}'
    return out.stdout.strip(), os.path.realpath(home)


def test_chdir_lands_in_the_scripts_own_folder():
    """The point of the whole thing: cwd becomes the script's folder."""
    with tempfile.TemporaryDirectory() as elsewhere:
        got, home = _run_script(
            'sd.chdir_to_script()\nimport os\nprint(os.path.realpath(os.getcwd()))',
            elsewhere)
        assert got == home, f'cwd is {got!r}, expected {home!r}'


def test_chdir_returns_the_directory_it_moved_to():
    """So a script can keep the path if it also wants it as a value."""
    with tempfile.TemporaryDirectory() as elsewhere:
        got, home = _run_script(
            'import os\nprint(os.path.realpath(sd.chdir_to_script()))', elsewhere)
        assert got == home, f'returned {got!r}, expected {home!r}'


def test_a_relative_path_then_means_what_it_looks_like():
    """The reason to move at all: 'Data/x.csv' should be the script's Data."""
    with tempfile.TemporaryDirectory() as elsewhere:
        got, home = _run_script(
            'sd.chdir_to_script()\n'
            'import os\n'
            'print(os.path.realpath(os.path.abspath(os.path.join("Data", "x.csv"))))',
            elsewhere)
        assert got == os.path.join(home, 'Data', 'x.csv'), got


def test_script_dir_reports_without_moving():
    """script_dir() is the non-mutating half; it must leave cwd alone."""
    with tempfile.TemporaryDirectory() as elsewhere:
        got, home = _run_script(
            'import os\n'
            'before = os.path.realpath(os.getcwd())\n'
            'd = os.path.realpath(sd.script_dir())\n'
            'after = os.path.realpath(os.getcwd())\n'
            'print(d, before == after)', elsewhere)
        d, unchanged = got.rsplit(' ', 1)
        assert d == home, f'script_dir() gave {d!r}, expected {home!r}'
        assert unchanged == 'True', 'script_dir() changed the working directory'


def test_it_never_answers_with_the_package_directory():
    """The caller is the script, not the kbstatpy frame that asked on its
    behalf -- the bug a naive `inspect.currentframe().f_back` would have."""
    with tempfile.TemporaryDirectory() as elsewhere:
        got, home = _run_script('import os\n'
                                'print(os.path.realpath(sd.script_dir()))', elsewhere)
        pkg = os.path.realpath(os.path.join(ROOT, 'kbstatpy'))
        assert got != pkg, 'answered with kbstatpy own directory'
        assert got == home


def test_a_fileless_caller_gets_none_rather_than_a_guess():
    """A notebook or REPL has no script; walking on would reach ipykernel."""
    scope = {'sd': _sd}                      # no __file__ in these globals
    exec(compile('d = sd.script_dir()', '<string>', 'exec'), scope)
    assert scope['d'] is None, f'invented a directory: {scope["d"]!r}'


def test_a_fileless_chdir_warns_and_does_not_move():
    """Silently staying put would be as confusing as silently moving."""
    before = os.getcwd()
    scope = {'sd': _sd}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        exec(compile('d = sd.chdir_to_script()', '<string>', 'exec'), scope)
    assert scope['d'] is None, scope['d']
    assert os.getcwd() == before, 'changed the working directory anyway'
    assert any('unchanged' in str(w.message) for w in caught), \
        [str(w.message) for w in caught]


def _run_with_package(body, workdir):
    """Run a script that imports the installed package, not the bare module."""
    home = tempfile.mkdtemp()
    path = os.path.join(home, 'analysis.py')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('import sys\nsys.path.insert(0, ' + repr(ROOT) + ')\n' + body)
    # The child runs from a different directory, so it cannot rely on the
    # parent's import path being reproducible from the environment alone: a
    # relative entry on sys.path resolves somewhere else, and on CI the child
    # lost numpy that way while the parent had it. Hand it the parent's path.
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(
        [p for p in sys.path if p and os.path.isabs(p)]
        + ([env['PYTHONPATH']] if env.get('PYTHONPATH') else []))
    # And drop what R put there. Importing kbstatpy starts R, which rewrites
    # the dynamic loader's search path to its own lib directory. Inherited by
    # a child, that makes the child resolve libpython out of R's directory
    # rather than its own, and its stdlib extensions then fail to load:
    #   _ctypes...so: undefined symbol: _PyErr_SetLocaleString
    # The parent is fine only because it started before R changed anything, so
    # the child is given the same clean start. It re-imports kbstatpy and R
    # sets these again for itself; nothing is lost.
    for var in ('LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH',
                'DYLD_FALLBACK_LIBRARY_PATH'):
        env.pop(var, None)
    out = subprocess.run([sys.executable, path], cwd=workdir, env=env,
                         capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, 'script failed:\n' + out.stderr
    return out.stdout.strip().splitlines()[-1], os.path.realpath(home)


BODY_CLASS_FORM = 'import os\nfrom kbstatpy import Kbstat\nprint(os.path.realpath(Kbstat.chdir_to_script()))\n'
BODY_SAME_OBJECT = 'from kbstatpy import Kbstat, script_dir, chdir_to_script\nprint(Kbstat.script_dir is script_dir and Kbstat.chdir_to_script is chdir_to_script)\n'


def test_the_class_form_finds_the_script_not_the_package():
    """Kbstat.chdir_to_script() must answer with the caller's folder.

    The staticmethod is defined in kbstat.py, inside the package, so an
    implementation that took currentframe().f_back, or that matched on the
    calling module, would answer with kbstatpy's own directory here and move
    the script into site-packages instead.
    """
    with tempfile.TemporaryDirectory() as elsewhere:
        got, home = _run_with_package(BODY_CLASS_FORM, elsewhere)
        assert got == home, 'moved to ' + repr(got) + ', expected ' + repr(home)
        assert os.path.basename(got) != 'kbstatpy'


def test_the_class_form_is_the_same_function():
    """Two spellings of one thing, so they cannot drift apart."""
    with tempfile.TemporaryDirectory() as elsewhere:
        got, _ = _run_with_package(BODY_SAME_OBJECT, elsewhere)
        assert got == 'True', got


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
