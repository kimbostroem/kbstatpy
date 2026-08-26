# Changes

## [1.15.0] - 2026-08-26

### Changes

- **Native Windows is now supported, with a `install.ps1` installer.** The README previously directed Windows users to WSL, on the grounds that `rpy2` -- the R bridge kbstatpy is built on -- could not be installed reliably on native Windows. That has not been true for some time: `rpy2-rinterface` publishes `win_amd64` wheels for CPython 3.9 through 3.14, and `rpy2` 3.6 carries deliberate Windows support, calling `os.add_dll_directory()` on R's DLL directory and handling both the pre-4.2 `bin\x64` layout and the merged `bin\` of R >= 4.2. CRAN serves every R package the installer needs as a Windows binary, so nothing compiles and Rtools is not required. kbstatpy's own code needed no changes for this: it shells out to nothing, spawns no processes, and builds every path through `os.path.join`. WSL remains documented as a fallback.

- **`install.ps1` handles three things that do not arise on macOS or Linux.** The Windows R installer does not add R to `PATH`, so R is located through the registry (and the default install location) rather than a `PATH` lookup alone. A non-interactive `Rscript` cannot answer R's "use a personal library?" prompt and errors out instead, so the user library is created before any package is installed. And because a failure to load `R.dll` surfaces at *import* -- long before any statistics run -- the installer verifies that `rpy2` can start R and load `glmmTMB` and `emmeans` before it reports success.

- **Both installers now enforce the version minimums they only used to print, and say where to get what is missing.** `install.sh` computed `PYTHON_VERSION` and `R_VERSION` and never compared them against anything, so Python 3.9 or R 4.3 produced a pip or R error further down that did not name the cause. Both installers now stop with the offending version, and name the package-manager command or download page for the platform in question -- including the detail that a distribution's own `r-base` is frequently older than 4.4 and that the CRAN repository is the fix. Failures during installation are annotated the same way: which build tools to install if something has to compile, and what to check when `rpy2` cannot start R.

- **Both installers now detect R packages that failed to install.** `install.packages()` only warns when a package cannot be installed, and `Rscript` still exits 0, so a missing `glmmTMB` was reported as successfully installed and then surfaced as an unrelated-looking R error during the first analysis. Both installers re-check `installed.packages()` afterwards and fail with the names.

### Fixed

- **Variable names and factor levels are now sanitised before they are used in output paths.** `save()` names the per-dependent-variable subdirectory after the variable, writes `Posthoc_<factor>.xlsx`, and -- when a fourth or later factor splits the data figure -- `DataPlots_<var>_<level>_<level>.*`. Those levels are ordinary data cells, so `5 mg/kg`, `50%` and `pre:post` are realistic values. Windows forbids `< > : " / \ | ? *` in a path component, refuses the reserved DOS device names (`NUL`, `CON`, `COM1`, ...) whatever the extension, and silently strips trailing dots and spaces. This went unnoticed because the library is developed on macOS, where only `/` is special -- and where it does not raise either: `os.path.join(out_dir, 'Force/BW')` quietly nests a directory, so the results tree silently differed from the one the user asked for, and the same analysis produced a different layout per operating system. Sanitising happens on every platform for that reason, not only on Windows. Names that are already safe are returned untouched, so no existing output path moves.

- **`CLAUDE.md` claimed that two of the tests need no R.** They do, as does every other test: `kbstatpy/__init__.py` imports `.kbstat`, which calls `ro.r('emmeans::emm_options(...)')` at module level, so `from kbstatpy import __version__` is enough to start R and require `emmeans`. There is no R-free test, which is also why the new CI workflow has no R-free job.

### Added

- **A CI workflow (`.github/workflows/ci.yml`), the repository's first.** The maintainer works on macOS, so nothing otherwise exercises `install.ps1` or the rpy2 bridge on Windows, and the Windows support above would be an assertion rather than a fact. It runs the real installer on Windows, Linux (Python 3.10 and 3.12) and macOS, then the test suite and all demos, and uploads the demo output so a figure that renders wrongly can be looked at. A separate job lints `install.ps1` against Windows PowerShell 5.1 -- the engine it targets, and one that no runner uses by default -- via PSScriptAnalyzer's compatibility profiles, which catch the PowerShell 7 syntax (`??`, ternaries, `&&` chains) that 5.1 rejects and a plain parse would accept.

