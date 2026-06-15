# Statistical Notes

Design decisions and their rationale for the kbstatpy library.

---

## Contrast coding: effects coding (`contr.sum`)

Categorical predictors are coded using **effects coding** (sum-to-zero contrasts, `contr.sum` in R).

With effects coding each coefficient represents a deviation from the **grand mean** across all levels. The alternative — treatment coding (`contr.treatment`, R's default) — codes each level as a deviation from a chosen reference level, making all coefficients dependent on that arbitrary choice.

Effects coding is a prerequisite for Type III sums of squares to be well-defined (see below). With treatment coding, Type III main-effect tests change depending on which level is chosen as the reference — a known pathology. With effects coding the tests are invariant.

---

## Sums of squares: Type III

The ANOVA table uses **Type III sums of squares**. Each effect is tested conditional on all other effects in the model, including higher-order interactions.

**Type II** tests each main effect after all other main effects but ignoring interactions that contain it. This gives slightly more power when interactions are truly absent, but it becomes inconsistent when interactions are present: the main-effect test no longer corresponds to a meaningful hypothesis.

**Type III** is the correct choice whenever interactions are included in the model (which is the default in kbstatpy). If a model has no interactions, Types II and III give identical results with effects coding and balanced data — so there is no scenario where switching to Type II would be an improvement.

Type III + effects coding is a coherent, principled pair. MATLAB's `fitglme` uses the same combination.

> **Caution:** when an interaction is significant, marginal main-effect estimates from `emmeans` average over the other factor. Main effects should be interpreted cautiously in that case — the interaction result is the primary finding.

---

## Degrees of freedom: Satterthwaite approximation and `df = Inf`

### Linear mixed models (LMMs, `distribution = 'normal'`)

For LMMs the **Satterthwaite approximation** is used to estimate the denominator degrees of freedom for each F-test. This accounts for the unbalanced random-effects structure and yields finite, data-adaptive df values. It is implemented via R's `lmerTest` and `emmeans` packages.

### Generalised linear mixed models (GLMMs, any other distribution)

The Satterthwaite approximation is **only defined for LMMs**. It relies on the model's Hessian being quadratic in the variance components — an assumption that does not hold for non-Gaussian likelihoods. For GLMMs, `emmeans` therefore falls back to **asymptotic (Wald) inference**, which yields `df = Inf` and chi-square tests.

This is mathematically correct behaviour, not a software error.

For comparison: MATLAB's `fitglme` also does not support Satterthwaite for GLMMs. Instead it uses the finite approximation `df2 = n − p`, where `n` is the number of observations and `p` is the number of fixed-effect columns. Both are approximations; the asymptotic `df = Inf` method used in kbstatpy is the more principled one because it does not pretend that a GLMM likelihood is quadratic.

---

## Random slopes in GLMMs — pymer4 bug and workaround

pymer4 0.9.x crashes when a GLMM contains random slopes (e.g. `(A + B | id)`). The bug is in pymer4's `broom.tidy()` result-parsing layer, which constructs a `data.frame` from two objects with mismatched row counts when more than one random-effect term is present per grouping factor. lme4 itself fits the model correctly — the failure is entirely in the Python post-processing step.

**Workaround:** kbstatpy includes a `GlmerDirect` class (`kbstatpy/_glmer_direct.py`) that calls lme4, emmeans, and broom directly via rpy2, bypassing pymer4's broken parsing layer. When `fit()` detects random slopes in a GLMM formula, it automatically routes to `GlmerDirect` instead of pymer4's `Glmer`. The rest of the pipeline (ANOVA, post-hoc, plots, output files) is unaffected — the two backends expose the same interface.

Random slopes in LMMs (`distribution = 'normal'`) are not affected by this bug and continue to use pymer4 directly.

---

## Post-hoc comparisons: `emmeans`

Post-hoc pairwise comparisons are computed via R's `emmeans` package (estimated marginal means). This correctly averages over the random-effects structure and accounts for unbalanced designs.

P-value adjustment defaults to **Holm's step-down method** (`posthoc_correction = 'holm'`), which controls the family-wise error rate and is uniformly more powerful than Bonferroni.

For LMMs, `emmeans` reports t-ratios with Satterthwaite degrees of freedom. For GLMMs it reports z-ratios (asymptotic), which kbstatpy detects automatically.

---

## VIF and multicollinearity

**Variance Inflation Factor (VIF)** measures how much the variance of a regression coefficient is inflated due to collinearity with other predictors. For predictor *j*:

```
VIF_j = 1 / (1 − R²_j)
```

where R²_j is the coefficient of determination of a linear regression of predictor *j* on all remaining predictors. A VIF of 1 means no collinearity; values above 5 are generally considered concerning, and values above 10 indicate severe collinearity.

**Why it matters:** highly correlated independent variables do not violate any formal assumption of linear regression, but they do inflate standard errors, widen confidence intervals, and destabilise coefficient estimates — making it hard to interpret individual predictor effects. VIF flags this before it becomes a problem.

**When kbstatpy computes VIF:** automatically whenever `options.x` contains numeric (continuous) variables. VIF is computed for all numeric variables in `options.x` + `options.covariate` jointly. Categorical predictors are excluded from the VIF calculation because collinearity between a categorical and a continuous variable is better assessed via other means (e.g. ANOVA on the continuous variable by group).

**Thresholds used:**

| VIF | Verdict |
|---|---|
| < 5 | OK |
| 5 – 10 | concerning |
| > 10 | severe |

Results are printed to the console and saved to `VIF.xlsx`. A visual summary is also embedded in the correlation scatter grid when `options.correlation` overlaps with the numeric predictors.

---

## Data filtering: `constraints`

`options.constraints` accepts a Python expression string that is passed directly to `pandas.DataFrame.query()`. The filter is applied before model fitting and before any correlation or VIF analysis — it is equivalent to manually subsetting the data before passing it to kbstatpy.

```python
options.constraints = 'Year > 1950'                  # numeric comparison
options.constraints = 'Species != "setosa"'           # categorical exclusion
options.constraints = 'Year > 1950 & GNP < 500'      # combined condition
```

Supported operators: `==` `!=` `<` `>` `<=` `>=`; combine with `&` (and) / `|` (or).

When a categorical column is filtered, kbstatpy removes the excluded level from the column's `Categorical` dtype (via `cat.remove_unused_categories()`). This prevents the excluded level from appearing as a phantom tick on plot axes or as a spurious empty group in post-hoc tables.

---

## Variable display labels: `rename`

`options.rename` provides two related but distinct operations in a single option:

1. **Level rename** — replaces a factor level value before the model is fitted:
   ```python
   options.rename = 'supp: OJ -> orange_juice, VC -> vitamin_c'
   ```
   The substitution happens in-place in the data so that the model, contrasts, and all table entries see the new value.

2. **Variable display label** — maps an internal column name to a human-readable label used in plot axes and table headers:
   ```python
   options.rename = 'mpg -> Consumption; cyl -> Cylinders'
   ```
   The internal column name is unchanged; only the display output is affected.

Both can be combined in the same string. The separator between variables is `;`; a `->` without a preceding `:` signals a variable label; a `variable: old -> new` signals a level rename. Numbers in level names are preserved as-is.

Display labels propagate to child `Kbstat` instances in multi-y runs, so a single `rename` entry in the parent covers all per-variable subdirectory outputs.

---

## Data plots: violin + jitter scatter

The data plot (`DataPlots.pdf/.png`) renders four visual layers per panel:

1. **Violin** — kernel density estimate of the marginal distribution, drawn with `seaborn.violinplot`. `cut=0.3` extends the KDE slightly beyond the data range to avoid hard edges. Alpha is set to 0.5 to keep the violin from obscuring the individual points behind it.

2. **Jittered scatter** — each raw observation is placed at its y-value with a random horizontal offset. The offset is drawn from a uniform distribution whose half-width is 75 % of the violin's local half-width at that y-value, keeping every dot visually inside the violin body. The random seed is fixed (`numpy.random.default_rng(0)`) for reproducibility.

   > Seaborn's own `swarmplot` was not used here because seaborn computes beeswarm positions lazily on every redraw event (`tight_layout`, `show`, `savefig`). Any post-hoc modification of dot positions via `set_offsets()` is silently overwritten before the figure is saved. The manual scatter approach avoids this entirely.

3. **IQR bar** — a thick vertical line (linewidth 4) from Q25 to Q75 of the raw data, drawn in dark grey (`'0.2'`).

4. **Estimated marginal mean (EMM)** — a white dot with a dark grey edge, placed at the model's back-transformed EMM. For simple models this is close to the arithmetic mean; for GLMMs or transformed models it reflects the model-estimated central tendency on the original scale.

Significance brackets are drawn above the panel using the post-hoc p-values (Holm-corrected).
