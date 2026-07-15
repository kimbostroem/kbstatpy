# Changes

## [1.8.1] - 2026-07-16

### Features

- Added `Kbstat.apply_font()`, a public static method that applies kbstat's house font-resolution (the Helvetica-first fallback chain and its macOS Helvetica.ttc bold-subface fix) to matplotlib's rcParams without needing a `Kbstat`/`KbstatOptions` instance. Lets a hand-built matplotlib figure that bypasses `run_save()` entirely still match kbstat's own `DataPlots` visually — call it once before building the figure, then use `fontweight='bold'` on the labels/ticks that should match. `Kbstat._apply_font()` (the internal, `options.font`-driven instance method) now delegates to it, unchanged in behavior.

## [1.8.0] - 2026-07-15

### Features

- `options.title` accepts `'none'` (case-insensitive) to suppress the data-plot title entirely: no text, and no vertical space reserved for it (the panel keeps the same size as with a title, closing the gap). The y-axis label is untouched, since it and the title otherwise both derive from the same variable display name (`options.rename`) and previously could not be controlled independently. The diagnostics page keeps its own "Diagnostics of <DV>" label regardless, since `'none'` only targets the reader-facing data plot.

## [1.7.1] - 2026-06-30

### Bugs

- The diagnostics footer no longer lists the residual types used in each panel. With both a distribution and a structure residual named, the line could overflow the figure width. The residual types remain documented in the README, STATISTICAL_NOTES, and `Summary.txt`; the footer now shows only the formula and fit statistics.

## [1.7.0] - 2026-06-30

### Features

- The data-plot scatter points are now **density-adaptive**: marker size and opacity taper with 1/√n (size from 7 down to a 1.5 floor, alpha from 0.4 down to a 0.08 floor) so dense violins stay legible instead of saturating to solid black. The jitter width is tied to the marker size in turn — fat dots (few points) keep a 25 % margin from the violin edge, while small dots (many points) spread to within 5 % of it, filling the body more naturally. Applies to both the healthy-data and outlier markers. STATISTICAL_NOTES updated.

## [1.6.0] - 2026-06-30

### Features

- The per-cell post-hoc tables (`Posthoc_<var>.xlsx`) now also include a marginal block: every conditioning column set to `any`, giving the pairwise comparison averaged over the conditioning factors. Added to the tables only — the plot brackets stay per-cell.

## [1.5.0] - 2026-06-30

### Changes

- `posthoc_compare` comparisons are now **conditional (per cell)** instead of marginal: each compared factor's levels are tested within every combination of the other factors, so each facet panel shows its own significance brackets and `Posthoc_<var>.xlsx` gains the conditioning factors as leading columns (one block of comparisons per cell, p-values corrected within the cell). This replaces the marginal comparison that drew the same brackets on every panel. Implemented cell-by-cell with the labelled `emmeans(~ var, at = ...)` form (the `~ var | by` form drops factor labels for the glmmTMB/pymer4 models). Demo 15, README, and STATISTICAL_NOTES updated.

## [1.4.3] - 2026-06-30

### Documentation

- Updated the README and STATISTICAL_NOTES diagnostic-plot descriptions to match the 1.4.2 residual split: the distribution panels (histogram, Q-Q) use DHARMa quantile residuals, while the structure panels (residuals-vs-fitted, lagged, scale-location) use deviance residuals.

## [1.4.2] - 2026-06-30

### Bugs

- Removed edge-line / stacking artifacts from the diagnostic scatter panels. The structure panels (residuals-vs-fitted, lagged residuals, scale-location) now use deviance residuals instead of DHARMa quantile residuals: the quantile residuals' ±Inf boundary capping (observations beyond every simulated draw, pinned to ±7) lined up into a frame along the panel edges. The distribution panels (histogram, Q-Q) keep the DHARMa quantile residuals for the normality check. Both residual types are noted in the diagnostics footer and `Summary.txt`.

## [1.4.1] - 2026-06-30

### Features

- New demo `demo_15_posthoc_compare` (script + notebook) showcasing `options.posthoc_compare`: it reuses the two-way ToothGrowth model from Demo 3 and compares both factors in one run, each plotted as if it were the first x-variable (its own `DataPlots_<var>` and `Posthoc_<var>`). Demo 3 now cross-references it.

