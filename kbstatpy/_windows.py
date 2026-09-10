"""Make R's own DLLs findable before rpy2 starts R (Windows only).

R keeps its shared libraries -- R.dll and its neighbours Rblas, Rlapack,
Rgraphapp, Riconv -- in ``<R_HOME>\\bin\\x64``, and loads several of them lazily:
the first package that needs LAPACK is what pulls in Rlapack.dll, not R
startup. That load is issued by R itself, through the plain Windows loader,
which searches the process ``PATH``. Nothing puts R's bin folder there: the R
installer deliberately leaves ``PATH`` alone, and rpy2 registers the folder
with ``os.add_dll_directory()``, which covers DLLs Python loads but not
necessarily ones R loads on its own.

When it goes wrong it goes wrong late and misleadingly. R starts, rpy2 reports
its version, and the failure surfaces at the first ``library()`` call as

    unable to load shared object '.../library/stats/libs/x64/stats.dll':
    LoadLibrary failure: The specified module could not be found

naming stats.dll, which is present, rather than the neighbour of R.dll that is
missing from the search path. Every model kbstatpy fits goes through ``stats``,
so the package is unusable on such a machine.

rpy2 has a second route to the folder -- it asks ``R CMD config --ldflags``
where R's libraries live -- but ``R CMD`` needs ``sh`` from Rtools, which a
Windows user installing binary packages has no other reason to have.

So the folder is put on ``PATH`` here, and registered as a DLL directory as
well, since the two mechanisms cover different callers and neither is
expensive. ``os.environ`` writes through to the real process environment on
Windows, so the loader sees the change. It has to happen before rpy2 is
imported, which is why ``kbstatpy/__init__.py`` calls this first, above its own
imports.

Everything here is a no-op on macOS and Linux.
"""
import os
import platform
import sys

# os.add_dll_directory() returns a handle that unregisters the directory when
# it is closed, so the handles are kept for the life of the process.
_dll_directories = []


def _r_home():
    """R's installation directory, or None.

    R_HOME first (an explicit choice, and what rpy2 itself reads), then the
    registry keys the R installer writes. R64 before R and machine-wide before
    per-user, matching install.ps1: prefer the 64-bit build, which is the only
    one rpy2 can load.
    """
    home = os.environ.get('R_HOME')
    if home and os.path.isdir(home):
        return home

    try:
        import winreg
    except ImportError:
        return None

    for root, key in ((winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\R-core\R64'),
                      (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\R-core\R'),
                      (winreg.HKEY_CURRENT_USER, r'SOFTWARE\R-core\R64'),
                      (winreg.HKEY_CURRENT_USER, r'SOFTWARE\R-core\R')):
        try:
            with winreg.OpenKey(root, key) as handle:
                path = winreg.QueryValueEx(handle, 'InstallPath')[0]
        except OSError:
            continue
        if path and os.path.isdir(path):
            return path

    return None


def _r_bin(home):
    """The folder holding R.dll inside an R installation, or None.

    R >= 4.2 merged ``bin\\x64`` into ``bin\\``, but the split layout is still
    what a current CRAN build installs, so both are tried -- architecture
    subfolder first, as rpy2 does.
    """
    if platform.machine().lower() == 'arm64':
        arch = 'arm64'
    elif sys.maxsize > 2 ** 32:
        arch = 'x64'
    else:
        arch = 'i386'

    for candidate in (os.path.join(home, 'bin', arch), os.path.join(home, 'bin')):
        if os.path.isfile(os.path.join(candidate, 'R.dll')):
            return candidate

    return None


def _prepend_path(path, bin_dir):
    """`bin_dir` in front of `path`, or `path` unchanged if it is in there.

    Entries are compared lowercased, unquoted and without a trailing
    separator, the three ways one folder gets spelled on a Windows PATH.
    Prepending unconditionally would be harmless the first time and untidy
    after the twentieth import in a notebook session.
    """
    # ';' rather than os.pathsep: this is a Windows PATH whatever the machine
    # reading it, and a Windows path is full of the ':' that os.pathsep is
    # elsewhere. The tests split one on macOS.
    entries = [e.strip('"').rstrip('\\').lower() for e in path.split(';') if e]
    if bin_dir.rstrip('\\').lower() in entries:
        return path
    return bin_dir + ';' + path if path else bin_dir


def prepare_r_dll_path():
    """Put R's library folder on the DLL search path. Returns it, or None.

    None means either "not Windows" or "R was not found", and is not an error
    in itself: R may be somewhere this cannot see, in which case importing rpy2
    fails next with a message about R, which is the more useful one. Silent by
    design -- a warning here would fire on every macOS and Linux import.
    """
    if os.name != 'nt':
        return None

    home = _r_home()
    if not home:
        return None

    bin_dir = _r_bin(home)
    if not bin_dir:
        return None

    os.environ['PATH'] = _prepend_path(os.environ.get('PATH', ''), bin_dir)

    add_dll_directory = getattr(os, 'add_dll_directory', None)
    if add_dll_directory is not None:
        try:
            _dll_directories.append(add_dll_directory(bin_dir))
        except OSError:
            # Vanished between the isfile() above and here, or unreadable.
            # PATH is already set, which is the half that matters.
            pass

    return bin_dir