- **`tests/test_path_sanitising.py`**, covering the forbidden characters, the reserved device names, trailing dots and spaces, the empty-after-sanitising fallback, and the end-to-end property that one component in yields one component out and never a nested path.

## [1.14.2] - 2026-08-25

### Changes

- **Dropped the references to the MATLAB library kbstatpy descends from where they only recorded provenance.** `show_emm_lines` was documented as "ported from the MATLAB predecessor's `plotLines`" in the option comment, the normalisation comment, the README table and the test docstring, and a test carried the name `test_matlab_style_string_is_accepted`. A reader of this library is not expected to know that software, so the phrase said nothing about what the option does. The comment explaining why an on/off option accepts strings at all keeps a reason, but one that stands on its own: a value may arrive as text from a config file, a command line or a spreadsheet cell and should need no conversion. The 1.14.0 changelog entry, and the published release notes taken from it, lost the same phrase.
- The references that carry statistical reasoning are deliberately kept -- the seven-bin effect-size labels reproduce a specific scheme including its midpoint bin edges, and the `df = Inf` choice for GLMMs is defended by the same limitation existing elsewhere -- since without them those decisions look arbitrary or, worse, wrong. See `STATISTICAL_NOTES.md`.

## [1.14.1] - 2026-08-25

### Changes

- **New demo 18, `demo_18_plot_annotations.py`, for the two plot-annotation options 1.14.0 added.** It refits demo 3's crossed two-way design on `toothgrowth.csv` with the factors swapped -- dose on the x-axis, supplement as panels -- so nothing about the model is new and the demo is purely about presentation. The EMM lines happen to make the interaction visible without consulting a table: under ascorbic acid the high-dose line clears the entire medium-dose violin, under orange juice the two overlap by a wide margin. The notebook runs the same model three times, bare then annotated then with solid lines, so the styles can be compared inline.
- **`demo_11_glmm_binomial.py` sets `show_group_size = True`.** Its bar plot printed the group counts automatically until 1.14.0 made them opt-in, so the demo had silently lost them; its cells are genuinely unbalanced (n = 21, 15, 14 at week 0), which is exactly where the counts are worth showing. Its docstring records the version change and points at demo 18.
- README and the Colab playground list the new demo. The README's demo count was also stale -- it said sixteen while seventeen were listed -- and now reads eighteen.

## [1.14.0] - 2026-08-25

### Changes

- **New option `show_emm_lines`: a horizontal reference line at each plotted group's EMM, drawn across the whole panel in that group's own colour.** The estimated marginal mean is already marked by the white dot, but reading one group's level against the *other* groups meant comparing dot heights by eye across the panel; the line makes the comparison direct. Each facet panel uses its own EMMs, and where none is available the line follows the same median fallback as the dot. Applies to violin and bar style alike. The option doubles as the line style: `True` gives the default dotted line -- which recedes furthest behind the violins and the significance brackets, so a line crossing a violin cannot be mistaken for plotted data -- while `'-'`, `'--'`, `':'`, `'-.'` (or the matplotlib names `'solid'`, `'dashed'`, `'dotted'`, `'dashdot'`) pick one explicitly. Solid reads calmest and makes the group colours easiest to attribute, at the cost of looking more like content than like a guide. Default `False`.
- **New option `show_group_size`: label each plotted group with its observation count (`n=12`).** *This changes existing output:* the counts used to be drawn unconditionally in bar style and were unavailable for violins, and they are now off by default in both, so bar plots lose them unless the option is set. The label is anchored to the top of what the group actually renders -- the violin's KDE tail, or the CI bar in bar style -- so it never lands inside the group's own body.

### Fixed