## [1.4.0] - 2026-06-30

### Features

- Diagnostic plots now use DHARMa simulation-based quantile residuals (transformed to the normal scale) instead of Pearson residuals. Under a correctly specified model these are ~N(0, 1) for any family (gaussian, gamma, binomial, Poisson, ...), so the residual histogram (with its Normal reference curve) and the Q-Q plot are honest normality checks even for non-Gaussian GLMMs. Falls back to deviance residuals (then Pearson) if DHARMa is unavailable or the simulation fails; the residual type is shown in the diagnostics footer.

### Dependencies

- Added the R package DHARMa (installed by install.sh).

## [1.3.1] - 2026-06-30

### Changes

- The residual histogram in the diagnostics plot now overlays a Normal(mean, sd) reference curve instead of a KDE. A KDE merely traced the bars and could not reveal non-normality; the fixed Gaussian lets skew and heavy tails show as gaps between the histogram and the dashed curve. The panel's y-axis is now density.

## [1.3.0] - 2026-06-30

### Features

- New option `max_iterations` (default 10000) setting the glmmTMB optimizer's iteration/evaluation cap for non-Gaussian GLMMs.

### Changes

- Raised the default glmmTMB optimizer iteration limit (`max_iterations=10000`). Large fixed-effect models — e.g. a `factor * factor` interaction with many levels — that previously stopped at the optimizer's default cap with a benign "Model convergence problem; iteration limit reached" warning now converge cleanly (code 0). Verified the estimates are unchanged (the default fit was already at the optimum).

## [1.2.0] - 2026-06-30

### Features

- New option `posthoc_compare` to choose which fixed-effect factor(s) get pairwise level comparisons. Each listed factor is plotted as if it were the first x-variable (its levels on the x-axis, the others as facet panels) with significance brackets between its violins, written to `DataPlots_<var>.*` and `Posthoc_<var>.xlsx`. `'auto'` (default) compares the first x-variable (previous behaviour); `''` or `'none'` turns comparisons off (violin plots only, no brackets). `auto`/`none` are reserved factor names.

### Changes

- Data-plot and posthoc output files are now suffixed with the compared variable's original name, e.g. `DataPlots_condition.png` / `Posthoc_condition.xlsx` (previously `DataPlots.png` / `Posthoc.xlsx`). With comparisons off, the plot is written as the unsuffixed `DataPlots.*` with no brackets and no posthoc table.

## [1.1.2] - 2026-06-30

### Bugs

- Silenced the repeated "Blended transforms not yet supported" warning emitted by mpld3 while writing the interactive HTML plots. It is an unactionable mpld3 limitation (its exporter cannot represent seaborn's blended-transform violins); the HTML still renders, only its zoom is approximate.

## [1.1.1] - 2026-06-30

### Bugs

- Data-plot suptitle no longer overlaps the top row of panels on tall faceted figures (e.g. one row per subject). It is anchored a constant physical distance above the panels — matching the diagnostics plot — instead of at a fixed figure fraction.

## [1.1.0] - 2026-06-29

### Features

- Connecting lines in the violin plots now span any number of factor levels (previously only two), tracing each subject's points across adjacent levels by identity.

### Bugs

- Connecting lines now tolerate outlier removal: a flagged point drops only the line segments touching it, rather than suppressing the lines for the whole panel. Pairing is now by subject id instead of by matching data values, which also fixes mis-connections when two subjects share a value.

## [1.0.0] - 2026-06-26

### Features

- Initial release. Python library for generalised linear mixed model (GLMM) analysis, modelled after the MATLAB kbstat library, with model fitting via R's lme4, glmmTMB, and emmeans (through pymer4 and rpy2).
- Post-hoc pairwise comparisons with Kenward-Roger / Satterthwaite degrees of freedom, Type III sums of squares, and effects-coded contrasts.
- Data transformation with automatic back-transformation of estimates for plots and tables.
- Standalone correlation analysis (Pearson and partial) and multicollinearity diagnostics (Variance Inflation Factor).
- Support for multiple dependent variables (multi-y) in a single call, with family-wise correction across them.
- Demo scripts on classic R datasets (demos/) and a run_demos.py runner.
