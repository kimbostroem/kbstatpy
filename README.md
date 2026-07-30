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
- [Multi-y](#multi-y)
- [Data transformation](#data-transformation)
- [Correlation analysis](#correlation-analysis)
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

- Python 3.10+
- R 4.4+
- **Platform:** macOS or Linux. On Windows, use [WSL](https://learn.microsoft.com/windows/wsl/install) (e.g. Ubuntu) and follow the Linux steps — `rpy2`, the R bridge kbstatpy relies on, is not reliably installable on native Windows.

All Python and R package dependencies are handled by the installer (see below).

---

## Installation

```bash
cd kbstatpy
bash install.sh
```

The installer (macOS/Linux):
1. Installs **kbstatpy** and its Python dependencies (`pymer4`, `rpy2`, `pandas`, `scipy`, `sympy`, `seaborn`, `openpyxl`, …) from `pyproject.toml`, so `import kbstatpy` works from any directory
2. Installs all required R packages (`lme4`, `lmerTest`, `glmmTMB`, `emmeans`, `DHARMa`, …)
3. On macOS: automatically fixes the `rpy2` / R version symlink if needed

On Windows, run these same steps inside a [WSL](https://learn.microsoft.com/windows/wsl/install) shell.

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

All list-valued options (`x`, `covariate`, `slope`, `interaction`, `y_units`, `x_units`, `correlation`) accept either a Python list or a comma-separated string — whichever is more convenient.

---

## Options reference

| Option | Type | Default | Description |
|---|---|---|---|
| `in_file` | str | `''` | Path to input data (.csv or .xlsx) |
| `out_dir` | str | `''` | Output directory for result files. Relative paths resolve against the current working directory. Leave empty to display results inline only and write nothing to disk (useful in notebooks); set a path to save all tables and figures |
| `demo_dir` | str | *(auto)* | Absolute path to the bundled demo folder, set at instantiation. Convenience anchor for example inputs, e.g. `os.path.join(options.demo_dir, 'data/sleep.csv')` (valid when running from the source tree). Outputs need no such anchor — a relative `out_dir` already resolves against the working directory |
| `formula` | str | `''` | Full Wilkinson formula (overrides `y`, `x`, `id`, `slope`, `interaction`) |
| `y` | str or list | `''` | Dependent variable(s). A list (or comma-separated string) runs one analysis per variable |
| `y_units` | str or list | `''` | Unit label(s) for the y-axis, e.g. `'ms'` or `'kg, N, m'` for multi-y |
| `x` | list / str | `[]` | Fixed-effect factor column names |
| `x_order` | str or dict | `None` | Reorder factor levels. String form: `'dose: low, medium, high'` or multiple variables `'dose: low, medium, high; supp: OJ, VC'`. Dict form also accepted: `{'dose': ['low','medium','high']}`. When used with `rename`, use the renamed variable and level names here |
| `rename` | str or dict | `None` | Rename factor levels and/or variable display labels. String form: `'cyl: 4 -> 4 cyl, 6 -> 6 cyl; dose: low -> Low dose'` for level renames, `'cyl -> Cylinders'` for variable display labels, or combine: `'cyl -> Cylinders; cyl: 4 -> 4 cyl, 6 -> 6 cyl'`. Variable renames apply to axis labels and table headers; level renames apply to data values before fitting |
| `x_units` | list / str | `''` | Unit label(s) for x-axis tick groups; `'1'` means no units |
| `id` | str | `''` | Random-effect grouping variable (e.g. subject ID) |
| `slope` | list / str | `[]` | Variables with random slopes (e.g. `'A, B'` → `(1 + A + B \| id)`) |
| `slope_correlated` | bool or str | `'auto'` | Random-effect covariance structure for the slopes: `True` (full covariance `(1 + s \| id)`), `False` (uncorrelated/diagonal — glmmTMB `diag(1 + s \| id)` for non-gaussian families, lme4 `(1 + s \|\| id)` for gaussian LMMs), or `'auto'` (default: fit correlated, then refit diagonal only if that fit is singular). The diagonal structure drops the correlation parameters and escapes the singular fits a many-level factor slope can otherwise produce. The structure actually used is reported in `Summary.txt` and the diagnostics footer. Ignored when an explicit `formula` is given. See [Random slopes in GLMMs](STATISTICAL_NOTES.md#random-slopes-in-glmms-pymer4-bug-and-workaround) |
| `interaction` | list / str | `[]` | Interaction terms to include (e.g. `'A, B'` → `A:B` in formula) |
| `covariate` | list / str | `[]` | Numeric covariates: included in the model but excluded from data plots and post-hoc |
| `y_transform` | str | `''` | Transform expression using `y` as placeholder, e.g. `'log(y)'`. EMMs and CIs are back-transformed automatically |
| `correlation` | list / str | `''` | Variables for pairwise Pearson correlation (must be numeric). Produces scatter grid, colour table, and Excel output |
| `constraints` | str | `''` | Row filter applied before analysis, e.g. `'Year > 1950'` or `'group != "control"'`. Standard Python operators: `==` `!=` `<` `>` `<=` `>=`; combine with `&` (and) / `\|` (or) |
| `distribution` | str | `'normal'` | Response distribution (see below) |
| `link` | str | `'auto'` | Link function (`'auto'`, `'log'`, `'logit'`, …) |
| `fit_method` | str | `'MPL'` | Fit method passed to lme4 |
| `max_iterations` | int | `10000` | Maximum optimizer iterations/function evaluations for glmmTMB fits (non-Gaussian GLMMs). Large fixed-effect models (e.g. a factor×factor interaction with many levels) can hit the default cap and emit a benign "iteration limit reached" warning even at the optimum; raising this lets them converge cleanly |
| `df_method` | str | `'auto'` | Denominator-df method for the fixed-effect ANOVA F-tests and post-hoc contrasts (used for both, so they stay consistent). `'auto'`: Kenward-Roger for Gaussian LMMs when `pbkrtest` is installed, else Satterthwaite; exact residual df for plain LMs; asymptotic (`df = Inf`) for GLMMs. Override with `'kenward-roger'`, `'satterthwaite'`, or `'asymptotic'` (aliases `'kr'`, `'satt'`, `'wald'`). An unavailable request warns and falls back. See [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md) |
| `remove_outliers_prefit` | bool | `False` | Flag and exclude outliers before fitting using the IQR rule (1.5 × IQR beyond Q1/Q3) per group. Protects the model from extreme raw values |
| `remove_outliers_postfit` | bool | `False` | Flag and exclude outliers after fitting based on Pearson residuals (z > 3), then refit. Catches observations that become outliers only in relation to the model. Can be combined with `remove_outliers_prefit` |
| `posthoc_method` | str | `'emm'` | Post-hoc method (currently `'emm'` for emmeans) |
| `posthoc_correction` | str | `'holm'` | P-value correction for pairwise comparisons *within* a model (`'holm'`, `'bonferroni'`, `'fdr'`, …) |
| `posthoc_compare` | str | `'auto'` | Which fixed-effect factor(s) to run pairwise level comparisons on. Each listed factor is plotted as if it were the first x-variable — its levels on the x-axis, the others as facet panels — with significance brackets. Comparisons are conditional (per cell): a factor's levels are compared within each combination of the other factors, so every facet panel gets its own brackets (and its own block of rows in `Posthoc_<var>.xlsx`, with the conditioning factors as leading columns), plus a marginal block (every conditioning column set to `'any'`) averaged over them. Comma-separated for multiple factors; `''` or `'none'` turns comparisons off (violins only, no brackets); `'auto'` (default) compares the first x-variable. Output files are suffixed with the variable name, e.g. `DataPlots_condition.*` / `Posthoc_condition.xlsx`. `'auto'` and `'none'` are reserved — a factor may not be named either |
| `profile_across` | str | `''` | Level-wise profile analysis across one ordered categorical factor B (must be in `x`). In addition to the normal analyses, profiles how the factor(s) that interact with B behave across B's ordered levels: each interacting factor's pairwise contrast *within* every level of B (Layer 1), and the interaction as a focused 1-df **linear trend** across B's positions reported next to the factor-omnibus (Layer 2). Level order from `x_order[B]` else B's existing order; the trend uses the level labels' numeric values when all parse (so unequal spacing is honoured), else equal-spaced ranks — its estimate is the per-unit slope of the profiled contrast, and its test reduces to the equal-spaced polynomial trend when spacing is equal. Writes `LevelProfile.xlsx` plus **two** figures: `LevelProfile` (absolute EMMs per level of the profiled factor) and `LevelProfileContrast` (the pairwise contrasts themselves across B, with 95% CIs and the fitted 1-df trend, which is the quantity the trend test actually measures). Meaningful when B interacts with the profiled factor and has ≥3 ordered levels (warns otherwise). See [Level-wise profile analysis](#level-wise-profile-analysis) |
| `y_correction` | str | `'none'` | Multiple-comparison correction applied *across* the dependent variables of a multi-y run, one family per model term: `'none'`, `'bonferroni'`, `'holm'`, `'FDR'` (Benjamini–Hochberg), `'FDR_correlated'` (Benjamini–Yekutieli, valid under dependence). Case-insensitive. Writes `MultipleComparisons.xlsx`. Only acts when `y` has more than one component (see [Multi-y](#multi-y)) |
| `plot_style` | str | `'auto'` | Data plot style: `'violin'` (violin + jitter), `'bar'` (observed mean bars with EMM overlay), or `'auto'` (bar for binary outcomes, violin for all others) |
| `title` | str | `''` | Data-plot title prefix. When set, the title becomes `'<title> (<DV>)'`, e.g. `title='Static'` → `'Static (Torque Amplitude)'`. Empty (default) shows just the plain dependent-variable name as the title. `'none'` (case-insensitive) suppresses the title entirely — no text, and no vertical space reserved for it — while leaving the y-axis label untouched (the title and y-axis label otherwise both derive from the same variable display name, so this is the only way to drop the title alone) |
| `title_font` | str or list | `''` | Font family for plot titles (suptitles), distinct from the body font (see `font`). Empty (default) derives a condensed/narrow variant of the body font when one is installed (e.g. `'Arial'` → `'Arial Narrow'`, `'DejaVu Sans'` → `'DejaVu Sans Condensed'`), otherwise the body font itself. Set a family name (or list of names) to override |
| `x_label` | str | `'variable_below_levels'` | How the x-axis labels the first factor's levels: `'variable_below_levels'` (default) level names as tick labels, with the variable name as the axis label below them; `'variable_equals_level'` each tick reads `'<variable> = <level>'`, no separate axis label; `'levels'` only the level names, the variable name is hidden; `'none'` no x-axis labelling at all (neither level ticks nor variable name) |
| `y_label` | str | `'variable_with_units'` | How the y-axis of the data plot is labelled: `'variable_with_units'` (default) variable name plus `[units]` when units are set; `'variable_only'` variable name only, no units; `'none'` no y-axis label at all |
| `data_outliers` | str | `'text'` | How data outliers (flagged by `remove_outliers_prefit`/`remove_outliers_postfit`) appear in the data plot. `'text'` (default) omits the points but annotates the count and percentage at the bottom of each panel, so the y-axis autoscales to the non-outlier data — useful when extreme outliers otherwise squash the plot; `'plot'` draws each outlier as a red X marker; `'hide'` omits them entirely. (Renamed from `show_outliers`, which still works with a deprecation warning; the old `'none'` maps to `'hide'`.) |
| `diagnostic_outliers` | str | `'text'` | How diagnostic outliers appear in the diagnostic distribution panels (histogram and Q-Q). These are the DHARMa quantile residuals that fall outside the entire simulated range and are capped at z = ±7 (a model-misfit / heavy-tail flag, distinct from the data outliers above). `'text'` (default) omits the capped points and annotates the count/percentage; `'plot'` shows them in a distinct colour (orange); `'hide'` omits them silently. |
| `y_scale` | str | `'linear'` | y-axis scale for the data plots and the profile plot (`profile_across`). `'log'` gives a logarithmic y-axis, which is useful when the panels of one figure span orders of magnitude (e.g. joint torque at the ankle vs the upper body), where a shared linear axis flattens the small-valued panels into slivers, and for gamma/log-link models, where a constant ratio becomes a constant distance. Significance brackets and the y-limit padding are computed in log space so their spacing stays even. Requires strictly positive plotted values; a non-positive value falls back to `'linear'` with a warning. The y-axis label gains a `(log scale)` note whenever the log axis is actually applied, since the ticks themselves show untransformed values. Diagnostic and correlation figures are never rescaled. |
| `figure_display` | str | `'show_close'` | How figures are shown on screen (all modes still save files): `'save_only'` (don't display — useful for batch/headless runs), `'show_close'` (display briefly, then close), `'show_keep'` (display and leave the window open). The brief pause applies only to interactive GUI backends; in a Jupyter notebook `show_close` and `show_keep` both simply render the figure inline once, while `save_only` suppresses inline display |
| `color_scheme` | str | `'Set1'` | Seaborn/matplotlib color palette for data plots |
| `color_sat` | float | `0.9` | Violin colour saturation (0–1) |
| `color_alpha` | float | `0.5` | Violin fill transparency (0 = transparent, 1 = opaque) |
| `font` | str | `'Helvetica, DejaVu Sans'` | Matplotlib font family, or a comma-separated fallback chain tried in order. The default is **Helvetica** — the real font on macOS/Windows and the bundled **TeX Gyre Heros** clone on Linux/Colab, so it renders as Helvetica everywhere with no system font install. kbstatpy also bundles **Latin Modern Sans** (the LaTeX look) and **TeX Gyre Termes** (a Times clone), all registered on import. Override with any family or chain; a request for Helvetica/Arial or Times falls back to its bundled clone where the real font is absent, keeping the intended look instead of dropping to the visibly-different DejaVu Sans. Convenient case-insensitive aliases: `'Sans'`/`'Modern'` → Latin Modern Sans, `'Times'` → Times New Roman (any family name is also matched case-insensitively). A missing family never warns; `''`/`'auto'` use matplotlib's own default. Bundled fonts are under the GUST Font License (see `kbstatpy/fonts/`). `''` or `'auto'` use matplotlib's own default (`'DejaVu Sans'`); a single name (e.g. `'Arial'`) forces just that one. Serif (matches journal body text): `'Times New Roman'`, `'Georgia'`, `'Palatino'`. To make a hand-built matplotlib figure (one that bypasses `run_save()` entirely) match kbstat's own plots, call the public `Kbstat.apply_font()` before building it, then use `fontweight='bold'` on the labels/ticks that should match |

### Supported distributions

| `distribution` | R family | Typical use |
|---|---|---|
| `'normal'` | `gaussian` | Continuous, symmetric outcomes → LMM |
| `'gamma'` | `Gamma` | Positive, right-skewed outcomes (reaction times, distances) |
| `'binomial'` | `binomial` | Binary / proportion outcomes |
| `'poisson'` | `poisson` | Count data |
| `'inverse_gaussian'` | `inverse.gaussian` | Positive, heavy right tail |

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

If `options.x` contains numeric predictors, VIF is also computed automatically (see below).

---

## Variance Inflation Factor (VIF)

When `options.x` contains numeric variables, VIF is computed automatically for all numeric variables in `options.x` + `options.covariate` as a multicollinearity check:

```
VIF < 5    → OK
VIF 5–10   → concerning
VIF > 10   → severe
```

Results are printed to the console and saved to **`VIF.xlsx`**.

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
| `Data.csv` | Copy of the input data as loaded and filtered |
| `Summary.txt` | Human-readable summary: formula, fit stats, ANOVA, post-hoc, and explanatory notes |
| `DataPlots.pdf/.png/.html` | Data plots with model 95 % CI bar, EMM marker, and significance brackets. Style depends on `plot_style`: violin + jitter scatter (default for continuous outcomes), or observed mean/proportion bars (default for binary outcomes). The `.html` version is interactive: hover over any data point to see its observation index, group, and value; hover over an EMM dot to see the marginal mean. A single plot shows at most three factors (x-axis, column facets, row facets); with a 4th (or further) fixed-effect factor the plot is split into one file per level-combination of the extra factor(s), named `DataPlots_<level>` (e.g. `DataPlots_male`, `DataPlots_female`) |
| `Diagnostics.pdf/.png/.html` | Six model diagnostic plots: histogram of residuals, Q-Q plot, residuals vs. fitted, lagged residuals, fitted vs. response, and either a random-effects Q-Q plot (for models with a random effect) or a Scale-Location plot (for plain linear models). The distribution panels (histogram, Q-Q) use DHARMa quantile residuals (normal-scaled; ~N(0,1) under a correct model for any family, so they are valid normality checks even for non-Gaussian GLMMs, with a deviance/Pearson fallback if DHARMa is unavailable); the structure panels (residuals vs. fitted, lagged, scale-location) use deviance residuals, which avoid the quantile residuals' boundary capping and suit structure/autocorrelation/homoscedasticity checks. The `.html` version is interactive with hover tooltips on all scatter panels. Inspect after every run — visual diagnostics are more reliable than formal tests (Shapiro–Wilk, Levene, Durbin–Watson) because formal tests have too little power at small n and flag trivial deviations at large n. See [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md#diagnostic-plots) for panel-by-panel interpretation |
| `Correlation.pdf/.png` | Scatter plot grid for `options.correlation` variables |
| `CorrelationTable.pdf/.png` | Colour-coded lower-triangle correlation table; `n.s.` on non-significant pairs |
| `Correlation.xlsx` | Pairwise Pearson r, p, significance, and Cohen's r label |
| `PartialCorrelation.pdf/.png` | Scatter grid of residual-based partial correlations (3+ variables only) |
| `PartialCorrelationTable.pdf/.png` | Colour-coded lower-triangle table for partial correlations |
| `PartialCorrelation.xlsx` | Partial r, p, significance, and Cohen's r label |
| `VIF.xlsx` | Variance Inflation Factors for numeric predictors (when applicable) |
| `LevelProfile.pdf/.png` | Profile plot for `profile_across`: response EMMs across the ordered factor, one line per level of the profiled factor, with 95 % CI error bars |
| `LevelProfile.xlsx` | Level-wise profile tables (when `profile_across` is set): a `Trend` sheet (linear-trend + factor-omnibus interaction tests) and a `Profile_<factor>` sheet of per-level contrasts per interacting factor |
| `MultipleComparisons.xlsx` | Across-y multiple-comparison correction (when `y_correction` is set and `y` has >1 component): per term, the raw and adjusted p-values for every dependent variable |

`Anova.xlsx`, `Posthoc.xlsx`, `Statistics.xlsx`, `Data.csv`, `Summary.txt`, `DataPlots`, and `Diagnostics` are written into a per-variable subdirectory of `out_dir` (named after the dependent variable), for single- and multi-y runs alike. Shared outputs that span all dependent variables — correlation results and `MultipleComparisons.xlsx` — are written to `out_dir` directly.

---

## Demo scripts

Sixteen worked examples are included in the `demos/` folder; each demo's script
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

---

## Statistical notes

See [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md) for the rationale behind key design decisions:

- **Effects coding** (`contr.sum`) — why it is used and why treatment coding is problematic
- **Type III sums of squares** — when Type II would differ and why Type III is preferred
- **Kenward-Roger / Satterthwaite df vs. df = Inf** — the `df_method` option, and why GLMMs yield asymptotic tests
- **Post-hoc comparisons with emmeans** — marginal means and Holm correction
- **VIF and multicollinearity** — what VIF measures and when it matters

---

## Known issues and workarounds

- **GLMM engine (glmmTMB, not glmer):** all non-Gaussian GLMMs are fitted with `glmmTMB` rather than `lme4::glmer`. glmer fits the correct point estimates and log-likelihood but returns a mis-scaled fixed-effect covariance for the continuous dispersion families (Gamma, inverse Gaussian), which collapses the standard errors and inflates Wald omnibus tests, post-hoc p-values, and EMM confidence intervals. glmmTMB estimates the dispersion as an explicit parameter and computes the covariance from a proper Hessian, so those quantities are reliable and mutually coherent. glmmTMB also handles random slopes natively, which additionally removes the old pymer4 random-slope crash (no `GlmerDirect` workaround needed). No action required from the user. See `STATISTICAL_NOTES.md` for details.
