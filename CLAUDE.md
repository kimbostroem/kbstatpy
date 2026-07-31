# kbstatpy

Solo-maintained repository. `develop` and `master` are kept identical; there is no
GitFlow in practice. Every commit on the trunk is one release.

## Release procedure

Cutting a release is one unit — do not stop after the commit. In order:

1. **Bump `kbstatpy/__init__.py`** — `__version__` is the single source of truth;
   `pyproject.toml` reads it via `version = { attr = "kbstatpy.__version__" }`.
2. **Add the `CHANGELOG.md` entry** — `## [X.Y.Z] - YYYY-MM-DD` at the top, with
   `### Fixed` / `### Changes` sections. The entry becomes the GitHub release
   notes verbatim, so write it for a reader who has not seen the diff: what was
   wrong, why it went unnoticed, what changed.
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
for f in tests/test_*.py; do echo "== $f"; python3 "$f"; done
```

Most tests need R with `glmmTMB` and `emmeans`, like the package itself. The
metadata and layout-only tests (`test_citation_metadata.py`,
`test_correlation_title_fits.py`) do not.

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
