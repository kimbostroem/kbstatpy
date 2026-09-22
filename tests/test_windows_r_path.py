#!/usr/bin/env python3
"""Tests for the Windows DLL search path fix in kbstatpy/_windows.py.

The failure it guards: on Windows, R loads its own shared libraries out of
`<R_HOME>\\bin\\x64`, and some of them (Rlapack) only when a package first
needs them. That folder is on no search path by default, so R starts, rpy2
reports its version, and then the first `library()` call dies with

    unable to load shared object '.../library/stats/libs/x64/stats.dll':
    LoadLibrary failure: The specified module could not be found

which names a file that is present rather than the R DLL beside it that
cannot be found. Every kbstatpy analysis goes through `stats`, so the package
was unusable on such a machine, with an error pointing nowhere near the cause.
It was reported from a real install (R 4.6.1, conda, no Rtools).

`prepare_r_dll_path()` fixes it, but only if it runs before rpy2 loads R --
hence the ordering test, which is the one thing a later tidy-up of the imports
in `__init__.py` would silently undo.

`_windows.py` is loaded here on its own, not through `import kbstatpy`, so
these run without R -- and, more to the point, they keep running on a machine
where the very bug under test stops the package from importing.

The same file also silences rpy2's `R CMD config` probe. On Windows rpy2
shells out to `R.exe CMD config --ldflags` at import; `R CMD` is a shell
script needing `sh` from Rtools, and without it Windows prints

    'sh' is not recognized as an internal or external command

to the console. rpy2 catches the resulting CalledProcessError and carries on,
so the only thing the message costs is the user's confidence, on every single
import. `silence_r_cmd_config()` raises that error directly instead of
provoking it, so rpy2 takes the identical fallback path in silence.

Run:  python3 tests/test_windows_r_path.py
"""
import ast
import importlib.util
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT_PATH = os.path.join(ROOT, 'kbstatpy', '__init__.py')
WINDOWS_PATH = os.path.join(ROOT, 'kbstatpy', '_windows.py')

_spec = importlib.util.spec_from_file_location('_kbstatpy_windows', WINDOWS_PATH)
_windows = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_windows)


def test_no_op_off_windows():
    """macOS and Linux find R's libraries by themselves; touching PATH there
    would be meddling, and R_HOME is not even how they look."""
    before = os.environ.get('PATH')
    result = _windows.prepare_r_dll_path()
    if os.name == 'nt':
        return
    assert result is None, f'expected None off Windows, got {result!r}'
    assert os.environ.get('PATH') == before, 'PATH was modified off Windows'


def test_runs_before_the_rpy2_import():
    """The whole point of the fix is its position: `from .kbstat import Kbstat`
    reaches rpy2, which starts R, and R reads the search path once. Moving the
    call below that import, or sorting the imports, restores the bug and looks
    like a tidy-up in the diff."""
    with open(INIT_PATH, encoding='utf-8') as fh:
        tree = ast.parse(fh.read())

    call_line = next(
        (node.lineno for node in ast.walk(tree)
         if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'prepare_r_dll_path'),
        None)
    assert call_line is not None, 'prepare_r_dll_path() is not called in __init__.py'

    kbstat_line = next(
        (node.lineno for node in tree.body
         if isinstance(node, ast.ImportFrom) and node.module == 'kbstat'),
        None)
    assert kbstat_line is not None, 'the .kbstat import is gone from __init__.py'
    assert call_line < kbstat_line, (
        f'prepare_r_dll_path() is called at line {call_line}, after the .kbstat '
        f'import at line {kbstat_line} - by then rpy2 has already started R')


def test_r_bin_needs_an_actual_r_dll():
    """R's folder is identified by R.dll being in it, not by its name: an
    R_HOME left over from an uninstalled R, or a bin\\ that only holds the
    launchers, must not be reported as the library folder."""
    with tempfile.TemporaryDirectory() as home:
        assert _windows._r_bin(home) is None, 'empty folder accepted as R_HOME'

        # The flat R >= 4.2 layout, and the only one testable off Windows: the
        # arch subfolder that is tried first is chosen by the running machine's
        # architecture, which here is not Windows'.
        bin_dir = os.path.join(home, 'bin')
        os.makedirs(bin_dir)
        assert _windows._r_bin(home) is None, 'bin\\ without R.dll accepted'

        open(os.path.join(bin_dir, 'R.dll'), 'w').close()
        assert _windows._r_bin(home) == bin_dir, 'bin\\R.dll not found'


