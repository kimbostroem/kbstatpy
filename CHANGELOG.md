# Changes

## [1.16.0] - 2026-09-11

### Bugs

- Gaussian LMMs fitted on more than 3000 observations were tested asymptotically (`df = Inf`) while `Summary.txt` reported Kenward-Roger or Satterthwaite. **Those results should be regenerated:** the p-values change little on designs well replicated within subjects, but the confidence intervals were too narrow, and an effect resting on few subjects could have been tested far too liberally. GLMMs are unaffected.

- Post-hoc SMD and partial eta-squared came back `NaN` on those same fits. They are populated again, now from the test's own finite df rather than the liberal `n - p` fallback.

- p-values too small to represent as a double printed as `0`, now as `<1e-308`.

- `Summary.txt` reported `Fit method: MPL`, which neither engine uses; it now names the estimator that ran. The note explaining `df = Inf` no longer blames GLMMs unconditionally.

### Features

- New option `kr_max_obs` (default 5000): the fit size above which `df_method='auto'` uses Satterthwaite rather than Kenward-Roger, which costs about a minute on 18 000 rows for df that agree to five digits. An explicit `df_method='kenward-roger'` is still honoured; `0` removes the cap.

## [1.15.7] - 2026-09-10

### Bugs

- Windows: on a machine where R's library folder is not on the `PATH`, R started but every analysis then failed at its first `library()` call with `unable to load shared object ... stats.dll`, naming a file that is present rather than the R DLL beside it that is not. Importing kbstatpy now puts that folder on the search path, so no `PATH` setting is needed by hand.

### Changes

- The Windows installer's verification step now imports kbstatpy the way a script does, instead of testing `rpy2` on its own, and its failure message names the two causes actually seen in the wild: R's DLLs not being findable, and a non-English R whose accented characters `rpy2` cannot decode.

## [1.15.6] - 2026-09-09

### Changes

- Rewrote the changelog entries from 1.9.0 onward, and the GitHub releases taken from them, in the brief style used before 1.9.0: what was added, fixed or changed, without the implementation detail. Entries that carry statistical consequences say more, since those affect how results should be read. `CLAUDE.md` records the style.

## [1.15.5] - 2026-09-09

### Changes

- First shortening of the 1.9.0-onward changelog entries. Superseded by 1.15.6.

## [1.15.4] - 2026-09-09

### Changes

- Corrected a claim in the 1.15.3 changelog about the CI package cache.

## [1.15.3] - 2026-09-09

### Bugs

- The Linux installer failed to install the R package `DHARMa`, and stopped. The cause was missing system libraries, which the installer now names, per distribution.
- Both installers now install R packages from whatever repositories R is configured with, instead of forcing CRAN. On Linux this means prebuilt binaries where they are available, so the install no longer compiles everything from source.

## [1.15.2] - 2026-09-09

### Bugs

- The test suite could not run on a clean checkout: it needs PyYAML, which is not a dependency of kbstatpy. It is now declared as a `test` extra.

## [1.15.1] - 2026-09-09

### Bugs

- The Windows installer stopped with an error instead of finding Python, on machines where the Microsoft Store placeholder `python.exe` comes first on the `PATH`.

### Features

- The Windows installer installs into an activated conda environment or venv, and accepts a `-Python` argument naming an interpreter directly. It reports which interpreter it is installing into before it starts.

## [1.15.0] - 2026-08-26

### Features

- Native Windows is supported, with an `install.ps1` installer. Nothing needs to be compiled and Rtools is not required. WSL remains documented as a fallback.
- Both installers check the Python and R version minimums, report which R packages failed to install, and say where to get what is missing.
- A CI workflow runs the installers, the test suite and all demos on Windows, Linux and macOS.

### Bugs

- Variable names and factor levels are sanitised before they are used in output paths. Levels such as `5 mg/kg`, `50%` or `pre:post` previously produced a results tree that differed from the one requested, and differed between operating systems. Names that were already safe are unchanged, so no existing output path moves.

## [1.14.2] - 2026-08-25

### Changes

- Removed the references to the MATLAB library kbstatpy descends from where they only recorded provenance. The references that explain a statistical choice are kept; see `STATISTICAL_NOTES.md`.

## [1.14.1] - 2026-08-25

### Features

- New demo 18, `demo_18_plot_annotations.py`, for the two plot-annotation options added in 1.14.0.

### Changes

- `demo_11_glmm_binomial.py` sets `show_group_size = True`, restoring the group counts it lost when 1.14.0 made them opt-in.

## [1.14.0] - 2026-08-25

### Features

- New option `show_emm_lines` draws a horizontal reference line at each group's estimated marginal mean, across the whole panel in that group's colour, so one group's level can be read against the others directly instead of by comparing dot heights. The option doubles as the line style. Default `False`.
- New option `show_group_size` labels each plotted group with its observation count. **This changes existing output:** the counts were previously drawn unconditionally in bar style and are now off by default.

