#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_DIR="$HOME/kbstatpy-test-env"

echo "=== kbstatpy install test ==="
echo ""

# ------------------------------------------------------------------
# 1. Create fresh virtual environment
# ------------------------------------------------------------------

echo "[1/4] Creating fresh virtual environment at $ENV_DIR ..."
rm -rf "$ENV_DIR"
python3 -m venv "$ENV_DIR"
echo "  Done."

# ------------------------------------------------------------------
# 2. Activate and run installer
# ------------------------------------------------------------------

echo ""
echo "[2/4] Activating environment and running install.sh ..."
source "$ENV_DIR/bin/activate"
bash "$SCRIPT_DIR/install.sh"

# ------------------------------------------------------------------
# 3. Run all demos
# ------------------------------------------------------------------

echo ""
echo "[3/4] Running demos ..."
DEMOS=$(ls "$SCRIPT_DIR/demos/scripts/demo_"*.py | sort)
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
        deactivate
        rm -rf "$ENV_DIR"
        exit 1
    fi
done

# ------------------------------------------------------------------
# 4. Clean up
# ------------------------------------------------------------------

echo ""
echo "[4/4] Cleaning up ..."
deactivate
rm -rf "$ENV_DIR"
echo "  Virtual environment removed."

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------

echo ""
if [ ${#FAILED[@]} -eq 0 ]; then
    echo "=== All demos passed ==="
else
    echo "=== ${#FAILED[@]} demo(s) FAILED ==="
    for f in "${FAILED[@]}"; do
        echo "  - $f"
    done
    echo ""
    echo "Last output:"
    cat /tmp/kbstatpy_demo_output.txt
    exit 1
fi
