#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# kbstatpy — one-shot setup for the demo notebooks on Google Colab.
#
# Each demo notebook fetches and runs this script from its first cell (only when
# running on Colab). It clones the repo (for the package source + demo data),
# installs kbstatpy in editable mode so `options.demo_dir` resolves to the clone,
# and installs the R packages kbstatpy relies on. Idempotent — safe to re-run.
# ---------------------------------------------------------------------------
set -e

# Colab runs notebooks in /content; fall back to the current dir elsewhere.
BASE="/content"; [ -d "$BASE" ] || BASE="$PWD"
REPO="$BASE/kbstatpy"

# 1. Clone the repo (skip if it is already here).
if [ ! -d "$REPO" ]; then
    echo "Cloning kbstatpy ..."
    git clone --depth 1 https://github.com/kimbostroem/kbstatpy.git "$REPO"
fi

# 2. Editable install so `import kbstatpy` works and demo_dir points at the clone.
echo "Installing kbstatpy (editable) ..."
pip install -q -e "$REPO"

# 3. Install the R packages kbstatpy uses (precompiled binaries; skips existing).
echo "Installing R packages (first run only, ~2-4 min) ..."
Rscript -e '
codename <- tryCatch(system("lsb_release -cs", intern = TRUE), error = function(e) "jammy")
if (length(codename) == 0 || codename == "") codename <- "jammy"
options(repos = c(CRAN = sprintf("https://packagemanager.posit.co/cran/__linux__/%s/latest", codename)))
pkgs <- c("lme4", "lmerTest", "glmmTMB", "emmeans", "pbkrtest", "DHARMa",
          "tibble", "broom", "broom.mixed", "report", "see", "parameters",
          "performance", "effectsize", "insight", "datawizard", "bayestestR")
missing <- pkgs[!pkgs %in% rownames(installed.packages())]
if (length(missing)) {
    cat("Installing R packages:", paste(missing, collapse = ", "), "\n")
    install.packages(missing)
} else {
    cat("R packages already present.\n")
}
'

echo "kbstatpy Colab setup complete — run the cells below."
