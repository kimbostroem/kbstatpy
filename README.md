# kbstatpy

A Python library for generalised linear mixed model (GLMM) analysis with post-hoc pairwise comparisons, data transformation, correlation analysis, and multicollinearity diagnostics. Modelled after the MATLAB `kbstat` library.

Fitting is done via R's `lme4` and `emmeans` packages (through `pymer4` and `rpy2`), giving access to the same statistical machinery used in R — Satterthwaite degrees of freedom, Type III sums of squares, and effects-coded contrasts — from a clean Python interface.

---

## Requirements

- Python 3.10+
- R 4.4+

All Python and R package dependencies are handled by the installer (see below).

---

## Installation

```bash
cd kbstatpy
bash install.sh
```

The installer:
1. Installs all required Python packages (`pymer4`, `rpy2`, `pandas`, `scipy`, `sympy`, `seaborn`, `openpyxl`, …)
2. Installs all required R packages (`lme4`, `lmerTest`, `emmeans`, …)
3. On macOS: automatically fixes the `rpy2` / R version symlink if needed

---

## Quick start

```python
from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file    = 'data/mydata.csv'       # path to your data file (.csv or .xlsx)
options.out_dir    = 'results/myanalysis'    # output folder (created if it doesn't exist)
options.y          = 'ResponseVariable'      # dependent variable column name
options.x          = 'FactorA, FactorB'      # fixed-effect factors (comma-separated string or list)
options.id         = 'Subject'               # random-effect grouping variable
options.distribution = 'gamma'
options.link       = 'log'

kb = Kbstat(options)
kb.run()   # fit → anova → posthoc → plots → save
```

`run()` is the one-shot pipeline. You can also call each step individually:

```python
kb.fit()      # fit the LMM / GLMM
kb.anova()    # compute Type III ANOVA table
kb.posthoc()  # pairwise comparisons via emmeans
kb.save()     # write output files to out_dir
```

All list-valued options (`x`, `covariate`, `slope`, `interaction`, `y_units`, `x_units`, `correlation`) accept either a Python list or a comma-separated string — whichever is more convenient.

---

## Options reference

| Option | Type | Default | Description |
|---|---|---|---|
| `in_file` | str | `''` | Path to input data (.csv or .xlsx) |
| `out_dir` | str | `''` | Output directory for result files |
| `formula` | str | `''` | Full Wilkinson formula (overrides `y`, `x`, `id`, `slope`, `interaction`) |
| `y` | str or list | `''` | Dependent variable(s). A list (or comma-separated string) runs one analysis per variable |
| `y_units` | str or list | `''` | Unit label(s) for the y-axis, e.g. `'ms'` or `'kg, N, m'` for multi-y |
| `x` | list / str | `[]` | Fixed-effect factor column names |
| `x_order` | str or dict | `None` | Reorder factor levels. String form: `'dose: low, medium, high'` or multiple variables `'dose: low, medium, high; supp: OJ, VC'`. Dict form also accepted: `{'dose': ['low','medium','high']}`. When used with `rename`, use the renamed variable and level names here |
| `rename` | str or dict | `None` | Rename factor levels and/or variable display labels. String form: `'cyl: 4 -> 4 cyl, 6 -> 6 cyl; dose: low -> Low dose'` for level renames, `'cyl -> Cylinders'` for variable display labels, or combine: `'cyl -> Cylinders; cyl: 4 -> 4 cyl, 6 -> 6 cyl'`. Variable renames apply to axis labels and table headers; level renames apply to data values before fitting |
| `x_units` | list / str | `''` | Unit label(s) for x-axis tick groups; `'1'` means no units |
| `id` | str | `''` | Random-effect grouping variable (e.g. subject ID) |
| `slope` | list / str | `[]` | Variables with random slopes (e.g. `'A, B'` → `(1 + A + B \| id)`) |
| `interaction` | list / str | `[]` | Interaction terms to include (e.g. `'A, B'` → `A:B` in formula) |
| `covariate` | list / str | `[]` | Numeric covariates: included in the model but excluded from data plots and post-hoc |
| `y_transform` | str | `''` | Transform expression using `y` as placeholder, e.g. `'log(y)'`. EMMs and CIs are back-transformed automatically |
| `correlation` | list / str | `''` | Variables for pairwise Pearson correlation (must be numeric). Produces scatter grid, colour table, and Excel output |
| `constraints` | str | `''` | Row filter applied before analysis, e.g. `'Year > 1950'` or `'group != "control"'`. Standard Python operators: `==` `!=` `<` `>` `<=` `>=`; combine with `&` (and) / `\|` (or) |
| `distribution` | str | `'normal'` | Response distribution (see below) |
| `link` | str | `'auto'` | Link function (`'auto'`, `'log'`, `'logit'`, …) |
| `fit_method` | str | `'MPL'` | Fit method passed to lme4 |
| `remove_outliers_prefit` | bool | `False` | Flag and exclude outliers before fitting using the IQR rule (1.5 × IQR beyond Q1/Q3) per group. Protects the model from extreme raw values |
| `remove_outliers_postfit` | bool | `False` | Flag and exclude outliers after fitting based on Pearson residuals (z > 3), then refit. Catches observations that become outliers only in relation to the model. Can be combined with `remove_outliers_prefit` |
| `posthoc_method` | str | `'emm'` | Post-hoc method (currently `'emm'` for emmeans) |
| `posthoc_correction` | str | `'holm'` | P-value correction (`'holm'`, `'bonferroni'`, `'fdr'`, …) |
| `color_scheme` | str | `'Set1'` | Seaborn/matplotlib color palette for data plots |
| `color_sat` | float | `0.9` | Violin colour saturation (0–1) |
| `color_alpha` | float | `0.5` | Violin fill transparency (0 = transparent, 1 = opaque) |
| `font` | str | `''` | Matplotlib font family for all plots. Empty string uses matplotlib's default (`'DejaVu Sans'`). Sans-serif (standard for scientific figures): `'Arial'`, `'Helvetica'`, `'Verdana'`, `'Calibri'`, `'Roboto'`, `'Liberation Sans'` (Arial substitute, always available on Linux). Serif (matches journal body text): `'Times New Roman'`, `'Georgia'`, `'Palatino'` |

