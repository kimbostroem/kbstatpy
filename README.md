# kbstatpy

A Python library for generalized linear mixed model (GLMM) analysis with post-hoc pairwise comparisons. Modelled after the MATLAB `kbstat` library.

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
1. Installs all required Python packages (`pymer4`, `rpy2`, `polars`, `pandas`, …)
2. Installs all required R packages (`lme4`, `lmerTest`, `emmeans`, …)
3. On macOS: automatically fixes the `rpy2` / R version symlink if needed

---

## Quick start

```python
from kbstatpy import Kbstat, KbstatOptions

options = KbstatOptions()
options.in_file    = 'data/mydata.csv'       # path to your data file (.csv or .xlsx)
options.out_dir    = 'results/myanalysis'    # output folder (created if it doesn't exist)
options.y          = 'ResponseVariable'      # name of the dependent variable column
options.x          = ['FactorA', 'FactorB']  # fixed-effect factors
options.id         = 'Subject'               # random-effect grouping variable
options.distribution = 'gamma'              # see distributions below
options.link       = 'log'

kb = Kbstat(options)
kb.run()   # fit → anova → posthoc → save
```

`run()` is the one-shot pipeline. You can also call each step individually:

```python
kb.fit()      # fit the LMM / GLMM
kb.anova()    # compute Type III ANOVA table
kb.posthoc()  # pairwise comparisons via emmeans
kb.save()     # write output files to out_dir
```

---

## Options reference

| Option | Type | Default | Description |
|---|---|---|---|
| `in_file` | str | `''` | Path to input data (.csv or .xlsx) |
| `out_dir` | str | `''` | Output directory for result files |
| `formula` | str | `''` | Full Wilkinson formula (overrides `y`, `x`, `id`) |
| `y` | str | `''` | Dependent variable column name |
| `x` | list | `[]` | Fixed-effect factor column names |
| `id` | str | `''` | Random-effect grouping variable (e.g. subject ID) |
| `slope` | list | `[]` | Variables with random slopes (e.g. `['A', 'B']` → `(1 + A + B \| id)`) |
| `distribution` | str | `'normal'` | Response distribution (see below) |
| `link` | str | `'auto'` | Link function (`'auto'`, `'log'`, `'logit'`, …) |
| `fit_method` | str | `'MPL'` | Fit method passed to lme4 |
| `posthoc_method` | str | `'emm'` | Post-hoc method (currently `'emm'` for emmeans) |
| `posthoc_correction` | str | `'holm'` | P-value correction (`'holm'`, `'bonferroni'`, `'fdr'`, …) |

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

## Output files

All files are written to `out_dir`:

| File | Contents |
|---|---|
| `Anova.xlsx` | Type III ANOVA table with F, df, p, partial η², SMD, effect size label |
| `Posthoc.xlsx` | Pairwise comparisons from emmeans with p-value correction |
| `Statistics.xlsx` | Descriptive statistics per group (N, mean, SD, SE, median, IQR, 95% CI) |
| `Data.csv` | Copy of the input data as loaded |
| `Summary.txt` | Human-readable summary: formula, model info, fit stats, ANOVA, post-hoc, and explanatory notes |

---

## Demo scripts

Two worked examples are included in the `demo/` folder:

| Script | Dataset | Description |
|---|---|---|
| `demo_reaction_time.py` | `reaction_time.csv` | Reaction times with two within-subject factors (A, B); gamma / log link |
| `demo_chocolate.py` | `Chocolate.csv` | Jump distances with two between-subject factors (Chocolate, Gender); gamma / log link |

Run a demo:

```bash
cd kbstatpy
python3 demo/demo_chocolate.py
```

Results are written to `demo/Results_chocolate/` and `demo/Results_rt/rt/` respectively.

---

## Statistical notes

See [STATISTICAL_NOTES.md](STATISTICAL_NOTES.md) for the rationale behind key design decisions:

- **Effects coding** (`contr.sum`) — why it is used and why treatment coding is problematic
- **Type III sums of squares** — when Type II would differ and why Type III is preferred
- **Satterthwaite df vs. df = Inf** — why GLMMs yield asymptotic tests and how this compares to MATLAB's `fitglme`
- **Post-hoc comparisons with emmeans** — marginal means and Holm correction

---

## Known issues and workarounds

- **Random slopes in GLMMs (pymer4 bug):** pymer4 0.9.x crashes when a GLMM contains random slopes (e.g. `(A + B | id)`). The bug is in pymer4's result-parsing layer; lme4 itself fits the model correctly. kbstatpy works around this automatically: when random slopes are explicitly defined via `options.slope` or detected in an explicit formula string, it routes to a custom `GlmerDirect` wrapper that calls lme4 and emmeans directly via rpy2, bypassing pymer4 entirely. No action required from the user. Random slopes in LMMs (`distribution = 'normal'`) are unaffected. See `STATISTICAL_NOTES.md` for details.