### Bugs

- `remove_outliers_prefit='off'` switched outlier removal **on**, and `slope_correlated='false'` fitted the correlated random-effect structure. Any string spelling of "off" meant its opposite, silently, so affected runs excluded outliers that should have been kept and fitted a structure that was not asked for. All on/off options now accept `true`/`false`, `on`/`off`, `yes`/`no` and `none` in either case, and reject anything else instead of reading it as true. Results produced with a string-valued flag should be rechecked.
- A significance bracket could be drawn through the group-size label beneath it in violin plots.

## [1.13.6] - 2026-07-31

### Bugs

- `CITATION.cff` was six minor versions stale and not valid CFF 1.2.0, so GitHub's "Cite this repository" panel had nothing valid to render. It is now valid and current, and a test keeps it in step with the released version.

## [1.13.5] - 2026-07-31

### Bugs

- `Summary.txt` reported the number of rows in the input table as the number of observations, rather than the number the model was fitted on. Rows removed as outliers or dropped as incomplete were counted in, so a fit on 6635 observations could be reported as 7100. The count now comes from the fitted model, and what was excluded is named. The `etaSqp` and `SMD` columns, which use that count, were affected in the same way and are corrected with it.

## [1.13.4] - 2026-07-30

### Bugs

- The title of a correlation figure was cut off in the PDF when the matrix was small. The PNG was unaffected.

### Changes

- The subtitle of a correlation figure is set smaller than the title, and the frame marking a significant cell is lighter than in 1.13.3.
- `STATISTICAL_NOTES.md` and the demo 5 description explain how to read the raw and partial correlation tables together: it is the difference between them that carries the message, and what conditioning can and cannot support. Partial correlation removes what is linearly predictable from the conditioning set and has no notion of cause, so it removes a spurious association for a confounder, creates one for a collider, and erases a real effect for a mediator. Confounder and mediator give the same signature with opposite meanings, so with the conditioning set being all remaining variables the partials are best read as a statement about redundancy rather than about mechanism.

## [1.13.3] - 2026-07-30

### Changes

- Cells whose correlation coefficient is significant now carry a heavier frame, coloured red for a positive and blue for a negative correlation, so the significant pairs and the block structure of a large matrix are legible at a glance.

## [1.13.2] - 2026-07-30

### Changes

- Correlation figures with many variables use larger type in a smaller cell, so the numbers stay readable past roughly twelve variables. Twelve or fewer is unchanged.

## [1.13.1] - 2026-07-30

### Changes

- `LevelProfileContrast` draws the fitted trend line for every significant trend. 1.13.0 suppressed it where the level estimates were far from collinear, which hid real results: a contrast with a significant trend could end up with no line at all. The estimates and their confidence intervals are plotted regardless, so a departure from the line remains visible as points sitting off it. `STATISTICAL_NOTES.md` records why joining the estimates instead was rejected, and why no departure-from-linearity statistic is reported.

## [1.13.0] - 2026-07-30

### Features

- A second figure for `profile_across`, `LevelProfileContrast`. `LevelProfile` plots the absolute estimated marginal means per level, but the tested quantity is the linear trend of the contrast *between* levels, which absolute means do not display and which is easily invisible when levels differ greatly in magnitude. The new figure plots that contrast with 95 % confidence intervals: ratios on a logarithmic axis for a log link, otherwise differences on a linear axis.

### Bugs

- Trend rows in `LevelProfile.xlsx` carried unlabelled integer codes for factors with three or more levels, so they could not be matched to the contrasts they describe.

## [1.12.1] - 2026-07-30

### Changes

- With `y_scale = 'log'`, the y-axis label carries a `(log scale)` note. The tick labels show untransformed values, so nothing but the tick spacing previously revealed that the axis was logarithmic.

## [1.12.0] - 2026-07-30

### Features

- New option `y_scale` (`'linear'` or `'log'`) for the data plots and the profile plot. A log axis suits panels spanning orders of magnitude, and gamma/log-link models, where the gaps between profile lines then are the group ratios. Significance brackets are placed in log space so their spacing stays even. Non-positive values fall back to a linear axis with a warning rather than being dropped from the figure. Diagnostic and correlation figures are never rescaled.

### Changes

- The profile plot no longer draws an x-axis label, which only repeated the factor name.

## [1.11.4] - 2026-07-30

### Bugs

