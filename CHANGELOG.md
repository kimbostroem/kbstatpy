# Changes

## [1.15.5] - 2026-09-09

### Changes

- **Shortened the changelog entries from 1.9.0 onward, and the GitHub releases taken from them.** They had grown to the point of being unreadable -- 1.10.0 ran to 991 words, 1.15.3 to 689 -- because `CLAUDE.md` asked for an entry written "for a reader who has not seen the diff" and set no length against it. Each change is now a headline sentence plus two or three of substance, with the deeper reasoning folded into a collapsed `<details>` block where it is worth keeping. Visible text across the 24 rewritten entries fell from about 6800 words to about 4000; nothing was deleted, only folded or compressed. Entries before 1.9.0 predate the verbose style and are untouched. `CLAUDE.md` now states the length limit and shows the folding pattern, so new entries follow it.

## [1.15.4] - 2026-09-09

### Fixed

- **A factual error in the 1.15.3 changelog.** It claimed the R library cache "had never hit" because `setup-r` overrides `R_LIBS_USER`. The override is real; the conclusion was not. `${{ env.R_LIBS_USER }}` picks up the value `setup-r` exports, so the cache path had been correct all along.

  <details><summary>What the empty cache list actually meant</summary>

  `actions/cache` does not save when a job fails, and no `install` job had succeeded on any platform since CI was added in 1.15.0: Linux on `DHARMa`, macOS and Windows on the missing PyYAML. Caches appeared the moment jobs started passing, one per successful job. The 1.15.3 change itself is unaffected, since both spellings name the same directory.
  </details>

## [1.15.3] - 2026-09-09

### Fixed

- **The Linux R package install failed on `DHARMa`, and the installer could not say why.** Both `ubuntu-latest` jobs had been red since 1.15.0. `install.packages()` ran with `quiet = TRUE`, so seventeen minutes of compilation produced no output and the guidance pointed at an error nobody could see. The install now runs with `options(warn = 1)` and without `quiet`, which identified the cause at once: missing `curl/curl.h` and `uv.h` headers.

  <details><summary>Why <code>DHARMa</code> alone, out of seventeen packages</summary>

  `curl` and `fs` could not configure, and the failure cascaded through `httr`, `sass`, `bslib`, `rmarkdown`, `shiny`, `htmlwidgets`, `qgam`, `plotly` and `gap` to `DHARMa` -- twelve packages, exactly the "There were 12 warnings" that had been reported without names.

  Of the ~130 packages in the recursive dependency closure, five declare system requirements: `curl` (libcurl, OpenSSL), `openssl` (OpenSSL), `fs` (libuv), `httpuv` (zlib) and `stringi` (ICU). Every one but `stringi` is reached only through `DHARMa`, via `gap` -> `plotly` -> `httr` -> `curl` and `qgam` -> `shiny` -> `bslib` -> `sass` -> `fs`. Every other top-level package stays inside pure R and C++. So a missing development header in the curl/libuv family presents as a single `DHARMa` failure with no visible connection to networking or the filesystem. Look there, not for a `DHARMa` bug.
  </details>

- **`install.sh` hardcoded `repos = "https://cloud.r-project.org"`, which is why anything was compiling.** CRAN serves Linux packages as source only, and passing `repos =` explicitly overrode the binary repository `ci.yml` had already configured through `use-public-rspm: true`, so that setting had never once taken effect. Both installers now use whatever repositories R is configured with, fall back to cloud CRAN when there are none, and print which they used.

- **The failure guidance names the system libraries, per distribution.** It previously listed R's build tooling only and referred to "the error above" that `quiet = TRUE` had suppressed. It now gives toolchain and library commands for the detected platform, says the failing package's own `[ANTICONF]`/`[CONFIGURE]` block is more trustworthy than any list, and points at Posit Package Manager as the way to not compile at all. Documented in the README.

- **The R library cache path is spelled out** as `${{ runner.temp }}/Library` rather than inferred from `${{ env.R_LIBS_USER }}`. The same directory, no longer disguised as a decision this workflow makes.

## [1.15.2] - 2026-09-09

### Fixed

