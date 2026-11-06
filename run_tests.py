#!/usr/bin/env python3
"""Run the kbstatpy test files in parallel and report pass/fail.

Each tests/test_*.py is a standalone script that starts its own R, so the
files are independent processes and run side by side; serially the suite
spends most of its time starting R and fitting models one file at a time.
They write to separate folders (their own /tmp/kbstatpy_* or a temporary
directory) and bind no fixed port, which is what makes this safe. A new test
must keep it so.

A file passes when it exits 0 and prints no FAIL or ERROR line.

Usage:
    python3 run_tests.py                 # all files, half the CPU cores at a time
    python3 run_tests.py -j 6            # six at a time
    python3 run_tests.py offset per_y    # only files whose name contains these
"""

import argparse
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).parent


def run(path):
    t0 = time.monotonic()
    env = dict(os.environ, MPLBACKEND='Agg', KBSTATPY_NO_UPDATE_CHECK='1')
    r = subprocess.run([sys.executable, str(path)], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    out = r.stdout + r.stderr
    n_pass = len(re.findall(r'^PASS\b', out, re.M))
    bad = [l for l in out.splitlines() if re.match(r'(FAIL|ERROR)\b', l)]
    ok = r.returncode == 0 and not bad
    return path.name, ok, n_pass, time.monotonic() - t0, out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('-j', '--jobs', type=int, default=max(1, (os.cpu_count() or 2) // 2),
                    help='files run at once (default: half the CPU cores)')
    ap.add_argument('names', nargs='*', help='run only files whose name contains one of these')
    args = ap.parse_args()

    files = sorted(ROOT.glob('tests/test_*.py'))
    if args.names:
        files = [f for f in files if any(n in f.name for n in args.names)]
    if not files:
        sys.exit('No test files match.')

    print(f'=== kbstatpy tests: {len(files)} files, {args.jobs} at a time ===\n')
    t0 = time.monotonic()
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for fut in as_completed(pool.submit(run, f) for f in files):
            name, ok, n_pass, secs, out = fut.result()
            results.append((name, ok, n_pass, secs, out))
            print(f'  {"ok    " if ok else "FAILED"} {name:<42} {n_pass:>3} passed  {secs:5.0f} s',
                  flush=True)

    failed = [r for r in results if not r[1]]
    for name, _, _, _, out in sorted(failed):
        print(f'\n--- {name} ---\n{out.rstrip()}')
    total = sum(r[2] for r in results)
    print(f'\n{total} tests passed in {len(results) - len(failed)} of {len(results)} files, '
          f'{time.monotonic() - t0:.0f} s wall time '
          f'({sum(r[3] for r in results):.0f} s one after another).')
    if failed:
        print(f'{len(failed)} file(s) FAILED: {", ".join(sorted(r[0] for r in failed))}')
        sys.exit(1)


if __name__ == '__main__':
    main()
