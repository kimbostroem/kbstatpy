#!/usr/bin/env python3
"""Keeps the newest CHANGELOG entry short.

CLAUDE.md asks for one or two sentences per item, and that instruction has not
held: entries have drifted into paragraphs several times and had to be rewritten
afterwards, twice at the user's prompting. Prose guidance is not enforceable, so
this is.

Only the newest section is checked, which is the one being written at release
time. Older entries are left as they are, including the long ones that prompted
the rule, because rewriting history is not the point and a test that fails on
untouched files is a test people learn to ignore.

What the limits are for: a bullet is the unit where the drift happens, one item
swelling into a paragraph of mechanism and worked reasoning. The cap is
deliberately loose enough for a breaking change that needs its consequence
spelled out, and tight enough that an explanation of *how* something works will
not fit. That belongs in the commit message and the code comments.

Run:  python3 tests/test_changelog_brevity.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(ROOT, 'CHANGELOG.md')

MAX_WORDS_PER_BULLET = 55
MAX_BULLETS_PER_SECTION = 12


def newest_section():
    """(version, text) of the topmost version block in the changelog."""
    text = open(CHANGELOG, encoding='utf-8').read()
    blocks = re.split(r'^(?=## \[)', text, flags=re.M)
    for block in blocks:
        m = re.match(r'## \[([0-9][0-9.]*)\]', block)
        if m:
            return m.group(1), block
    raise AssertionError('no version section found in CHANGELOG.md')


def bullets(block):
    """Top-level '- ' items, each joined into one string."""
    out, current = [], None
    for line in block.splitlines():
        if line.startswith('- '):
            if current is not None:
                out.append(current)
            current = line[2:].strip()
        elif current is not None:
            if line.strip():
                current += ' ' + line.strip()
            else:
                out.append(current)
                current = None
    if current is not None:
        out.append(current)
    return out


def test_the_newest_entry_matches_the_version():
    """A stale heading means the entry below it describes the wrong release."""
    version, _ = newest_section()
    init = open(os.path.join(ROOT, 'kbstatpy', '__init__.py'), encoding='utf-8').read()
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init)
    assert m, 'no __version__ in kbstatpy/__init__.py'
    assert version == m.group(1), (
        f'newest changelog entry is {version}, __version__ is {m.group(1)}')


def test_no_bullet_in_the_newest_entry_is_an_essay():
    """The cap that does the work.

    Long enough for a breaking change and its consequence, too short for the
    mechanism behind it.
    """
    version, block = newest_section()
    over = [(len(b.split()), b) for b in bullets(block)
            if len(b.split()) > MAX_WORDS_PER_BULLET]
    assert not over, (
        f'{len(over)} bullet(s) in {version} exceed {MAX_WORDS_PER_BULLET} '
        f'words. Say what changed and what it means for the reader; leave the '
        f'mechanism to the commit message.\n' +
        '\n'.join(f'  [{n} words] {b[:100]}...' for n, b in over))


def test_the_newest_entry_is_not_a_list_of_everything():
    """Many small bullets is the other way to write a long entry."""
    version, block = newest_section()
    found = bullets(block)
    assert len(found) <= MAX_BULLETS_PER_SECTION, (
        f'{version} has {len(found)} bullets, more than '
        f'{MAX_BULLETS_PER_SECTION}. Group them, or leave out what a user '
        f'would not notice.')


def test_the_newest_entry_uses_the_standard_headings():
    """Features / Bugs / Changes, so a reader can skip to what affects them."""
    version, block = newest_section()
    heads = re.findall(r'^### (.+)$', block, re.M)
    assert heads, f'{version} has no ### section headings'
    allowed = {'Features', 'Bugs', 'Changes', 'Known limitations'}
    unknown = [h for h in heads if h not in allowed]
    assert not unknown, f'{version} has unexpected headings: {unknown}'


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
