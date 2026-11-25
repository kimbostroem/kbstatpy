#!/usr/bin/env python3
"""Tests for the update notice in notebooks.

What it guards: an installation on a JupyterHub stays at the version it was
installed with, so students who installed on different days run different
versions, and a fix released later never reaches them. In a notebook kbstatpy
now looks up the newest release while R starts and says when it is newer.

The failures guarded: the notice must appear when a newer version exists, with
the install line on a JupyterHub; it must not appear when the running version
is current or newer; a lookup that fails (no network) must stay silent and must
not break the import; and outside a notebook, or with KBSTATPY_NO_UPDATE_CHECK
or KBSTATPY_QUIET, there is no notice (and no lookup) at all.

No network is used: KBSTATPY_VERSION_URL points the lookup at a local file
holding a made-up __version__, and a notebook kernel is stood in for by a module
named ipykernel, which is all kbstatpy looks at.

Needs R (each case imports the package in a fresh interpreter).

Run:  python3 tests/test_update_notice.py
"""
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKE_KERNEL = "import sys, types; sys.modules['ipykernel'] = types.ModuleType('ipykernel')\n"


def _version_file(version):
    path = os.path.join(tempfile.mkdtemp(), '__init__.py')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(f'__version__ = "{version}"\n')
    return pathlib.Path(path).as_uri()


def _import(url, notebook=True, **env_extra):
    env = dict(os.environ)
    for k in ('KBSTATPY_QUIET', 'KBSTATPY_NO_UPDATE_CHECK', 'JUPYTERHUB_USER'):
        env.pop(k, None)
    env['KBSTATPY_VERSION_URL'] = url
    env.update(env_extra)
    code = ('import sys\nsys.path.insert(0, ' + repr(ROOT) + ')\n'
            + (FAKE_KERNEL if notebook else '') + 'import kbstatpy\n')
    out = subprocess.run([sys.executable, '-c', code], capture_output=True,
                         text=True, env=env, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout


def test_a_newer_release_is_announced():
    out = _import(_version_file('99.0.0'))
    assert 'kbstatpy 99.0.0 is available' in out, out
    assert out.index(' ready (') < out.index('is available'), out


def test_on_a_jupyterhub_the_notice_gives_the_install_line():
    out = _import(_version_file('99.0.0'), JUPYTERHUB_USER='student')
    assert 'install_jupyterhub.sh' in out and 'Restart Kernel' in out, out


def test_the_current_or_an_older_version_is_not_announced():
    # The running version, read from the source rather than imported, which
    # would start R in this process too.
    import re
    src = open(os.path.join(ROOT, 'kbstatpy', '__init__.py'), encoding='utf-8').read()
    current = re.search(r'^__version__\s*=\s*"([^"]+)"', src, re.M).group(1)
    for version in (current, '0.1.0'):
        out = _import(_version_file(version))
        assert ' ready (' in out and 'is available' not in out, (version, out)


def test_a_failed_lookup_stays_silent():
    out = _import('http://127.0.0.1:9/__init__.py')         # nothing listens on port 9
    assert ' ready (' in out and 'is available' not in out, out


def test_no_notice_outside_a_notebook():
    out = _import(_version_file('99.0.0'), notebook=False)
    assert 'is available' not in out and out.strip() == '', out


def test_it_can_be_switched_off():
    for var in ('KBSTATPY_NO_UPDATE_CHECK', 'KBSTATPY_QUIET'):
        out = _import(_version_file('99.0.0'), **{var: '1'})
        assert 'is available' not in out, (var, out)


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
