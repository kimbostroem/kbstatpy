from ._windows import prepare_r_dll_path, silence_r_cmd_config

# Before any import that reaches rpy2, and hence before R starts: on Windows R
# only finds its own DLLs once its bin folder is on the process search path
# (see _windows.py). A no-op elsewhere.
prepare_r_dll_path()

# Also before rpy2: on Windows rpy2 probes `R CMD config`, which needs `sh`
# from Rtools and otherwise prints a shell error to the console on every
# import. The failure is already handled by rpy2; only the noise is new.
silence_r_cmd_config()

from ._scriptdir import chdir_to_script, script_dir  # noqa: E402
from .options import KbstatOptions   # noqa: E402
from .kbstat import Kbstat           # noqa: E402

__version__ = "1.29.0"
__all__ = ["Kbstat", "KbstatOptions", "chdir_to_script", "script_dir",
           "__version__"]
