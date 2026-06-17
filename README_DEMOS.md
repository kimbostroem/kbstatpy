# kbstatpy demos

Thirteen worked examples live in `demos/`, each as both a script
(`demos/scripts/demo_NN_*.py`) and a Jupyter notebook
(`demos/notebooks/demo_NN_*.ipynb`). They use only standard, citable R
datasets so the results are reproducible and the statistical points are easy to
check against the literature.

This guide explains, for each demo, **what it demonstrates**, the **model** it
fits, and the **meaning of the dataset**. For the underlying theory (effects
coding, Type III sums of squares, Satterthwaite df, EMMs, diagnostics, …) see
[STATISTICAL_NOTES.md](STATISTICAL_NOTES.md); for the API and options see
[README.md](README.md).

## Running the demos

First regenerate the datasets once (writes CSVs into `demos/data/`):

```bash
Rscript export_datasets.R
```

Then run any script…

```bash
python3 demos/scripts/demo_01_unpaired.py
```

…or open the matching notebook in `demos/notebooks/` and run all cells. Each run
writes its tables and figures into `demos/scripts/results/demo_NN_*/` (scripts)
or `demos/notebooks/results/demo_NN_*/` (notebooks).

The three groups below mirror the structure of the statistical notes: demos 1–5
reproduce classical tests exactly, demos 6–11 go beyond them, and demos 12–13
show analytical conveniences that run alongside the modelling pipeline.

---

## Equivalence to classical tests (demos 1–5)

Each model here reduces to a textbook test, so you can verify kbstatpy against a
known answer before trusting it on harder problems.

### Demo 1 — Unpaired t-test
**Dataset:** `sleep` (R base; Cushny & Peebles 1905 / Student 1908). The extra
hours of sleep gained by **10 patients** under each of **two soporific drugs**;
here the two drug groups are treated as independent.
**Model:** `extra ~ group` (plain linear model).
**Shows:** an `lm` with a two-level factor and effects coding is algebraically
identical to an independent-samples (Student) t-test — `F = t²`, same df
(`n − 2`), same p-value — and this holds even with unequal group sizes.

### Demo 2 — Paired t-test
**Dataset:** `sleep`, the same data as demo 1, but now using the fact that both
drugs were measured on the **same 10 patients**.
**Model:** `extra ~ group + (1 | ID)` (random intercept per patient).
**Shows:** a random intercept per subject absorbs between-patient baseline
differences, reproducing a paired t-test (`df = n − 1`). Comparing the p-value
with demo 1 illustrates how accounting for pairing increases power.

### Demo 3 — Two-way ANOVA
**Dataset:** `ToothGrowth` (R base). Odontoblast (tooth) length in **60 guinea
pigs** given vitamin C by two delivery methods (`OJ` = orange juice, `VC` =
ascorbic acid) at three doses (low / medium / high), 10 animals per cell.
**Model:** `len ~ supp * dose` (two crossed between-subject factors + interaction).
**Shows:** with effects coding, Type III SS, and a balanced design, the result
is numerically identical to a classical two-way factorial ANOVA, including the
interaction term.

### Demo 4 — One-way repeated-measures ANOVA
**Dataset:** `ergoStool` (nlme; Wretenberg, Arborelius & Lindberg 1993).
Perceived effort (Borg scale) for **9 subjects** to rise from each of **4 stool
types** — one rating per subject per stool (balanced, no replication).
**Model:** `effort ~ Type + (1 | Subject)`.
**Shows:** an exact one-way repeated-measures ANOVA equivalent — the Type III
F-test matches `aov(effort ~ Type + Error(Subject/Type))`, with the random
intercept reproducing the compound-symmetry covariance RM-ANOVA assumes. A
4-level within-subject factor is a more honest RM-ANOVA than a 2-level one
(which is just the paired t-test of demo 2).

### Demo 5 — Pearson and partial correlation
**Dataset:** `longley` (R base; Longley 1967). A classic econometrics
benchmark **built to be severely multicollinear**: 16 annual US macroeconomic
observations (1947–1962) where GNP, population, and year all trend together.
**Model:** none — purely exploratory correlation.
**Shows:** pairwise Pearson correlations plus **partial correlations** (the
association between two variables after regressing out all others), which
disentangle direct relationships from shared trends. `constraints = 'Year > 1950'`
demonstrates row filtering (restricting to the post-war growth period).

---

## Transcending classical tests (demos 6–11)

From here the models express designs and distributions that classical t-tests
and ANOVA cannot handle.

### Demo 6 — Random slopes
**Dataset:** `sleepstudy` (lme4; Belenky et al. 2003). Reaction times of **18
subjects** over days of sleep deprivation; `Period` contrasts a rested vs a
deprived block.
**Model:** `Reaction ~ Period + (1 + Period | Subject)`.
**Shows:** a random slope lets each subject respond to sleep loss at their own
rate, not just start from their own baseline. This has no classical equivalent —
RM-ANOVA assumes a single shared time effect. The random-effects table gains a
slope variance and an intercept–slope correlation.

