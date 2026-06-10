#!/usr/bin/env bash
set -e

echo "=== kbstatpy installer ==="
echo ""

# ------------------------------------------------------------------
# 1. Check prerequisites
# ------------------------------------------------------------------

echo "[1/4] Checking prerequisites..."

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.10+ and re-run."
    exit 1
fi

if ! command -v pip3 &>/dev/null; then
    echo "ERROR: pip3 not found. Please install pip and re-run."
    exit 1
fi

if ! command -v R &>/dev/null; then
    echo "ERROR: R not found. Please install R (https://cran.r-project.org) and re-run."
    exit 1
fi

if ! command -v Rscript &>/dev/null; then
    echo "ERROR: Rscript not found. Please install R and re-run."
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
R_VERSION=$(R --version | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
echo "  Python $PYTHON_VERSION found"
echo "  R $R_VERSION found"

# ------------------------------------------------------------------
# 2. Install Python packages
# ------------------------------------------------------------------

echo ""
echo "[2/4] Installing Python packages..."

pip3 install \
    pymer4 \
    polars \
    pyarrow \
    pandas \
    rpy2 \
    scikit-learn \
    formulae \
    great_tables \
    joblib \
    numpy

echo "  Python packages installed."

# ------------------------------------------------------------------
# 3. Install R packages
# ------------------------------------------------------------------

echo ""
echo "[3/4] Installing R packages..."

Rscript -e '
pkgs <- c(
    "lme4", "lmerTest", "emmeans",
    "tibble", "broom", "broom.mixed",
    "report", "see", "parameters", "performance",
    "effectsize", "insight", "datawizard", "bayestestR"
)
missing <- pkgs[!pkgs %in% installed.packages()[, "Package"]]
if (length(missing) > 0) {
    cat("Installing R packages:", paste(missing, collapse=", "), "\n")
    install.packages(missing, repos="https://cloud.r-project.org", quiet=TRUE)
} else {
    cat("All R packages already installed.\n")
}
'

echo "  R packages installed."

# ------------------------------------------------------------------
# 4. Fix rpy2 R version symlink (macOS only)
# ------------------------------------------------------------------

echo ""
echo "[4/4] Checking rpy2 / R version compatibility (macOS only)..."

if [[ "$(uname)" == "Darwin" ]]; then
    R_VERSIONS_DIR="/Library/Frameworks/R.framework/Versions"
    CURRENT_R=$(readlink "$R_VERSIONS_DIR/Current" 2>/dev/null || ls -1 "$R_VERSIONS_DIR" | grep -v Current | sort -V | tail -1)
    CURRENT_R_PATH="$R_VERSIONS_DIR/$CURRENT_R"

    # Find the rpy2 .so and extract the R version it was compiled against
    SO_PATH=$(python3 -c "import site; print(site.getsitepackages()[0])" 2>/dev/null)/_rinterface_cffi_api.abi3.so
    COMPILED_AGAINST=$(otool -L "$SO_PATH" 2>/dev/null | grep -oE 'R\.framework/Versions/[^/]+' | head -1 | grep -oE '[^/]+$' || true)

    if [[ -n "$COMPILED_AGAINST" && "$COMPILED_AGAINST" != "$CURRENT_R" ]]; then
        SYMLINK_PATH="$R_VERSIONS_DIR/$COMPILED_AGAINST"
        if [[ ! -e "$SYMLINK_PATH" ]]; then
            echo "  rpy2 was compiled against R $COMPILED_AGAINST but R $CURRENT_R is installed."
            echo "  Creating compatibility symlink (requires sudo)..."
            sudo ln -sf "$CURRENT_R_PATH" "$SYMLINK_PATH"
            echo "  Symlink created: $SYMLINK_PATH -> $CURRENT_R_PATH"
        else
            echo "  Compatibility symlink already exists."
        fi
    else
        echo "  rpy2 and R versions are compatible — no symlink needed."
    fi
else
    echo "  Not macOS — skipping symlink check."
fi

# ------------------------------------------------------------------
# Done
# ------------------------------------------------------------------

echo ""
echo "=== Installation complete ==="
echo ""
echo "To verify, run:"
echo "  python3 demo/demo_reaction_time.py"
echo ""
