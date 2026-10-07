import os as _os
import sys as _sys
import time as _time

# In a notebook, say that R is starting before it does: the first import loads
# R and its packages, which takes seconds on a laptop and up to a minute on a
# small cloud share (a JupyterHub, Colab), and until now the cell sat there
# without a word, which looked like a hang. Only in a notebook kernel
# (ipykernel); a script's output stays as it was, since tools read it.
# KBSTATPY_QUIET=1 silences it there too.
_ANNOUNCE = 'ipykernel' in _sys.modules and not _os.environ.get('KBSTATPY_QUIET')
_t0 = _time.monotonic()
if _ANNOUNCE:
    print('kbstatpy: starting R and loading its packages '
          '(the first time in a session this can take up to a minute) ...', flush=True)

from ._windows import prepare_r_dll_path, silence_r_cmd_config  # noqa: E402

# Before any import that reaches rpy2, and hence before R starts: on Windows R
# only finds its own DLLs once its bin folder is on the process search path
# (see _windows.py). A no-op elsewhere.
prepare_r_dll_path()

# Also before rpy2: on Windows rpy2 probes `R CMD config`, which needs `sh`
# from Rtools and otherwise prints a shell error to the console on every
# import. The failure is already handled by rpy2; only the noise is new.
silence_r_cmd_config()

from ._scriptdir import chdir, script_dir  # noqa: E402
from .options import KbstatOptions   # noqa: E402
from .kbstat import Kbstat           # noqa: E402

__version__ = "1.39.0"
__all__ = ["Kbstat", "KbstatOptions", "chdir", "script_dir",
           "__version__"]

if _ANNOUNCE:
    print(f'kbstatpy {__version__} ready ({_time.monotonic() - _t0:.0f} s).', flush=True)
