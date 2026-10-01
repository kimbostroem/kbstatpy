#!/usr/bin/env python3
"""save() writes the code that created the options into out_dir.

A results folder used to hold every table and figure but not the analysis
that made them, so a downloaded zip from Colab, or a folder found months
later, could not be rerun or even checked against what was asked for. The
code is captured when KbstatOptions() is created: in a notebook the options
and the run call sit in different cells, and only the first holds the
analysis.

Cases: a script is copied under its own name; a notebook cell (whose text
IPython keeps in linecache under a name never written to disk) becomes
analysis.py with the run call appended; save_script=False and an exec() of a
plain string write nothing. Needs R, like every test here.

Run:  python3 tests/test_save_script.py
"""
import linecache
import os
import subprocess
import sys
import tempfile
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('MPLBACKEND', 'Agg')

DATA = os.path.join(ROOT, 'demos', 'data', 'sleep.csv')

OPTIONS = textwrap.dedent(f"""\
    from kbstatpy import Kbstat, KbstatOptions
    options = KbstatOptions()
    options.in_file = {DATA!r}
    options.y = 'extra'
    options.x = 'group'
    options.figure_display = 'save_only'
    options.diagnostic_sims = 50
    """)


def test_a_script_is_copied_under_its_own_name():
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, 'my_analysis.py')
        with open(script, 'w') as fh:
            fh.write(OPTIONS + "options.out_dir = 'out'\nKbstat(options).run_save()\n")
        subprocess.run([sys.executable, script], cwd=tmp, check=True,
                       capture_output=True, env={**os.environ, 'PYTHONPATH': ROOT})
        copy = os.path.join(tmp, 'out', 'my_analysis.py')
        assert os.path.isfile(copy), 'script not copied into out_dir'
        assert open(copy).read() == open(script).read(), 'copy differs from the script'


def test_a_notebook_cell_becomes_a_runnable_analysis_py():
    # Mimic ipykernel: the cell is compiled under a temporary file name that
    # exists only in linecache, and its globals carry no __file__.
    with tempfile.TemporaryDirectory() as tmp:
        cell_name = os.path.join(tmp, 'ipykernel_0', '12345.py')
        cell = OPTIONS + f"options.out_dir = {os.path.join(tmp, 'out')!r}\n"
        linecache.cache[cell_name] = (len(cell), None, cell.splitlines(True), cell_name)
        ns = {'__name__': '__main__'}
        exec(compile(cell, cell_name, 'exec'), ns)
        ns['Kbstat'](ns['options']).run_save()        # the "run cell"
        out = os.path.join(tmp, 'out', 'analysis.py')
        assert os.path.isfile(out), 'notebook cell not written as analysis.py'
        text = open(out).read()
        assert text.startswith(cell.rstrip()), 'analysis.py is not the options cell'
        assert text.rstrip().endswith('Kbstat(options).run_save()'), 'run call not appended'


def test_switched_off_or_without_source_nothing_is_written():
    with tempfile.TemporaryDirectory() as tmp:
        for name, extra in (('off', "options.save_script = 'off'\n"), ('exec', '')):
            out = os.path.join(tmp, name)
            ns = {'__name__': '__main__'}
            exec(OPTIONS + extra + f"options.out_dir = {out!r}\n"
                 "Kbstat(options).run_save()\n", ns)
            written = [f for f in os.listdir(out) if f.endswith('.py')]
            assert not written, f'{name}: wrote {written}'


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