def test_path_is_prepended_once():
    """Prepending on every import would grow PATH without bound in a notebook,
    and the spelling of an existing entry varies: Windows PATHs carry quoted
    entries, trailing backslashes and any mixture of case."""
    bin_dir = r'C:\Program Files\R\R-4.6.1\bin\x64'
    sep = ';'

    assert _windows._prepend_path('', bin_dir) == bin_dir, 'empty PATH mishandled'

    grown = _windows._prepend_path(r'C:\Windows', bin_dir)
    assert grown == bin_dir + sep + r'C:\Windows', f'not prepended: {grown}'

    for spelling in (bin_dir,
                     bin_dir.lower(),
                     bin_dir + '\\',
                     '"' + bin_dir + '"'):
        path = r'C:\Windows' + sep + spelling
        assert _windows._prepend_path(path, bin_dir) == path, (
            f'duplicated an entry already present as {spelling!r}')


class _FakeSituation:
    """Stands in for rpy2.situation: the two attributes the fix touches."""

    class subprocess:                                   # noqa: N801
        class CalledProcessError(Exception):
            def __init__(self, returncode, cmd, output=None):
                super().__init__(f'{cmd} -> {returncode}')
                self.returncode, self.cmd, self.output = returncode, cmd, output

    @staticmethod
    def get_r_flags(r_home, flags):
        raise AssertionError('get_r_flags was called: a process was spawned')


def _with_fake_rpy2(fn, *, os_name, sh_path):
    """Run `fn` with os.name, shutil.which and rpy2.situation substituted."""
    fake = _FakeSituation()
    real_name, real_which = _windows.os.name, _windows.shutil.which
    real_mod = sys.modules.get('rpy2.situation')
    sys.modules['rpy2.situation'] = fake
    sys.modules.setdefault('rpy2', type(sys)('rpy2'))
    _windows.os.name = os_name
    _windows.shutil.which = lambda cmd: sh_path if cmd == 'sh' else None
    try:
        return fn(fake)
    finally:
        _windows.os.name, _windows.shutil.which = real_name, real_which
        if real_mod is None:
            sys.modules.pop('rpy2.situation', None)
        else:
            sys.modules['rpy2.situation'] = real_mod


def test_silencer_is_a_no_op_off_windows():
    """macOS and Linux never take rpy2's `R CMD config` branch, so touching
    rpy2 there would be meddling with a library for no reason."""
    def check(fake):
        assert _windows.silence_r_cmd_config() is False
        assert fake.get_r_flags is _FakeSituation.get_r_flags, (
            'rpy2 was patched on a platform that does not need it')
    _with_fake_rpy2(check, os_name='posix', sh_path=None)


def test_silencer_leaves_rpy2_alone_when_rtools_is_installed():
    """With `sh` present the probe succeeds and its answer is authoritative --
    better than the bin\\x64 guess the fallback makes."""
    def check(fake):
        assert _windows.silence_r_cmd_config() is False
        assert fake.get_r_flags is _FakeSituation.get_r_flags, (
            'discarded a working R CMD config')
    _with_fake_rpy2(check, os_name='nt', sh_path=r'C:\rtools\usr\bin\sh.exe')


def test_silencer_replaces_the_probe_when_sh_is_missing():
    """The replacement must raise exactly what openrlib catches, or the
    silencing turns a handled failure into an unhandled one."""
    def check(fake):
        assert _windows.silence_r_cmd_config() is True
        assert fake.get_r_flags is not _FakeSituation.get_r_flags, (
            'the probe was left in place')
        try:
            fake.get_r_flags('C:\\R', '--ldflags')
        except _FakeSituation.subprocess.CalledProcessError:
            pass                                        # what rpy2 expects
        else:
            raise AssertionError('replacement did not raise CalledProcessError')
    _with_fake_rpy2(check, os_name='nt', sh_path=None)


def test_silencer_runs_before_the_rpy2_import():
    """Same trap as prepare_r_dll_path(): once rpy2.rinterface is imported,
    openrlib has already run the probe and printed the message."""
    with open(INIT_PATH, encoding='utf-8') as fh:
        tree = ast.parse(fh.read())

    call_line = next(
        (node.lineno for node in ast.walk(tree)
         if isinstance(node, ast.Call)
         and getattr(node.func, 'id', None) == 'silence_r_cmd_config'),
        None)
    assert call_line is not None, 'silence_r_cmd_config() is not called in __init__.py'

    kbstat_line = next(
        (node.lineno for node in tree.body
         if isinstance(node, ast.ImportFrom) and node.module == 'kbstat'),
        None)
    assert kbstat_line is not None, 'the .kbstat import is gone from __init__.py'
    assert call_line < kbstat_line, (
        f'silence_r_cmd_config() is called at line {call_line}, after the '
        f'.kbstat import at line {kbstat_line} - by then rpy2 has run the probe')


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
