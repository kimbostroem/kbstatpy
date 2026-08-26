#!/usr/bin/env bash
set -e

echo "=== kbstatpy installer ==="
echo ""

# ------------------------------------------------------------------
# Helpers  (test marker: everything above HELPERS_END is sourceable)
# ------------------------------------------------------------------

# Which platform's package manager to name in the guidance below. Kept coarse on
# purpose: the point is to hand the user a command that works, not to enumerate
# every distribution.
detect_os() {
    case "$(uname)" in
        Darwin) echo macos ;;
        Linux)
            if [ -r /etc/os-release ]; then
                # Subshell so the os-release variables do not leak into the script.
                local id
                id=$(. /etc/os-release 2>/dev/null; echo "${ID:-} ${ID_LIKE:-}")
                case "$id" in
                    *debian*|*ubuntu*) echo debian ;;
                    *fedora*|*rhel*|*centos*) echo fedora ;;
                    *arch*)  echo arch ;;
                    *suse*)  echo suse ;;
                    *)       echo linux ;;
                esac
            else
                echo linux
            fi
            ;;
        *) echo other ;;
    esac
}

# True when $1 is an older version than $2. awk rather than `sort -V`, which is
# absent from some BSD userlands, and rather than a bash 4 construct, because
# macOS still ships bash 3.2.
version_lt() {
    if [ "$1" = "$2" ]; then
        return 1
    fi
    awk -v a="$1" -v b="$2" '
    BEGIN {
        na = split(a, A, "."); nb = split(b, B, ".");
        n = (na > nb ? na : nb);
        for (i = 1; i <= n; i++) {
            x = (i <= na ? A[i] + 0 : 0);
            y = (i <= nb ? B[i] + 0 : 0);
            if (x < y) { exit 0 }
            if (x > y) { exit 1 }
        }
        exit 1
    }'
}

python_help() {
    echo "  Where to get Python 3.10+:"
    case "$(detect_os)" in
        macos)
            echo "    Homebrew:   brew install python@3.13"
            echo "    Installer:  https://www.python.org/downloads/macos/"
            ;;
        debian)
            echo "    apt:        sudo apt update && sudo apt install python3 python3-pip python3-venv"
            echo "    Older Debian/Ubuntu releases ship Python < 3.10; newer builds are in"
            echo "    the deadsnakes PPA:  https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa"
            ;;
        fedora)
            echo "    dnf:        sudo dnf install python3 python3-pip"
            ;;
        arch)
            echo "    pacman:     sudo pacman -S python python-pip"
            ;;
        suse)
            echo "    zypper:     sudo zypper install python3 python3-pip"
            ;;
        *)
            echo "    Downloads:  https://www.python.org/downloads/"
            ;;
    esac
}

r_help() {
    echo "  Where to get R 4.4+:"
    case "$(detect_os)" in
        macos)
            echo "    Homebrew:   brew install --cask r"
            echo "    Installer:  https://cran.r-project.org/bin/macosx/"
            ;;
        debian)
            echo "    The distribution's own r-base is frequently older than 4.4."
            echo "    Add the CRAN repository instead, which carries current R:"
            echo "      Ubuntu:   https://cran.r-project.org/bin/linux/ubuntu/"
            echo "      Debian:   https://cran.r-project.org/bin/linux/debian/"
            ;;
        fedora)
            echo "    dnf:        sudo dnf install R"
            echo "    Details:    https://cran.r-project.org/bin/linux/fedora/"
            ;;
        arch)
            echo "    pacman:     sudo pacman -S r"
            ;;
        suse)
            echo "    zypper:     sudo zypper install R-base"
            ;;
        *)
            echo "    Downloads:  https://cran.r-project.org"
            ;;
    esac
}

# Printed when rpy2 cannot start R. This is the one failure that survives a
# clean-looking install, so it gets its own guidance rather than a bare stack
# trace.
rpy2_help() {
    echo "  What usually causes this:"
    case "$(detect_os)" in
        macos)
            echo "    * rpy2 was built against a different R version than the one installed."
            echo "      Step 4 above creates a compatibility symlink; re-run this installer"
            echo "      after installing or upgrading R."
            echo "    * A stale wheel: python3 -m pip install --force-reinstall --no-cache-dir rpy2"
            ;;
        debian|fedora|arch|suse|linux)
            echo "    * R's shared library is missing. R must be built with --enable-R-shlib;"
            echo "      the CRAN packages are, some distribution packages are not."
            echo "      Ubuntu/Debian also need the headers:  sudo apt install r-base-dev"
            echo "    * R_HOME is not set or points elsewhere:  export R_HOME=\$(R RHOME)"
            echo "    * A stale wheel: python3 -m pip install --force-reinstall --no-cache-dir rpy2"
            ;;
        *)
            echo "    * R_HOME is not set or points elsewhere:  export R_HOME=\$(R RHOME)"
            ;;
    esac
    echo "  rpy2 installation notes: https://rpy2.github.io/doc/latest/html/overview.html"
}

