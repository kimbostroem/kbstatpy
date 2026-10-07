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
set -e

ENV="${KBSTATPY_ENV:-$HOME/envs/kbstat}"
REPO_URL="git+https://github.com/kimbostroem/kbstatpy.git"

# R and the R packages come from conda-forge as matching binaries: nothing is
# compiled, and rpy2 is built against exactly this R. The list is the one in
# demos/colab_setup.sh.
PKGS="python=3.12 pip ipykernel rpy2 r-base r-lme4 r-lmertest r-glmmtmb r-emmeans
      r-pbkrtest r-dharma r-tibble r-broom r-broom.mixed r-report r-see r-parameters
      r-performance r-effectsize r-insight r-datawizard r-bayestestr"

# 1. A solver that works without touching the system installation.
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

# 2. The environment, by path in the home folder.
if [ -x "$ENV/bin/python" ]; then
    echo "Environment $ENV exists: keeping it (delete the folder to start afresh)."
else
    echo "Creating the environment in $ENV with $SOLVER (first time only, a few minutes) ..."
    # shellcheck disable=SC2086  # PKGS is a word list on purpose
    "$SOLVER" create -y -q -p "$ENV" -c conda-forge $PKGS
fi

# 3. kbstatpy itself, always the newest from GitHub. The first call brings the
#    Python dependencies; the second replaces kbstatpy even when the version
#    number has not changed since the last run.
echo "Installing kbstatpy ..."
"$ENV/bin/pip" install -q "$REPO_URL"
"$ENV/bin/pip" install -q --force-reinstall --no-deps "$REPO_URL"

# 4. The kernel, with R_HOME pinned to the env's R.
"$ENV/bin/python" -m ipykernel install --user --name kbstat --display-name "kbstatpy" \
    --env R_HOME "$ENV/lib/R"

echo
echo "kbstatpy setup complete. Reload the page in the browser; the Launcher now has a"
echo "\"kbstatpy\" notebook. In an open notebook: Kernel > Change Kernel > kbstatpy."
