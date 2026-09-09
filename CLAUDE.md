# kbstatpy

Solo-maintained repository. `develop` and `master` are kept identical; there is no
GitFlow in practice. Every commit on the trunk is one release.

## Release procedure

Cutting a release is one unit — do not stop after the commit. In order:

1. **Bump `kbstatpy/__init__.py`** — `__version__` is the single source of truth;
   `pyproject.toml` reads it via `version = { attr = "kbstatpy.__version__" }`.
2. **Add the `CHANGELOG.md` entry** — `## [X.Y.Z] - YYYY-MM-DD` at the top, with
   `### Features` / `### Bugs` / `### Changes` sections (plus `### Known
   limitations` where one applies).

   **Be brief.** State what was added, fixed or changed, from the point of view
   of someone using the library. One or two sentences per item; a whole entry
   should read in well under a minute. No implementation detail: not the
   function that changed, not the mechanism of the bug, not how it was
   diagnosed. That belongs in the commit message and in code comments, which is
   where a reader who has seen the diff will look.

   **The exception is statistical consequence.** Where a change affects how
   results should be read or trusted, say more: a wrong number that was
   published, output that must be regenerated, a default that alters what is
   estimated, an effect size that is approximate. Spell those out plainly — they
   are the reason anyone reads a changelog for this library.

   Entries up to 1.8.1 are the model for the style; 1.9.0 onward drifted into
   essays and were rewritten to match in 1.15.6.

3. **Update `CITATION.cff`** — `version` and `date-released`. Nothing imports this
   file, so only `tests/test_citation_metadata.py` catches a stale one.
4. **Run the tests** — `for f in tests/test_*.py; do python3 "$f"; done`. Two of
   them guard the steps above: `test_citation_metadata.py` fails if
   `__version__`, the newest changelog heading, and `CITATION.cff` disagree.
5. **Commit on `develop`** — subject `Release X.Y.Z: <headline>`, then a short
   body paragraph. End with the `Co-Authored-By:` trailer.
6. **Fast-forward `master`** — `git checkout master && git merge --ff-only develop`.
7. **Annotated tag** on `master` — `git tag -a vX.Y.Z -m "Release X.Y.Z: <headline>"`,
   message matching the commit subject.
8. **Push** — `git push origin develop master vX.Y.Z`.
9. **Publish the GitHub release** — `gh release create vX.Y.Z --title vX.Y.Z --latest
   --notes-file <changelog section>`, the notes being that version's changelog
   section with the `## [X.Y.Z]` heading itself stripped.

## Tests

Plain scripts, no pytest: each file runs standalone and prints `PASS`/`FAIL` per
test, exiting non-zero on failure.

```bash
python3 -m pip install -e ".[test]"      # once: PyYAML, for the CITATION check
for f in tests/test_*.py; do echo "== $f"; python3 "$f"; done
```

Every test needs R with `glmmTMB` and `emmeans`, like the package itself --
including the metadata and layout-only ones. There is no R-free test and there
cannot be one while `kbstatpy/__init__.py` imports `.kbstat`, which calls
`ro.r('emmeans::emm_options(...)')` at module level: `from kbstatpy import
__version__` is enough to start R.

New tests state in their module docstring what the guarded failure mode was and
why it went unnoticed — a bare assertion does not survive a refactor that has
forgotten the reason for it. Verify a new guard actually discriminates: revert
the fix, confirm the test fails, restore it.

## Conventions

- British spelling in prose and docstrings (`generalised`, `behaviour`).
- Comments explain *why*, not what; the codebase is dense with statistical
  reasoning that is not recoverable from the code.
- Statistical decisions that a reader might mistake for bugs (df = Inf for
  GLMMs, `glmmTMB` over `lme4::glmer` for the dispersion families) are
  documented in `STATISTICAL_NOTES.md` and surfaced in `Summary.txt`.
