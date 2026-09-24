# kbstatpy

[![Release](https://img.shields.io/github/v/release/kimbostroem/kbstatpy?label=release&color=blue)](https://github.com/kimbostroem/kbstatpy/releases) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/kbstatpy_colab.ipynb)

A Python library for generalised linear mixed model (GLMM) analysis with post-hoc pairwise comparisons, data transformation, correlation analysis, and multicollinearity diagnostics. Modelled after the MATLAB `kbstat` library.

Fitting is done via R's `lme4` (Gaussian LMMs), `glmmTMB` (non-Gaussian GLMMs), and `emmeans` packages (through `pymer4` and `rpy2`), giving access to the same statistical machinery used in R — Kenward-Roger / Satterthwaite degrees of freedom, Type III sums of squares, and effects-coded contrasts — from a clean Python interface.

## Table of contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Data format](#data-format)
- [Quick start](#quick-start)
- [Options reference](#options-reference)
  - [Notes on particular options](#notes-on-particular-options)
- [Multi-y](#multi-y)
- [Data transformation](#data-transformation)
- [Correlation analysis](#correlation-analysis)
- [Residual spread ratio](#residual-spread-ratio)
- [Variance Inflation Factor (VIF)](#variance-inflation-factor-vif)
- [Level-wise profile analysis](#level-wise-profile-analysis)
- [Output files](#output-files)
- [Demo scripts](#demo-scripts)
  - [Try the demos on Google Colab](#try-the-demos-on-google-colab)
- [Statistical notes](#statistical-notes)
- [Known issues and workarounds](#known-issues-and-workarounds)
- [Changelog](CHANGELOG.md) · [Releases](https://github.com/kimbostroem/kbstatpy/releases)

---

## Requirements

- Python 3.10+ (64-bit)
- R 4.4+
- **Platform:** macOS, Linux, or Windows. macOS and Linux are the routinely tested platforms; native Windows is supported by `install.ps1` (see below), with [WSL](https://learn.microsoft.com/windows/wsl/install) as a fallback.

All Python and R package dependencies are handled by the installer (see below).

---

## Installation

**macOS / Linux**

```bash
cd kbstatpy
bash install.sh
```

**Windows**

```powershell
cd kbstatpy
powershell -ExecutionPolicy Bypass -File install.ps1
```

**Anaconda / Miniconda, or a venv:** activate the environment you want *first* and the installer uses it — no extra flag needed. This works from the Anaconda Prompt as well as from PowerShell, since the installer reads `CONDA_PREFIX` / `VIRTUAL_ENV` and those survive into the `powershell` call:

```powershell
conda create -n kbstatpy python=3.13
conda activate kbstatpy
powershell -ExecutionPolicy Bypass -File install.ps1
```

The installer prints the full path of the interpreter it is about to write to before it installs anything, and names the conda environment or venv it belongs to — so nothing lands in an environment you did not mean. With none activated it installs into the interpreter it finds and says so. To pick one without activating it, pass `-Python` (a path to `python.exe`, or the environment folder, or a command name to look up on `PATH`):

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -Python C:\Users\me\anaconda3\envs\kbstatpy\python.exe
```

Only Python is installed per environment. The R packages go into your R user library and are shared by every environment, which is what you want: they are the same packages either way.

> **`python.exe : Python was not found; run without arguments to install from the Microsoft Store`**
> PowerShell found the Microsoft Store placeholder named `python.exe` instead of your Python — usually because Anaconda is installed but no environment is activated in the shell you called from. Activate one, or pass `-Python`, as above. (Up to version 1.15.0 the installer aborted here with a `NativeCommandError` instead of moving on to the next interpreter; fixed in 1.15.1.)

> **`unable to load shared object '...\library\stats\libs\x64\stats.dll': LoadLibrary failure: The specified module could not be found`**
> R started (`rpy2` even reports its version) but cannot load its own libraries. The file it names is present; the R DLLs beside `R.dll` that it depends on are not on the search path, because R installs itself without touching `PATH`. From version 1.15.7 `import kbstatpy` puts them there itself. On an older version, or if it persists, set it for your account and open a new shell (with your own R version in the path):
> ```powershell
> $p = [Environment]::GetEnvironmentVariable('Path', 'User')
> [Environment]::SetEnvironmentVariable('Path', $p + ';C:\Program Files\R\R-4.6.1\bin\x64', 'User')
> ```

> **`UnicodeDecodeError: 'utf-8' codec can't decode byte ...` while R prints a message**
> R is reporting in a language whose accented characters `rpy2` cannot decode, so the real message is lost behind this one. Switch R to English and open a new shell: `[Environment]::SetEnvironmentVariable('LANGUAGE', 'en', 'User')`.

Either installer:
1. Checks the prerequisites and **stops with instructions if one is missing or too old** — which package manager command or download page to use for Python 3.10+ and R 4.4+ on your platform, rather than a failure further down that does not name the cause
2. Installs **kbstatpy** and its Python dependencies (`pymer4`, `rpy2`, `pandas`, `scipy`, `sympy`, `seaborn`, `openpyxl`, …) from `pyproject.toml`, so `import kbstatpy` works from any directory
3. Installs all required R packages (`lme4`, `lmerTest`, `glmmTMB`, `emmeans`, `DHARMa`, …)
4. Verifies that `rpy2` can actually start R and load `glmmTMB` and `emmeans`, so a broken bridge is reported here instead of part-way through your first analysis

Plus what the platform needs on top of that:
- **macOS:** fixes the `rpy2` / R version symlink if needed, and warns about a mismatched Xcode Command Line Tools architecture
- **Windows:** installs into the activated conda environment or venv if there is one (and reports which), finds R through the registry (the R installer does not add R to `PATH`, so there is nothing to configure by hand), and creates the personal R library that a non-interactive `Rscript` cannot create on demand. `import kbstatpy` then adds R's own library folder (`<R_HOME>\bin\x64`) to the search path of that Python process, so R can load the DLLs it fetches lazily, `Rlapack` above all; nothing has to be set by hand for this either

On Windows nothing needs to be compiled: `rpy2` installs from a prebuilt `win_amd64` wheel, and CRAN serves the R packages as Windows binaries, so Rtools is not required.

On **Linux** the opposite holds: CRAN serves Linux packages as source only, so a cold install compiles the whole dependency closure — around 130 packages, a quarter of an hour — and needs a C/C++/Fortran toolchain plus libcurl, OpenSSL, libuv, zlib and ICU in their `-dev`/`-devel` form (`sudo apt install r-base-dev build-essential libcurl4-openssl-dev libssl-dev libuv1-dev zlib1g-dev libicu-dev cmake` on Debian/Ubuntu). `DHARMa` is the package that needs most of them, by way of `gap` → `plotly` → `httr` → `curl` and `qgam` → `shiny` → `bslib` → `sass` → `fs`, so a missing header shows up as a `DHARMa` failure that looks unrelated to anything network- or filesystem-shaped. `install.sh` names the command for your distribution if a build fails.

To avoid compiling altogether, point R at a binary repository — [Posit Package Manager](https://packagemanager.posit.co/client/#/repos/cran/setup) serves prebuilt packages for the common distributions — and put the `options(repos = ...)` line it gives you in `~/.Rprofile`. `install.sh` installs from whatever repository R is configured with, and falls back to CRAN when that is nothing.

Native Windows support is recent — earlier versions of `rpy2` could not be installed there reliably, and this README said so. If a native install does give trouble, run the macOS/Linux steps inside a [WSL](https://learn.microsoft.com/windows/wsl/install) shell (e.g. Ubuntu) instead, and please open an issue.

---

## Data format

kbstatpy requires input data in **long format**: one row per observation, with separate columns for the response variable and each grouping factor. Wide-format data — where repeated measurements are spread across columns (e.g. `Week_0`, `Week_2`, `Week_4`) — must be reshaped before use.

```python
# Convert wide → long with pandas
df_long = df_wide.melt(id_vars='Subject', var_name='Week', value_name='score')
```

See [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md#long-vs-wide-data-format) for a full explanation with examples and the R equivalent (`tidyr::pivot_longer()`).

---

## Quick start

```python
from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file    = 'data/mydata.csv'       # path to your data file (.csv or .xlsx)
options.out_dir    = 'results/myanalysis'    # output folder (created if it doesn't exist)
options.y          = 'ResponseVariable'      # dependent variable column name
options.x          = 'FactorA, FactorB'      # fixed-effect factors (comma-separated list)
options.id         = 'Subject'               # random-effect grouping variable
options.distribution = 'gamma'
options.link       = 'log'

kb = Kbstat(options)
kb.run_save()   # compute, display, and save — all in one call
```

`run_save()` is the convenience one-liner: it is exactly `run()` followed by
`save()`, which you can also call separately. `run()` computes the analysis,
displays it, and gathers the results into `kb.output`; `save()` writes
`kb.output` to `out_dir` (a no-op if `out_dir` is unset). The split is handy in
notebooks — run to view inline, then save only when you want files:

```python
kb.run()      # fit, ANOVA, post-hoc, plots, printed summary → kb.output
kb.save()     # write kb.output to out_dir
```

You can also drive the pipeline step by step and then save what was produced:

```python
kb.fit()      # fit the LMM / GLMM
kb.anova()    # Type III ANOVA table
kb.posthoc()  # pairwise comparisons via emmeans
kb.save()     # write the results produced so far to out_dir
```

On a remote Jupyter server, `save()` writes to the *server*. To pull the results
to your own machine, `kb.download_link()` zips `out_dir` and returns a clickable
download link (pass a folder to zip a parent holding several runs):

```python
kb.save()
kb.download_link()
```

All list-valued options (`x`, `covariate`, `slope`, `interaction`, `y_units`, `x_units`, `correlation`, `correlation_control`) accept either a Python list or a comma-separated string — whichever is more convenient — and all default to `''`, with the exception of `interaction`, whose default is the structure keyword `'auto'`.

To start from something fuller, copy [`analysis_template.py`](analysis_template.py) from the repository root: the five required options are filled in and the rest are commented out, each showing the value kbstatpy would use anyway and a one-line note on what it does.

### Relative paths and where the script is run from

`in_file` and `out_dir` are resolved against the working directory, which is set by whatever started the script and is not necessarily the folder the script is in. An IDE's run button, a terminal, a cron entry and a double-click can each pick a different one, so a plain relative path may silently read or write somewhere unintended.

**`base_dir` anchors them to the script**, without moving the process, so anything else the script does relative to where it was launched keeps working:

```python
options.base_dir = 'script_dir'     # 'auto' is a synonym
options.in_file  = 'Data/gait.csv'  # the script's Data, wherever it is run from
options.out_dir  = 'Results/gait'
```

| `base_dir` | meaning |
|---|---|
| `''` | default, relative paths follow the working directory |
| `'.'` | the same, said explicitly |
| `'script_dir'` / `'auto'` | the calling script's own folder |
| any path | that folder, absolute or itself relative to the working directory |

The keyword is resolved when it is assigned, so `options.base_dir` afterwards holds the real path: print it and you see where the analysis will read and write. An absolute `in_file` or `out_dir` ignores it. Both keywords are ordinary words, so if a directory of that name exists, assigning the keyword warns and takes the keyword; write `'./auto'` or an absolute path to mean the directory.

**`Kbstat.chdir()` anchors the whole script instead**, by moving the working directory to the calling script's folder. Use it when every path in the script should be script-relative, not only kbstatpy's two:

```python
from kbstatpy import Kbstat

Kbstat.chdir()            # now in the script's folder
Kbstat.chdir('../Data')   # script-relative, because that is where we are
```

It replaces the usual `script_dir = os.path.dirname(os.path.abspath(__file__))` opening and returns the directory it moved to. It takes the same vocabulary as `base_dir`: `'script_dir'` (the default, `'auto'` synonymous), or any path. **A plain path resolves the way `os.chdir` resolves it, against the working directory, not against the script** — redefining that would give one relative path two meanings depending on which function received it. So a lone `chdir('../Data')` still depends on where the script was started; move to the script first, as above.

`Kbstat.script_dir()` returns the same folder **without** changing anything, for a script that would rather build its paths explicitly. `base_dir = Kbstat.script_dir()` is the spelling with no keyword at all.

Both take the path from the call stack, so nothing has to be passed in and `__file__` never appears in the script. In a REPL, a notebook cell or `exec()` there is no script to locate: they return `None`, and `chdir()` warns and leaves the working directory alone rather than guessing. Both are also importable on their own, as `chdir` and `script_dir`; the methods exist so a script needs no import beyond the `Kbstat` it already has.


### Formulas and several outcomes

`formula` replaces the fields it covers, so `y`, `x`, `id` and `interaction` can be left unset:

```python
options.formula = 'score ~ group * condition + (1 | subject)'
```

**The left-hand side and `options.y` are the same slot.** Write `y` there and it is a placeholder that `options.y` fills in, so one right-hand side serves several outcomes:

```python
options.y       = 'y1, y2'
options.formula = 'y ~ x1 + (1 | subject)'   # fits y1 ~ x1 + (1 | subject), then y2 ~ ...
```

`Y` reads the same as `y`. An expression keeps its shape, so `log(y) ~ x1` becomes `log(y1) ~ x1`.

**Write a real column name instead and that one outcome is fitted**, whatever `options.y` lists. That is the quick way to look at a single model without editing `options.y`, and kbstatpy says so rather than dropping the list silently:

```python
options.y       = 'y1, y2'
options.formula = 'y1 ~ x1 + (1 | subject)'   # fits y1 only, and warns that y is ignored
```

Random terms are written as in lme4, including nested (`(1 | subject/session)`) and several terms (`(1 | subject) + (1 | subject:session)`).

With neither given, the dependent variable is taken from the formula. The cost of the convention is that a column genuinely called `y` or `Y` cannot be named on the left; set `options.y` to it instead.


## Options reference

**Values are case-insensitive, and a wrong one raises.** The options that take a fixed set of values (`distribution`, `plot_style`, `figure_display`, `x_label`, `y_label`, `correlation_method`, `posthoc_method`, `posthoc_family`, `y_correction`, `y_scale`, `data_outliers`, `slope_correlated`) accept any capitalisation and reject anything outside their set, rather than falling back silently. `posthoc_correction` is the exception: its value goes to R, where method names such as `BH` and `BY` are case-sensitive.

**Switching an option off.** Which of `''` and `'none'` turns something off depends on what the option names, and the two are not interchangeable. Options that name *things* — variables, factors, expressions (`x`, `covariate`, `slope`, `interaction`, `correlation`, `correlation_control`, `profile_across`, `dispersion`, `constraints`) — are switched off by leaving them **empty**; `'none'` there is read as a name, so `correlation = 'none'` looks for a column called `none` and fails. Options that name a *mode or method* (`posthoc_correction`, `y_correction`, `data_outliers`, `x_label`, `y_label`) take **`'none'`** as one of their listed choices, and `''` falls back to the default rather than to "off". On/off flags (`show_group_size`, `show_emm_lines`, `remove_outliers_*`) also accept `'none'` for off, alongside `False`. Two deliberate exceptions: `posthoc_compare` accepts either spelling, and for `title` the two differ — `''` shows the plain variable name, `'none'` removes the title entirely.

| Option | Type | Description |
|---|---|---|
| `in_file` | str | Path to the input data (`.csv` or `.xlsx`) |
| `out_dir` | str | Output directory, resolved against `base_dir` (the working directory by default). Empty (default) displays results without writing anything, which suits notebooks |
| `base_dir` | str | Directory a relative `in_file`/`out_dir` resolves against. `''` (default) the working directory; `'script_dir'` (or `'auto'`) the calling script's folder; or any path. Absolute paths ignore it |
| `demo_dir` | str | *(auto)* Absolute path to the bundled demo folder, for example inputs: `os.path.join(options.demo_dir, 'data/sleep.csv')` |
| `formula` | str | Explicit Wilkinson formula. A complete alternative to `y`, `x`, `id` and `interaction` rather than an addition. `y` (or `Y`) on the left is a placeholder that `options.y` fills in, one model per entry; a real column name there fits that one outcome (see below) |
| `y` | str or list | Dependent variable(s). Several run one analysis each, see [Multi-y](#multi-y) |
| `y_units` | str or list | Default `''` (no units). Unit label(s) for the y-axis, e.g. `'ms'`, or `'kg, N, m'` for multi-y, matched to `y` by position. An empty entry, or `'1'`, means that variable has no unit |
| `x` | list / str | Fixed-effect factor column names |
| `x_order` | str or dict | Level order, e.g. `'dose: low, medium, high; supp: OJ, VC'`. With `rename`, use the renamed names |
| `rename` | str or dict | Display labels for variables and levels, e.g. `'cyl -> Cylinders; cyl: 4 -> 4 cyl'`. Variable renames affect labels and headers, level renames affect the data before fitting |
| `x_units` | list / str | Default `''` (no units). Unit label(s) for x-axis tick groups, matched to `x` by position. An empty entry, or `'1'`, means that factor has no unit, e.g. `', mg'` labels the second factor only |
| `id` | str | Random grouping factor(s). Several, comma-separated, are crossed; lme4's `/` and `:` nest. Several trials per subject and condition: `'subject/session'`, or the condition effect is tested against the trial scatter. See [Crossed and nested grouping factors](STATISTICAL_NOTES.md#crossed-and-nested-grouping-factors) and [pseudo-replication](STATISTICAL_NOTES.md#several-trials-per-condition-pseudo-replication) |
| `slope` | list / str | Variables with random slopes, e.g. `'A, B'` → `(1 + A + B \| id)` |
| `slope_correlated` | bool or str | Default `'auto'`. Covariance structure for the slopes: `True` full, `False` diagonal, `'auto'` full with a diagonal fallback when it comes back singular |
| `interaction` | list / str / int | Default `'auto'`, every interaction the design can support. `''` is additive, an integer caps the order, `'all'` is the full factorial, or name the terms. See [Model structure](STATISTICAL_NOTES.md#model-structure-and-why-kbstatpy-will-not-pick-one-for-you) |
| `covariate` | list / str | Numeric covariates: in the model, out of the plots and post-hoc |
| `scale_covariates` | bool | Default `True`. Centre and scale the numeric covariates to z-scores before fitting. It changes no result — a covariate not in an interaction has its coefficient and its standard error divided by the same number, so every t, F and p is identical, and estimated marginal means are evaluated at the covariate means either way — but it conditions the optimisation, which matters where covariates span very different magnitudes. `Data.csv` keeps each covariate in its own units and adds the fitted values beside it as `<name>_scaled`, and `Summary.txt` names what was scaled. Categorical and constant covariates are left alone |
| `y_transform` | str | Transform with `y` as placeholder, e.g. `'log(y)'`, `'sqrt(y)'`, `'y**0.4'`. `^` is accepted for exponentiation. EMMs and CIs are back-transformed |
| `correlation` | list / str | Numeric variables for pairwise correlation, see [Correlation analysis](#correlation-analysis). Also spelled `correlate` |
| `correlation_method` | str | Default `'pearson'`. Or `'spearman'`, rank-based and robust to outliers. Applies to the raw and partial tables |
| `correlation_control` | list / str | Variable(s) partialled out of every correlation. They are not shown in the matrix |
| `constraints` | str | Row filter applied before analysis, e.g. `'Year > 1950 & group != "control"'`. Also spelled `constraint` |
| `distribution` | str | Default `'normal'`. Response distribution, see [Supported distributions](#supported-distributions) |
| `link` | str | Link function. `'auto'` (default) is identity for normal, logit for binomial, log for the rest. That is kbstatpy's choice, not R's canonical link, for gamma and inverse Gaussian (see [Supported distributions](#supported-distributions)) |
| `dispersion` | str | Dispersion model for the glmmTMB families. A factor name gives that factor its own dispersion |
| `fit_method` | str | Default `'MPL'`. Label for the estimator named in `Summary.txt`; nothing is passed to the fitting engine |
| `max_iterations` | int | Default `10000`. Optimizer cap for glmmTMB fits. Raise it if a large model reports an iteration limit at the optimum |
| `df_method` | str | Default `'auto'`. Denominator df for the ANOVA and the post-hoc, used for both so they agree. Also `'kenward-roger'`, `'satterthwaite'`, `'asymptotic'`. See [Degrees of freedom](STATISTICAL_NOTES.md#degrees-of-freedom-kenward-roger-and-satterthwaite) |
| `kr_max_obs` | int | Default `5000`. Above this, `df_method='auto'` takes Satterthwaite. A cost threshold, not a statistical one; `0` removes it |
| `model_comparison` | bool | Default `False`. Report AIC/BIC for a ladder of fixed-effect structures beside the fitted one. **A report, not a selection**, see [Model structure](STATISTICAL_NOTES.md#model-structure-and-why-kbstatpy-will-not-pick-one-for-you) |
| `remove_outliers_prefit` | bool | Default `False`. Exclude outliers before fitting, by the IQR rule per group |
| `remove_outliers_postfit` | bool | Default `False`. Exclude outliers after fitting, by Pearson residual, then refit. Combines with the prefit rule |
| `posthoc_method` | str | Default `'emm'` (emmeans) |
| `posthoc_correction` | str | Default `'holm'`. P-value correction within a model: `'bonferroni'`, `'fdr'`, `'tukey'`, … |
| `posthoc_family` | str | Default `'cell'`. What the correction spans: `'cell'` each cell separately, `'pooled'` all cells as one family, `'cross'` within each cell then across. See [What counts as a family](STATISTICAL_NOTES.md#what-counts-as-a-family-posthoc_family) |
| `posthoc_compare` | str | Default `'auto'` (the first x-variable). Which factor(s) get pairwise comparisons, comma-separated; `''` or `'none'` turns them off. Comparisons are per cell, see [Comparing any factor](STATISTICAL_NOTES.md#comparing-any-factor-per-cell-demo-15) |
| `profile_across` | str | Name one ordered factor to profile the factors interacting with it across its levels, see [Level-wise profile analysis](#level-wise-profile-analysis) |
| `y_correction` | str | Default `'none'`. Correction across the dependent variables of a multi-y run: `'bonferroni'`, `'holm'`, `'FDR'`, `'FDR_correlated'`. See [Family-wise correction](STATISTICAL_NOTES.md#family-wise-correction-across-dependent-variables-demo-13) |
| `plot_style` | str | Default `'auto'` (bar for binary outcomes, violin otherwise). Or `'violin'`, `'bar'` |
| `show_group_size` | bool | Default `False`. Annotate each group with its observation count |
| `show_emm_lines` | bool or str | Default `False`. Draw a reference line at each group's marginal mean. `True` is dotted; a line style may be given instead |
| `title` | str | Data-plot title prefix: the title becomes `'<title> (<DV>)'`. Empty (default) shows the variable name alone, `'none'` suppresses the title entirely |
| `title_font` | str or list | Font for plot titles. Empty (default) derives a condensed variant of `font` where one is installed |
| `x_label` | str | Default `'variable_below_levels'`. How the x-axis labels the first factor: also `'variable_equals_level'`, `'levels'`, `'none'` |
| `y_label` | str | Default `'variable_with_units'`. Also `'variable_only'` and `'none'` |
| `data_outliers` | str | Default `'text'`, which annotates the count rather than plotting it, so the axis scales to the rest of the data. Also `'plot'` and `'none'` |
| `diagnostic_sims` | int/str | Default `'auto'`. Simulations behind the DHARMa quantile residuals, which sets their resolution. An integer pins it |
| `y_scale` | str | Default `'linear'`. `'log'` suits panels spanning orders of magnitude and log-link models; it needs strictly positive values and falls back with a warning |
| `figure_display` | str | Default `'show_close'`. Also `'save_only'` and `'show_keep'`. Every mode saves files |
| `color_scheme` | str | Default `'Set1'`. Seaborn/matplotlib palette |
| `color_sat` | float | Default `0.9`. Violin colour saturation, 0 to 1 |
| `color_alpha` | float | Default `0.5`. Violin fill transparency, 0 transparent to 1 opaque |
| `font` | str or list | Default `'Helvetica, DejaVu Sans'`. Font family, or a fallback chain tried in order. See [Fonts](#fonts) |

### Notes on particular options

Options whose behaviour needs more than a line. The statistical ones are in [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md), linked from the table above.

#### Fonts

`font` takes a family or a comma-separated fallback chain, tried in order. The default resolves to **Helvetica**: the real font on macOS and Windows, and the bundled **TeX Gyre Heros** clone on Linux and Colab, so plots look the same everywhere without installing anything. kbstatpy also bundles **Latin Modern Sans** (the LaTeX look) and **TeX Gyre Termes** (a Times clone), registered on import and available under the GUST Font License (see `kbstatpy/fonts/`).

A request for Helvetica, Arial or Times falls back to the bundled clone where the real font is absent, rather than dropping to the visibly different DejaVu Sans. Family names match case-insensitively, and `'Sans'`/`'Modern'` and `'Times'` are accepted as aliases. A missing family never warns; `''` and `'auto'` use matplotlib's own default.

`title_font` sets the title face separately. Left empty it derives a condensed variant of the body font where one is installed, e.g. `'Arial'` → `'Arial Narrow'`.

To make a hand-built matplotlib figure match kbstatpy's plots, call the public `Kbstat.apply_font()` before building it, then use `fontweight='bold'` on the labels and ticks that should match.

#### Reference lines at the marginal means

`show_emm_lines` draws a horizontal line across the panel at each group's estimated marginal mean, in that group's colour, so levels can be read off against the other groups' distributions instead of comparing dot heights by eye. `True` uses a dotted line, which recedes furthest behind the violins and brackets so it cannot be mistaken for plotted data; passing a style (`'-'`, `'--'`, `':'`, `'-.'`, or the matplotlib names) overrides that, with solid reading calmest at the cost of looking more like content. Each panel uses its own EMMs, falling back to the median where none is available.

#### Logarithmic y-axis

`y_scale = 'log'` helps where the panels of one figure span orders of magnitude, since a shared linear axis flattens the small-valued panels into slivers, and for gamma or log-link models, where a constant ratio becomes a constant distance. Significance brackets and the axis padding are computed in log space so their spacing stays even, and the axis label gains a `(log scale)` note because the ticks show untransformed values. Diagnostic and correlation figures are never rescaled.

#### Diagnostic simulation count

`diagnostic_sims` sets the resolution of the DHARMa quantile residuals: a quantile residual can only take the values `k/n_sim`, so the most extreme value expressible is `qnorm(1/n_sim)` and anything beyond it is capped. Too few simulations show up as horizontal rows of points at the ends of the Q-Q plot and inflate the capped count. `'auto'` asks for twice the number of observations, bounded and then held under a memory budget, since DHARMa keeps an observations × simulations matrix. These simulations serve the diagnostic figures only; no estimate, statistic or p-value comes from them.

#### Outliers in the data plot

`data_outliers` governs only the display; exclusion is `remove_outliers_prefit` and `remove_outliers_postfit`. The default `'text'` omits the points and annotates the count and percentage under each panel, so the y-axis scales to the remaining data instead of being squashed by an extreme value. `'plot'` draws each one as a red X. (Renamed from `show_outliers`, which still works with a deprecation warning.)

#### Figures in notebooks

`figure_display` pauses only on interactive GUI backends. In a notebook, `'show_close'` and `'show_keep'` both render inline once and `'save_only'` suppresses the inline display. Every mode writes the files.

#### On/off options

`remove_outliers_prefit`, `remove_outliers_postfit`, `show_group_size`, `show_emm_lines` and `model_comparison` accept `True`/`False` and also the strings `'true'`/`'false'`, `'on'`/`'off'`, `'yes'`/`'no'` and `'none'` (= off), so scripts ported from MATLAB work unchanged. An unrecognised value raises rather than being read as truthy.

### Supported distributions

| `distribution` | R family | Typical use |
|---|---|---|
| `'normal'` | `gaussian` | Continuous, symmetric outcomes → LMM |
| `'gamma'` | `Gamma` | Positive, right-skewed outcomes (reaction times, distances). Uses a **log** link, not R's canonical inverse (see below) |
| `'binomial'` | `binomial` | Binary / proportion outcomes |
| `'poisson'` | `poisson` | Count data |
| `'inverse_gaussian'` | `inverse.gaussian` | Positive, heavy right tail. Uses a **log** link, not R's canonical `1/mu^2` (see below) |
| `'tweedie'` | `tweedie` | Positive continuous, variance between Poisson and gamma. The others fix the variance power at 0, 1, 2 and 3; tweedie estimates it, and `Summary.txt` reports the estimate |

**The link `'auto'` chooses is kbstatpy's recommendation, not R's canonical one.** They coincide for every family but gamma and inverse Gaussian. R's `Gamma()` defaults to the inverse link, which applied practice abandoned: `beta` then acts on 1/mu, so a *positive* coefficient means a *smaller* mean and every gamma coefficient reads backwards; `mu = 1/(X beta)` requires the linear predictor to stay positive, where `exp(X beta)` never can; and every other positive-outcome family here uses a log, so switching `distribution` between `'gamma'` and `'tweedie'` used to change the mean model rather than only the variance function, leaving the two uncomparable by AIC. Set `link = 'inverse'` to get the canonical link back. `inverse_gaussian` gets a log for the same reasons, its canonical `1/mu^2` being harder still to read.

**A caveat specific to `inverse_gaussian`:** glmmTMB accepts `link = '1/mu^2'` and then fits a **log** link anyway, while `family(m)$link` keeps echoing `1/mu^2`. Verified on a model with a continuous covariate by reconstructing the linear predictor from the fitted values: with `'1/mu^2'` requested, η equals log(μ), and the fit is identical to the log fit in coefficients and log-likelihood. (A factor-only design cannot show this: it saturates the fixed-effect means, so every link gives the same fitted values.) This is not a display-only bug — the numbers themselves are the log fit's. Checked against glmmTMB 1.1.14. kbstatpy therefore reports the link actually used, and warns if you ask for `1/mu^2`. So the default change costs nothing for existing inverse Gaussian models: they were already being fitted on a log link, whatever the summary claimed. `'inverse'` and `'identity'` *are* honoured.

When `distribution = 'normal'` a linear mixed model (LMM) is fitted via `lmer`. All other distributions produce a GLMM via `glmmTMB`. (Earlier versions used `lme4::glmer`, but it returns mis-scaled standard errors for the continuous dispersion families — Gamma and inverse Gaussian — so `glmmTMB`, which estimates the dispersion explicitly, is used instead. See `STATISTICAL_NOTES.md`.)

---

## Multi-y

Set `options.y` to a list (or comma-separated string) to run the full pipeline independently for each dependent variable:

```python
options.y       = 'Sepal.Length, Sepal.Width, Petal.Length, Petal.Width'
options.y_units = 'cm'   # single entry expands to all variables
```

Results are saved into per-variable subdirectories under `out_dir`. A shared correlation analysis (if `options.correlation` is set) runs once after all models have been fitted.

To correct for multiple comparisons across these dependent variables, set `options.y_correction` (`'bonferroni'`, `'holm'`, `'FDR'`, or `'FDR_correlated'`). Each model term is treated as its own family — e.g. the `Role` p-values across all DVs are adjusted together, the `Age` p-values separately, and so on — and the raw and adjusted p-values are written to `MultipleComparisons.xlsx` in `out_dir`. Note this corrects only within a single run: if your family of tests spans several separate runs (e.g. one per task or condition), apply the correction at that outer level instead.

---

## Data transformation

Set `options.y_transform` to an expression using `y` as the placeholder:

```python
options.y_transform = 'log(y)'   # log-transform before fitting
```

The inverse is derived automatically via `sympy`. Estimated marginal means, confidence intervals, and pairwise differences in the post-hoc table are all back-transformed to the original scale.

---

## Correlation analysis

Set `options.correlation` to a list of numeric variable names:

```python
options.correlation = 'hp, wt'   # variables must be numeric
```

This produces:
- **`Correlation.png/.pdf`** — scatter plot grid (one panel per unique pair) with regression line and r/p annotation
- **`CorrelationTable.png/.pdf`** — colour-coded lower-triangle table (red = positive, blue = negative; significant pairs coloured, non-significant shown as `n.s.`)
- **`Correlation.xlsx`** — full pairwise table with r, p, significance stars, and Cohen's r label

When three or more variables are correlated, partial correlations are also produced (residuals after regressing out all other variables):
- **`PartialCorrelation.png/.pdf`** — scatter grid of residuals
- **`PartialCorrelationTable.png/.pdf`** — colour-coded lower-triangle table for partial r
- **`PartialCorrelation.xlsx`** — partial r, p, significance, and Cohen's r label

VIF is computed for every model with two or more numeric covariates, independently of this analysis (see below).

---

## Residual spread ratio

The **Residuals vs Fitted** panel carries a `spread ratio`: mean |residual| in the top third of fitted values divided by the same in the bottom third. It puts a number on the fan that the panel is there to show, so two fits can be compared without flipping between figures.

Near 1 is constant spread. Rising well above it is heteroscedasticity, the residuals widening as the fitted values grow. It is reported in `Summary.txt` as well as on the panel.

**It is descriptive, not a test.** There is no null distribution behind it, so it carries no p-value and is never starred. A formal check would be a Breusch-Pagan or White test, neither of which transfers cleanly to a mixed model.

**It compares fits of the same family, not one family against another.** The ratio is computed on whichever residuals the panel draws. For a gaussian fit those are the response residuals, so it measures the raw fan. For a GLMM they are deviance or Pearson residuals, already divided by the standard deviation the model assumes, so it measures the fan *left over* once the variance function has done its work. A tweedie fit reporting a ratio near 1 has accounted for its heteroscedasticity; it does not mean the raw data were homoscedastic.

It is omitted when there are too few observations for the tertiles to mean anything, when the fitted values barely vary, or when the bottom third has no spread to divide by.

---

## Variance Inflation Factor (VIF)

VIF is computed for every fit with two or more numeric covariates. In practice that means `options.covariate`: `options.x` is cast to factors before fitting, so a numeric variable placed there is a grouping factor with one level per distinct value, not a continuous predictor with a variance to inflate. It needs no `correlation` analysis and no numeric variable in `x`: up to version 1.23.2 it lived inside the correlation analysis and so went unreported unless that was separately requested, which is how a model with severely collinear covariates could come out looking healthy.

A predictor nearly determined by the others cannot be estimated precisely. The coefficients stay unbiased and the fit is unaffected, but the standard error of such a term is inflated by about √VIF, so its own p-value should not be read as an effect. Terms that are not collinear keep their precision. A correlation matrix will not reveal this: a variable can be nearly determined by two others while correlating only moderately with each.

```
VIF < 5    → OK
VIF 5–10   → concerning
VIF > 10   → severe
```

These are the conventional rules of thumb, not tests, and they have no distributional basis. What matters is whether the resulting standard error is too wide for the question, so a high VIF on a nuisance covariate is far less troubling than one on the term under test.

**Read the VIF together with the sample size.** For an ordinary least-squares fit the standard error is exactly

```
SE(β̂ⱼ) = (σ / sⱼ) · √( VIF / (n − 1) )
```

so collinearity and sample size enter it together: a large VIF matters less when there is plenty of data and more when there is not. The reported table therefore carries `n` beside the VIF, and next to it the number of **independent** units, which is the count that actually carries the information. A predictor that is constant within each subject is estimated from the subjects however many rows there are, and reporting the row count alone would overstate the evidence, easily by an order of magnitude:

```
  variable               VIF   SE x      n  indep.  verdict     varies
  Weight                31.9   5.7x    578      25  severe      between Subject
  BMI                   17.7   4.2x    578      25  severe      between Subject
  Avg_walking_speed      9.8   3.1x    578     578  concerning  within Subject
  Step_Width             1.1   1.1x    578     578  OK          within Subject
```

Every predictor is listed, in `Summary.txt` and in **`VIF.xlsx`** beside the model's other tables, worst first — a value below the flag is information too, and the table's absence would otherwise be ambiguous. The diagnostics figure, which has no room for a table, names only the flagged terms and the worst of them. A term at 10 or above also raises a warning.

---

## Level-wise profile analysis

When one factor is an **ordered series of levels** — spinal segments, joints along
a limb, dose steps, time points — the question is often not "is there an effect at
some level?" but "how does another factor's effect change *across* the ordered
levels?" The pattern across levels is itself the finding. Set `options.profile_across`
to that ordered factor:

```python
options.x            = 'supp, dose'
options.interaction  = 'supp, dose'          # B must interact with the profiled factor
options.x_order      = 'dose: low, medium, high'   # fixes the level order for the trend
options.profile_across = 'dose'
```

On top of the usual analyses, kbstatpy then profiles the factor(s) that interact
with B (here `supp`) across B's ordered levels, in two layers:

- **Layer 1 — per level.** Each interacting factor's pairwise contrast computed
  *within* every level of B (the level-by-level profile), with per-level estimate,
  CI, and p — marginal over any further factors.
- **Layer 2 — trend.** The interaction as a focused **1-df linear trend** across
  B's ordered positions (an emmeans polynomial interaction contrast on the fitted
  model), reported alongside the factor-omnibus `A:B` already in the ANOVA. Leading
  with the trend follows the principle that *a focused trend beats a diffuse
  omnibus*.

Level order is taken from `x_order[B]` if set, else B's existing order. Positions
are the level labels' numeric values when they all parse as numbers — so genuinely
unequal spacing (e.g. dose `1, 2, 10`) is honoured — otherwise equal-spaced ranks.
The trend's estimate is the per-unit slope of the profiled contrast across B, and
its test reduces exactly to the equal-spaced polynomial trend when spacing is equal.
The analysis is meaningful only when B
interacts with the profiled factor (otherwise the profile is flat by construction)
and has ≥3 ordered levels (with 2, the "trend" is just the single contrast); both
cases warn. This produces:

- **`LevelProfile.pdf/.png`** — the profile plot: response EMMs across B, one line
  per level of the profiled factor, with 95 % CI error bars.
- **`LevelProfile.xlsx`** — a `Trend` sheet (linear-trend and factor-omnibus tests)
  plus a `Profile_<factor>` sheet per interacting factor (the per-level contrasts).

See `demos/scripts/demo_16_profile.py` for a worked example (the OJ-vs-VC advantage
in `ToothGrowth` attenuating monotonically across dose).

---

## Output files

All files are written into a per-variable subdirectory of `out_dir` (named after the dependent variable):

| File | Contents |
|---|---|
| `Anova.xlsx` | Type III ANOVA table with F, df, p, partial η², SMD, effect size label |
| `Posthoc.xlsx` | Pairwise EMM comparisons: response-scale means and CIs, difference, t/z, SMD, p (raw + corrected) |
| `Statistics.xlsx` | Descriptive statistics per group (N, mean, SD, SE, median, IQR, EMM, 95% CI) |
| `Data.csv` | Copy of the input data as loaded and filtered. With `scale_covariates` on, each scaled covariate appears beside its original as `<name>_scaled` |
| `Summary.txt` | Human-readable summary: formula, fit stats, ANOVA, post-hoc, and explanatory notes |
| `DataPlots.pdf/.png/.html` | Data plots with model 95 % CI bar, EMM marker, and significance brackets. Style depends on `plot_style`: violin + jitter scatter (default for continuous outcomes), or observed mean/proportion bars (default for binary outcomes). `show_emm_lines` extends each group's EMM across the panel as a reference line, and `show_group_size` labels each group with its observation count. The `.html` version is interactive: hover over any data point to see its observation index, group, and value; hover over an EMM dot to see the marginal mean. A single plot shows at most three factors (x-axis, column facets, row facets); with a 4th (or further) fixed-effect factor the plot is split into one file per level-combination of the extra factor(s), named `DataPlots_<level>` (e.g. `DataPlots_male`, `DataPlots_female`) |
| `Diagnostics.pdf/.png/.html` | Six model diagnostic plots: histogram of residuals, Q-Q plot, residuals vs. fitted, lagged residuals, fitted vs. response, and either a random-effects Q-Q plot (for models with a random effect) or a Scale-Location plot (for plain linear models). The distribution panels (histogram, Q-Q) use DHARMa quantile residuals (normal-scaled; ~N(0,1) under a correct model for any family, so they are valid normality checks even for non-Gaussian GLMMs, with a deviance/Pearson fallback if DHARMa is unavailable); the structure panels (residuals vs. fitted, lagged, scale-location) use deviance residuals, which avoid the quantile residuals' boundary capping and suit structure/autocorrelation/homoscedasticity checks. The `.html` version is interactive with hover tooltips on all scatter panels. Inspect after every run — visual diagnostics are more reliable than formal tests (Shapiro–Wilk, Levene, Durbin–Watson) because formal tests have too little power at small n and flag trivial deviations at large n. See [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md#diagnostic-plots) for panel-by-panel interpretation |
| `Correlation.pdf/.png` | Scatter plot grid for `options.correlation` variables |
| `CorrelationTable.pdf/.png` | Colour-coded lower-triangle correlation table; `n.s.` on non-significant pairs |
| `Correlation.xlsx` | Pairwise Pearson r, p, significance, and Cohen's r label |
| `PartialCorrelation.pdf/.png` | Scatter grid of residual-based partial correlations (3+ variables only) |
| `PartialCorrelationTable.pdf/.png` | Colour-coded lower-triangle table for partial correlations |
| `PartialCorrelation.xlsx` | Partial r, p, significance, and Cohen's r label |
| `VIF.xlsx` | Variance Inflation Factors for the numeric predictors, with the sample size and the number of independent units beside each |
| `LevelProfile.pdf/.png` | Profile plot for `profile_across`: response EMMs across the ordered factor, one line per level of the profiled factor, with 95 % CI error bars |
| `LevelProfile.xlsx` | Level-wise profile tables (when `profile_across` is set): a `Trend` sheet (linear-trend + factor-omnibus interaction tests) and a `Profile_<factor>` sheet of per-level contrasts per interacting factor |
| `MultipleComparisons.xlsx` | Across-y multiple-comparison correction (when `y_correction` is set and `y` has >1 component): per term, the raw and adjusted p-values for every dependent variable |

`Anova.xlsx`, `Posthoc.xlsx`, `Statistics.xlsx`, `Data.csv`, `Summary.txt`, `DataPlots`, and `Diagnostics` are written into a per-variable subdirectory of `out_dir` (named after the dependent variable), for single- and multi-y runs alike. Shared outputs that span all dependent variables — correlation results and `MultipleComparisons.xlsx` — are written to `out_dir` directly.

---

## Demo scripts

Eighteen worked examples are included in the `demos/` folder; each demo's script
docstring and notebook intro cell explain its dataset and statistical content.
Run any demo with:

```bash
cd kbstatpy
python3 demos/scripts/demo_01_unpaired.py
```

| Script | Dataset | Description |
|---|---|---|
| `demo_01_unpaired.py` | `sleep.csv` | Unpaired t-test equivalent — two independent groups, plain LM |
| `demo_02_paired.py` | `sleep.csv` | Paired t-test equivalent — same data with random intercept per subject |
| `demo_03_twoway.py` | `toothgrowth.csv` | Two-way ANOVA equivalent — two between-subject factors |
| `demo_04_lmm.py` | `ergostool.csv` | LMM with random intercepts — one within-subject factor (one-way RM-ANOVA equivalent) |
| `demo_05_correlation.py` | `longley.csv` | Standalone correlation analysis — no model fitted; `constraints` restricts to post-war years (numeric filter) |
| `demo_06_lmm_slopes.py` | `sleepstudy.csv` | LMM with random intercepts and random slopes |
| `demo_07_lmm_transform.py` | `sleepstudy.csv` | LMM with log-transform; EMMs and CIs back-transformed to original scale |
| `demo_08_glmm_gamma.py` | `oats.csv` | GLMM with gamma distribution and log link |
| `demo_09_lmm_partial_interaction.py` | `npk.csv` | LMM with three factors and a partial interaction |
| `demo_10_outliers.py` | `stackloss.csv` | Outlier removal: same LM run twice (default vs. pre-fit IQR + post-fit residual removal) to show the effect on fit quality and estimates |
| `demo_11_glmm_binomial.py` | `bacteria.csv` | GLMM with binomial distribution and logit link — binary outcome (bacteria present/absent) with repeated measures per child |
| `demo_12_multi_y.py` | `iris.csv` | Multiple dependent variables + pairwise correlation analysis; `constraints` excludes setosa (categorical filter) |
| `demo_13_family_correction.py` | `mtcars.csv` | Family-wise correction across multiple dependent variables (`y_correction`) — six outcomes vs transmission, FDR-adjusted as one family per term |
| `demo_14_lm_vif.py` | `mtcars.csv` | LM with mixed numeric/categorical predictors and automatic VIF |
| `demo_15_posthoc_compare.py` | `toothgrowth.csv` | Compare several factors with `posthoc_compare` — one per-cell comparison plot + post-hoc table per factor, each plotted as if it were first |
| `demo_16_profile.py` | `toothgrowth.csv` | Level-wise profile analysis with `profile_across` — how the supp effect changes across the ordered dose levels: per-level contrast (Layer 1) + focused linear-trend interaction (Layer 2) |
| `demo_17_dispersion.py` | `toothgrowth.csv` | Per-group dispersion with `dispersion` (glmmTMB `dispformula`) — a Gamma model fitted with constant vs by-dose dispersion; the by-dose fit lowers AIC when groups differ in relative scatter |
| `demo_18_plot_annotations.py` | `toothgrowth.csv` | Plot annotations that leave the model untouched: `show_emm_lines` extends each group's EMM across its panel (and picks the line style), `show_group_size` labels each group with its observation count |

**Equivalence to classical tests** (demos 1–5) — see [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md):

- **Demo 1** — identical to an independent-samples t-test (F = t², same df and p-value)
- **Demo 2** — equivalent to a paired t-test for balanced data (same estimate, SE, df = n − 1, and p-value); generalises to missing data and unequal group sizes
- **Demo 3** — identical to a classical two-way factorial ANOVA with Type III SS (10 observations per cell)
- **Demo 4** — identical to a one-way repeated-measures ANOVA (4-level within-subject factor) under compound symmetry; LMM generalises to missing cells and unbalanced designs
- **Demo 5** — classical Pearson correlation; additionally computes partial correlations to isolate direct associations when variables co-trend

**Transcending classical tests** (demos 6–11) — see [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md):

- **Demo 6** — no classical equivalent; random slopes capture subject-specific trajectories that RM-ANOVA assumes away
- **Demo 7 vs. 8** — log-transform LMM and gamma GLMM are both valid for right-skewed positive data; gamma is preferred when variance scales with the mean
- **Demo 9** — partial interactions keep the model parsimonious; classical ANOVA always tests all pairwise interactions
- **Demo 10** — data imbalance (unequal cell sizes) can arise by design, through data loss, or through outlier removal; all three cases invalidate classical ANOVA, while GLM fits by maximum likelihood on individual observations and handles any degree of imbalance without modification
- **Demo 11** — binary dependent variables cannot be modelled with gaussian ANOVA; binomial GLMM with logit link models the probability directly and correctly

**Analytical extensions** (demos 12–15) — see [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md):

- **Demo 12** — multiple dependent variables in one call; within-model post-hoc is Holm-corrected, and correction across the dependent variables is available via `y_correction` (Demo 13)
- **Demo 13** — family-wise correction across multiple dependent variables (`y_correction`), one family per model term
- **Demo 14** — VIF flags collinearity among numeric predictors before it distorts coefficient estimates
- **Demo 15** — `posthoc_compare` runs the pairwise comparisons (and brackets) on any chosen factor(s) instead of just the first, each plotted as if it were the first variable, and per cell (the factor is compared within each combination of the others, so every facet panel gets its own brackets)
- **Demo 16** — `profile_across` profiles a factor's effect across an ordered factor's levels: per-level contrasts (Layer 1) plus the interaction as a focused 1-df linear trend reported against the diffuse omnibus (Layer 2) — the "pattern across levels is the finding" view
- **Demo 17** — `dispersion` sets glmmTMB's `dispformula` so the dispersion can vary by a factor instead of the default constant `~1`; a Gamma model fitted with constant vs by-group dispersion shows the better fit (lower AIC) when groups differ in relative scatter

The demo datasets are already included as CSVs in `demos/data/`. You only need
to regenerate them if you change `export_datasets.R`:

```bash
Rscript export_datasets.R
```

### Try the demos on Google Colab

Every demo is also a **notebook you can open and run in the browser** — no local
install, no R to set up on your own machine — on a free
[Google Colab](https://colab.research.google.com) runtime. Open one and run it
top to bottom: the first cell installs everything (~3–5 min, once per session) and
the analysis — tables and figures — renders inline. Running or editing a cell
gives you your own private copy, so you can experiment freely.

New here? The guided playground walks through one demo and points to the rest:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/kbstatpy_colab.ipynb)

Or open any individual demo directly — each installs itself and renders its
results inline:

| Demo | Open in Colab |
|---|---|
| 1 · Unpaired *t*-test equivalent | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_01_unpaired.ipynb) |
| 2 · Paired *t*-test equivalent | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_02_paired.ipynb) |
| 3 · Two-way ANOVA equivalent | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_03_twoway.ipynb) |
| 4 · One-way RM-ANOVA (LMM) | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_04_lmm.ipynb) |
| 5 · Standalone correlation analysis | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_05_correlation.ipynb) |
| 6 · LMM with random slopes | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_06_lmm_slopes.ipynb) |
| 7 · LMM with log-transform | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_07_lmm_transform.ipynb) |
| 8 · GLMM (gamma, log link) | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_08_glmm_gamma.ipynb) |
| 9 · LMM with partial interaction | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_09_lmm_partial_interaction.ipynb) |
| 10 · Outlier removal (pre/post-fit) | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_10_outliers.ipynb) |
| 11 · GLMM (binomial, logit link) | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_11_glmm_binomial.ipynb) |
| 12 · Multiple dependent variables + correlation | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_12_multi_y.ipynb) |
| 13 · Family-wise correction across DVs | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_13_family_correction.ipynb) |
| 14 · LM with mixed predictors + VIF | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_14_lm_vif.ipynb) |
| 15 · `posthoc_compare` across factors | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_15_posthoc_compare.ipynb) |
| 16 · Level-wise profile (`profile_across`) | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_16_profile.ipynb) |
| 17 · Per-group dispersion (`dispersion`) | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_17_dispersion.ipynb) |
| 18 · Plot annotations (`show_emm_lines`, `show_group_size`) | [notebook ▸](https://colab.research.google.com/github/kimbostroem/kbstatpy/blob/master/demos/notebooks/demo_18_plot_annotations.ipynb) |

---

## Statistical notes

See [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md) for the rationale behind key design decisions:

- **Effects coding** (`contr.sum`) — why it is used and why treatment coding is problematic
- **Type III sums of squares** — when Type II would differ and why Type III is preferred
- **Kenward-Roger / Satterthwaite df vs. df = Inf** — the `df_method` option, why GLMMs yield asymptotic tests, and how large fits are handled
- **Post-hoc comparisons with emmeans** — marginal means and Holm correction, over a family scope you choose (`posthoc_family`)
- **Which scale the post-hoc columns are on** — `emm_1`, `emm_2` and `diff` are on the response scale; `t`, `df` and `p` come from the contrast on the link scale, so under a non-identity link `t` is not `diff` over its standard error, and under a decreasing link the two carry opposite signs. `Summary.txt` states this whenever the link is not the identity
- **VIF and multicollinearity** — what VIF measures and when it matters

---

## Known issues and workarounds

- **GLMM engine (glmmTMB, not glmer):** all non-Gaussian GLMMs are fitted with `glmmTMB` rather than `lme4::glmer`. glmer fits the correct point estimates and log-likelihood but returns a mis-scaled fixed-effect covariance for the continuous dispersion families (Gamma, inverse Gaussian), which collapses the standard errors and inflates Wald omnibus tests, post-hoc p-values, and EMM confidence intervals. glmmTMB estimates the dispersion as an explicit parameter and computes the covariance from a proper Hessian, so those quantities are reliable and mutually coherent. glmmTMB also handles random slopes natively, which additionally removes the old pymer4 random-slope crash (no `GlmerDirect` workaround needed). No action required from the user. See `STATISTICAL_NOTES.md` for details.
