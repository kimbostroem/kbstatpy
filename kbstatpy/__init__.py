from ._windows import prepare_r_dll_path

# Before any import that reaches rpy2, and hence before R starts: on Windows R
# only finds its own DLLs once its bin folder is on the process search path
# (see _windows.py). A no-op elsewhere.
prepare_r_dll_path()

from .options import KbstatOptions   # noqa: E402
from .kbstat import Kbstat           # noqa: E402

__version__ = "1.22.0"
__all__ = ["Kbstat", "KbstatOptions", "__version__"]