- **A significance bracket could be drawn through the `n=` label beneath it in violin plots.** The bracket stack is anchored above the tallest thing a panel has rendered, spaced in units of the y-range *as it stood before the stack expanded the axis*. A label's height is fixed in points, so on the taller axis it covers more data units and grows up into the bracket that was placed to clear it: a three-bracket stack expands the axis by roughly 40 %, which reduced a clearance of about 4 pt to under one pixel. Bar plots never showed it, their limits being pinned to 0..1.15. The gap is now measured in points once the y-limits are final, and only the stacks that came out tighter than 5 pt are lifted -- so panels that already clear their content, the bar plots included, are untouched. Measured on the demo figures: violin clearance 0.3 px -> 5.8 px, bar clearance unchanged at 6.5 px.
- **`remove_outliers_prefit='off'` switched outlier removal ON, and `slope_correlated='false'` fitted the correlated random-effect structure.** Both flags were read as raw truthiness, and a non-empty string is truthy, so any string spelling of "off" meant its opposite -- silently, since neither warns. All the on/off options now go through one parser (`_as_flag`): `True`/`False` plus `'true'`/`'false'`, `'on'`/`'off'`, `'yes'`/`'no'` and `'none'` (= off), case- and whitespace-insensitive, with `'auto'` kept as `slope_correlated`'s third mode. An unrecognised value now raises instead of being read as truthy, so a typo like `'offf'` is a visible error rather than a silent inversion. This also means `slope_correlated`'s consumers, which compare against `False` by identity and `'auto'` by equality, are guaranteed the three values they expect.
- `tests/test_emm_lines.py` and `tests/test_group_size_labels.py`. The bracket-clearance guard measures the gap in points on the finished figure rather than checking data-coordinate ordering, which is what the old geometry satisfied while still colliding.

## [1.13.6] - 2026-07-31

### Fixed

- **`CITATION.cff` was six minor versions stale and not valid CFF 1.2.0.** It declared `version: 1.7.1` against a released 1.13.5, because nothing imports the file, so a release could leave it behind without anything breaking. It also lacked the required `message` key, gave `type: software-code` where the schema allows only `software` or `dataset`, and carried `programming-languages`, a CodeMeta key that CFF does not define — so GitHub's "Cite this repository" panel had nothing valid to render, and the invalid keys were silently dropped rather than reported. The file is now valid, current, and carries `license`, `abstract`, and `keywords` in place of the undefined key.
- `tests/test_citation_metadata.py` keeps it that way: it asserts that the three version sources agree — `kbstatpy.__version__` (which `pyproject.toml` reads via `version = {attr = ...}`), the newest `CHANGELOG.md` heading, and `CITATION.cff` — and that the file stays schema-valid, so a release that forgets any of them fails the suite instead of drifting unnoticed. Metadata only, so it needs neither R nor glmmTMB.

### Changes

- `CLAUDE.md` records the release procedure the repository already follows (version bump, changelog entry, `CITATION.cff`, commit on `develop`, fast-forward `master`, annotated `vX.Y.Z` tag, GitHub release with the changelog section as its notes), which until now had to be reconstructed from the git history.

## [1.13.5] - 2026-07-31

### Fixed

- **`Summary.txt` reported the row count of the input table as the number of observations, not the number the model was actually fitted on.** The fit excludes the rows flagged by `remove_outliers_prefit` / `remove_outliers_postfit`, and R drops incomplete rows on top of that, so on a 7100-row table with 465 outliers flagged the run printed `Pre-fit outlier removal: 465 observation(s) flagged by IQR rule` and then reported `Number of observations : 7100` for a fit that used 6635. The count now comes from the fitted model itself (`nobs()`, falling back to the row count handed to it), and whatever was held out is named rather than absorbed: `Number of observations : 6635 (of 7100: 465 excluded as outliers)`, listing missing values separately when they also shrink n. Clean data still reports a bare count with no breakdown. This mattered most when cross-checking against the MATLAB kbstat library, which reports the post-removal count: the two looked like they disagreed on the data even where they agreed on the model and the estimates.
- The `etaSqp` and `SMD` columns of the ANOVA table substitute n for an infinite `df2`, and took that n from the outlier-excluded frame, which still contains rows R dropped as missing. They now use the same count as the fit, so the effect sizes and the reported n cannot drift apart.
- `tests/test_summary_n_obs.py`.

## [1.13.4] - 2026-07-30

### Fixed

- **The title of a correlation figure was cut off in the PDF when the matrix was small.** Both grids size their canvas from the matrix and its diagonal labels, ignoring the title, so a five-variable partial-correlation table came out under 3 in wide while its subtitle, `(residuals after removing all other variables)`, needs about 5 in at 13 pt; the PDF, whose canvas is fixed, lost both ends of it. The PNG was unaffected and therefore hid the problem, being saved with `bbox_inches='tight'`. The title is now measured against the canvas: it scales down towards the available width (to a floor of 0.75x, below which it would be unreadable), and whatever still does not fit widens the canvas, the extra split evenly so the matrix stays centred underneath. Wide grids have room to spare and are left at full size and unchanged in width.
- `tests/test_correlation_title_fits.py`. Layout only, so it needs neither R nor glmmTMB.