### Supported distributions

| `distribution` | R family | Typical use |
|---|---|---|
| `'normal'` | `gaussian` | Continuous, symmetric outcomes → LMM |
| `'gamma'` | `Gamma` | Positive, right-skewed outcomes (reaction times, distances) |
| `'binomial'` | `binomial` | Binary / proportion outcomes |
| `'poisson'` | `poisson` | Count data |
| `'inverse_gaussian'` | `inverse.gaussian` | Positive, heavy right tail |

When `distribution = 'normal'` a linear mixed model (LMM) is fitted via `lmer`. All other distributions produce a GLMM via `glmer`.

---

## Multi-y

Set `options.y` to a list (or comma-separated string) to run the full pipeline independently for each dependent variable:

```python
options.y       = 'Sepal.Length, Sepal.Width, Petal.Length, Petal.Width'
options.y_units = 'cm'   # single entry expands to all variables
```

Results are saved into per-variable subdirectories under `out_dir`. A shared correlation analysis (if `options.correlation` is set) runs once after all models have been fitted.

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

## Output files

All files are written to `out_dir`:

| File | Contents |
|---|---|
| `Anova.xlsx` | Type III ANOVA table with F, df, p, partial η², SMD, effect size label |
| `Posthoc.xlsx` | Pairwise EMM comparisons: response-scale means and CIs, difference, t/z, SMD, p (raw + corrected) |
| `Statistics.xlsx` | Descriptive statistics per group (N, mean, SD, SE, median, IQR, 95% CI) |
| `Data.csv` | Copy of the input data as loaded and filtered |
| `Summary.txt` | Human-readable summary: formula, fit stats, ANOVA, post-hoc, and explanatory notes |
| `DataPlots.pdf/.png` | Violin plots with jittered data points (constrained inside violin body), model 95 % CI bar, EMM marker, and significance brackets |
| `Diagnostics.pdf/.png` | Six model diagnostic plots (residuals, Q-Q, leverage, …) |
| `Correlation.pdf/.png` | Scatter plot grid for `options.correlation` variables |
| `CorrelationTable.pdf/.png` | Colour-coded lower-triangle correlation table; `n.s.` on non-significant pairs |
| `Correlation.xlsx` | Pairwise Pearson r, p, significance, and Cohen's r label |
| `PartialCorrelation.pdf/.png` | Scatter grid of residual-based partial correlations (3+ variables only) |
| `PartialCorrelationTable.pdf/.png` | Colour-coded lower-triangle table for partial correlations |
| `PartialCorrelation.xlsx` | Partial r, p, significance, and Cohen's r label |
| `VIF.xlsx` | Variance Inflation Factors for numeric predictors (when applicable) |

For multi-y runs, `Anova.xlsx`, `Posthoc.xlsx`, `Statistics.xlsx`, `DataPlots`, and `Diagnostics` are written into per-variable subdirectories. Correlation outputs are shared and written to `out_dir` directly.

---

## Demo scripts

Twelve worked examples are included in the `demo/` folder. Run any demo with:

```bash
cd kbstatpy
python3 demo/demo_01_unpaired.py
```

