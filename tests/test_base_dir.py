#!/usr/bin/env python3
"""Tests for options.base_dir.

What it replaces: `in_file` and `out_dir` are resolved against the working
directory, which is chosen by whatever started the script. An IDE run button,
a terminal, a cron entry and a double-click each pick a different one, so the
same relative path can read or write somewhere unintended and say nothing.

`base_dir = 'auto'` anchors them to the calling script's folder without moving
the process, which is the difference from Kbstat.chdir_to_script(): a script
that also does file work relative to where it was launched keeps that working.

Three failures are guarded.

The keyword is resolved at assignment, not at run time: by the time a run is
under way the caller is whichever module called in, so a late resolution would
answer with kbstatpy's own folder or a helper's.

A directory named `auto` would otherwise be shadowed silently. The keyword
wins -- it has to, or the keyword would stop working wherever such a folder
happened to exist -- but it warns, and './auto' means the folder.

And the default has to stay exactly as it was: an empty base_dir, or an
absolute path, must not be touched.

Needs R (it imports the package).

Run:  python3 tests/test_base_dir.py
"""
import os
import subprocess
import sys
import tempfile
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from kbstatpy import Kbstat, KbstatOptions      # noqa: E402


def _script(body, workdir, folder=None):
    """Run `body` as a script in its own folder, started from `workdir`."""
    home = folder or tempfile.mkdtemp()
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
    out = subprocess.run([sys.executable, path], cwd=workdir, env=env,
                         capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, 'script failed:\n' + out.stderr
    return out.stdout.strip().splitlines()[-1], os.path.realpath(home)


BODY_RESOLVE = (
    "import os\n"
    "from kbstatpy import KbstatOptions\n"
    "o = KbstatOptions()\n"
    "o.base_dir = 'auto'\n"
    "print(os.path.realpath(o.base_dir))\n")

BODY_BOTH_KEYWORDS = (
    "import os\n"
    "from kbstatpy import Kbstat, KbstatOptions\n"
    "seen = set()\n"
    "for kw in ('script_dir', 'auto'):\n"
    "    o = KbstatOptions()\n"
    "    o.base_dir = kw\n"
    "    seen.add(os.path.realpath(o.base_dir))\n"
    "seen.add(os.path.realpath(Kbstat.script_dir()))\n"
    "print(len(seen) == 1 and seen.pop() == "
    "os.path.realpath(os.path.dirname(os.path.abspath(__file__))))\n")

BODY_INFILE = (
    "import os\n"
    "from kbstatpy import Kbstat, KbstatOptions\n"
    "o = KbstatOptions()\n"
    "o.base_dir = 'auto'\n"
    "o.in_file = 'Data/x.csv'\n"
    "print(os.path.realpath(Kbstat(o)._resolve_path(o.in_file)))\n")

BODY_NO_CHDIR = (
    "import os\n"
    "from kbstatpy import KbstatOptions\n"
    "before = os.path.realpath(os.getcwd())\n"
    "o = KbstatOptions()\n"
    "o.base_dir = 'auto'\n"
    "print(before == os.path.realpath(os.getcwd()))\n")


def test_the_keyword_becomes_the_scripts_folder():
    """Assigning it must leave a real path behind, not the word."""
    with tempfile.TemporaryDirectory() as elsewhere:
        got, home = _script(BODY_RESOLVE, elsewhere)
        assert got == home, 'base_dir is ' + repr(got) + ', expected ' + repr(home)
        assert got != 'auto'


def test_a_relative_in_file_is_anchored_to_it():
    """The point of the option: 'Data/x.csv' is the script's Data/x.csv."""
    with tempfile.TemporaryDirectory() as elsewhere:
        got, home = _script(BODY_INFILE, elsewhere)
        assert got == os.path.join(home, 'Data', 'x.csv'), got


def test_it_does_not_move_the_process():
    """The whole difference from chdir_to_script(): nothing global changes."""
    with tempfile.TemporaryDirectory() as elsewhere:
        got, _ = _script(BODY_NO_CHDIR, elsewhere)
        assert got == 'True', 'the working directory moved'


def test_an_empty_base_dir_resolves_against_the_working_directory():
    """The default must behave exactly as before the option existed.

    That is not "leave the path alone": kbstatpy has always made a relative
    in_file/out_dir absolute against the working directory, so output lands
    somewhere writable and a later chdir cannot move it.
    """
    o = KbstatOptions()
    k = Kbstat(o)
    for rel in (os.path.join('Data', 'x.csv'), 'Results'):
        assert k._resolve_path(rel) == os.path.abspath(rel), rel


def test_an_absolute_path_is_left_alone():
    """base_dir anchors relative paths; it must not rewrite absolute ones."""
    o = KbstatOptions()
    o.base_dir = os.sep + os.path.join('some', 'root')
    absolute = os.sep + os.path.join('elsewhere', 'x.csv')
    assert Kbstat(o)._resolve_path(absolute) == absolute


def test_a_plain_path_is_accepted_as_well_as_the_keyword():
    """base_dir is a directory option first and a keyword second."""
    o = KbstatOptions()
    o.base_dir = os.path.join('some', 'root')
    assert o.base_dir == os.path.join('some', 'root'), o.base_dir
    got = Kbstat(o)._resolve_path(os.path.join('Data', 'x.csv'))
    assert got == os.path.abspath(
        os.path.join('some', 'root', 'Data', 'x.csv')), got


def test_a_directory_named_auto_warns_instead_of_being_shadowed_silently():
    """The keyword wins, but never quietly: './auto' is the way to mean it."""
    start = os.getcwd()
    with tempfile.TemporaryDirectory() as home:
        os.mkdir(os.path.join(home, 'auto'))
        os.chdir(home)
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                o = KbstatOptions()
                o.base_dir = 'auto'
            msgs = [str(w.message) for w in caught]
            assert any('also' in m and './auto' in m for m in msgs), msgs
        finally:
            os.chdir(start)


def test_a_fileless_caller_warns_and_falls_back_to_the_working_directory():
    """A notebook has no script; inventing a folder would be worse than cwd."""
    scope = {'KbstatOptions': KbstatOptions}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        exec(compile("o = KbstatOptions()\no.base_dir = 'auto'",
                     '<string>', 'exec'), scope)
    assert scope['o'].base_dir == os.getcwd(), scope['o'].base_dir
    assert any('no script' in str(w.message) or 'none here' in str(w.message)
               for w in caught), [str(w.message) for w in caught]


def test_both_keywords_and_the_method_agree():
    """'script_dir', 'auto' and Kbstat.script_dir() name one folder.

    They are three spellings of the same thing, so a change that resolved one
    of them differently would be a silent split in the vocabulary.
    """
    with tempfile.TemporaryDirectory() as elsewhere:
        got, _ = _script(BODY_BOTH_KEYWORDS, elsewhere)
        assert got == 'True', got


def test_the_explicit_keyword_is_accepted():
    """'script_dir' is the documented primary; it must actually resolve."""
    o = KbstatOptions()
    o.base_dir = 'script_dir'
    assert o.base_dir != 'script_dir', 'left as the literal word'
    assert os.path.isdir(o.base_dir), o.base_dir


def test_a_dot_means_the_working_directory_not_the_script():
    """'.' keeps its ordinary meaning, which is why it is not a keyword.

    Redefining it would give one character two meanings two lines apart, and
    would leave no way to say "explicitly the working directory".
    """
    o = KbstatOptions()
    o.base_dir = '.'
    assert o.base_dir == '.', o.base_dir
    rel = os.path.join('Data', 'x.csv')
    assert Kbstat(o)._resolve_path(rel) == os.path.abspath(rel)


def test_an_absolute_path_survives_both_guards():
    """Absolute in_file/out_dir must ignore base_dir entirely.

    Two things protect this -- the isabs early return and os.path.join's own
    handling of an absolute second argument -- and each alone suffices, so
    only removing both reveals the behaviour. Asserted on the result rather
    than on either mechanism.
    """
    o = KbstatOptions()
    o.base_dir = os.sep + os.path.join('some', 'root')
    k = Kbstat(o)
    for absolute in (os.sep + os.path.join('elsewhere', 'x.csv'),
                     os.sep + 'x.csv'):
        assert k._resolve_path(absolute) == absolute, absolute


if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print('PASS  ' + name)
            except AssertionError as e:
                failures += 1
                print('FAIL  ' + name + '\n      ' + str(e))
            except Exception as e:
                failures += 1
                print('ERROR ' + name + '\n      ' + type(e).__name__ + ': ' + str(e))
    print('\n' + ('all tests passed' if not failures
                  else str(failures) + ' test(s) FAILED'))
    sys.exit(1 if failures else 0)
