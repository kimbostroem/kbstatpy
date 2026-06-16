# Statistical Notes

## Why GLM?

**The classical model and its distributional assumption.** A t-test or ANOVA decomposes each observation into a group mean and a residual:

```
y_ij = μ_i + ε_ij,    ε_ij ~ Normal(0, σ²)
```

Because `μ_i` is a fixed constant, this is equivalent to saying that the response outcomes within each group are normally distributed: `y_ij ~ Normal(μ_i, σ²)`. Both phrasings describe the same assumption — you will encounter both in textbooks. The "residuals" framing is more useful in practice because it is what can actually be checked after fitting. A plain linear model (`lm` / `lmer`) makes exactly the same assumption; it is computationally equivalent to ANOVA, not a relaxation of it.

**The GLM generalisation.** A generalised linear model replaces the fixed gaussian assumption with two explicit choices:

```
y_i ~ p(μ_i, φ)           [response distribution from the exponential family]
g(μ_i) = x_i β            [linear predictor linked to the mean via link function g]
```

The response distribution `p` can be gaussian (recovering the classical case), gamma (positive right-skewed outcomes), binomial (proportions), Poisson (counts), or others. The link function `g` maps the linear predictor — which ranges over all real numbers — to the natural scale of the mean (e.g. the log link ensures positive means for a gamma model). Crucially, the scatter of individual observations around the mean is governed entirely by `p`, not by a normality assumption on the residuals. This makes GLM a strict generalisation: when `p` is gaussian and `g` is the identity, GLM reduces to ordinary linear regression.

**Why this matters in practice.** Real data routinely violate the normality assumption. Reaction times and physical measurements are strictly positive and right-skewed. Proportions are bounded between 0 and 1. Count data are discrete and cannot be negative. Fitting a gaussian model to such outcomes produces biased estimates, incorrect standard errors, and meaningless predictions (e.g. negative reaction times). The principled solution is to choose a distribution that matches the data-generating process, which is exactly what GLM allows.

Beyond the distributional assumption, GLM also removes several other constraints of the classical toolkit:

- **Repeated measures and nested data** — random effects (the "mixed" in GLMM) account for the correlation structure within subjects or clusters, giving correct standard errors without requiring compound symmetry.
- **Unbalanced data** — maximum-likelihood estimation operates on individual observations, not cell means, so missing data, dropout, and outlier removal do not invalidate the analysis.
- **Multiple predictors and interactions** — fixed effects, random slopes, partial interactions, and numeric covariates are all first-class citizens in the same model formula.

Crucially, when the classical assumptions *are* met, GLM gives exactly the same answer as the classical test. The sections below document this equivalence and then demonstrate where GLM goes further.

---

## Table of contents

