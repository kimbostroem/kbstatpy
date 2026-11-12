#!/usr/bin/env python3
"""figure_display='show_keep' must show the figures and keep them open.

The guarded failure mode: in a plain script, 'show_keep' only called
plt.show(block=False). That never runs the GUI event loop, so no window was
drawn, and the script then exited, taking any window with it: nothing was
shown and nothing kept.

Checked headlessly: the GUI calls are recorded, not made, so no window opens.
Under an interactive backend, 'show_keep' must draw (plt.pause) and register
one exit hook, which blocks in plt.show(block=True) while figures are open;
in an interactive session (sys.ps1 set) no hook is registered.

Run:  python3 tests/test_figure_display_keep.py
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import kbstatpy.kbstat as kbmod                # noqa: E402
from kbstatpy.kbstat import Kbstat             # noqa: E402
from kbstatpy.options import KbstatOptions     # noqa: E402

FAILED = []


def check(name, cond, detail=''):
    print(('PASS' if cond else 'FAIL'), name, detail)
    if not cond:
        FAILED.append(name)


calls = []
hooks = []
plt.show = lambda block=None: calls.append(('show', block))
plt.pause = lambda t: calls.append(('pause', t))
Kbstat._interactive_backend = staticmethod(lambda: True)
import atexit  # noqa: E402
atexit.register = lambda f: hooks.append(f)


def show(mode):
    o = KbstatOptions()
    o.figure_display = mode
    kb = Kbstat.__new__(Kbstat)
    kb.options = o
    fig = plt.figure()
    kb._show_fig(fig, close=True)
    return fig


# --- plain script ---
for name in ('ps1',):
    if hasattr(sys, name):
        delattr(sys, name)
kbmod._KEEP_HOOKED = False
fig = show('show_keep')
check('show_keep: window drawn', ('pause', 0.1) in calls, str(calls))
check('show_keep: figure not closed', plt.fignum_exists(fig.number))
show('show_keep')
check('show_keep: one exit hook, however many figures', len(hooks) == 1, str(len(hooks)))
calls.clear()
hooks[0]()
check('exit hook blocks while figures are open', ('show', True) in calls, str(calls))
plt.close('all')
calls.clear()
hooks[0]()
check('exit hook does nothing once all are closed', not calls, str(calls))

# --- show_close and save_only unchanged ---
calls.clear()
fig = show('show_close')
check('show_close: 3 s pause, then closed',
      ('pause', 3) in calls and not plt.fignum_exists(fig.number), str(calls))
calls.clear()
show('save_only')
check('save_only: no show, no pause', not calls, str(calls))
check('no further hooks', len(hooks) == 1)

# --- interactive session: its own event loop keeps the windows ---
hooks.clear()
kbmod._KEEP_HOOKED = False
sys.ps1 = '>>> '
show('show_keep')
check('interactive session: no exit hook', not hooks)
del sys.ps1

if FAILED:
    print(f'\n{len(FAILED)} FAILED')
    sys.exit(1)
print('\nAll passed')
