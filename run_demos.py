#!/usr/bin/env python3
"""Run all kbstatpy demo scripts and report pass/fail."""

import subprocess
import sys
from pathlib import Path

script_dir = Path(__file__).parent
demos = sorted(script_dir.glob('demo/demo_*.py'))

print('=== kbstatpy demo runner ===\n')

failed = []
for demo in demos:
    print(f'  {demo.name:<45}', end='', flush=True)
    result = subprocess.run(
        [sys.executable, str(demo)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print('OK')
    else:
        print('FAILED')
        failed.append(demo.name)
        print()
        print(result.stdout)
        print(result.stderr)

print()
if failed:
    print(f'=== {len(failed)} demo(s) FAILED ===')
    for name in failed:
        print(f'  {name}')
    sys.exit(1)
else:
    print('=== All demos passed ===')