| Script | Dataset | Description |
|---|---|---|
| `demo_01_unpaired.py` | `sleep.csv` | Unpaired t-test equivalent — two independent groups, plain LM |
| `demo_02_paired.py` | `sleep.csv` | Paired t-test equivalent — same data with random intercept per subject |
| `demo_03_twoway.py` | `toothgrowth.csv` | Two-way ANOVA equivalent — two between-subject factors |
| `demo_04_lmm.py` | `sleepstudy.csv` | LMM with random intercepts — one within-subject factor |
| `demo_05_correlation.py` | `longley.csv` | Standalone correlation analysis — no model fitted; `constraints` restricts to post-war years (numeric filter) |
| `demo_06_lmm_slopes.py` | `sleepstudy.csv` | LMM with random intercepts and random slopes |
| `demo_07_lmm_transform.py` | `sleepstudy.csv` | LMM with log-transform; EMMs and CIs back-transformed to original scale |
| `demo_08_glmm_gamma.py` | `oats.csv` | GLMM with gamma distribution and log link |
| `demo_09_lmm_partial_interaction.py` | `npk.csv` | LMM with three factors and a partial interaction |
| `demo_10_outliers.py` | `stackloss.csv` | Outlier removal: same LM run twice (default vs. pre-fit IQR + post-fit residual removal) to show the effect on fit quality and estimates |
| `demo_11_glmm_binomial.py` | `bacteria.csv` | GLMM with binomial distribution and logit link — binary outcome (bacteria present/absent) with repeated measures per child |
| `demo_12_multi_y.py` | `iris.csv` | Multiple dependent variables + pairwise correlation analysis; `constraints` excludes setosa (categorical filter) |
| `demo_13_lm_vif.py` | `mtcars.csv` | LM with mixed numeric/categorical predictors and automatic VIF |

**Equivalence to classical tests** (demos 1–4 and 5, all datasets perfectly balanced) — see [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md):

- **Demo 1** — identical to an independent-samples t-test (F = t², same df and p-value)
- **Demo 2** — equivalent to a paired t-test; Satterthwaite df ≈ n − 1, slightly more conservative, generalises to missing data
- **Demo 3** — identical to a classical two-way factorial ANOVA with Type III SS (10 observations per cell)
- **Demo 4** — identical to a one-way repeated-measures ANOVA under compound symmetry; LMM generalises to missing time points and unbalanced designs
- **Demo 5** — classical Pearson correlation; additionally computes partial correlations to isolate direct associations when variables co-trend

**Transcending classical tests** (demos 6–11) — see [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md):

- **Demo 6** — no classical equivalent; random slopes capture subject-specific trajectories that RM-ANOVA assumes away
- **Demo 7 vs. 8** — log-transform LMM and gamma GLMM are both valid for right-skewed positive data; gamma is preferred when variance scales with the mean
- **Demo 9** — partial interactions keep the model parsimonious; classical ANOVA always tests all pairwise interactions
- **Demo 10** — data imbalance (unequal cell sizes) can arise by design, through data loss, or through outlier removal; all three cases invalidate classical ANOVA, while GLM fits by maximum likelihood on individual observations and handles any degree of imbalance without modification
- **Demo 11** — binary dependent variables cannot be modelled with gaussian ANOVA; binomial GLMM with logit link models the probability directly and correctly

**Analytical extensions** (demos 12 and 13) — see [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md):

- **Demo 12** — multiple dependent variables in one call; within-model post-hoc is Holm-corrected, cross-variable correction is the researcher's responsibility
- **Demo 13** — VIF flags collinearity among numeric predictors before it distorts coefficient estimates

To regenerate the demo datasets from R (required once before running the demos):

```bash
Rscript export_datasets.R
```

---

## Statistical notes

See [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md) for the rationale behind key design decisions:

- **Effects coding** (`contr.sum`) — why it is used and why treatment coding is problematic
- **Type III sums of squares** — when Type II would differ and why Type III is preferred
- **Satterthwaite df vs. df = Inf** — why GLMMs yield asymptotic tests
- **Post-hoc comparisons with emmeans** — marginal means and Holm correction
- **VIF and multicollinearity** — what VIF measures and when it matters

---

## Known issues and workarounds

- **Random slopes in GLMMs (pymer4 bug):** pymer4 0.9.x crashes when a GLMM contains random slopes (e.g. `(A + B | id)`). kbstatpy works around this automatically via a `GlmerDirect` wrapper that calls lme4 and emmeans directly via rpy2, bypassing pymer4 entirely. No action required from the user. Random slopes in LMMs are unaffected. See `STATISTICAL_NOTES.md` for details.