### Changes

- The subtitle of a correlation figure is now set at 11 pt against the 13 pt of the title proper, instead of both lines sharing one size, so it reads as a subtitle rather than a second heading.
- The frame marking a significant cell in the correlation scatter grid is 1.2 pt rather than 1.6 pt (non-significant cells keep their 0.5 pt hairline). 1.13.3 introduced the frame and erred on the heavy side; at Paper3 density the significant cells still stand out clearly at the lighter weight without dominating the scatters they enclose.
- `STATISTICAL_NOTES.md` and the demo 5 description now explain how to read the raw and partial tables together, since it is the difference between them that carries the message: a high raw correlation that collapses in the partial marks redundancy within the variable set, a partial that stays high marks an association the other variables do not capture, and a low raw correlation that grows in the partial marks suppression. They also set out what conditioning can and cannot tell you: partial correlation removes what is linearly predictable from the conditioning set and has no notion of cause, so it removes a spurious association for a confounder, **creates** one for a collider, and erases a real effect for a mediator. Confounder and mediator produce the same signature with opposite meanings, and no amount of data distinguishes them, so with the conditioning set being simply all remaining variables the partials are best read as a statement about redundancy rather than about mechanism.

## [1.13.3] - 2026-07-30

### Changes

- In the correlation scatter grid (`Correlation` / `PartialCorrelation`), cells whose coefficient is significant now carry a heavier frame, coloured by the direction of the correlation (red for positive, blue for negative, matching the existing colouring of the r-value). Significance was previously signalled only by the colour and weight of the r-value printed inside the cell, which is easy to miss in a large grid: the Skating/Paper3 run with sixteen variables has 120 cells. The frame encodes both facts at once, its weight marking significance and its colour the direction, so the significant pairs and the block structure of the matrix are legible at a glance. Non-significant cells keep the original light hairline.

## [1.13.2] - 2026-07-30

### Changes

- The correlation figures kept a legible-but-small type floor while their cell size stayed fixed, so past roughly twelve variables the text became small relative to its box, and relative to the whole figure as well, since the diagonal labels widen the canvas. With sixteen variables the coloured table drew 5 pt numbers in a 0.55 in cell. The type floor is raised and the cell shrunk for large matrices, in both the coloured table (`CorrelationTable`) and the scatter grid (`Correlation`): at sixteen variables the table now uses 7 pt in a 0.48 in cell, so the numbers occupy 20% of the cell instead of 13%, and the figure comes out narrower too. Behaviour at twelve variables or fewer is unchanged apart from the raised floor.

## [1.13.1] - 2026-07-30

### Changes

- `LevelProfileContrast` now draws the fitted trend line for **every** significant trend. 1.13.0 suppressed it where the level estimates were far from collinear, on the grounds that a straight line through a rise-then-fall pattern asserts a gradient the data do not show. That was the wrong trade: it hid real results, since a contrast with a significant trend could end up with no line at all. Because the estimates and their confidence intervals are plotted regardless, a departure from the line is visible as points sitting off it, so the line cannot conceal a bend; this is the ordinary logic of a regression plot. The `PROFILE_COLLINEAR_TOL` attribute is gone.
- `STATISTICAL_NOTES.md` records the reasoning, including why joining the estimates instead was also rejected (it shows the observed shape but not the tested quantity, and degenerates into an uninterpretable zigzag for more than three levels) and why no departure-from-linearity statistic is reported (with k levels the departure carries k−2 df, so isolating the quadratic term would be arbitrary for k > 3, and the diffuse alternative is already covered by the factor omnibus).

## [1.13.0] - 2026-07-30

### Added

- **A second figure for `profile_across`: `LevelProfileContrast`.** The existing `LevelProfile` plots the absolute EMMs per level of the profiled factor, but the Layer-2 statistic is a linear trend of the *contrast between* those levels, which absolute EMMs do not display, and which is easily invisible when the levels differ greatly in magnitude. The new figure plots the contrast itself across the ordered factor, with 95% confidence intervals taken from `emmeans`' own link-scale estimates and standard errors. For a log link it shows ratios on a logarithmic axis with a reference line at 1; otherwise differences on a linear axis with a reference line at 0. Produced automatically alongside the existing plot, and available as `result.fig_profile_contrast`.
- The fitted 1-df trend line is overlaid **only where the level estimates are close to collinear** (largest deviation from the fitted line below half the slope magnitude). A 1-df linear contrast can be significant on a rise-then-fall pattern because it weights the endpoints; drawing a line through that would assert a monotone gradient the data do not show, so in that case the p-value is annotated and no line is drawn.
- `profile_across_result` gained `per_level_link`, the `emmeans` contrast table on the link scale (`estimate`, `SE`) per interacting factor, which is what the new figure consumes.
- `tests/test_profile_contrast.py`.

