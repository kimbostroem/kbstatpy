#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== kbstatpy demo runner ==="
echo ""

DEMOS=$(ls "$SCRIPT_DIR/demo/demo_"*.py | sort)
FAILED=()

for demo in $DEMOS; do
    name=$(basename "$demo")
    printf "  %-45s" "$name"
    if python3 "$demo" > /tmp/kbstatpy_demo_output.txt 2>&1; then
        echo "OK"
    else
        echo "FAILED"
        echo ""
        echo "Output:"
        cat /tmp/kbstatpy_demo_output.txt
        exit 1
    fi
done

echo ""
echo "=== All demos passed ==="