- **Partial correlations from `correlate()` had inverted signs.** Each variable was residualised with its eventual partner still in the predictor set, which yields exactly the negative of the partial correlation. Magnitudes were correct, so the error was easy to miss: near-duplicate measures appeared strongly negatively correlated. Both members of a pair are now residualised on the same conditioning set, excluding the pair itself. The partial scatter grid had the same cause and is corrected with it.
- **Any `PartialCorrelation` output produced by 1.10.0 through 1.11.3 has inverted signs and should be regenerated.** Raw and covariate-adjusted correlations are unaffected.

## [1.11.3] - 2026-07-29

### Changes

- The correlation effect-size label uses the same seven-bin scheme as the eta-squared and d labels, so all of kbstatpy's effect-size labels now describe equivalent magnitudes with the same words.

## [1.11.2] - 2026-07-29

### Changes

- Effect-size labels use a single seven-bin scheme for both partial eta-squared and Cohen's d. Previously the two used different bins and thresholds, so the ANOVA and post-hoc tables could describe the same magnitude with different words.
- The post-hoc effect-size label is taken from the contrast's partial eta-squared rather than the standardised mean difference. Both remain in the table as numeric columns.

## [1.11.1] - 2026-07-29

### Bugs

- Post-hoc effect sizes were degenerate for GLMMs: every standardised mean difference came out exactly 0, because the non-Gaussian families are tested asymptotically. They are now computed from the contrast statistic with the residual degrees of freedom, and a partial eta-squared column is reported alongside. `Summary.txt` notes that these effect sizes treat repeated within-subject observations as independent and are therefore liberal, approximate upper bounds. The p-values and estimated marginal means were never affected.
- The post-hoc `diff` column was empty whenever a factor level name contained a special character, such as the hyphen in `Med-ADHD`.

## [1.11.0] - 2026-07-25

### Features

- New option `diagnostic_outliers` controls how residual outliers are shown in the diagnostic panels: annotated as a count (default), plotted in a distinct colour, or hidden. These are a model-misfit flag and are deliberately kept separate from the pre-fit data outliers.

### Changes

- `show_outliers` is renamed `data_outliers` and takes the same values as `diagnostic_outliers`. The old name still works as a deprecated alias.

## [1.10.0] - 2026-07-25

### Features

- New option `correlation_method` selects Pearson (default) or Spearman for both the raw and the partial correlations.
- New option `correlation_control` partials named covariates out of every correlation before it is computed. The control variables are kept out of the matrix and the figure titles note the adjustment.
- New option `dispersion` lets the dispersion of the glmmTMB families vary by a factor instead of being constant, which is worth using when pooled groups differ widely in scatter. Ignored for gaussian models.
- New option `slope_correlated` chooses the random-slope covariance structure: correlated, diagonal, or `'auto'` (the default), which fits the correlated structure and refits diagonally only if that fit is singular. The structure actually used is reported in `Summary.txt`, so a fallback is never silent.

### Bugs

- Partial-correlation p-values used the wrong degrees of freedom, ignoring the conditioning variables, so they were too small. The coefficients were unaffected.
- `Summary.txt` listed the fit statistics twice for glmmTMB models.
- The formula parser mistook the intercept controls `0` and `1` in a random-effects term for random-slope variables and rejected the formula.

### Changes

- `show_outliers` now defaults to annotating outliers as a count rather than plotting them, so the y-axis scales to the bulk of the data instead of being squashed by extreme points.
- Redesigned the correlation figures as a compact lower-triangle matrix, with the scatter grid mirroring the table.
- Tuned the default plot font sizes, and made titles and axis labels bold throughout.
- Added demo 17 for `dispersion`.

### Known limitations

- With `slope_correlated` diagonal or `'auto'`, a **categorical** random slope in a gaussian model is not fully uncorrelated: lme4 keeps the correlations among the levels within that slope. The non-gaussian families, fitted with glmmTMB, are unaffected.

## [1.9.0] - 2026-07-17

### Features

- New option `profile_across` names an ordered categorical factor and profiles how the factors interacting with it behave across its levels: pairwise contrasts per level, and the interaction as both a factor omnibus and a focused linear trend across the ordered positions, weighted by their real spacing. Writes `LevelProfile.xlsx` and a profile plot. Demo 16.
- kbstatpy ships and registers Latin Modern Sans, TeX Gyre Heros and TeX Gyre Termes, so plots render identically on every platform with no system font install. A request for Helvetica, Arial or Times falls back to the bundled clone where the real font is absent, instead of dropping to a visibly different family.
- The demos run on Google Colab, with a one-click playground notebook and per-demo links.

### Bugs

- Fixed a matplotlib font warning for plot titles on platforms without Helvetica.
- `Output`, `ModelResult` and `CorrelationResult` no longer print their entire contents when displayed.

### Changes

- Enlarged the label, title and tick sizes of the data, diagnostics and profile plots.
- The descriptive-statistics table reports only the factor-level combinations that occur, rather than the full cartesian product padded with empty cells.

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