- **CI failed on every platform because the test suite needs PyYAML and nothing installed it.** `tests/test_citation_metadata.py` validates `CITATION.cff` as real YAML, which a regex could not do, but PyYAML is not a runtime dependency, so neither installer pulls it in and the requirement existed only on the maintainer's machine. On the runners the first test file died with `ModuleNotFoundError: No module named 'yaml'` and took the whole `Test suite` step down with it. It is now a `test` extra in `pyproject.toml`, installed by CI, and the import raises a message naming the extra instead of a bare traceback.

  <details><summary>Why this mattered more than a missing package usually does</summary>

  The suite had been red since 1.15.0 for a reason unrelated to anything it guards, which is the worst state for a signal to be in: the Windows job was reporting failure at the same time as it was proving native Windows support worked. Every other test file passed on both affected platforms.
  </details>

## [1.15.1] - 2026-09-09

### Fixed

- **`install.ps1` aborted on the Microsoft Store `python.exe` placeholder instead of trying the next interpreter.** A Windows user running the documented command got a `NativeCommandError` at step 1. Rejecting that placeholder is exactly what the candidate loop was written to do, but PowerShell turns anything a native executable writes to stderr into an error record, and under `$ErrorActionPreference = 'Stop'` that record is terminating. Every external call now goes through a helper that relaxes the preference in its own function scope, leaving the rest of the script strict.

  <details><summary>Why <code>2&gt;$null</code> did not help, and why CI missed it</summary>

  The error record is raised before the redirection discards the text, so the probe's `2>$null` was no protection. The same rule would have killed the R package step on a cold machine, since R writes its download progress to stderr. CI caught neither, because the runner's `python` is real and its R library was cached, so nothing wrote to stderr there. `tests/test_install_ps1.py` now fails if a later edit reintroduces a direct call or drops the reset -- the only automated guard possible for a script that cannot be executed on the maintainer's platform.
  </details>

### Changes

- **The installer uses an activated conda environment or venv, and takes a `-Python` argument.** `CONDA_PREFIX` and `VIRTUAL_ENV` are read ahead of `PATH`, which also removes the failure above for anyone with an environment active. `-Python` accepts a path to `python.exe`, an environment folder, or a command name, and is never silently substituted: if it cannot be used, the installer stops.

- **It prints the interpreter it is about to write to, and the environment it belongs to.** On a machine carrying Anaconda, a python.org install and the Store alias at once, `Python 3.12 found` does not say where the packages went. It also warns when an environment is active but the chosen interpreter lies outside it, notes when the target is conda `base`, and says what to do when nothing is active. Only the Python side is per-environment; the R packages stay shared.

- **The Store placeholder is named in the error when no Python is found**, with the two ways out, rather than a bare `no working Python found`. The README's Windows section quotes the error verbatim so a search for it lands on the fix.

## [1.15.0] - 2026-08-26

### Changes

- **Native Windows is supported, with an `install.ps1` installer.** The README previously directed Windows users to WSL because `rpy2` could not be installed reliably there; that has not been true for some time. Nothing compiles: `rpy2` installs from a `win_amd64` wheel and CRAN serves the R packages as Windows binaries, so Rtools is not required. WSL remains documented as a fallback.

  <details><summary>What changed upstream, and why kbstatpy needed no code changes</summary>

  `rpy2-rinterface` publishes `win_amd64` wheels for CPython 3.9 through 3.14, and `rpy2` 3.6 carries deliberate Windows support, calling `os.add_dll_directory()` on R's DLL directory and handling both the pre-4.2 `bin\x64` layout and the merged `bin\` of R >= 4.2. kbstatpy itself shells out to nothing, spawns no processes, and builds every path through `os.path.join`.
  </details>

- **`install.ps1` handles three things that do not arise on macOS or Linux.** The Windows R installer does not add R to `PATH`, so R is found through the registry. A non-interactive `Rscript` cannot answer R's "use a personal library?" prompt, so the user library is created up front. And a failure to load `R.dll` surfaces at *import*, long before any statistics run, so the bridge is verified before success is reported.

- **Both installers enforce the version minimums they only used to print.** `install.sh` computed `PYTHON_VERSION` and `R_VERSION` and never compared them against anything, so Python 3.9 or R 4.3 produced a confusing failure further down. Both now stop with the offending version and name the package-manager command or download page for the platform.

