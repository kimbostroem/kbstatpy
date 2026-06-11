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

## Post-hoc comparisons: `emmeans`

Post-hoc pairwise comparisons are computed via R's `emmeans` package (estimated marginal means). This correctly averages over the random-effects structure and accounts for unbalanced designs.

P-value adjustment defaults to **Holm's step-down method** (`posthoc_correction = 'holm'`), which controls the family-wise error rate and is uniformly more powerful than Bonferroni.