### Fixed

- **Trend rows carried unlabelled integer codes for factors with three or more levels.** `emmeans` returns integer codes rather than labels in the `*_pairwise` column for this model class (the same label-dropping quirk already handled in `_pairwise_for`), so `LevelProfile.xlsx` showed `contrast` values of `1`, `2`, `3` and the trend rows could not be joined to the contrasts they describe. The labels are now fetched from `pairs()` on the same `emmeans` grid, which also keeps the ordering `emmeans`' own rather than the data's factor order (`x_order` can differ from it).

## [1.12.1] - 2026-07-30

### Changes

- With `y_scale = 'log'`, the y-axis label now carries a `(log scale)` note, on the data plots and on the profile plot. The tick labels show untransformed values, so previously nothing but the tick spacing revealed that the axis was logarithmic, and a reader skimming the figure could take the values as linear. This mirrors the existing `(original scale)` note used for `y_transform`. The note is keyed to the scale actually applied, so a fallback to a linear axis (triggered by non-positive values) is never labelled as log.

## [1.12.0] - 2026-07-30

### Added

- **`options.y_scale`** (`'linear'` default, or `'log'`) sets the y-axis scale of the data plots and of the profile plot (`options.profile_across`). A log axis is the readable choice when the panels of one figure span orders of magnitude — with a shared linear axis the small-valued panels collapse into slivers even when they carry the largest effects — and it suits gamma/log-link models, where a constant ratio becomes a constant distance and the gaps between profile lines therefore *are* the group ratios. Significance brackets and the y-limit padding are computed in log space, so their spacing stays even instead of drifting or escaping the axis. Strictly positive values are required: because matplotlib silently drops `y <= 0` on a log axis, a non-positive value falls back to a linear axis with a warning rather than quietly deleting points. Diagnostic and correlation figures are never rescaled.
- `tests/test_y_scale_log.py` — fits a small gamma/log GLMM and checks that the log axis is applied, that brackets stay inside the axis and stay evenly spaced *in log space*, that non-positive data falls back to linear with a warning, and that the profile plot has no x-axis label.

### Changes

- The profile plot no longer draws an x-axis label. Its tick labels are the profiled factor's own level names and the title already names the factor, so the label only repeated the factor name (e.g. a redundant "JointGroup" under `Ankle / Hip / Upper Body`).

## [1.11.4] - 2026-07-30

### Fixed

- **`correlate()` partial correlations had inverted signs.** Each variable was residualised on *all the other* correlation variables, i.e. with its eventual partner still in the predictor set. For a pair (i, j) that yields `corr(resid_i | all others, resid_j | all others)`, which is identically **minus** the partial correlation, by the precision-matrix identity `partial_r(i,j) = -P_ij / sqrt(P_ii * P_jj)` with `P = inv(cov)`. Magnitudes were correct, so only the signs were wrong — which made the error easy to miss and produced strongly negative "partial correlations" between measures that are near-duplicates of each other. Both members of a pair are now residualised on the same conditioning set, excluding the pair itself.
- The partial **scatter grid** was affected by the same cause and is fixed with it: it now plots the pair-specific residuals, so the plotted slope agrees with the labelled coefficient. `_plot_corr_scatter` takes a new optional `pair_arrays` argument for this.
- `STATISTICAL_NOTES.md` described the incorrect construction; corrected, with a note on why the conditioning set must exclude both members.

### Added

- `tests/test_partial_correlation_sign.py` — checks the partial coefficients against the precision-matrix definition (signs included), plus a collider case that must come out negative, a redundancy case that must stay positive, a `correlation_control` case, and a consistency check between the scatter slopes and the reported coefficients. Verified to fail on the pre-1.11.4 code.

### Note

Any `PartialCorrelation.xlsx` / `PartialCorrelation.png` / `PartialCorrelationTable.png` produced by 1.10.0 through 1.11.3 has inverted partial correlations and should be regenerated. Raw and covariate-adjusted correlations (`Correlation.xlsx`) are unaffected.

