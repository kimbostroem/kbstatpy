"""Tell a notebook user when a newer kbstatpy has been released.

An installation on a JupyterHub stays at the version it was installed with;
nothing updates it. In a course that means students on different versions,
and a fix released after their installation never reaches them. So, in a
notebook only, kbstatpy looks up the newest version while R starts and, if it
is newer than the one running, says so and how to update.

The lookup reads `__version__` from the master branch on raw.githubusercontent.com
rather than asking the GitHub API: the API allows 60 unauthenticated requests
an hour per IP address, and a whole class on a university network shares one.
It runs in a background thread with a short timeout, and every failure (no
network, a proxy, a certificate problem) ends in silence: an update notice is
never worth an error message or a delay.

KBSTATPY_NO_UPDATE_CHECK=1 switches it off, as does KBSTATPY_QUIET=1.
KBSTATPY_VERSION_URL points it elsewhere (the tests use a local file).
"""
import os
import re
import threading
import urllib.request

VERSION_URL = ('https://raw.githubusercontent.com/kimbostroem/kbstatpy/'
               'master/kbstatpy/__init__.py')
HUB_INSTALL = ('curl -sSL https://raw.githubusercontent.com/kimbostroem/kbstatpy/'
               'master/install_jupyterhub.sh | bash')
TIMEOUT = 2.0


def _as_tuple(version):
    return tuple(int(p) for p in re.findall(r'\d+', version)[:3])


class UpdateCheck:
    """Look up the newest version in the background; ask for the notice later."""

    def __init__(self):
        self.latest = None
        url = os.environ.get('KBSTATPY_VERSION_URL') or VERSION_URL
        self._thread = threading.Thread(target=self._fetch, args=(url,), daemon=True)
        self._thread.start()

    def _fetch(self, url):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
                text = r.read(65536).decode('utf-8', 'replace')
            m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.M)
            if m:
                self.latest = m.group(1)
        except Exception:
            pass

    def notice(self, installed, wait=1.0):
        """The update notice, or '' when up to date, unknown, or still waiting."""
        self._thread.join(wait)
        if not self.latest:
            return ''
        try:
            if _as_tuple(self.latest) <= _as_tuple(installed):
                return ''
        except ValueError:
            return ''
        if os.environ.get('JUPYTERHUB_USER'):
            how = ('To update: run this line again in a terminal, then '
                   'Kernel > Restart Kernel:\n  ' + HUB_INSTALL)
        else:
            how = ('To update: see https://github.com/kimbostroem/kbstatpy/blob/master/INSTALL.md, '
                   'then restart the kernel.')
        return f'kbstatpy {self.latest} is available (this is {installed}). {how}'


def start():
    """An UpdateCheck, or None where checking is switched off."""
    if os.environ.get('KBSTATPY_NO_UPDATE_CHECK') or os.environ.get('KBSTATPY_QUIET'):
        return None
    return UpdateCheck()
