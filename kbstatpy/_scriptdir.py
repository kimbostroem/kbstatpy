"""Find, and optionally move to, the directory of the script that is running.

Every evaluation script starts by locating itself, because the data sit next
to it rather than next to whatever directory it happens to be launched from::

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, '..', 'Data')

Three lines of boilerplate, an `import os` that the script otherwise does not
need, and a trap: run the same script from another folder and the plain
relative path that looked fine silently resolves somewhere else. An IDE's
"run" button, a cron entry and a double-click each pick a different working
directory.

`chdir_to_script()` collapses that to one line and makes plain relative paths
mean what they look like -- relative to the script.

The script's path comes from the call stack rather than from an argument, so
nothing has to be passed in and `__file__` never appears in the script. The
first frame outside this package is the caller, and the search stops there: it
must not continue up into the interpreter's own frames, which do have a
`__file__`, and following them would answer with ipykernel's install
directory in a notebook.

A context with no `__file__` at all -- a REPL, a notebook cell, `exec()` of a
string -- has no script directory to name. Both functions answer None there
rather than guessing, and `chdir_to_script()` warns and leaves the working
directory alone, since in those contexts it is already the one the user chose.
"""
import inspect
import os
import sys
import warnings

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))


def _caller_file():
    """Absolute path of the file of the first frame outside this package.

    None when that frame has no `__file__`. The walk stops at the first frame
    outside the package rather than continuing until it finds a `__file__`:
    the caller is that frame, and if it has no file then no file is the
    honest answer.
    """
    frame = inspect.currentframe()
    try:
        while frame is not None:
            name = frame.f_globals.get('__file__')
            inside = bool(name) and os.path.abspath(name).startswith(
                _PACKAGE_DIR + os.sep)
            if not inside:
                return os.path.abspath(name) if name else None
            frame = frame.f_back
    finally:
        # Frames hold references to their locals; dropping ours keeps this out
        # of the reference cycles the cycle collector would otherwise have to
        # break.
        del frame
    return None


def script_dir():
    """Directory of the calling script, or None if it has no file.

    Replaces `os.path.dirname(os.path.abspath(__file__))` without changing the
    working directory, for a script that would rather build its paths
    explicitly than move.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller and friends: the script is inside the bundle, and the
        # data sits beside the executable.
        return os.path.dirname(os.path.abspath(sys.executable))

    name = _caller_file()
    return os.path.dirname(name) if name else None


def chdir_to_script():
    """Change the working directory to the calling script's. Returns it.

    Returns None, with a warning and no change, when there is no script to
    move to.
    """
    target = script_dir()
    if target is None:
        warnings.warn(
            'chdir_to_script(): no script file to locate (interactive session, '
            'notebook, or exec()); the working directory is unchanged.',
            stacklevel=2)
        return None

    os.chdir(target)
    return target