# HELPERS_END

MIN_PYTHON=3.10
MIN_R=4.4

# ------------------------------------------------------------------
# 1. Check prerequisites
# ------------------------------------------------------------------

echo "[1/5] Checking prerequisites..."

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found."
    python_help
    exit 1
fi

# `python3 -m pip` rather than the pip3 executable: pip is frequently installed
# without a pip3 on PATH (and vice versa), and -m cannot target the wrong
# interpreter.
if ! python3 -m pip --version &>/dev/null; then
    echo "ERROR: pip is not available for this python3."
    echo "  Try:  python3 -m ensurepip --upgrade"
    case "$(detect_os)" in
        debian) echo "  or:   sudo apt install python3-pip" ;;
        fedora) echo "  or:   sudo dnf install python3-pip" ;;
        arch)   echo "  or:   sudo pacman -S python-pip" ;;
        suse)   echo "  or:   sudo zypper install python3-pip" ;;
    esac
    echo "  Installing pip: https://pip.pypa.io/en/stable/installation/"
    exit 1
fi

if ! command -v R &>/dev/null || ! command -v Rscript &>/dev/null; then
    echo "ERROR: R not found (need both R and Rscript on PATH)."
    r_help
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
R_VERSION=$(R --version | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)

# These minimums were previously printed but not enforced, so an old interpreter
# failed later with an unrelated-looking pip or R error instead of being named here.
if version_lt "$PYTHON_VERSION" "$MIN_PYTHON"; then
    echo "ERROR: Python $PYTHON_VERSION found, but kbstatpy needs $MIN_PYTHON or newer."
    python_help
    echo "  If a newer Python is already installed, run this installer with it, e.g.:"
    echo "    python3.13 -m venv ~/kbstatpy-env && source ~/kbstatpy-env/bin/activate && bash install.sh"
    exit 1
fi
echo "  Python $PYTHON_VERSION found"

if [ -n "$R_VERSION" ] && version_lt "$R_VERSION" "$MIN_R"; then
    echo "ERROR: R $R_VERSION found, but kbstatpy needs $MIN_R or newer."
    echo "  glmmTMB and emmeans track current R closely; older R either cannot install"
    echo "  them or installs versions that disagree with each other."
    r_help
    exit 1
fi
if [ -n "$R_VERSION" ]; then
    echo "  R $R_VERSION found"
else
    echo "  R found (version could not be determined)"
fi

# ------------------------------------------------------------------
# 1b. Check Xcode CLT architecture (macOS only)
# ------------------------------------------------------------------

XCODE_ARCH_OK=true
if [[ "$(uname)" == "Darwin" ]]; then
    CLT_LIB="/Library/Developer/CommandLineTools/usr/lib/libxcrun.dylib"
    if [[ -f "$CLT_LIB" ]]; then
        MACHINE_ARCH=$(uname -m)   # arm64 on Apple Silicon, x86_64 on Intel
        if file "$CLT_LIB" | grep -q "$MACHINE_ARCH"; then
            echo "  Xcode Command Line Tools architecture OK ($MACHINE_ARCH)"
        else
            XCODE_ARCH_OK=false
            echo "  WARNING: Xcode Command Line Tools architecture mismatch detected."
            echo "    Your machine is $MACHINE_ARCH but the CLT library is a different arch."
            echo "    Some packages that require compilation may fail to build."
            echo "    To fix: sudo rm -rf /Library/Developer/CommandLineTools && xcode-select --install"
            echo "    Continuing with pre-built fallback versions where possible..."
        fi
    else
        XCODE_ARCH_OK=false
        echo "  Xcode Command Line Tools not found - packages needing compilation may fail."
        echo "    To install: xcode-select --install"
    fi
fi

# ------------------------------------------------------------------
# 2. Install Python packages
# ------------------------------------------------------------------

echo ""
echo "[2/5] Installing Python packages..."

python3 -m pip install --upgrade pip --quiet

