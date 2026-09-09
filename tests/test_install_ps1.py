#!/usr/bin/env python3
"""Static checks on install.ps1, the Windows installer.

install.ps1 cannot be executed anywhere in this project's test loop: the
development machines are macOS, there is no Windows CI, and PowerShell 5.1
behaviour differs from pwsh on other platforms in exactly the area that broke.
So it is checked by reading instead, and only for failure modes that actually
occurred.

The failure these guard against: the installer set
`$ErrorActionPreference = 'Stop'` and then invoked native executables directly.
PowerShell 5.1 wraps anything a native executable writes to stderr in an error
record, and under 'Stop' that record is *terminating*. `2>$null` does not help,
because the record is raised before the redirection discards the text. The
consequences on a real user's machine:

  * The Microsoft Store python.exe placeholder prints "Python was not found" to
    stderr. That aborted the installer at the first candidate probe with a
    NativeCommandError, instead of rejecting the placeholder and moving on to
    the `py -3` launcher - so the whole thing failed at step 1 on any machine
    where the Store alias was ahead of the real Python on PATH.
  * R prints download progress to stderr, so step 3 would have died the same
    way on any machine that got that far.

The fix routes every native call through Invoke-Native / Get-NativeLine, which
reset the preference in their own function scope. These tests fail if a later
edit reintroduces a bare native call, or removes the reset - neither of which
looks wrong in a diff.

The remaining tests are a crude syntax check, for the same reason: nothing here
can run the script, so an unbalanced brace or here-string would otherwise reach
a user unnoticed.

No R, no imports from the package.

Run:  python3 tests/test_install_ps1.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PS1_PATH = os.path.join(ROOT, 'install.ps1')

# The only two functions allowed to invoke a native executable.
NATIVE_HELPERS = ('Invoke-Native', 'Get-NativeLine')


def lines():
    with open(PS1_PATH, encoding='utf-8') as fh:
        return fh.read().split('\n')


def strip_here_strings(src):
    """Blank out @'...'@ / @"..."@ bodies, keeping line numbering intact.

    Their contents are R and Python, so PowerShell rules do not apply to them.
    Returns (blanked lines, True if a here-string was left open).
    """
    out, inside = [], False
    for line in src:
        if not inside and re.search(r"@[\"']$", line.rstrip()):
            inside = True
            out.append('')
            continue
        if inside:
            if line.strip() in ("'@", '"@'):
                inside = False
            out.append('')
            continue
        out.append(line)
    return out, inside


def strip_quotes_and_comments(line):
    """Drop comments and the contents of quoted strings from one code line."""
    out, i = '', 0
    while i < len(line):
        ch = line[i]
        if ch == '#':
            break
        if ch == "'":
            i += 1
            while i < len(line):
                if line[i] == "'":
                    if i + 1 < len(line) and line[i + 1] == "'":
                        i += 2
                        continue
                    break
                i += 1
            i += 1
            continue
        if ch == '"':
            i += 1
            while i < len(line):
                if line[i] == '`':
                    i += 2
                    continue
                if line[i] == '"':
                    break
                i += 1
            i += 1
            continue
        out += ch
        i += 1
    return out


def code_lines():
    """1-indexed map of line number -> line with strings and comments removed."""
    blanked, _ = strip_here_strings(lines())
    return {n: strip_quotes_and_comments(l) for n, l in enumerate(blanked, 1)}


def function_range(name):
    """(first, last) 1-indexed line numbers of a function's body, by brace depth."""
    code = code_lines()
    start = next((n for n, l in code.items()
                  if re.match(r'^\s*function\s+' + re.escape(name) + r'\b', l)), None)
    assert start, f'install.ps1 has no function {name}'
    depth = 0
    for n in range(start, max(code) + 1):
        depth += code[n].count('{') - code[n].count('}')
        if depth == 0 and n > start:
            return start, n
    raise AssertionError(f'function {name} is never closed')


def test_native_calls_only_happen_in_the_two_helpers():
    """The regression guard. A bare `& $exe` outside the helpers runs under
    $ErrorActionPreference = 'Stop', where one line on stderr kills the run."""
    allowed = [function_range(name) for name in NATIVE_HELPERS]
    offenders = []
    for n, line in code_lines().items():
        # The call operator: `& $exe ...`, as opposed to `-and`, `&&` or a `&`
        # inside a string (already stripped above).
        if not re.search(r'(?<![\w&\-])&\s', line):
            continue
        if any(lo <= n <= hi for lo, hi in allowed):
            continue
        offenders.append(f'  line {n}: {line.strip()}')
    assert not offenders, (
        'native executables must be invoked through '
        + ' / '.join(NATIVE_HELPERS) + ', not directly:\n' + '\n'.join(offenders))


def test_both_helpers_reset_the_error_action_preference():
    """Without the reset the helpers are no better than a direct call."""
    src = lines()
    for name in NATIVE_HELPERS:
        lo, hi = function_range(name)
        body = '\n'.join(src[lo - 1:hi])
        assert re.search(r"\$ErrorActionPreference\s*=\s*'Continue'", body), (
            f"{name} does not set $ErrorActionPreference = 'Continue', so a "
            'native command writing to stderr still aborts the installer')


def test_script_scope_stays_strict():
    """The relaxation must be local to the helpers - the cmdlet calls in the rest
    of the script are written on the assumption that a failure stops the run."""
    assert re.search(r"^\$ErrorActionPreference\s*=\s*'Stop'\s*$",
                     '\n'.join(lines()), re.M), \
        "install.ps1 no longer sets $ErrorActionPreference = 'Stop' at script scope"


def test_here_strings_are_closed():
    _, unterminated = strip_here_strings(lines())
    assert not unterminated, 'install.ps1 has an unterminated here-string'


def test_brackets_balance():
    """Crude syntax check: nothing in this repo can parse PowerShell."""
    code = code_lines()
    for open_ch, close_ch, label in (('{', '}', 'braces'),
                                     ('(', ')', 'parentheses'),
                                     ('[', ']', 'brackets')):
        depth = 0
        for n in sorted(code):
            depth += code[n].count(open_ch) - code[n].count(close_ch)
            assert depth >= 0, f'unbalanced {label}: extra {close_ch!r} at line {n}'
        assert depth == 0, f'unbalanced {label}: {depth} unclosed {open_ch!r}'


def test_no_shell_operators_powershell_51_rejects():
    """`&&` and `||` are syntax errors in Windows PowerShell 5.1 (they arrived in
    pwsh 7), including inside the guidance the installer prints for the user to
    paste."""
    offenders = [f'  line {n}: {l.strip()}'
                 for n, l in enumerate(strip_here_strings(lines())[0], 1)
                 if '&&' in l or '||' in l]
    assert not offenders, (
        'Windows PowerShell 5.1 does not accept && or ||:\n' + '\n'.join(offenders))


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
