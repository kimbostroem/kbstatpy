#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# kbstatpy — one-shot setup for the demo notebooks on Google Colab.
#
# Each demo notebook fetches and runs this script from its first cell (only when
# running on Colab). It clones the repo, installs kbstatpy so the *running*
# kernel can import it, links the bundled demo data where options.demo_dir
# expects it, and installs the R packages kbstatpy relies on. Idempotent.
# ---------------------------------------------------------------------------
set -e

# Colab runs notebooks in /content; fall back to the current dir elsewhere.
BASE="/content"; [ -d "$BASE" ] || BASE="$PWD"
# NOT "kbstatpy": a directory of that name in the working dir would shadow the
# installed package as an empty namespace ("cannot import name ... unknown location").
REPO="$BASE/kbstatpy-src"

# 1. Clone the repo, or refresh an existing checkout to the latest master so a
#    re-run always picks up the newest code (no need to delete the runtime).
if [ ! -d "$REPO" ]; then
    echo "Cloning kbstatpy ..."
    git clone --depth 1 https://github.com/kimbostroem/kbstatpy.git "$REPO"
else
    echo "Updating kbstatpy to latest master ..."
    git -C "$REPO" fetch -q --depth 1 origin master && git -C "$REPO" reset -q --hard FETCH_HEAD
fi

# 2. Install kbstatpy. A *regular* (non-editable) install lands in site-packages,
#    so the already-running kernel imports it immediately. An editable install
#    would only take effect after a kernel restart (its .pth is read at startup).
#    Uninstall first so a re-run cleanly replaces any earlier install.
echo "Installing kbstatpy ..."
pip uninstall -y kbstatpy >/dev/null 2>&1 || true
pip install -q "$REPO"

# 3. The demos are not shipped inside the wheel, but options.demo_dir looks for
#    them next to the installed package — so link the clone's demos folder there.
#    Use find_spec (locates the package WITHOUT importing it): importing kbstatpy
#    here would pull in pymer4 -> importr("lme4"), and the R packages below are
#    not installed yet.
DEMOS_PARENT=$(python3 -c "import importlib.util, os; s = importlib.util.find_spec('kbstatpy'); print(os.path.dirname(os.path.dirname(s.origin)))")
ln -sfn "$REPO/demos" "$DEMOS_PARENT/demos"
echo "Linked demo data -> $DEMOS_PARENT/demos"
# (Plot fonts need no system install: kbstatpy bundles Latin Modern Sans and a
#  Helvetica clone and registers them with matplotlib on import.)

# 4. Install the R packages kbstatpy uses. The HTTPUserAgent makes Posit Package
#    Manager serve precompiled binaries instead of source (fast, no compiler noise).
echo "Installing R packages (first run only, ~1-2 min) ..."
Rscript -e '
codename <- tryCatch(system("lsb_release -cs", intern = TRUE), error = function(e) "jammy")
if (length(codename) == 0 || codename == "") codename <- "jammy"
options(
    repos = c(CRAN = sprintf("https://packagemanager.posit.co/cran/__linux__/%s/latest", codename)),
    HTTPUserAgent = sprintf("R/%s R (%s)", getRversion(),
                            paste(getRversion(), R.version["platform"],
                                  R.version["arch"], R.version["os"]))
)
pkgs <- c("lme4", "lmerTest", "glmmTMB", "emmeans", "pbkrtest", "DHARMa",
          "tibble", "broom", "broom.mixed", "report", "see", "parameters",
          "performance", "effectsize", "insight", "datawizard", "bayestestR")
missing <- pkgs[!pkgs %in% rownames(installed.packages())]
if (length(missing)) {
    cat("Installing R packages (binary):", paste(missing, collapse = ", "), "\n")
    install.packages(missing, quiet = TRUE)
} else {
    cat("R packages already present.\n")
}
'

echo "kbstatpy Colab setup complete — run the cells below."