# Install kbstatpy and all its Python dependencies (declared in pyproject.toml).
# Editable (-e) so the install tracks this checkout - users can pull updates
# without reinstalling. This makes `import kbstatpy` work from any directory,
# so the demos no longer need sys.path hacks.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! python3 -m pip install -e "$SCRIPT_DIR"; then
    echo ""
    echo "ERROR: installing the Python packages failed."
    echo "  If the failure mentions a compiler, a missing Python.h, or 'building wheel':"
    case "$(detect_os)" in
        macos)  echo "    xcode-select --install" ;;
        debian) echo "    sudo apt install build-essential python3-dev" ;;
        fedora) echo "    sudo dnf install gcc gcc-c++ python3-devel" ;;
        arch)   echo "    sudo pacman -S base-devel" ;;
        suse)   echo "    sudo zypper install gcc gcc-c++ python3-devel" ;;
    esac
    echo "  If it mentions a permission error, install into a virtual environment:"
    echo "    python3 -m venv ~/kbstatpy-env && source ~/kbstatpy-env/bin/activate"
    exit 1
fi

# great_tables >= 0.15.0 depends on multimark which requires compilation.
# Pin to the last pre-built version if the Xcode CLT are absent or mismatched.
if [[ "$XCODE_ARCH_OK" != "true" ]]; then
    echo "  (pinning great_tables==0.14.0 to avoid multimark build failure)"
    python3 -m pip install --quiet "great_tables==0.14.0"
fi

echo "  kbstatpy and Python packages installed."

# ------------------------------------------------------------------
# 3. Install R packages
# ------------------------------------------------------------------

echo ""
echo "[3/5] Installing R packages..."

Rscript -e '
pkgs <- c(
    "lme4", "lmerTest", "glmmTMB", "emmeans", "pbkrtest", "DHARMa",
    "tibble", "broom", "broom.mixed",
    "report", "see", "parameters", "performance",
    "effectsize", "insight", "datawizard", "bayestestR"
)
missing <- pkgs[!pkgs %in% installed.packages()[, "Package"]]
if (length(missing) > 0) {
    cat("Installing R packages:", paste(missing, collapse=", "), "\n")
    install.packages(missing, repos="https://cloud.r-project.org", quiet=TRUE)

    # install.packages() only warns when a package fails and Rscript still exits
    # 0, so without this re-check a missing package surfaced much later as an
    # unrelated-looking R error during the first analysis.
    still <- missing[!missing %in% installed.packages()[, "Package"]]
    if (length(still) > 0) {
        cat("ERROR: these R packages failed to install:", paste(still, collapse=", "), "\n")
        quit(status = 1)
    }
} else {
    cat("All R packages already installed.\n")
}
' || {
    echo ""
    echo "ERROR: installing the R packages failed."
    echo "  These packages compile from source on Linux and need R's build tooling:"
    case "$(detect_os)" in
        macos)  echo "    xcode-select --install    (and a Fortran compiler: brew install gcc)" ;;
        debian) echo "    sudo apt install r-base-dev build-essential" ;;
        fedora) echo "    sudo dnf install R-devel gcc-c++ gcc-gfortran" ;;
        arch)   echo "    sudo pacman -S base-devel gcc-fortran" ;;
        suse)   echo "    sudo zypper install R-base-devel gcc-c++ gcc-fortran" ;;
    esac
    echo "  Some also need system libraries; the error above names which."
    echo "  CRAN package pages list their system requirements, e.g."
    echo "    https://cran.r-project.org/package=glmmTMB"
    exit 1
}

echo "  R packages installed."

# ------------------------------------------------------------------
# 4. Fix rpy2 R version symlink (macOS only)
# ------------------------------------------------------------------

echo ""
echo "[4/5] Checking rpy2 / R version compatibility (macOS only)..."

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
        echo "  rpy2 and R versions are compatible - no symlink needed."
    fi
else
    echo "  Not macOS - skipping symlink check."
fi

# ------------------------------------------------------------------
# 5. Verify the rpy2 -> R bridge
# ------------------------------------------------------------------

echo ""
echo "[5/5] Verifying the rpy2 -> R bridge..."

# Everything above can succeed while rpy2 is still unable to start R, and that
# failure otherwise surfaces in the middle of the user's first analysis. Load the
# two R packages every non-Gaussian model needs, so the check is end-to-end.
if python3 - <<'EOF'
import rpy2.robjects as ro
print('  rpy2 -> ' + ro.r('R.version.string')[0])
ro.r('suppressMessages(library(glmmTMB))')
ro.r('suppressMessages(library(emmeans))')
print('  glmmTMB and emmeans load through the bridge')
import kbstatpy
print('  kbstatpy ' + kbstatpy.__version__ + ' imports')
EOF
then
    :
else
    echo ""
    echo "ERROR: rpy2 could not start R."
    rpy2_help
    echo "  Failing all that, the demos also run on Google Colab - see README.md."
    exit 1
fi

# ------------------------------------------------------------------
# Done
# ------------------------------------------------------------------

echo ""
echo "=== Installation complete ==="
echo ""
echo "To verify, run any of the demos in the demos/scripts subfolder, e.g."
echo "  python3 demos/scripts/demo_01_unpaired.py"
echo ""