- **Both installers detect R packages that failed to install.** `install.packages()` only warns and `Rscript` still exits 0, so a missing `glmmTMB` was reported as installed and then surfaced as an unrelated-looking R error during the first analysis. They now re-check `installed.packages()` and fail with the names.

### Fixed

- **Variable names and factor levels are sanitised before they are used in output paths.** Levels like `5 mg/kg`, `50%` and `pre:post` are ordinary data cells, and `save()` puts them into directory and file names. Sanitising happens on every platform, and names already safe are returned untouched, so no existing output path moves.

  <details><summary>Why macOS hid this</summary>

  Windows forbids `< > : " / \ | ? *` in a path component, refuses the reserved DOS device names (`NUL`, `CON`, `COM1`, ...) whatever the extension, and silently strips trailing dots and spaces. On macOS only `/` is special, and it does not raise either: `os.path.join(out_dir, 'Force/BW')` quietly nests a directory, so the results tree silently differed from the one the user asked for, and the same analysis produced a different layout per operating system.
  </details>

- **`CLAUDE.md` claimed that two of the tests need no R.** They do, as does every other test: `kbstatpy/__init__.py` imports `.kbstat`, which calls `ro.r('emmeans::emm_options(...)')` at module level, so `from kbstatpy import __version__` is enough to start R.

### Added

- **A CI workflow, the repository's first.** It runs the real installer on Windows, Linux (Python 3.10 and 3.12) and macOS, then the test suite and all demos, and uploads the demo output. A separate job lints `install.ps1` against Windows PowerShell 5.1 -- the engine it targets, and one no runner uses by default -- via PSScriptAnalyzer's compatibility profiles, which catch the PowerShell 7 syntax (`??`, ternaries, `&&` chains) that a plain parse would accept.

- **`tests/test_path_sanitising.py`**, covering the forbidden characters, the reserved device names, trailing dots and spaces, the empty-after-sanitising fallback, and the property that one component in yields one component out.

## [1.14.2] - 2026-08-25

### Changes

- **Dropped the references to the MATLAB library kbstatpy descends from where they only recorded provenance.** `show_emm_lines` was documented as "ported from `plotLines`" in the option comment, the README table and the test docstring; a reader of this library is not expected to know that software, so the phrase said nothing about what the option does. The 1.14.0 entry and its published release notes lost the same phrase.
- The references that carry statistical reasoning are deliberately kept -- the seven-bin effect-size labels and the `df = Inf` choice for GLMMs would look arbitrary or wrong without them. See `STATISTICAL_NOTES.md`.

## [1.14.1] - 2026-08-25

### Changes

- **New demo 18, `demo_18_plot_annotations.py`,** for the two plot-annotation options 1.14.0 added. It refits demo 3's crossed two-way design with the factors swapped, so nothing about the model is new and the demo is purely about presentation. The notebook runs the same model three times, bare then annotated then with solid lines, so the styles can be compared inline.
- **`demo_11_glmm_binomial.py` sets `show_group_size = True`.** Its bar plot printed group counts automatically until 1.14.0 made them opt-in, so the demo had silently lost them; its cells are genuinely unbalanced, which is exactly where the counts are worth showing.
- README and the Colab playground list the new demo. The README's demo count was also stale (sixteen against seventeen listed) and now reads eighteen.

## [1.14.0] - 2026-08-25

### Changes

- **New option `show_emm_lines`: a horizontal reference line at each plotted group's EMM, across the whole panel in that group's own colour.** The white dot already marks the EMM, but reading one group's level against the *others* meant comparing dot heights by eye. The option doubles as the line style: `True` gives the default dotted line, or pass `'-'`, `'--'`, `':'`, `'-.'`. Default `False`.

  <details><summary>Why dotted is the default</summary>

  Dotted recedes furthest behind the violins and the significance brackets, so a line crossing a violin cannot be mistaken for plotted data. Solid reads calmest and makes the group colours easiest to attribute, at the cost of looking more like content than like a guide. Each facet panel uses its own EMMs, and where none is available the line follows the same median fallback as the dot. Applies to violin and bar style alike.
  </details>