## [1.11.3] - 2026-07-29

### Changes

- The correlation effect-size label (`_r_label`, used for Pearson r and Spearman rho in the `correlate()` output) now uses the same seven-bin `_cohen_label` scheme as the eta-squared and d labels, with the r/rho Cohen anchors 0.1/0.3/0.5 (matching MATLAB `effprint('r')`/`effprint('rho')`). It was the last effect-size labeler still on the old four-bin scheme (`negligible`/`small`/`medium`/`large`); now all of kbstatpy's effect-size labels (η², d/SMD, r, rho) share one consistent seven-bin ruler.

## [1.11.2] - 2026-07-29

### Changes

- Effect-size verbal labels now use a single **seven-bin** scheme for both partial eta-squared and Cohen's d, reproducing the MATLAB kbstat `effprint` bins (`very small`, `small`, `small to medium`, `medium`, `medium to large`, `large`, `very large`). Previously the partial-eta-squared labeler used only four bins (and returned `negligible` below 0.01) while the d labeler used seven bins with slightly-off thresholds (0.05/0.225 instead of MATLAB's 0.10/0.275), so the ANOVA table (eta-squared) and the post-hoc table (d) could describe the same magnitude with different words. Both now derive from a shared `_cohen_label` with the metric's Cohen anchors (eta-squared 0.01/0.06/0.14, d 0.2/0.5/0.8), so a value and its equivalent in the other metric label consistently.
- The post-hoc effect-size label is now taken from the contrast's partial eta-squared (matching the MATLAB `emm` post-hoc), not from the SMD; both `SMD` and `etaSqp` are still reported as numeric columns.

## [1.11.1] - 2026-07-29

### Bugs