### Demo 7 — Log-transformed LMM
**Dataset:** `sleepstudy`, shared with demo 6.
**Model:** `log(Reaction) ~ Period + (1 | Subject)`; EMMs, CIs, and pairwise
differences are back-transformed to milliseconds automatically.
**Shows:** how to handle strictly positive, right-skewed outcomes by modelling
on the log scale. The back-transformed mean is a geometric mean (median-like),
which contrasts instructively with the gamma GLMM of demo 8.

### Demo 8 — Gamma GLMM
**Dataset:** `Oats` (nlme; Yates 1935). A split-plot field trial: oat **yield**
for 3 varieties × 4 nitrogen levels across **6 blocks** (72 plots).
**Model:** `yield ~ Variety * Nitrogen + (1 | Block)`, gamma family with log link.
**Shows:** a GLMM that models a positive, right-skewed outcome directly, assuming
the variance scales with the mean squared (constant coefficient of variation) —
an alternative to the log-transform of demo 7 when the variance–mean relationship
is genuinely multiplicative. The data plot facets by nitrogen with significance
brackets per panel.

### Demo 9 — Partial interaction
**Dataset:** `npk` (R base; Venables & Ripley 2002). A classic agricultural
experiment: pea **yield** under three binary treatments — nitrogen (N),
phosphate (P), potassium (K) — across **6 complete blocks** (24 plots).
**Model:** `yield ~ N + P*K + (1 | block)` — only the P×K interaction is tested,
not N×P or N×K.
**Shows:** the `interaction` option including a *subset* of possible
interactions. Where classical ANOVA tests all pairwise interactions, here only
the one hypothesised term is fitted, keeping the model parsimonious and
preserving degrees of freedom.

### Demo 10 — Outlier removal
**Dataset:** `stackloss` (R base; Brownlee 1965). Ammonia lost (`stack.loss`)
during an industrial oxidation process over **21 plant runs**; observations 1,
3, 4, and 21 are textbook influential outliers used throughout the robust-
regression literature.
**Model:** `stack.loss ~ Air.Flow + Water.Temp + Acid.Conc.` (Air.Flow binned
into three operating regimes for the plot; the other two enter as numeric
covariates). The same model is fit **twice** — once untouched, once with pre-fit
IQR + post-fit residual outlier removal.
**Shows:** kbstatpy's two-pass, principled outlier handling and how removing
influential points shifts the estimates, while keeping the excluded points
visible and the analysis valid under the resulting imbalance.

### Demo 11 — Binomial GLMM
**Dataset:** `bacteria` (MASS). Presence/absence of *H. influenzae* in **50
children** with otitis media, measured at five time points (weeks 0, 2, 4, 6,
11) under three treatments (placebo / drug / drug+); 220 observations.
**Model:** `present ~ trt + week + (1 | ID)`, binomial family with logit link.
**Shows:** the case classical tests cannot touch — a binary outcome whose mean is
a probability bounded in [0, 1]. The logit-link GLMM models the log-odds
directly; EMMs are back-transformed to probabilities. A random intercept per
child handles the repeated measures.

---

## Analytical extensions (demos 12–13)

Conveniences that run alongside the core pipeline.

### Demo 12 — Multiple dependent variables + correlation
**Dataset:** `iris` (R base; Fisher 1936). Four flower measurements for **150
plants** across 3 species; `setosa` is excluded here so only *versicolor* and
*virginica* are compared.
**Model:** four separate LMs, `{Sepal.Length, Sepal.Width, Petal.Length,
Petal.Width} ~ Species`, plus a pairwise correlation among the four measurements.
**Shows:** passing a list to `options.y` runs the full pipeline once per outcome
(results in per-variable subdirectories), and a shared correlation analysis runs
in the same call. `constraints = 'Species != "setosa"'` demonstrates categorical
filtering.

### Demo 13 — Multicollinearity (VIF)
**Dataset:** `mtcars` (R base; Henderson & Velleman 1981). Performance figures
for **32 car models**; here fuel economy (`mpg`) is modelled from engine power
(`hp`) and weight (`wt`) — two strongly correlated covariates — plus number of
cylinders (`cyl`) as a categorical predictor.
**Model:** `mpg ~ cyl + hp + wt` (with `hp`, `wt` as numeric covariates).
**Shows:** automatic Variance Inflation Factor computation for the numeric
predictors (thresholds: < 5 OK, 5–10 concerning, > 10 severe), flagging
collinearity that inflates standard errors before it distorts interpretation.
`correlation = 'hp, wt'` adds a scatter grid with VIF on the diagonal.

---

For the statistical reasoning behind these choices — why effects coding, why
Type III SS, when GLMM beats a transform, how to read the diagnostic plots — see
[STATISTICAL_NOTES.md](STATISTICAL_NOTES.md).