- **New option `show_group_size`: label each plotted group with its observation count (`n=12`).** *This changes existing output:* the counts used to be drawn unconditionally in bar style and were unavailable for violins; they are now off by default in both. The label is anchored to the top of what the group actually renders, so it never lands inside the group's own body.

### Fixed

- **A significance bracket could be drawn through the `n=` label beneath it in violin plots.** The gap is now measured in points once the y-limits are final, and only stacks that came out tighter than 5 pt are lifted, so panels that already clear their content are untouched. Measured on the demo figures: violin clearance 0.3 px -> 5.8 px, bar unchanged at 6.5 px.

  <details><summary>The interaction that caused it</summary>

  The bracket stack is anchored above the tallest thing a panel has rendered, spaced in units of the y-range *as it stood before the stack expanded the axis*. A label's height is fixed in points, so on the taller axis it covers more data units and grows up into the bracket that was placed to clear it: a three-bracket stack expands the axis by roughly 40 %, which reduced a clearance of about 4 pt to under one pixel. Bar plots never showed it, their limits being pinned to 0..1.15.
  </details>

- **`remove_outliers_prefit='off'` switched outlier removal ON, and `slope_correlated='false'` fitted the correlated structure.** Both flags were read as raw truthiness, and a non-empty string is truthy, so any string spelling of "off" meant its opposite, silently. All on/off options now go through one parser (`_as_flag`) accepting `True`/`False`, `'true'`/`'false'`, `'on'`/`'off'`, `'yes'`/`'no'` and `'none'`, case- and whitespace-insensitive, with `'auto'` kept for `slope_correlated`. An unrecognised value now raises, so a typo like `'offf'` is a visible error rather than a silent inversion.
- `tests/test_emm_lines.py` and `tests/test_group_size_labels.py`.

## [1.13.6] - 2026-07-31

### Fixed

- **`CITATION.cff` was six minor versions stale and not valid CFF 1.2.0.** It declared `version: 1.7.1` against a released 1.13.5, because nothing imports the file. It also lacked the required `message` key, gave a `type` the schema does not allow, and carried a CodeMeta key CFF does not define, so GitHub's "Cite this repository" panel had nothing valid to render and the invalid keys were dropped rather than reported. The file is now valid and current.
- **`tests/test_citation_metadata.py` keeps it that way.** It asserts that the three version sources agree -- `kbstatpy.__version__`, the newest `CHANGELOG.md` heading, and `CITATION.cff` -- and that the file stays schema-valid, so a release that forgets any of them fails the suite.

### Changes

- `CLAUDE.md` records the release procedure the repository already follows, which until now had to be reconstructed from the git history.

## [1.13.5] - 2026-07-31

### Fixed

- **`Summary.txt` reported the row count of the input table, not the number of observations the model was fitted on.** On a 7100-row table with 465 outliers flagged, it reported 7100 for a fit that used 6635. The count now comes from the fitted model itself, and whatever was held out is named: `6635 (of 7100: 465 excluded as outliers)`. Clean data still reports a bare count.

  <details><summary>Why this mattered beyond the number itself</summary>

  It showed up when cross-checking against the MATLAB kbstat library, which reports the post-removal count: the two looked like they disagreed on the data even where they agreed on the model and the estimates. Separately, the `etaSqp` and `SMD` columns substitute n for an infinite `df2` and took it from the outlier-excluded frame, which still contains rows R dropped as missing; they now use the same count as the fit, so the effect sizes and the reported n cannot drift apart.
  </details>

- `tests/test_summary_n_obs.py`.

## [1.13.4] - 2026-07-30

### Fixed

- **The title of a correlation figure was cut off in the PDF when the matrix was small.** Both grids size their canvas from the matrix and its diagonal labels, ignoring the title. The title is now measured against the canvas: it scales down towards the available width (to a floor of 0.75x), and whatever still does not fit widens the canvas, the extra split evenly so the matrix stays centred. Wide grids are unchanged.

  <details><summary>Why the PNG hid it</summary>

  A five-variable partial-correlation table came out under 3 in wide while its subtitle, `(residuals after removing all other variables)`, needs about 5 in at 13 pt; the PDF, whose canvas is fixed, lost both ends of it. The PNG is saved with `bbox_inches='tight'` and was therefore unaffected.
  </details>