- [Equivalence to classical tests](#equivalence-to-classical-tests)
  - [Independent-samples t-test (Demo 1)](#independent-samples-t-test-demo-1)
  - [Paired t-test (Demo 2)](#paired-t-test-demo-2)
  - [Two-way ANOVA (Demo 3)](#two-way-anova-demo-3)
  - [Repeated-measures ANOVA (Demo 4)](#repeated-measures-anova-demo-4)
  - [Pearson and partial correlation (Demo 5)](#pearson-and-partial-correlation-demo-5)
- [Transcending classical tests](#transcending-classical-tests)
  - [Random slopes — subject-specific trajectories (Demo 6)](#random-slopes-subject-specific-trajectories-demo-6)
  - [Log-transform LMM vs. gamma GLMM (Demos 7 and 8)](#log-transform-lmm-vs-gamma-glmm-demos-7-and-8)
  - [Partial interactions (Demo 9)](#partial-interactions-demo-9)
  - [Outlier removal, unbalanced designs and data loss (Demo 10)](#outlier-removal-unbalanced-designs-and-data-loss-demo-10)
- [Analytical extensions](#analytical-extensions)
  - [Multiple dependent variables (Demo 11)](#multiple-dependent-variables-demo-11)
  - [Multicollinearity diagnostics — VIF (Demo 12)](#multicollinearity-diagnostics-vif-demo-12)
  - [Contrast coding: effects coding (`contr.sum`)](#contrast-coding-effects-coding-contrsum)
  - [Sums of squares: Type III](#sums-of-squares-type-iii)
  - [Degrees of freedom: Satterthwaite approximation and `df = Inf`](#degrees-of-freedom-satterthwaite-approximation-and-df-inf)
  - [Post-hoc comparisons: `emmeans`](#post-hoc-comparisons-emmeans)
  - [VIF and multicollinearity](#vif-and-multicollinearity)
- [Technical aspects](#technical-aspects)
  - [Data filtering: `constraints`](#data-filtering-constraints)
  - [Variable display labels: `rename`](#variable-display-labels-rename)
  - [Data plots: violin + jitter scatter](#data-plots-violin-jitter-scatter)
  - [Back-transformation of EMM and CI](#back-transformation-of-emm-and-ci)
  - [Random slopes in GLMMs — pymer4 bug and workaround](#random-slopes-in-glmms-pymer4-bug-and-workaround)

---

## Equivalence to classical tests

kbstatpy fits all models through the LMM/GLMM framework, but for simple designs the results reduce exactly (or nearly exactly) to their classical counterparts.

### Independent-samples t-test (Demo 1)

`lm(y ~ group)` with effects coding and two levels is algebraically identical to an independent-samples t-test. The F-statistic from the ANOVA table equals t², and the p-value is the same. Degrees of freedom are n − 2 in both cases.

### Paired t-test (Demo 2)

`lmer(y ~ group + (1 | id))` is equivalent to a paired t-test for balanced, complete data, but not algebraically identical. The paired t-test operates directly on pairwise differences (df = n − 1 = 9 for the sleep data). The LMM estimates a random-intercept variance and uses Satterthwaite degrees of freedom, which will be close but not necessarily integer. For balanced data the p-values are very similar; the LMM is slightly more conservative. The LMM is strictly more general: it handles missing observations and unequal group sizes without modification.

### Two-way ANOVA (Demo 3)

`lm(y ~ A * B)` with effects coding and Type III sums of squares is exactly a classical two-way factorial ANOVA, provided the design is balanced (equal n per cell). The `ToothGrowth` dataset used in Demo 3 has exactly 10 observations per cell, so the results are numerically identical to a classical two-way ANOVA.

For unbalanced designs, Type III SS with effects coding still gives well-defined, interpretable tests — classical ANOVA software often struggles or produces ambiguous results in this case.

### Repeated-measures ANOVA (Demo 4)

`lmer(y ~ time + (1 | subject))` is equivalent to a one-way repeated-measures ANOVA when:
1. The design is balanced (same number of observations per subject per condition), and
2. The compound symmetry assumption holds (equal variances and equal pairwise correlations across all time points).

Both conditions are met in the `sleepstudy` data used in Demo 4 (5 observations per subject per period, two periods), so the F-statistic and p-value match a classical RM-ANOVA exactly. The LMM again generalises gracefully: it handles missing time points, unbalanced designs, and more complex covariance structures (random slopes, crossed random effects) that are outside the scope of classical RM-ANOVA.

### Pearson and partial correlation (Demo 5)

Pearson r between two variables X and Y captures their total linear association, including any portion mediated by or confounded with a third variable Z. This is a classical analysis available in any statistics package.

When three or more variables are correlated simultaneously, kbstatpy additionally computes **partial correlations** — the Pearson r between the residuals of regressing X on all other variables and the residuals of regressing Y on all other variables. This isolates the direct association between X and Y that cannot be explained by the remaining variables, and is particularly valuable when variables co-trend over time or share a common driver (as in the Longley macroeconomic data used in Demo 5).

---

## Transcending classical tests

From Demo 5 onwards the models go beyond what classical ANOVA and t-tests can express. The linear mixed model framework — and its generalisation to non-Gaussian outcomes — offers a unified language for designs that classical methods either cannot handle at all or handle only through awkward workarounds. The subsections below highlight what each demo achieves that would be impossible or impractical with classical tools.

### Random slopes — subject-specific trajectories (Demo 6)

Adding random slopes (`(1 + time | subject)`) allows each subject's response to change at a different rate across time, not just shift vertically. This has no classical equivalent: RM-ANOVA assumes a single fixed time effect shared by all subjects. When individual trajectories differ substantially — as in the sleep deprivation data, where some subjects are much more sensitive to sleep loss than others — a random-slopes model is more realistic and yields better-calibrated estimates and standard errors.

The cost is additional parameters (one variance and one covariance per random-effect term), which requires sufficient subjects (typically ≥ 20) for stable estimation.

### Log-transform LMM vs. gamma GLMM (Demos 7 and 8)

Both Demo 7 (log-transformed Gaussian LMM) and Demo 8 (gamma GLMM with log link) are appropriate for positive, right-skewed outcomes. They differ in what they assume about the error structure:

- **Log-transform LMM** (Demo 7): takes `log(y)` before fitting a Gaussian model. Assumes the *log-scale* residuals are normally distributed with constant variance. Back-transforms EMMs and CIs via `exp()`.
- **Gamma GLMM** (Demo 8): models `y` directly with a gamma distribution and log link. Assumes the *response-scale* variance is proportional to the mean squared (coefficient of variation is constant). More natural for data with multiplicative noise.

In practice, both approaches often give similar conclusions. The gamma GLMM is preferred when the variance–mean relationship is clearly multiplicative; the log-transform LMM is simpler to explain and diagnose. If log-transformed residuals look Gaussian and homoscedastic, either is defensible.

### Partial interactions (Demo 9)

Classical two-way ANOVA always tests all pairwise interactions simultaneously. When a design has three or more factors, it is often scientifically meaningful to include only a subset of interactions — for example, testing N×P but not N×K. In standard ANOVA software this requires manual contrast specification; in kbstatpy it is expressed directly via `options.interaction`.

Including only the theoretically motivated interactions keeps the model parsimonious, preserves degrees of freedom, and avoids inflating the multiple-comparison burden with interactions that are not of interest.

### Outlier removal, unbalanced designs and data loss (Demo 10)

**What "unbalanced" means.** A dataset is *balanced* when every cell of the factorial design contains the same number of observations — for example, exactly 10 measurements for each combination of group and time point. Classical ANOVA was derived for this special case: equal cell sizes make the group means orthogonal, and the total variance partitions cleanly and unambiguously into factor effects. As soon as cell sizes differ, the group means are no longer independent, the Type I and Type III sums of squares diverge, and standard ANOVA formulas produce incorrect F-statistics.

**Sources of imbalance.** Cell-size inequality can arise in three distinct ways:

- **Unbalanced design**: the study was intentionally planned with unequal group sizes — for example, because one condition is harder or more expensive to recruit for, or because a control group is deliberately oversampled to increase power.
- **Data loss**: a nominally balanced protocol loses observations during data collection — through participant dropout, equipment failure, recording errors, or missing sessions. The design was balanced on paper; the data are not.
- **Outlier removal**: extreme observations are excluded after collection. Even a single removal from one cell is enough to break the balance assumptions that ANOVA requires.

All three produce the same consequence for classical ANOVA. The distinction matters because data loss and outlier removal can introduce imbalance without any deliberate choice in the study design, and researchers may not recognise that their previously balanced dataset has become unbalanced.

**GLM handles imbalance without modification.** GLM estimates model parameters directly by maximum likelihood, fitting the model to individual observations rather than to cell means. The likelihood function is well-defined for any pattern of cell sizes — balanced, partially unbalanced, or severely unbalanced — so no special treatment is needed. There is no requirement for imputation, no correction factor, and no need to drop entire groups to restore balance. kbstatpy exploits this directly: after outlier removal, the model is simply refit on whatever observations remain, and the reported estimates, standard errors, and p-values are correct regardless of the resulting imbalance.

**Two-pass outlier removal in kbstatpy.** Outlier removal should always be principled, not automatic. kbstatpy provides a two-pass strategy controlled by `remove_outliers_prefit` and `remove_outliers_postfit`:

1. **Pre-fit IQR pass** (`remove_outliers_prefit`): flags observations more than 1.5 × IQR beyond Q1 or Q3 within each group. This uses only the raw data, requires no model, and protects the initial fit from being distorted by extreme values.
2. **Post-fit residual pass** (`remove_outliers_postfit`): flags observations with Pearson residual z > 3 after the first fit, then refits. These are points that look unremarkable in isolation but deviate strongly from the model's predictions — a subtler form of influence.

A useful sanity check after outlier removal is whether AIC decreased. A large drop (as in Demo 10: 108.8 → 74.5) confirms the removed observations were genuinely influential. A negligible drop suggests the flagged points were not actually distorting the model and removal was unnecessary.

Removed observations are retained in the dataset with `is_outlier = True` and shown as distinct markers in the data plot, making the exclusion transparent and reproducible.

---

## Analytical extensions

Capabilities that run alongside the core modelling pipeline, and the statistical rationale behind kbstatpy's key modelling choices.

### Multiple dependent variables (Demo 11)

Running the same model independently for each of k dependent variables is a common workflow in multivariate research (e.g. analysing all limb segments, all biomarkers, or all performance metrics in one call). kbstatpy handles this via `options.y` as a list, saving results into per-variable subdirectories automatically.

One caveat: testing k outcomes multiplies the family-wise type I error rate. kbstatpy does not automatically apply a cross-variable correction (e.g. Bonferroni across variables) because the appropriate strategy depends on the research question — confirmatory analyses with pre-registered hypotheses call for stricter correction than exploratory screening. Within each model, post-hoc p-values are Holm-corrected across pairwise comparisons.

### Multicollinearity diagnostics — VIF (Demo 12)

Demo 12 illustrates the typical situation in biomechanical and physiological research: a categorical predictor (number of cylinders) and two correlated continuous covariates (horsepower, weight). The categorical predictor appears in the violin plot; the numeric covariates are checked for collinearity via VIF and visualised in the correlation scatter grid with VIF values on the diagonal.

Detecting collinearity before interpreting individual predictor effects is essential — highly correlated predictors inflate standard errors and destabilise coefficient estimates even when no formal assumption is violated. See the post-hoc section for the mathematical definition and thresholds.

### Contrast coding: effects coding (`contr.sum`)

Categorical predictors are coded using **effects coding** (sum-to-zero contrasts, `contr.sum` in R).

With effects coding each coefficient represents a deviation from the **grand mean** across all levels. The alternative — treatment coding (`contr.treatment`, R's default) — codes each level as a deviation from a chosen reference level, making all coefficients dependent on that arbitrary choice.

Effects coding is a prerequisite for Type III sums of squares to be well-defined (see section 3.4). With treatment coding, Type III main-effect tests change depending on which level is chosen as the reference — a known pathology. With effects coding the tests are invariant.

### Sums of squares: Type III

The ANOVA table uses **Type III sums of squares**. Each effect is tested conditional on all other effects in the model, including higher-order interactions.

**Type II** tests each main effect after all other main effects but ignoring interactions that contain it. This gives slightly more power when interactions are truly absent, but it becomes inconsistent when interactions are present: the main-effect test no longer corresponds to a meaningful hypothesis.

**Type III** is the correct choice whenever interactions are included in the model (which is the default in kbstatpy). If a model has no interactions, Types II and III give identical results with effects coding and balanced data — so there is no scenario where switching to Type II would be an improvement.

Type III + effects coding is a coherent, principled pair. MATLAB's `fitglme` uses the same combination.

> **Caution:** when an interaction is significant, marginal main-effect estimates from `emmeans` average over the other factor. Main effects should be interpreted cautiously in that case — the interaction result is the primary finding.

### Degrees of freedom: Satterthwaite approximation and `df = Inf`

#### Linear mixed models (LMMs, `distribution = 'normal'`)

For LMMs the **Satterthwaite approximation** is used to estimate the denominator degrees of freedom for each F-test. This accounts for the unbalanced random-effects structure and yields finite, data-adaptive df values. It is implemented via R's `lmerTest` and `emmeans` packages.

#### Generalised linear mixed models (GLMMs, any other distribution)

The Satterthwaite approximation is **only defined for LMMs**. It relies on the model's Hessian being quadratic in the variance components — an assumption that does not hold for non-Gaussian likelihoods. For GLMMs, `emmeans` therefore falls back to **asymptotic (Wald) inference**, which yields `df = Inf` and chi-square tests.

This is mathematically correct behaviour, not a software error.

For comparison: MATLAB's `fitglme` also does not support Satterthwaite for GLMMs. Instead it uses the finite approximation `df2 = n − p`, where `n` is the number of observations and `p` is the number of fixed-effect columns. Both are approximations; the asymptotic `df = Inf` method used in kbstatpy is the more principled one because it does not pretend that a GLMM likelihood is quadratic.

### Post-hoc comparisons: `emmeans`

Post-hoc pairwise comparisons are computed via R's `emmeans` package (estimated marginal means). This correctly averages over the random-effects structure and accounts for unbalanced designs.

P-value adjustment defaults to **Holm's step-down method** (`posthoc_correction = 'holm'`), which controls the family-wise error rate and is uniformly more powerful than Bonferroni.

For LMMs, `emmeans` reports t-ratios with Satterthwaite degrees of freedom. For GLMMs it reports z-ratios (asymptotic), which kbstatpy detects automatically.

### VIF and multicollinearity

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

## Technical aspects

Implementation details and design decisions behind kbstatpy's data handling, visualisation, and output.

### Data filtering: `constraints`

`options.constraints` accepts a Python expression string that is passed directly to `pandas.DataFrame.query()`. The filter is applied before model fitting and before any correlation or VIF analysis — it is equivalent to manually subsetting the data before passing it to kbstatpy.

```python
options.constraints = 'Year > 1950'                  # numeric comparison
options.constraints = 'Species != "setosa"'           # categorical exclusion
options.constraints = 'Year > 1950 & GNP < 500'      # combined condition
```

Supported operators: `==` `!=` `<` `>` `<=` `>=`; combine with `&` (and) / `|` (or).

When a categorical column is filtered, kbstatpy removes the excluded level from the column's `Categorical` dtype (via `cat.remove_unused_categories()`). This prevents the excluded level from appearing as a phantom tick on plot axes or as a spurious empty group in post-hoc tables.

### Variable display labels: `rename`

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

### Data plots: violin + jitter scatter

The data plot (`DataPlots.pdf/.png`) renders four visual layers per panel:

1. **Violin** — kernel density estimate of the marginal distribution, drawn with `seaborn.violinplot`. `cut=0.3` extends the KDE slightly beyond the data range to avoid hard edges. Alpha is set to 0.5 to keep the violin from obscuring the individual points behind it.

2. **Jittered scatter** — each raw observation is placed at its y-value with a random horizontal offset. The offset is drawn from a uniform distribution whose half-width is 75 % of the violin's local half-width at that y-value, keeping every dot visually inside the violin body. The random seed is fixed (`numpy.random.default_rng(0)`) for reproducibility.

   > Seaborn's own `swarmplot` was not used here because seaborn computes beeswarm positions lazily on every redraw event (`tight_layout`, `show`, `savefig`). Any post-hoc modification of dot positions via `set_offsets()` is silently overwritten before the figure is saved. The manual scatter approach avoids this entirely.

3. **95 % CI bar** — a thick vertical line (linewidth 4) from the lower to the upper 95 % confidence limit of the model's estimated marginal mean, drawn in dark grey (`'0.2'`). CIs come from `emmeans` and are always on the original response scale (see the back-transformation section). If no model has been fitted (correlation-only runs), this falls back to the raw IQR.

4. **Estimated marginal mean (EMM)** — a white dot with a dark grey edge, placed at the model's back-transformed EMM. For simple models this is close to the arithmetic mean; for GLMMs or transformed models it reflects the model-estimated central tendency on the original scale.

Significance brackets are drawn above the panel using the post-hoc p-values (Holm-corrected).

### Back-transformation of EMM and CI

Estimated marginal means and their confidence intervals are always reported and plotted on the **original response scale**, regardless of model type.

Two separate `emmeans` calls are made internally:

1. **Link-scale** (`type` default) — feeds `pairs()` to produce pairwise contrasts. On this scale the test statistics (t/z ratio), degrees of freedom, and p-values are correctly computed. For a GLMM with log link this is the log scale; for an LMM with `y_transform = 'log(y)'` this is the log-transformed scale.

2. **Response-scale** (`type = 'response'`) — feeds the EMM display columns in the posthoc table (`emm_1`, `emm_2`) and the CI bar / EMM dot in the data plot. For GLMMs, R's emmeans applies the inverse link function automatically. For LMMs with `y_transform`, the Python-side `_inverse_fn` (derived symbolically via sympy) is applied on top.

This separation is necessary because requesting `type = 'response'` from `pairs()` returns ratios (multiplicative contrasts) with integer-coded contrast labels, breaking the named-level matching used to build the posthoc table.

**What this means in practice:**

| Model type | EMM display | CI display | t/z, p |
|---|---|---|---|
| LMM, no transform | raw scale | raw scale | linear scale |
| LMM + `y_transform = 'log(y)'` | original scale (exp applied) | original scale | log scale |
| GLMM, log link | original scale (exp applied by R) | original scale | log scale |
| GLMM, logit link | original scale (probability) | original scale | logit scale |

### Random slopes in GLMMs — pymer4 bug and workaround

pymer4 0.9.x crashes when a GLMM contains random slopes (e.g. `(A + B | id)`). The bug is in pymer4's `broom.tidy()` result-parsing layer, which constructs a `data.frame` from two objects with mismatched row counts when more than one random-effect term is present per grouping factor. lme4 itself fits the model correctly — the failure is entirely in the Python post-processing step.

**Workaround:** kbstatpy includes a `GlmerDirect` class (`kbstatpy/_glmer_direct.py`) that calls lme4, emmeans, and broom directly via rpy2, bypassing pymer4's broken parsing layer. When `fit()` detects random slopes in a GLMM formula, it automatically routes to `GlmerDirect` instead of pymer4's `Glmer`. The rest of the pipeline (ANOVA, post-hoc, plots, output files) is unaffected — the two backends expose the same interface.

Random slopes in LMMs (`distribution = 'normal'`) are not affected by this bug and continue to use pymer4 directly.
