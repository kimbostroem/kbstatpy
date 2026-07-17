# Statistical Notes

## Table of contents

- [Why linear mixed models — and why GLM?](#why-linear-mixed-models-and-why-glm)
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
  - [Binomial GLMM — binary outcomes (Demo 11)](#binomial-glmm-binary-outcomes-demo-11)
- [Analytical extensions](#analytical-extensions)
  - [Multiple dependent variables (Demo 12)](#multiple-dependent-variables-demo-12)
  - [Family-wise correction across dependent variables (Demo 13)](#family-wise-correction-across-dependent-variables-demo-13)
  - [Multicollinearity diagnostics — VIF (Demo 14)](#multicollinearity-diagnostics-vif-demo-14)
  - [Level-wise profile analysis (Demo 16)](#level-wise-profile-analysis-demo-16)
  - [Contrast coding: effects coding (`contr.sum`)](#contrast-coding-effects-coding-contrsum)
  - [Sums of squares: Type III](#sums-of-squares-type-iii)
  - [Degrees of freedom: Kenward-Roger and Satterthwaite](#degrees-of-freedom-kenward-roger-and-satterthwaite)
  - [Post-hoc comparisons: `emmeans`](#post-hoc-comparisons-emmeans)
  - [Why estimated marginal means?](#why-estimated-marginal-means)
  - [VIF and multicollinearity](#vif-and-multicollinearity)
- [Technical aspects](#technical-aspects)
  - [Long vs. wide data format](#long-vs-wide-data-format)
  - [Wilkinson notation for model formulae](#wilkinson-notation-for-model-formulae)
  - [Data filtering: `constraints`](#data-filtering-constraints)
  - [Variable display labels: `rename`](#variable-display-labels-rename)
  - [Data plots: violin or bar plot](#data-plots-violin-or-bar-plot)
  - [Diagnostic plots](#diagnostic-plots)
  - [Back-transformation of EMM and CI](#back-transformation-of-emm-and-ci)
  - [Random slopes in GLMMs — pymer4 bug and workaround](#random-slopes-in-glmms-pymer4-bug-and-workaround)

---

## Why linear mixed models — and why GLM?

The classical statistical toolkit — t-tests, one-way ANOVA, repeated-measures ANOVA — was designed for narrow, idealised conditions: a flat, non-nested fixed-effects structure, perfectly balanced cell sizes, independent observations, and normally distributed response outcomes within each group. Real experimental data routinely violate several of these conditions at once, motivating two successive generalisations.

**From classical tests to linear models (LM / LMM).** A t-test or ANOVA decomposes each observation into a group mean and a residual:

```
y_ij = μ_i + ε_ij,    ε_ij ~ Normal(0, σ²)
```

Because `μ_i` is a fixed constant, this is equivalent to saying that the response outcomes within each group are normally distributed: `y_ij ~ Normal(μ_i, σ²)`. Both phrasings describe the same assumption — you will encounter both in textbooks. The "residuals" framing is more useful in practice because it is what can actually be checked after fitting.

A linear model (`lm`) and its mixed-model extension (`lmer`) make the same distributional assumption, but remove several structural constraints of the classical tests:

- **Unbalanced data** — maximum-likelihood estimation operates on individual observations, not cell means, so unequal cell sizes do not invalidate the analysis the way they do for classical ANOVA. Missing data and dropout are handled correctly *provided they are missing at random* (MAR); data missing for reasons related to the unobserved outcome (MNAR) bias the estimates regardless of how the model is fit.
- **Multiple predictors and interactions** — fixed effects, partial interactions, and numeric covariates are all accommodated in the same formula.
- **Repeated measures and nested data** — the "mixed" in LMM refers to the combination of *fixed effects* (the population-level factor effects of scientific interest, shared across all observations) and *random effects* (individual-level deviations, e.g. each subject's personal baseline or slope). Random effects account for the correlation structure within subjects or clusters, giving correct standard errors without requiring compound symmetry.

**From LMM to GLMM — the generalisation step.** The specific contribution of the *generalised* linear model is the ability to replace the fixed gaussian assumption with an explicit choice of response distribution and link function:

```
y_i ~ p(μ_i, φ)           [response distribution from the exponential family]
g(μ_i) = x_i β + z_i b   [linear predictor (fixed + random) linked to the mean via g]
```

The response distribution `p` can be gaussian (recovering the LMM case), gamma (positive right-skewed outcomes), binomial (binary or proportion outcomes), Poisson (counts), or others. The link function `g` maps the linear predictor — which ranges over all real numbers — to the natural scale of the mean (e.g. the log link constrains the mean to be positive for a gamma model; the logit link maps the predictor to a probability between 0 and 1 for a binomial model). When `p` is gaussian and `g` is the identity, GLMM reduces exactly to LMM.

Binary and other discrete outcomes deserve special mention. A binary dependent variable has a mean that is a probability, bounded strictly between 0 and 1 — something a gaussian model cannot respect. Classical t-tests and ANOVA have no principled solution for this case, whereas a binomial GLMM with logit link handles it directly and correctly (see [Demo 11](#binomial-glmm-binary-outcomes-demo-11) for the full argument).

**Why the choice of distribution matters.** Real data routinely violate the normality assumption. Reaction times and many physical measurements are strictly positive and right-skewed. Proportions are bounded between 0 and 1. Count data are discrete and cannot be negative. Fitting a gaussian model to such outcomes produces biased estimates, incorrect standard errors, and meaningless predictions (e.g. negative reaction times). The principled solution is to choose a distribution that matches the data-generating process — which is exactly what GLMM allows and what classical tests and plain LMMs cannot do.

When the classical assumptions *are* met, the full GLMM reduces to its classical equivalent and gives the same answer. The sections below document this equivalence and then demonstrate where the generalisation becomes necessary.

---

## Equivalence to classical tests

kbstatpy fits all models through the LMM/GLMM framework, but for simple designs the results reduce exactly (or nearly exactly) to their classical counterparts.

### Independent-samples t-test (Demo 1)

`lm(y ~ group)` with effects coding and two levels is algebraically identical to an independent-samples t-test — and unlike the ANOVA equivalence in Demo 3, this holds regardless of whether the two groups are balanced. The Student's t-test uses a pooled variance and a standard error that scales with `√(1/n₁ + 1/n₂)`, which naturally accommodates unequal group sizes; `lm` does exactly the same. The F-statistic from the ANOVA table equals t², and the p-value is the same. Degrees of freedom are n − 2 in both cases.

### Paired t-test (Demo 2)

`lmer(y ~ group + (1 | id))` is algebraically identical to a paired t-test for balanced data: same point estimate, same standard error, df = n − 1 = 9, and the same p-value. The LMM arrives there differently — by estimating a random-intercept variance and applying a small-sample df method (Kenward-Roger by default, Satterthwaite otherwise; both exact here) — but the numerical result is the same. Differences arise only when the data are unbalanced, or when the model has multiple random effects or a crossed structure; in those cases the df become non-integer and the LMM and paired t-test diverge. The LMM is strictly more general: it handles missing observations and unequal group sizes without modification.

### Two-way ANOVA (Demo 3)

`lm(y ~ A * B)` with effects coding and Type III sums of squares is exactly a classical two-way factorial ANOVA, provided the design is balanced (equal n per cell). The `ToothGrowth` dataset used in Demo 3 has exactly 10 observations per cell, so the results are numerically identical to a classical two-way ANOVA.

For unbalanced designs, Type III SS with effects coding still gives well-defined, interpretable tests — classical ANOVA software often struggles or produces ambiguous results in this case.

### Repeated-measures ANOVA (Demo 4)

`lmer(y ~ condition + (1 | subject))` is equivalent to a one-way repeated-measures ANOVA when:
1. The design is balanced (one observation per subject per condition), and
2. The compound symmetry assumption holds (equal variances and equal pairwise correlations across all conditions).

Demo 4 uses the `ergoStool` data (nlme): 9 subjects each rate the perceived effort (Borg scale) of arising from 4 stool types, exactly one rating per subject per type. The design is balanced, and because the four stool types have no natural ordering there is no serial trend to make adjacent conditions correlate more strongly than distant ones — so compound symmetry is a reasonable assumption rather than a fiction. The random intercept reproduces exactly that covariance structure, and the Type III F-test matches the classical RM-ANOVA to the displayed precision: `F(3, 24) = 22.36, p = 3.9 × 10⁻⁷` from both `lmer` (with the default Kenward-Roger df, which is exact here, as is Satterthwaite) and `aov(effort ~ Type + Error(Subject/Type))`. The LMM again generalises gracefully: it handles missing cells, unbalanced designs, and more complex covariance structures (random slopes, crossed random effects) that are outside the scope of classical RM-ANOVA.

A four-level within-subject factor is also a more honest demonstration than a two-level one: a repeated-measures ANOVA with only two conditions is just a paired t-test (`F = t²`), already covered in Demo 2.

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

They also differ in what they estimate on the original scale: back-transforming the log-LMM mean via `exp()` yields a geometric mean — the median on the original scale — whereas the gamma GLMM with log link targets the arithmetic mean, so the two back-transformed EMMs can differ even on identical data.

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

**GLM handles imbalance without modification.** GLM estimates model parameters directly by maximum likelihood, fitting the model to individual observations rather than to cell means. The likelihood function is well-defined for any pattern of cell sizes — balanced, partially unbalanced, or severely unbalanced — so no special treatment is needed. There is no requirement for imputation, no correction factor, and no need to drop entire groups to restore balance. kbstatpy exploits this directly: after outlier removal, the model is simply refit on whatever observations remain, and the estimates and standard errors remain valid regardless of the resulting imbalance.

**Two-pass outlier removal in kbstatpy.** Outlier removal should always be principled, not automatic. kbstatpy provides a two-pass strategy controlled by `remove_outliers_prefit` and `remove_outliers_postfit`:

1. **Pre-fit IQR pass** (`remove_outliers_prefit`): flags observations more than 1.5 × IQR beyond Q1 or Q3 within each group. This uses only the raw data, requires no model, and protects the initial fit from being distorted by extreme values.
2. **Post-fit residual pass** (`remove_outliers_postfit`): flags observations with Pearson residual z > 3 after the first fit, then refits. These are points that look unremarkable in isolation but deviate strongly from the model's predictions — a subtler form of influence. Note that because this pass selects points using the model's own residuals and then reports inference from the refit on the same data, the resulting p-values are mildly anti-conservative (a form of post-selection inference); treat them as descriptive rather than exactly calibrated.

A useful sanity check after outlier removal is whether the fixed-effect estimates and their standard errors shift materially: a substantial change confirms the removed observations were genuinely influential, while a negligible change suggests the flagged points were not actually distorting the model and removal was unnecessary. Note that AIC cannot be used for this comparison — AIC is only comparable between models fit to the *same* observations. After removing points the likelihood is evaluated on a smaller set, so the AIC will almost always drop (as in Demo 10: 108.8 → 74.5) whether or not removal was justified; the decrease therefore confirms nothing on its own.

Removed observations are retained in the dataset with `is_outlier = True` and shown as distinct markers in the data plot, making the exclusion transparent and reproducible.

### Binomial GLMM — binary outcomes (Demo 11)

Classical t-tests and ANOVA have no valid counterpart for binary dependent variables. A binary outcome — bacteria present or absent, treatment succeeded or failed, response correct or incorrect — takes only the values 0 and 1, so the mean is a probability bounded strictly between 0 and 1. Applying a gaussian model to such data is fundamentally wrong: it can predict probabilities below 0 or above 1, it assumes constant variance (whereas binomial variance is `μ(1−μ)`, highest at `μ = 0.5` and zero at the boundaries), and it produces incorrect standard errors and p-values.

A binomial GLMM with logit link handles binary outcomes correctly. The logit link function

```
logit(μ) = log(μ / (1 − μ)) = x β
```

maps the linear predictor — which ranges over all real numbers — to a probability between 0 and 1. The model estimates the log-odds of the event for each combination of predictors, and EMMs are back-transformed to the probability scale for reporting.

Demo 11 uses the `bacteria` dataset (MASS package): 50 children with otitis media, measured at up to five time points (weeks 0, 2, 4, 6, 11), under three treatments (placebo, drug, drug+). The outcome is presence or absence of *H. influenzae* bacteria. A random intercept per child accounts for the within-subject correlation across time points.

---

## Analytical extensions

Capabilities that run alongside the core modelling pipeline, and the statistical rationale behind kbstatpy's key modelling choices.

### Multiple dependent variables (Demo 12)

Running the same model independently for each of k dependent variables is a common workflow in multivariate research (e.g. analysing all limb segments, all biomarkers, or all performance metrics in one call). kbstatpy handles this via `options.y` as a list, saving results into per-variable subdirectories automatically.

One caveat: testing k outcomes multiplies the family-wise type I error rate. kbstatpy can apply a cross-variable correction across the family of dependent variables via `options.y_correction` (see the next section); the appropriate strategy depends on the research question — confirmatory analyses with pre-registered hypotheses call for stricter correction than exploratory screening. Within each model, post-hoc p-values are Holm-corrected across pairwise comparisons.

### Family-wise correction across dependent variables (Demo 13)

When several dependent variables are tested in one run, the per-variable omnibus p-values form a family and the family-wise type I error rate grows with the number of outcomes. `options.y_correction` adjusts them together — one family per model term (the `Role` p-values across all outcomes, the `Age` p-values separately, and so on) — and writes the raw and adjusted values to `MultipleComparisons.xlsx`. Choices are `bonferroni` and `holm` (control the family-wise error rate), and `FDR` / `FDR_correlated` (Benjamini–Hochberg / Benjamini–Yekutieli, control the false discovery rate; the latter is valid under arbitrary dependence, appropriate when the outcomes are correlated).

This corrects within a single run. When the family of tests spans several separate runs (e.g. one model per condition or task), those p-values are not visible to a single call and the correction must be applied at that outer level instead.

### Multicollinearity diagnostics — VIF (Demo 14)

Demo 14 illustrates the typical situation in biomechanical and physiological research: a categorical predictor (number of cylinders) and two correlated continuous covariates (horsepower, weight). The categorical predictor appears in the violin plot; the numeric covariates are checked for collinearity via VIF and visualised in the correlation scatter grid with VIF values on the diagonal.

Detecting collinearity before interpreting individual predictor effects is essential — highly correlated predictors inflate standard errors and destabilise coefficient estimates even when no formal assumption is violated. See [VIF and multicollinearity](#vif-and-multicollinearity) for the mathematical definition and thresholds.

### Level-wise profile analysis (Demo 16)

Some factors are an **ordered series of levels** — spinal segments cranial→caudal, joints along a limb, dose steps, time points. There the scientific question is usually not "is there an effect at some level?" but "how does another factor's effect *change across* the ordered levels?" — the *pattern* is the finding, and testing each level in isolation both misses that pattern and pays a multiplicity price. `options.profile_across = 'B'` names the ordered factor B and, on top of the normal analyses, profiles how the factor(s) that interact with B behave across its levels, in two layers.

**Layer 1 — the per-level profile.** For each factor A that interacts with B, kbstatpy reports A's pairwise contrast computed *within each level of B*, as `emmeans` simple effects pulled from the **single fitted `A * B` model** (marginal over any further factors). Reading the per-level contrasts out of one model — rather than fitting each level separately — is deliberate: the levels of a within-subject ordered factor are correlated (a subject's six spinal levels share that subject's overall loading), and the single model with its `(1 | id)` term borrows strength across levels and shares one covariate adjustment and one residual-variance estimate, which regularises noisy per-level differences. Separate per-level fits discard that structure and, when each level is one value per subject, degenerate to a plain LM per level.

**Layer 2 — the trend across levels.** The `A:B` interaction is reported two ways. The **factor omnibus** (k−1 df, straight from the Type III ANOVA) asks whether the A-effect differs across B's levels in *any* pattern — a diffuse test. The **focused linear trend** (1 df) asks the sharper question the ordered hypothesis actually poses: does the A-effect change *monotonically* along B? It is a custom linear contrast over B whose weights are the centred level **positions** — the labels' numeric values when they parse as numbers (so genuinely unequal spacing like dose 1 / 2 / 10 is honoured), otherwise equal-spaced ranks — and its estimate is the per-unit slope of A's contrast across B. Because it is a *contrast on the same factor model* (not a refit with B entered as a numeric covariate), it stays coherent with the omnibus and the Layer-1 profile — all three come from one fit — and reduces exactly to the equal-spaced orthogonal-polynomial linear trend when the spacing is equal. Leading with the focused trend follows the general principle that **a focused 1-df test beats a diffuse omnibus** when the alternative is directional: the trend can reach significance while the omnibus does not.

**When it applies.** The profile is meaningful only when B **interacts** with the profiled factor: under the single-model approach an additive `A + B` model implies a constant A-effect across B by construction, so the profile would be flat and no trend is defined — kbstatpy warns in that case. It also expects B to be **ordered** (set `x_order` so the positions run in the intended direction) and to have **≥3 levels** (with two, the "trend" is just the single contrast, redundant with the omnibus). When B interacts with more than one factor (e.g. `A * B * C`), each interacting factor is profiled marginally across B and the higher-order `A:B:C` interaction is surfaced as a heterogeneity flag, since a large three-way means the marginal profile is averaging over real level-by-level differences. As with any data-driven pattern in a modest sample, the gradient is best treated as the finding rather than the per-level significance stars.

### Contrast coding: effects coding (`contr.sum`)

Categorical predictors are coded using **effects coding** (sum-to-zero contrasts, `contr.sum` in R).

With effects coding each coefficient represents a deviation from the **grand mean** across all levels. The alternative — treatment coding (`contr.treatment`, R's default) — codes each level as a deviation from a chosen reference level, making all coefficients dependent on that arbitrary choice.

Effects coding is a prerequisite for Type III sums of squares to be well-defined (see [Sums of squares: Type III](#sums-of-squares-type-iii)). With treatment coding, Type III main-effect tests change depending on which level is chosen as the reference — a known pathology. With effects coding the tests are invariant.

### Sums of squares: Type III

The ANOVA table uses **Type III sums of squares**. Each effect is tested conditional on all other effects in the model, including higher-order interactions.

**Type II** tests each main effect after all other main effects but ignoring interactions that contain it. This gives slightly more power when interactions are truly absent, but it becomes inconsistent when interactions are present: the main-effect test no longer corresponds to a meaningful hypothesis.

**Type III** is the correct choice whenever interactions are included in the model (which is the default in kbstatpy). If a model has no interaction terms, Types II and III are identical for every effect — regardless of coding or balance, since each main effect is then tested against the same set of remaining terms either way — so there is no scenario where switching to Type II would be an improvement.

Type III + effects coding is a coherent, principled pair. MATLAB's `fitglme` uses the same combination.

> **Caution:** when an interaction is significant, marginal main-effect estimates from `emmeans` average over the other factor. Main effects should be interpreted cautiously in that case — the interaction result is the primary finding.

### Degrees of freedom: Kenward-Roger and Satterthwaite

The denominator degrees of freedom for the fixed-effect tests are controlled by the `df_method` option (default `'auto'`). The **same method is used for the omnibus ANOVA F-tests and the post-hoc contrasts alike**, so the two strata are always consistent, and the method actually used is reported in `Summary.txt` (under MODEL INFORMATION and beside the ANOVA and post-hoc tables).

#### Linear mixed models (LMMs, `distribution = 'normal'`)

With `df_method = 'auto'` an LMM uses the **Kenward-Roger** method when the R package `pbkrtest` is installed, and **Satterthwaite** otherwise. Both yield finite, data-adaptive df that account for the random-effects structure. Kenward-Roger additionally inflates the fixed-effect covariance matrix to reflect the uncertainty in the estimated variance components, which makes it better calibrated at small sample sizes and **exact on balanced classical designs**: it reproduces the integer df and F-statistic of the corresponding ANOVA / t-test (see Demos 2 and 4). Satterthwaite shares that exactness for single-error-stratum balanced cases but is otherwise an approximation. Both are implemented via R's `lmerTest`, `pbkrtest`, and `emmeans`.

You can override the choice with `df_method = 'kenward-roger'`, `'satterthwaite'`, or `'asymptotic'` (Wald z, `df = Inf`). A request that is not available for the fitted model or dataset — Kenward-Roger without `pbkrtest`, a small-sample method on a GLMM, or a KR computation that fails on a degenerate fit — emits a warning and falls back, recommending valid alternatives (including `'auto'`).

#### Generalised linear mixed models (GLMMs, any other distribution)

The Kenward-Roger and Satterthwaite machinery is **only defined for LMMs**. It is derived for the Gaussian LMM, where an exact t-reference distribution for fixed-effect contrasts is available; GLMMs have no exact small-sample t-distribution for their contrasts. For GLMMs, `emmeans` therefore falls back to **asymptotic (Wald) inference**, which yields `df = Inf` and chi-square tests, regardless of `df_method` (requesting a small-sample method on a GLMM warns and uses asymptotic inference).

This is mathematically correct behaviour, not a software error.

For comparison: MATLAB's `fitglme` also does not support these small-sample methods for GLMMs. Instead it uses the finite approximation `df2 = n − p`, where `n` is the number of observations and `p` is the number of fixed-effect columns. Both are approximations; the asymptotic `df = Inf` method used in kbstatpy is the more principled one because the Wald statistic for a GLMM contrast is asymptotically chi-square — its natural reference distribution — whereas `n − p` is a finite-sample fudge factor with no exact justification for non-Gaussian likelihoods.

### GLMM engine: `glmmTMB` (not `glmer`)

All non-Gaussian GLMMs are fitted with `glmmTMB`, not `lme4::glmer`. This matters because the Wald inference above (and the `emmeans` post-hoc below) are only as good as the model's fixed-effect covariance matrix.

`glmer` is built around binomial and Poisson likelihoods, which have **no free dispersion parameter** (dispersion is fixed at 1). For the continuous families that *do* carry a dispersion — **Gamma and inverse Gaussian** — `glmer`'s profiled-deviance machinery estimates the dispersion poorly and returns a **mis-scaled covariance matrix**. The point estimates and the log-likelihood are correct, but the standard errors can collapse to a small fraction of their true size. Because every Wald quantity is built from those SEs, the result is silently catastrophic: omnibus chi-squares in the thousands, partial η² ≈ 1, and post-hoc p-values of essentially zero — for effects that are not actually significant. (We observed exactly this: a Gamma fit with a true `p ≈ 0.27` reported `p ≈ 0` with SEs ~100× too small, while a likelihood-ratio test — which never touches the covariance — gave the correct answer. The fit also tripped a convergence warning.)

`glmmTMB` estimates the dispersion as an **explicit parameter** and computes the covariance from a proper (automatic-differentiation) Hessian, so the standard errors are correct and the Wald omnibus, the post-hoc comparisons, and the EMM confidence intervals are all reliable **and mutually coherent** (the omnibus and the pairwise tests agree). It supports every family kbstatpy exposes (binomial, Poisson, Gamma, inverse Gaussian) and handles random slopes natively. For binomial and Poisson the two engines agree (no dispersion to misestimate); the switch is what makes the continuous-dispersion families trustworthy. Gaussian LMMs are unaffected — they continue to use `lmer`/`lmerTest` so the Kenward-Roger / Satterthwaite degrees of freedom above are preserved.

### Post-hoc comparisons: `emmeans`

Post-hoc pairwise comparisons are computed via R's `emmeans` package (estimated marginal means). This correctly averages over the random-effects structure and accounts for unbalanced designs.

By default comparisons are run on the first fixed-effect factor. `options.posthoc_compare` selects one or more factors to compare instead (each gets its own `DataPlots_<var>` and `Posthoc_<var>`). These comparisons are **conditional (per cell)**: a factor's levels are compared *within each combination of the other factors* rather than marginally, so each facet panel carries its own brackets and the result can differ across panels (e.g. two doses may differ significantly under one supplement but not another). Per-cell p-values are corrected within the cell. This is the kind of within-cell contrast a significant interaction calls for — see the caution above about interpreting marginal main effects when an interaction is present. For reference, `Posthoc_<var>.xlsx` also includes a **marginal block** (every conditioning column set to `any`) giving the comparison averaged over the conditioning factors; this appears in the table only — the plot brackets stay per-cell.

P-value adjustment defaults to **Holm's step-down method** (`posthoc_correction = 'holm'`), which controls the family-wise error rate and is uniformly more powerful than Bonferroni.

For LMMs, `emmeans` reports t-ratios with Kenward-Roger or Satterthwaite degrees of freedom (per `df_method`, matching the omnibus). For GLMMs it reports z-ratios (asymptotic), which kbstatpy detects automatically.

For a single factor with only two levels there is exactly one pairwise comparison, so the post-hoc *test* is redundant with the omnibus: F = t², the same df and p-value, and the multiple-comparison correction is a no-op. kbstatpy still reports it, because the post-hoc table is the only place the **effect estimate** appears — the between-group difference with its direction and 95 % confidence interval (and, for GLMMs, the back-transformed ratio: an odds ratio, a rate ratio). The ANOVA says *whether* there is an effect and *how large in standardised terms* (partial η², SMD); the post-hoc says *by how much, in which direction, on the response scale* — usually the number one actually reports. So the redundancy is confined to the hypothesis test, not the information.

### Why estimated marginal means?

A **raw group mean** is the arithmetic average of all observations in that group. It is easy to compute and straightforward to interpret — but it is sensitive to every source of variation in the data, including imbalances that have nothing to do with the factor of interest.

An **estimated marginal mean (EMM)** is the group mean as predicted by the fitted model, after marginalising over (averaging out) all other terms in the model. Concretely, it is the model-predicted response for a given level of the factor of interest, evaluated at the mean of all covariates and with the random effects held at their mean (zero).

**When EMMs equal raw means.** In the simplest case — a balanced design, no covariates, no random effects, no transformation, identity link — the EMM for each group equals the raw group mean exactly. This is why Demos 1–4, which use fully balanced datasets with no covariates, show the EMM dot sitting in the centre of the violin.

**When EMMs diverge from raw means.** Any of the following causes a divergence:

- **Unbalanced cell sizes.** If one group has more observations than another, the raw grand mean is dominated by the larger group. The EMM weights each group equally regardless of sample size, giving the estimate that represents the population contrast rather than the sample composition.
- **Covariates.** If a numeric covariate is in the model and its distribution differs across groups, raw group means conflate the factor effect with the covariate effect. The EMM is evaluated at the covariate mean, isolating the factor effect at a common reference point.
- **Random effects.** The random effects are held at their mean (zero), so the EMM is the population-level fixed-effect prediction rather than a value tied to the particular subjects sampled. For an identity link this coincides with the marginal mean; for a non-linear link (see below) it is the value for a *typical* subject, not the population-averaged mean — `emmeans` does not integrate over the random-effect distribution unless bias adjustment is explicitly requested.
- **Non-linear link functions (GLMMs).** With a log link, the model works on the log scale. Back-transforming `exp(mean of log-scale estimates)` is not the same as taking the mean on the response scale — Jensen's inequality guarantees they differ whenever the transformation is non-linear. The EMM applies the inverse link to the model's linear prediction, whereas the raw mean ignores the transformation entirely; note that the back-transformed value is a typical-subject (median-like) quantity rather than the population-averaged mean.
- **Data transformation (`y_transform`).** Analogous to the link function case: the EMM is computed in the transformed space and then back-transformed, whereas the raw mean is computed directly on the original values.

**Why this matters for inference.** Post-hoc pairwise tests compare EMMs, not raw means, for exactly these reasons: EMMs represent the factor contrast that the model is actually testing, unconfounded by covariate distribution, imbalance, or link-function non-linearity. Reporting raw group means alongside model-derived p-values is potentially misleading — the p-value corresponds to the EMM contrast, not the raw mean difference.

**Visible in the data plots.** The white dot and CI bar in each panel show the EMM; the violin (or bar) shows the raw data distribution. A visible gap between the two is not an error — it signals that the model is adjusting for structure in the data that a simple group mean would ignore. See the [data plots section](#data-plots-violin-or-bar-plot) for the layer-by-layer description.

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

### Long vs. wide data format

kbstatpy requires input data in **long format** (also called *tidy* format). Understanding the distinction is important because research data are often collected or stored in wide format, and importing wide-format data without reshaping it is a common source of errors.

**Wide format** encodes a categorical factor by spreading its levels across columns rather than storing them as values in a single column. This pattern appears in several common data collection scenarios:

- **Repeated measurements over time** — one column per time point:

  | Subject | Week_0 | Week_2 | Week_4 |
  |---|---|---|---|
  | S01 | 142 | 138 | 125 |
  | S02 | 155 | 160 | 148 |

- **Experimental conditions or groups** — one column per condition, with each subject measured under all of them:

  | Subject | Control | DrugA | DrugB |
  |---|---|---|---|
  | S01 | 12.3 | 9.1 | 8.4 |
  | S02 | 14.0 | 11.2 | 10.5 |

- **Body sides or anatomical locations** — one column per limb or sensor:

  | Subject | Left_knee | Right_knee |
  |---|---|---|
  | S01 | 142 | 138 |
  | S02 | 155 | 160 |

In every case the structure is the same: what should be a factor level (the time point, the condition, the side) has been promoted to a column name, and the table has one row per subject rather than one row per observation. This is compact and easy to read, but it hides the factor structure from any analysis tool that works on column names.

**Long format** places every observation on its own row, with separate columns for the grouping variables and the response. The first example above becomes:

| Subject | Week | score |
|---|---|---|
| S01 | 0 | 142 |
| S01 | 2 | 138 |
| S01 | 4 | 125 |
| S02 | 0 | 155 |
| S02 | 2 | 160 |
| … | … | … |

Each row is one observation. The variable `Week` is now an explicit column that can appear in `options.x`, be tested in the ANOVA table, and enter the model formula. The response `score` is a single column that can be assigned to `options.y`. The same transformation applies to any of the wide-format examples above: the column-name factor becomes a value in a new grouping column, and all the measurements collapse into one response column.

**Why the model requires long format.** The statistical model operates on individual observations: each row contributes one likelihood term. The model formula `score ~ week + (1 | Subject)` maps column names to model terms — it has no concept of "spread across columns". Wide format has no single response column and no explicit factor column for the grouping dimension, so there is nothing to assign to `options.y` and `options.x`.

**Converting wide to long in Python.** `pandas.melt()` is the standard tool:

```python
import pandas as pd

df_wide = pd.read_csv('data_wide.csv')   # Subject, Week_0, Week_2, Week_4

df_long = df_wide.melt(
    id_vars    = 'Subject',
    var_name   = 'Week',
    value_name = 'score'
)
df_long['Week'] = df_long['Week'].str.replace('Week_', '').astype(int)
df_long.to_csv('data_long.csv', index=False)
```

In R the equivalent is `tidyr::pivot_longer()`.

### Wilkinson notation for model formulae

kbstatpy uses Wilkinson notation — the same formula syntax as R's `lme4` and `lm` — to specify statistical models. A formula describes the response variable, the fixed effects, and (for mixed models) the random effects.

**Basic structure:**

```
y ~ x1 + x2          # y as a function of two additive fixed effects
y ~ x1 * x2          # main effects of x1 and x2 plus their interaction (x1 + x2 + x1:x2)
y ~ x1 + x1:x2       # main effect of x1 and the x1×x2 interaction, but not the main effect of x2
```

The `*` operator expands to all main effects and their interaction. The `:` operator specifies an interaction term only, without implying the main effects. This makes it straightforward to include partial interactions (Demo 9).

**Random effects** are added in parentheses after a `|` separator:

```
y ~ x + (1 | id)          # random intercept per subject: each subject has their own baseline
y ~ x + (1 + x | id)      # random intercept and random slope: each subject has their own baseline and their own response to x
```

The left side of `|` specifies which terms vary by subject; the right side names the grouping variable. A random intercept `(1 | id)` accounts for the fact that repeated measurements from the same subject are correlated. A random slope `(x | id)` additionally allows each subject to respond differently to `x`.

**In kbstatpy**, the formula is assembled automatically from `options.y`, `options.x`, `options.id`, `options.slope`, and `options.interaction`. The `options.formula` field accepts a full Wilkinson formula string and overrides all of these when set, giving full control for non-standard model specifications.

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

### Data plots: violin or bar plot

The plot style is selected via `options.plot_style` (`'violin'`, `'bar'`, or `'auto'`). Both styles share the same model-based overlay layers; they differ in how the raw data are summarised.

**Violin style** (default for continuous outcomes):

1. **Violin** — kernel density estimate of the marginal distribution, drawn with `seaborn.violinplot`. `cut=0.3` extends the KDE slightly beyond the data range to avoid hard edges. Alpha is set to 0.5 to keep the violin from obscuring the individual points behind it.

2. **Jittered scatter** — each raw observation is placed at its y-value with a random horizontal offset. The offset is drawn from a uniform distribution whose half-width is a fraction of the violin's local half-width at that y-value, keeping every dot inside the violin body. The random seed is fixed (`numpy.random.default_rng(0)`) for reproducibility. The dots are **density-adaptive**: as the number of points in a panel grows, the marker size and opacity both taper with 1/√n (size from 7 down to a floor of 1.5, alpha from 0.4 down to a floor of 0.08) so that dense panels stay legible instead of saturating to a solid black mass. The jitter fraction is tied to the marker size in turn — fat dots (few points) spread over 75 % of the half-width to keep a margin and avoid spilling over the edge, while small dots (many points) spread over up to 95 %, filling the violin body more naturally.

   > Seaborn's own `swarmplot` was not used here because seaborn computes beeswarm positions lazily on every redraw event (`tight_layout`, `show`, `savefig`). Any post-hoc modification of dot positions via `set_offsets()` is silently overwritten before the figure is saved. The manual scatter approach avoids this entirely.

**Bar style** (default for binary outcomes):

1. **Observed mean bar** — a filled bar whose height is the arithmetic mean of the raw data in that group (i.e. the observed proportion for binary outcomes). The bar colour matches the group colour; a thin black border improves legibility. An `n=` label is placed just above the CI bar top.

**Shared overlay layers** (both styles):

2. **95 % CI bar** — a thick vertical line (linewidth 4) from the lower to the upper 95 % confidence limit of the model's estimated marginal mean, drawn in dark grey (`'0.2'`). CIs come from `emmeans` and are always on the original response scale (see the back-transformation section). If no model has been fitted (correlation-only runs), this falls back to the raw IQR.

3. **Estimated marginal mean (EMM)** — a white dot with a dark grey edge, placed at the model's back-transformed EMM. For simple models this is close to the arithmetic mean; for GLMMs or transformed models it reflects the model-estimated central tendency on the original scale.

**Why the EMM dot may not align with the centre of the violin or bar.** The violin/bar shows the *raw data distribution*; the EMM dot and CI bar show the *model's estimate* after adjusting for covariates, random effects, and the link function. A visible gap is informative — it signals the model is doing real work. See [Why estimated marginal means?](#why-estimated-marginal-means) for the full explanation.

Significance brackets are drawn above the panel using the post-hoc p-values (Holm-corrected).

### Diagnostic plots

`Diagnostics.pdf/.png` contains six panels that together check the key assumptions of the fitted model. They should be inspected after every run before drawing conclusions from the ANOVA or post-hoc tables. The **distribution panels** (residual histogram and Normal Q-Q plot) use **DHARMa simulation-based quantile residuals** transformed to the normal scale. Under a correctly specified model these are distributed ~N(0, 1) for *any* family (gaussian, gamma, binomial, Poisson, …) — unlike Pearson residuals, which are right-skewed for non-Gaussian families even when the model is correct and would make the histogram and Q-Q plot look misspecified when they are not. This makes those two panels honest normality checks across all model types. The **structure panels** (residuals vs. fitted, lagged residuals, scale-location) use **deviance residuals** instead: quantile residuals cap any observation that falls beyond every simulated draw at ±7, which forms spurious edge-lines in a scatter plot, whereas deviance residuals are unbounded, free of that artifact, and are the appropriate residual for checking structure, autocorrelation, and homoscedasticity. If the DHARMa R package is unavailable, the distribution panels fall back to deviance residuals (more symmetric than Pearson for GLMs), then Pearson as a last resort; the residual types actually used are recorded in `Summary.txt`.

**Why plots rather than formal tests?** A natural alternative is to test assumptions with statistical tests — Kolmogorov–Smirnov or Shapiro–Wilk for normality, Levene's test for equal variance, Durbin–Watson for autocorrelation. These tests have a fundamental problem in the context of LM and GLMM: their sensitivity scales with sample size in the wrong direction. With small samples (n < 30), where assumption violations genuinely threaten the validity of the analysis, formal tests have low power and will almost never reject — giving false reassurance. With large samples (n > 200), the same tests become so sensitive that they reject for trivial deviations — a residual distribution that is practically indistinguishable from normal will still produce a significant Shapiro–Wilk p-value, triggering unnecessary concern about a model that is perfectly adequate.

Diagnostic plots do not have this problem. A Q-Q plot with 20 points and one with 500 points both show the same thing: whether the residuals follow the reference distribution closely enough to trust the inference. The researcher's eye integrates the severity and pattern of the deviation — a few points drifting slightly off the diagonal near the tails is not the same as a systematic S-curve across the full range, even if a formal test treats both as equally "significant" at large n. The same logic applies to heteroscedasticity: a funnel that doubles the spread across the fitted range matters; random scatter that a Levene test flags at n = 300 probably does not.

There is also a conceptual mismatch: formal normality tests apply to the raw data, whereas the relevant assumption for LM is normality of the *residuals* — the variation left over after the model has removed the systematic group effects and random structure. Testing the raw outcome for normality before fitting confuses the two. The diagnostic plots work directly on the residuals and therefore test the right quantity.

**1. Histogram of residuals.**
A histogram of the Pearson residuals with a KDE overlay. For a Gaussian LMM the distribution should be approximately bell-shaped and centred on zero. Strong skew or multimodality suggests a distributional mismatch — consider switching to a gamma or binomial GLMM as appropriate. For GLMMs the histogram reflects the Pearson residuals after the link transformation, so mild deviation from normality is expected and acceptable.

**2. Normal Q-Q plot.**
Quantiles of the Pearson residuals are plotted against the theoretical quantiles of the standard normal. Points should fall close to the diagonal reference line. Systematic deviation in the tails indicates a heavier-tailed distribution (S-curve curling outward) or lighter-tailed distribution (curling inward) than assumed. The Q-Q and histogram together give a more complete picture than either alone: the histogram shows the overall shape; the Q-Q is more sensitive to tail behaviour.

**3. Residuals vs. fitted values.**
Pearson residuals plotted against the model's fitted values, with a horizontal reference line at zero. Look for a flat, horizontal band of roughly constant width. A U-shape or arc indicates a missing non-linear term in the model. A funnel (variance growing with the fitted value) indicates heteroscedasticity — if present in a Gaussian LMM, consider a log transform (`y_transform`) or a gamma GLMM.

**4. Lagged residuals.**
Residual at observation *i* plotted against residual at observation *i+1*. This tests for serial autocorrelation: if consecutive residuals are independent the cloud should be an **unstructured, isotropic scatter centred at (0, 0)** — no tilt, no pattern. A circular cloud is the expected appearance.

- **Positive slope (tilted up-right):** positive autocorrelation — consecutive residuals tend to share the same sign. Common in repeated-measures designs where the random intercept does not fully absorb within-subject correlation. Consider adding a random slope.
- **Negative slope (tilted down-right):** negative autocorrelation — residuals alternate in sign. Less common; can occur in oscillatory processes.
- **Fan shape along the diagonal:** variance of consecutive pairs grows, indicating heteroscedasticity in the time domain.

This panel is only informative when observations have a natural ordering (time series, repeated measures with a defined sequence). For purely cross-sectional data the ordering is arbitrary and any apparent tilt is not a model violation.

**5. Fitted vs. response.**
Model-fitted values on the x-axis, actual raw observations on the y-axis, with an identity line (slope = 1, intercept = 0) as reference. Points should scatter symmetrically around the identity line. A systematic bow above or below the line indicates that the model is biased in a particular range of the response — a signal that a transformation or a different distribution family may be needed. The spread around the line reflects residual variance; the overall correlation reflects model fit.

**6. Cook's distance.**
A bar chart of Cook's distance for each observation, with a dashed reference line at the conventional threshold 4/n (where n is the number of observations). Cook's D measures how much the vector of all fitted values would change if observation *i* were removed — it combines leverage (how unusual the predictor values are) with residual magnitude into a single influence statistic. Bars coloured red exceed the 4/n threshold and warrant investigation.

A high-leverage observation is one with unusual predictor values; by itself that is not a problem. A large residual is one the model fits poorly; by itself that may just reflect noise. A large Cook's D means both are true simultaneously — the observation sits far from the main predictor cloud *and* the model fits it badly, so it is actively pulling the fitted surface towards itself. These are the observations most likely to distort coefficient estimates and should be examined carefully.

**Influence is not the same as error.** A red bar does not mean the observation should be removed. There are several legitimate reasons for high influence:

- **Extreme but valid data** — a subject who genuinely had an unusually strong response. Removing them would bias the model towards the less extreme majority and misrepresent the true population variability.
- **High leverage from predictor values** — an observation at the edge of the design space (e.g. the highest dose combined with the lowest response) is naturally influential without being wrong.
- **Small group sizes** — with few observations per cell, any single point carries more weight. The 4/n threshold can be conservative in mixed models with sparse cells.

The recommended workflow when red bars appear is: (1) identify the flagged observations by index in `Data.csv`; (2) check whether the values are plausible given the measurement context; (3) remove only if there is a concrete justification — a data entry error, a recording artifact, or a known protocol violation. If the value looks extreme but genuine, keep it, or run the model with and without it and report both results.

For this reason, kbstatpy's automatic outlier removal (`remove_outliers_prefit`, `remove_outliers_postfit`) is based on IQR and residual z-scores rather than Cook's D. Automating removal based on influence alone would silently discard valid extreme observations, which is statistically unjustifiable.

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

### Random slopes in GLMMs

GLMMs are fitted with `glmmTMB` (see "GLMM engine" above), which handles random slopes (e.g. `(A + B | id)`) natively through its own rpy2 wrapper (`kbstatpy/_glmmtmb.py`) — no special-casing is needed, and the same engine serves both the random-intercept and random-slope cases.

Historical note: earlier versions used `lme4::glmer` through `pymer4`, whose 0.9.x `broom.tidy()` layer crashed on GLMM random slopes (it built a `data.frame` from two objects with mismatched row counts). That required a separate `GlmerDirect` rpy2 wrapper. Moving the GLMM engine to `glmmTMB` resolved both the random-slope crash and the mis-scaled Gamma/inverse-Gaussian standard errors, so the old workaround is gone.

Random slopes in LMMs (`distribution = 'normal'`) use `lmer`/`lmerTest` and are unaffected.