- `tests/test_correlation_title_fits.py`. Layout only, so it needs neither R nor glmmTMB.

### Changes

- The subtitle of a correlation figure is 11 pt against the 13 pt of the title, so it reads as a subtitle rather than a second heading.
- The frame marking a significant cell is 1.2 pt rather than 1.6 pt; 1.13.3 introduced it and erred on the heavy side.
- **`STATISTICAL_NOTES.md` and the demo 5 description explain how to read the raw and partial tables together**, since it is the difference between them that carries the message.

  <details><summary>What conditioning can and cannot tell you</summary>

  A high raw correlation that collapses in the partial marks redundancy within the variable set; a partial that stays high marks an association the other variables do not capture; a low raw correlation that grows in the partial marks suppression.

  Partial correlation removes what is linearly predictable from the conditioning set and has no notion of cause, so it removes a spurious association for a confounder, **creates** one for a collider, and erases a real effect for a mediator. Confounder and mediator produce the same signature with opposite meanings, and no amount of data distinguishes them, so with the conditioning set being simply all remaining variables the partials are best read as a statement about redundancy rather than about mechanism.
  </details>

## [1.13.3] - 2026-07-30

### Changes

- **Cells whose correlation coefficient is significant now carry a heavier frame**, coloured by the direction of the correlation (red for positive, blue for negative, matching the r-value's own colouring). Significance was previously signalled only by the colour and weight of the r-value printed inside the cell, which is easy to miss in a large grid -- the sixteen-variable case has 120 cells. Non-significant cells keep the original light hairline.

## [1.13.2] - 2026-07-30

### Changes

- **Raised the type floor and shrank the cell for large correlation matrices**, in both the coloured table and the scatter grid. Past roughly twelve variables the text had become small relative to its box and to the figure: at sixteen variables the table drew 5 pt numbers in a 0.55 in cell, and now uses 7 pt in a 0.48 in cell, so the numbers occupy 20 % of the cell instead of 13 % and the figure comes out narrower. Twelve variables or fewer is unchanged apart from the raised floor.

## [1.13.1] - 2026-07-30

### Changes

- **`LevelProfileContrast` draws the fitted trend line for *every* significant trend.** 1.13.0 suppressed it where the level estimates were far from collinear, on the grounds that a straight line through a rise-then-fall pattern asserts a gradient the data do not show. That was the wrong trade: it hid real results, since a contrast with a significant trend could end up with no line at all. The estimates and their confidence intervals are plotted regardless, so a departure from the line is visible as points sitting off it. `PROFILE_COLLINEAR_TOL` is gone.

  <details><summary>The two alternatives that were rejected</summary>

  Joining the estimates instead shows the observed shape but not the tested quantity, and degenerates into an uninterpretable zigzag for more than three levels. No departure-from-linearity statistic is reported because with k levels the departure carries k-2 df, so isolating the quadratic term would be arbitrary for k > 3, and the diffuse alternative is already covered by the factor omnibus. Recorded in `STATISTICAL_NOTES.md`.
  </details>

## [1.13.0] - 2026-07-30

### Added

- **A second figure for `profile_across`: `LevelProfileContrast`.** The existing `LevelProfile` plots the absolute EMMs per level, but the Layer-2 statistic is a linear trend of the *contrast between* those levels, which absolute EMMs do not display and which is easily invisible when the levels differ greatly in magnitude. The new figure plots the contrast itself with 95 % confidence intervals from `emmeans`' link-scale estimates: ratios on a logarithmic axis for a log link, otherwise differences on a linear axis. Available as `result.fig_profile_contrast`.
- The fitted 1-df trend line is overlaid only where the level estimates are close to collinear, since a 1-df linear contrast can be significant on a rise-then-fall pattern by weighting the endpoints. (Reversed in 1.13.1.)
- `profile_across_result` gained `per_level_link`, the `emmeans` contrast table on the link scale, which the new figure consumes.
- `tests/test_profile_contrast.py`.

### Fixed

- **Trend rows carried unlabelled integer codes for factors with three or more levels.** `emmeans` returns integer codes rather than labels in the `*_pairwise` column for this model class, so `LevelProfile.xlsx` showed `contrast` values of `1`, `2`, `3` and the trend rows could not be joined to the contrasts they describe. The labels are now fetched from `pairs()` on the same grid, which also keeps the ordering `emmeans`' own.

## [1.12.1] - 2026-07-30

### Changes

- **With `y_scale = 'log'`, the y-axis label carries a `(log scale)` note**, on the data plots and the profile plot. The tick labels show untransformed values, so previously nothing but the tick spacing revealed that the axis was logarithmic. This mirrors the existing `(original scale)` note used for `y_transform`, and is keyed to the scale actually applied, so a fallback to a linear axis is never labelled as log.

## [1.12.0] - 2026-07-30

### Added

- **`options.y_scale`** (`'linear'` default, or `'log'`) sets the y-axis scale of the data plots and the profile plot. Significance brackets and the y-limit padding are computed in log space, so their spacing stays even instead of drifting or escaping the axis. Strictly positive values are required: because matplotlib silently drops `y <= 0` on a log axis, a non-positive value falls back to a linear axis with a warning rather than quietly deleting points. Diagnostic and correlation figures are never rescaled.

  <details><summary>When a log axis is the readable choice</summary>

  With a shared linear axis, panels spanning orders of magnitude collapse into slivers even when they carry the largest effects. It also suits gamma/log-link models, where a constant ratio becomes a constant distance and the gaps between profile lines therefore *are* the group ratios.
  </details>

- `tests/test_y_scale_log.py`.

### Changes

- The profile plot no longer draws an x-axis label. Its tick labels are the profiled factor's own level names and the title already names the factor, so the label only repeated it.

## [1.11.4] - 2026-07-30

### Fixed

- **`correlate()` partial correlations had inverted signs.** Each variable was residualised on *all the other* correlation variables, with its eventual partner still in the predictor set, which yields identically minus the partial correlation. Magnitudes were correct, so the error was easy to miss, and it produced strongly negative "partial correlations" between measures that are near-duplicates. Both members of a pair are now residualised on the same conditioning set, excluding the pair itself.

  <details><summary>The identity, and what else this touched</summary>

  For a pair (i, j) the old construction gives `corr(resid_i | all others, resid_j | all others)`, which is minus the partial correlation by the precision-matrix identity `partial_r(i,j) = -P_ij / sqrt(P_ii * P_jj)` with `P = inv(cov)`. The partial scatter grid had the same cause and is fixed with it, now plotting the pair-specific residuals so the plotted slope agrees with the labelled coefficient. `STATISTICAL_NOTES.md` described the incorrect construction and is corrected.
  </details>

### Added

- `tests/test_partial_correlation_sign.py` -- checks the coefficients against the precision-matrix definition, signs included, plus a collider case that must come out negative, a redundancy case that must stay positive, and a `correlation_control` case. Verified to fail on the pre-1.11.4 code.

### Note

Any `PartialCorrelation.xlsx` / `.png` produced by 1.10.0 through 1.11.3 has inverted partial correlations and should be regenerated. Raw and covariate-adjusted correlations are unaffected.

## [1.11.3] - 2026-07-29

### Changes

- **The correlation effect-size label now uses the same seven-bin scheme as the eta-squared and d labels**, with the r/rho Cohen anchors 0.1/0.3/0.5. It was the last effect-size labeler still on the old four-bin scheme, so all of kbstatpy's labels now share one ruler.

## [1.11.2] - 2026-07-29

### Changes

- **Effect-size labels use a single seven-bin scheme for both partial eta-squared and Cohen's d** (`very small` through `very large`). Previously the eta-squared labeler used four bins while the d labeler used seven with slightly different thresholds, so the ANOVA and post-hoc tables could describe the same magnitude with different words. Both now derive from a shared `_cohen_label` with the metric's own anchors (eta-squared 0.01/0.06/0.14, d 0.2/0.5/0.8).
- The post-hoc effect-size label is taken from the contrast's partial eta-squared rather than the SMD; both are still reported as numeric columns.

## [1.11.1] - 2026-07-29

### Bugs

- **Post-hoc effect sizes are no longer degenerate for GLMMs.** The pairwise SMD was computed as `2*|t|/sqrt(df)`, but the non-Gaussian families are tested asymptotically (df = Inf), so every SMD collapsed to exactly 0. It is now derived from the contrast `F = t^2` with the residual df `n - p` when the test df is infinite, and a partial eta-squared column (`etaSqp`) is added alongside it.

  <details><summary>The caveat this carries</summary>

  Finite Satterthwaite/Kenward-Roger df are still used for the Gaussian LMMs. `n - p` treats the repeated within-subject observations as independent, so these effect sizes are liberal -- approximate upper bounds -- which `Summary.txt` now notes. The p-values and EMMs are unaffected.
  </details>

- **The post-hoc `diff` column came out `NaN` when a factor level name contained a special character** (for example the hyphen in `Med-ADHD`): emmeans wraps such names in parentheses in the contrast label, and the level parser did not strip them, so the EMM lookup missed. The parser now strips a surrounding parenthesis pair.

## [1.11.0] - 2026-07-25

### Features

- **Control how diagnostic outliers are shown (`diagnostic_outliers`).** `'text'` (the default) omits the capped points and annotates the count and percentage at the bottom of each panel, `'plot'` draws them in orange, and `'hide'` omits them silently.

  <details><summary>What is being capped, and why it is a separate concept</summary>

  The diagnostic distribution panels use DHARMa quantile residuals; observations outside the entire simulated range have no proper quantile and DHARMa caps them at z = +/-7, where they pile up as an edge spike in the histogram and a horizontal band in the Q-Q. Omitting them lets the axes autoscale to the bulk of the residuals. This is a model-misfit / heavy-tail flag, deliberately kept as a separate concept, and a separate colour, from the pre-fit data outliers.
  </details>

### Changes

- **Renamed `show_outliers` to `data_outliers`**, with the same vocabulary as `diagnostic_outliers` (`'plot'` | `'text'` | `'hide'`), so the two outlier-display options are fully analogous. `show_outliers` still works as a deprecated alias, and its old value `'none'` maps to `'hide'`. The default is unchanged.

## [1.10.0] - 2026-07-25

### Features

- **Spearman correlations.** New `options.correlation_method` (`'pearson'` default, or `'spearman'`) selects the method for both the raw and the partial correlations; the Spearman partials are computed on the ranks. The figure titles name the method.
- **Adjust correlations for covariates.** New `options.correlation_control` names variables (e.g. `'Age'`) to partial out of every correlation before it is computed. The control variables are kept out of the matrix and the figure titles note the adjustment.
- **Per-group dispersion for the glmmTMB families.** New `options.dispersion` sets the right-hand side of glmmTMB's `dispformula`, letting dispersion vary by a factor instead of the default constant `~1`. Useful when pooled groups differ widely in scatter; ignored for gaussian models.
- **Random-slope covariance structure with an auto-fallback (`slope_correlated`).** `True` keeps the full covariance `(1 + s | id)`, `False` fits an uncorrelated diagonal structure, and `'auto'` (the default) fits the correlated structure first and refits diagonally only when that fit is singular. The structure actually used is reported in `Summary.txt`.

  <details><summary>What counts as singular, and what is reported where</summary>

  Diagonal is glmmTMB `diag(1 + s | id)` for the non-gaussian families and lme4's `(1 + s || id)` for gaussian LMMs, dropping the intercept-slope and slope-slope correlation parameters. `'auto'` refits on a non-positive-definite Hessian, a boundary correlation, a non-finite likelihood, or an lme4 fit failure, so it keeps the richer model where the data support it and escapes the singular, NaN-likelihood fit a many-level factor slope can otherwise produce. A departure from the correlated default also appears in the diagnostics-plot footer; an `'auto'` fallback is flagged as auto-selected, and an explicit `slope_correlated=True` that comes back singular warns and points at `'auto'`/`False`. Ignored when an explicit `formula` is supplied.
  </details>

### Changes

- **`show_outliers` now defaults to `'text'`** (was `'plot'`), so the y-axis autoscales to the non-outlier data instead of being squashed by extreme points. Pass `'plot'` for the old red-X behaviour or `'none'` to omit them.
- **Tuned the default plot font sizes and unified title/label weight.** Panel titles and axis labels 14 -> 13, the suptitle's starting size 17 -> 15, the outlier annotation 9 -> 10; ticks unchanged at 11. Titles and axis labels are now bold house-wide, so the diagnostics and profile plots match the data plots.
- **Redesigned the correlation figures for a compact, unified look.** Both tables are now a tight lower-triangle matrix with the variable names on the diagonal, and the scatter output is a lower-triangle scatter-plot matrix that mirrors it, rather than a square grid of all pairwise panels.

### Bugs

- Partial-correlation p-values now use `df = n - 2 - g` (g = number of conditioning variables) instead of `n - 2`; the coefficients are unchanged.
- `Summary.txt` no longer lists the fit statistics twice for glmmTMB models.
- The formula parser no longer mistakes the intercept controls `0` and `1` for random-slope variables, and now accepts the diagonal syntaxes `diag(1 + A | id)` and `(1 + A || id)`.

### Documentation

- Demo 17 (`dispersion` / `dispformula`): a Gamma model on `ToothGrowth` fitted with constant against by-dose dispersion. README, STATISTICAL_NOTES and Colab entries for the Spearman option, the covariate adjustment and `slope_correlated`.

### Known limitations

- **Diagonal random slopes for a *categorical* factor in a gaussian LMM are not fully uncorrelated.** lme4's `||` decorrelates the intercept from the slope and distinct slope terms, but not the correlations among the levels *within* a single categorical slope. glmmTMB's `diag()` decorrelates fully, so only gaussian LMMs with a categorical random slope are affected.

  <details><summary>What a real fix would need</summary>

  `(1 + s || id)` expands to `(1 | id) + (0 + factor | id)`, keeping that block correlated. A genuinely diagonal structure there needs the factor expanded into indicator terms (afex-style `expand_re = TRUE`), which is not done automatically. The alternatives are that expansion, or a small engine-override option to fit a gaussian model via glmmTMB, which would gain the correct `diag()` at the cost of lme4's Kenward-Roger / Satterthwaite denominator df. Deferred until a real case needs it.
  </details>

## [1.9.0] - 2026-07-17

### Features

- **Level-wise profile analysis via `options.profile_across`.** Names an ordered categorical factor and profiles how the factors interacting with it behave across its levels: per-level pairwise contrasts from the single fitted model (Layer 1), and the interaction as both a factor omnibus and a focused 1-df linear trend across the ordered positions (Layer 2, a position-weighted contrast that honours real numeric spacing). Writes `LevelProfile.xlsx` and a profile plot. Demo 16.
- **Bundled fonts, cross-platform.** kbstatpy ships and registers Latin Modern Sans, TeX Gyre Heros and TeX Gyre Termes (GUST Font License) on import, so plots render identically on every platform with no system font install. A request for `'Helvetica'`/`'Arial'` or `'Times'` keeps the real font on macOS/Windows and falls back to its bundled clone on Linux/Colab instead of dropping to DejaVu Sans. Case-insensitive `options.font` aliases (`'Sans'`/`'Modern'`, `'Times'`).
- **Run the demos on Google Colab.** `demos/kbstatpy_colab.ipynb` plus per-demo "Open in Colab" links; each notebook self-installs via `demos/colab_setup.sh`.

### Changes

- Enlarged the data, diagnostics and profile plots' label, title and tick sizes; significance brackets unchanged, and the dense correlation grids keep their own sizes.
- The descriptive-statistics table uses `observed=True`, reporting only the factor-level combinations that occur rather than the full cartesian product padded with empty `N=0` cells.
- When the body font resolves to Latin Modern Sans, `mathtext.fontset='cm'`, so in-plot math matches the LaTeX look.

### Bugs

- Fixed a matplotlib "font family not found" warning for plot titles on platforms without Helvetica.
- Silenced a pandas `FutureWarning` from the categorical groupby.
- Concise `__repr__` for `Output`/`ModelResult`/`CorrelationResult`; the dataclass default dumped the full summary text, DataFrames and figure objects.

### Documentation

- STATISTICAL_NOTES: Level-wise profile analysis (Demo 16) and Comparing any factor per cell (Demo 15), plus a note on why the two-level post-hoc is still reported. README: the `profile_across` option and section, the bundled-font behaviour, the Colab section, and demo 16.

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
