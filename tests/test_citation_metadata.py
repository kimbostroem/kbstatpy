#!/usr/bin/env python3
"""Tests that CITATION.cff stays valid and in step with the released version.

CITATION.cff is the one file a release can forget without anything breaking: no
import reads it, so nothing complains, and it had silently drifted six minor
versions behind (1.7.1 against 1.13.4) before anyone noticed. It also carried two
keys that CFF 1.2.0 does not define, so GitHub's "Cite this repository" panel had
nothing valid to render. These tests make both failure modes loud at the moment
they happen — a release that leaves CITATION.cff behind fails the suite.

Three version sources must agree: `kbstatpy.__version__` (which pyproject reads
via `version = {attr = ...}`), the newest CHANGELOG heading, and CITATION.cff.

Metadata only, so this needs neither R nor glmmTMB.

Run:  python3 tests/test_citation_metadata.py
"""
import datetime as dt
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from kbstatpy import __version__ as PKG_VERSION    # noqa: E402

CFF_PATH = os.path.join(ROOT, 'CITATION.cff')
CHANGELOG_PATH = os.path.join(ROOT, 'CHANGELOG.md')

# CFF 1.2.0 top-level keys for a software citation, from the schema guide.
# Anything outside this set is silently ignored by consumers, which is how
# `programming-languages` (a CodeMeta key, not a CFF one) survived unnoticed.
CFF_KEYS = {
    'abstract', 'authors', 'cff-version', 'commit', 'contact', 'date-released',
    'doi', 'identifiers', 'keywords', 'license', 'license-url', 'message',
    'preferred-citation', 'references', 'repository', 'repository-artifact',
    'repository-code', 'title', 'type', 'url', 'version',
}
CFF_REQUIRED = {'cff-version', 'message', 'title', 'authors'}
CFF_TYPES = {'software', 'dataset'}


def cff():
    with open(CFF_PATH, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def changelog_version():
    with open(CHANGELOG_PATH, encoding='utf-8') as fh:
        m = re.search(r'^## \[([0-9]+\.[0-9]+\.[0-9]+)\]', fh.read(), re.M)
    assert m, 'no version heading found in CHANGELOG.md'
    return m.group(1)


def test_citation_version_matches_the_package():
    """The regression guard: a release that forgets CITATION.cff fails here."""
    assert str(cff()['version']) == PKG_VERSION, (
        f"CITATION.cff says version {cff()['version']}, package says "
        f'{PKG_VERSION} — bump CITATION.cff as part of the release')


def test_changelog_version_matches_the_package():
    """The other half of the same release step."""
    assert changelog_version() == PKG_VERSION, (
        f'newest CHANGELOG entry is {changelog_version()}, package says '
        f'{PKG_VERSION}')


def test_required_keys_are_present():
    missing = CFF_REQUIRED - set(cff())
    assert not missing, f'CITATION.cff is missing required CFF keys: {sorted(missing)}'


def test_no_undefined_keys():
    """An unknown key is not an error to any consumer — it is simply dropped, so
    only a test catches it."""
    unknown = set(cff()) - CFF_KEYS
    assert not unknown, (
        f'CITATION.cff has keys CFF 1.2.0 does not define: {sorted(unknown)}')


def test_type_is_a_valid_cff_type():
    t = cff().get('type', 'software')
    assert t in CFF_TYPES, f'type: {t!r} is not one of {sorted(CFF_TYPES)}'


def test_authors_carry_a_name():
    authors = cff()['authors']
    assert authors, 'CITATION.cff lists no authors'
    for a in authors:
        assert ('family-names' in a and 'given-names' in a) or 'name' in a, \
            f'author entry carries no usable name: {a!r}'


def test_date_released_is_an_iso_date():
    raw = cff().get('date-released')
    assert raw is not None, 'CITATION.cff has no date-released'
    # yaml parses an unquoted ISO date into a date object; accept either form
    if not isinstance(raw, dt.date):
        dt.date.fromisoformat(str(raw))     # raises if malformed


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