- Post-hoc effect sizes are no longer degenerate for GLMMs. The pairwise SMD (Cohen's d) was computed as `2·|t|/√df`, but the non-Gaussian families are tested asymptotically (df = Inf), so every SMD collapsed to exactly 0. The SMD is now derived from the contrast `F = t²` with the residual df `n − p` as the denominator when the test df is infinite (finite Satterthwaite/Kenward-Roger df are still used for the Gaussian LMMs), reproducing the MATLAB kbstat convention so it is non-zero and interpretable. A partial eta-squared column (`etaSqp`) is added to the post-hoc table alongside it, computed from the same `F` and df. A `Summary.txt` note cautions that `n − p` treats the repeated within-subject observations as independent, so these effect sizes are liberal (approximate upper bounds); the p-values and EMMs are unaffected.
- The post-hoc `diff` column (the response-scale difference of the two EMMs) came out `NaN` whenever a factor level name contained a special character (e.g. the hyphen in `Med-ADHD`): emmeans wraps such names in parentheses in the contrast label, and the level parser did not strip them, so the EMM lookup missed. The parser now strips a surrounding parenthesis pair, so `diff` is computed and the `<factor>_1` / `<factor>_2` columns show the bare level names.

## [1.11.0] - 2026-07-25

### Features

- **Control how diagnostic outliers are shown (`diagnostic_outliers`).** The diagnostic distribution panels (histogram and Q-Q) use DHARMa quantile residuals; observations outside the entire simulated range have no proper quantile and DHARMa caps them at z = ±7, where they pile up as an edge spike in the histogram and a horizontal band in the Q-Q. New `options.diagnostic_outliers` controls their display: `'text'` (default) omits the capped points and annotates the count/percentage at the bottom of each panel on a semi-transparent white background (so the axes autoscale to the bulk of the residuals), `'plot'` draws them in a distinct colour (orange), and `'hide'` omits them silently. This is a model-misfit / heavy-tail flag, deliberately kept as a separate concept (and separate colour) from the pre-fit data outliers.

### Changes

- **Renamed `show_outliers` to `data_outliers`** and gave it the same vocabulary as `diagnostic_outliers` (`'plot'` | `'text'` | `'hide'`), so the two outlier-display options are fully analogous. `show_outliers` still works as a deprecated alias (emits a `DeprecationWarning`), and its old value `'none'` maps to the new `'hide'`. Default is unchanged (`'text'`).

## [1.10.0] - 2026-07-25

### Features

- **Spearman correlations.** New `options.correlation_method` (`'pearson'`, the default, or `'spearman'`) selects the method for both the raw and the partial correlations; Spearman partial correlations are the partial correlations computed on the ranks. The figure titles name the method.
- **Adjust correlations for covariates.** New `options.correlation_control` names variable(s) (e.g. `'Age'`) to partial out of every correlation before it is computed: the raw table then reports adjusted correlations and the partial table additionally controls for them. The control variables are kept out of the matrix, and the figure titles note the adjustment (e.g. "Partial Correlations (adjusted for Age)").
- **Per-group dispersion for the glmmTMB families.** New `options.dispersion` sets the right-hand side of glmmTMB's `dispformula` (e.g. `'JointGroup'` → `dispformula = ~ JointGroup`), letting the dispersion vary by a factor instead of the default constant `~1`. Useful when pooled groups differ widely in scale/scatter; ignored for gaussian (LM/LMM) models.
- **Random-slope covariance structure with an auto-fallback (`slope_correlated`).** New `options.slope_correlated` accepts `True`, `False`, or `'auto'` (the default). `True` keeps the full covariance among the random intercept and slopes, `(1 + s | id)`. `False` fits an uncorrelated (diagonal) structure — glmmTMB `diag(1 + s | id)` for the non-gaussian families, lme4's `(1 + s || id)` for gaussian LMMs — which drops the intercept-slope and slope-slope correlation parameters. `'auto'` fits the correlated structure first and refits with the diagonal one only when that fit is singular (non-positive-definite Hessian, boundary correlation, non-finite likelihood, or an lme4 fit failure), so it keeps the richer model where the data support it and escapes the singular, NaN-likelihood fit a many-level factor slope can otherwise produce. The structure actually used is reported in `Summary.txt` (a "Random-slope structure" line) and, when it departs from the plain correlated default, in the diagnostics-plot footer; an `'auto'` fallback is flagged as auto-selected, and an explicit `slope_correlated=True` that comes back singular warns and points at `'auto'`/`False`. Ignored when an explicit `formula` is supplied.

### Changes

- **`show_outliers` now defaults to `'text'`** (was `'plot'`). Flagged outliers are annotated as a count and percentage at the bottom of each data-plot panel instead of drawn as red X markers, so the y-axis autoscales to the non-outlier data by default rather than being squashed by extreme points. Pass `show_outliers='plot'` for the old red-X behaviour or `'none'` to omit them entirely.
- **Tuned default plot font sizes and unified title/label weight.** Panel/subplot titles and axis labels 14 → 13, the figure suptitle's starting size 17 → 15 (it still auto-shrinks to fit the plot width), and the outlier-count annotation 9 → 10; tick numbers unchanged at 11. Titles and axis labels are now bold house-wide (via `axes.titleweight`/`axes.labelweight`), so the diagnostics and profile plots match the data plots; numeric tick labels stay regular weight and the correlation grids (which set their own text weight) are unaffected.
- **Redesigned the correlation figures for a compact, unified look.** The correlation and partial-correlation tables are now a tight lower-triangle matrix with the variable names on the diagonal, replacing the larger layout with separate header bands. The scatter output is now a lower-triangle scatter-plot matrix that mirrors that table — variable names on the diagonal and a mini scatter with regression line and the r-value in each cell — instead of a square grid of all pairwise panels. The r-values sit on a semi-transparent white background so they stay readable over the points.

### Bugs

- Partial-correlation p-values now use the correct degrees of freedom, `df = n - 2 - g` (g = number of conditioning variables), instead of `n - 2`; the coefficients are unchanged.
- `Summary.txt` no longer lists the fit statistics twice for glmmTMB models (previously once rounded via the AIC/BIC/logLik attributes, then again at full precision from the model's fit-stats table); AIC/BIC/logLik/deviance are now printed once, each to 3 decimals.
- The formula parser no longer mistakes the intercept controls `0` and `1` for random-slope variables. A random-effects term like `(0 + A | id)` or `(1 + A | id)` previously parsed `0`/`1` as slopes and failed validation with `Random slope variable(s) ['0'] not found in fixed-effect factors`; they are now recognised as intercept controls and stripped from the slope list. The parser also accepts the diagonal syntaxes `diag(1 + A | id)` (glmmTMB) and `(1 + A || id)` (lme4).

### Documentation

- Added Demo 17 (`dispersion` / `dispformula`): a Gamma model on `ToothGrowth` fitted with constant vs by-dose dispersion, showing the lower AIC when groups differ in relative scatter. Script, notebook, README table/list, and Colab playground entry.
- STATISTICAL_NOTES.md: documented the Spearman correlation option and covariate adjustment (with the g-adjusted partial-correlation degrees of freedom) in the correlation section, and added a "Per-group dispersion (`dispformula`)" section (Demo 17).
- README.md and STATISTICAL_NOTES.md document `slope_correlated`: the README options table gains a row, and the "Random slopes in GLMMs" section explains the correlated/diagonal/`'auto'` choice, when the correlated slope goes singular, and the lme4 `||` caveat (it does not decorrelate the levels within a categorical slope, unlike glmmTMB's `diag()`).

### Known limitations

- **Diagonal random slopes for a *categorical* factor in a gaussian LMM are not fully uncorrelated.** `slope_correlated=False`/`'auto'` emits lme4's `(1 + s || id)` for gaussian LMMs, but lme4's `||` decorrelates only the intercept from the slope and distinct slope terms — it does *not* drop the correlations among the levels *within* a single categorical slope (it expands to `(1 | id) + (0 + factor | id)`, keeping that block correlated). glmmTMB's `diag()` decorrelates fully, so the non-gaussian families are unaffected; only gaussian LMMs with a categorical random slope see the limitation. A genuinely diagonal structure there needs the factor expanded into indicator terms (afex-style `expand_re = TRUE`), which is not done automatically. Possible future work: either that expansion, or a small engine-override option to fit a gaussian model via glmmTMB (which would gain the correct `diag()` at the cost of lme4's Kenward-Roger / Satterthwaite denominator df). Deferred until a real case needs it.

## [1.9.0] - 2026-07-17

### Features

- **Level-wise profile analysis** via `options.profile_across`. Names an ordered categorical factor and, on top of the usual analyses, profiles how the factor(s) interacting with it behave across its levels: per-level pairwise contrasts from the single fitted model (Layer 1), and the interaction as both a factor omnibus and a focused 1-df linear trend across the ordered positions (Layer 2 — a position-weighted contrast that honours real numeric spacing and reduces to the equal-spaced polynomial trend). Writes `LevelProfile.xlsx` and a profile plot; new `ModelResult` fields. Demo 16, README, and STATISTICAL_NOTES added.
- **Bundled fonts, cross-platform.** kbstatpy now ships and registers Latin Modern Sans, TeX Gyre Heros, and TeX Gyre Termes (GUST Font License) on import, so plots render identically on every platform with no system font install. A request for `'Helvetica'`/`'Arial'` or `'Times'` keeps the real font on macOS/Windows and falls back to its bundled clone (TeX Gyre Heros / Termes) on Linux/Colab, instead of dropping to DejaVu Sans. Added friendly case-insensitive `options.font` aliases (`'Sans'`/`'Modern'` → Latin Modern Sans, `'Times'` → Times New Roman) and case-insensitive family matching.
- **Run the demos on Google Colab.** Added `demos/kbstatpy_colab.ipynb` (a one-click playground) and per-demo "Open in Colab" links; each demo notebook self-installs via `demos/colab_setup.sh` (clones the repo, installs kbstatpy and the R packages, links the datasets). README "Open in Colab" badge and section.

### Changes

- Enlarged the data, diagnostics, and profile plots' label/title/tick sizes (axis labels and panel titles 14, tick numbers 11, figure title 17); significance brackets unchanged, and the dense correlation grids keep their own sizes.
- The descriptive-statistics table now uses `observed=True`, reporting only the factor-level combinations that occur rather than the full cartesian product padded with empty `N=0` cells.
- When the body font resolves to Latin Modern Sans, `mathtext.fontset='cm'` so in-plot math (e.g. the Scale-Location √ label) matches the LaTeX look.

### Bugs

- Fixed a matplotlib "font family not found" warning for plot titles on platforms without Helvetica: the title font now resolves to an installed family, like the body font.
- Silenced a pandas `FutureWarning` from the categorical groupby (`observed=True`).
- Concise `__repr__` for `Output`/`ModelResult`/`CorrelationResult` (the dataclass default dumped the full summary text, DataFrames, and figure objects).

### Documentation

- STATISTICAL_NOTES: added Level-wise profile analysis (Demo 16) and Comparing any factor per cell (Demo 15), plus a note on why the two-level post-hoc is still reported.
- README: the `profile_across` option and section, bundled-font behaviour and aliases, the Colab section, and demo 16.

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
