#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# kbstatpy — one-shot setup on a JupyterHub (e.g. JupyterHub.nrw), for people
# without a Google account or who prefer their university's servers.
#
# Run once, in a terminal on the hub or from the template's setup cell:
#
#   curl -sSL https://raw.githubusercontent.com/kimbostroem/kbstatpy/master/install_jupyterhub.sh | bash
#
# It creates a conda environment in the home folder with Python, R and every R
# package kbstatpy needs, installs kbstatpy into it, and registers it as the
# Jupyter kernel "kbstatpy". The home folder persists on a hub, so this is a
# one-off (unlike Colab). Running it again updates kbstatpy and leaves the rest.
#
# Three things a plain `conda create` gets wrong on such hubs, all hit on
# JupyterHub.nrw:
#   - the system conda may ask for the libmamba solver without having it
#     ("non-default solver backend (libmamba) ... not recognized"): use mamba,
#     or fetch micromamba when there is no mamba;
#   - the system envs folder is read-only: create the env by path in $HOME;
#   - the hub has its own R (for RStudio), which rpy2 picks up instead of the
#     env's R, so R packages "are not installed": register the kernel with
#     R_HOME pointing at the env's R.
# ---------------------------------------------------------------------------
# No `set -e`: every step runs, and step 5 decides whether it all worked, so
# the run always ends with a clear message instead of stopping mid-way.

ENV="${KBSTATPY_ENV:-$HOME/envs/kbstat}"
REPO_URL="git+https://github.com/kimbostroem/kbstatpy.git"

# R and the R packages come from conda-forge as matching binaries: nothing is
# compiled, and rpy2 is built against exactly this R. The list is the one in
# demos/colab_setup.sh.
PKGS="python=3.12 pip ipykernel rpy2 r-base r-lme4 r-lmertest r-glmmtmb r-emmeans
      r-pbkrtest r-dharma r-tibble r-broom r-broom.mixed r-report r-see r-parameters
      r-performance r-effectsize r-insight r-datawizard r-bayestestr"

START=$(date +%s)
step() { echo; echo "==> [$1/5] $2"; }
echo "=================================================================="
echo " Installing kbstatpy. This takes a few minutes the first time."
echo " It is finished when you see 'kbstatpy is installed' below and the"
echo " input line (ending in \$) is back. Until then, leave this tab open."
echo "=================================================================="

# 1. A solver that works without touching the system installation.
step 1 "Finding a package manager"
if command -v mamba >/dev/null 2>&1; then
    SOLVER="mamba"
elif command -v micromamba >/dev/null 2>&1; then
    SOLVER="micromamba"
else
    echo "No mamba found: fetching micromamba into ~/bin ..."
    mkdir -p "$HOME/bin"
    curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C "$HOME" bin/micromamba
    SOLVER="$HOME/bin/micromamba"
fi
echo "    using $SOLVER"

# 2. The environment, by path in the home folder. Not quiet: the download
#    progress is the only sign of life during the longest step. An existing
#    env is completed rather than skipped, so a run that was interrupted
#    (closed tab, lost connection) is repaired by simply running this again.
if [ -x "$ENV/bin/python" ]; then
    step 2 "Checking the environment in $ENV (installs only what is missing)"
    # shellcheck disable=SC2086  # PKGS is a word list on purpose
    "$SOLVER" install -y -p "$ENV" -c conda-forge $PKGS
else
    step 2 "Creating the environment in $ENV: Python, R and R packages (the long step)"
    # shellcheck disable=SC2086
    "$SOLVER" create -y -p "$ENV" -c conda-forge $PKGS
fi

# 3. kbstatpy itself, always the newest from GitHub. The first call brings the
#    Python dependencies; the second replaces kbstatpy even when the version
#    number has not changed since the last run.
step 3 "Installing kbstatpy from GitHub (about a minute)"
"$ENV/bin/pip" install "$REPO_URL" 2>&1 | grep -E "^(Collecting|Successfully|ERROR)" || true
"$ENV/bin/pip" install -q --force-reinstall --no-deps "$REPO_URL"

# 4. The kernel, with R_HOME pinned to the env's R.
step 4 "Registering the Jupyter kernel 'kbstatpy'"
"$ENV/bin/python" -m ipykernel install --user --name kbstat --display-name "kbstatpy" \
    --env R_HOME "$ENV/lib/R"

# 5. Load it the way the kernel will, R included, so a broken installation is
#    reported here and not in the first notebook cell.
step 5 "Checking that kbstatpy loads (starts R once)"
VERSION=$(R_HOME="$ENV/lib/R" "$ENV/bin/python" -c \
    "import IPython, stack_data, kbstatpy; print(kbstatpy.__version__)" 2>/dev/null | tail -1) || true
MIN=$(( ($(date +%s) - START + 59) / 60 ))
echo
echo "=================================================================="
if [ -n "$VERSION" ]; then
    echo " kbstatpy is installed (version $VERSION, took about $MIN min)."
    echo
    echo " Next: reload this page in the browser (F5, or Cmd+R on a Mac)."
    echo " The Launcher then has a 'kbstatpy' tile under Notebook. In a"
    echo " notebook that is already open: Kernel > Change Kernel > kbstatpy."
    echo " You can close this terminal now."
else
    echo " Something went wrong: kbstatpy does not load yet."
    echo " Run the same command once more; it completes what is missing."
    echo " If this message comes again, copy the lines above it and ask for help."
fi
echo "=================================================================="
[ -n "$VERSION" ]
