# kbstatpy

Solo-maintained repository. `develop` and `master` are kept identical; there is no
GitFlow in practice. Every commit on the trunk is one release.

## Release procedure

Cutting a release is one unit — do not stop after the commit. In order:

1. **Bump `kbstatpy/__init__.py`** — `__version__` is the single source of truth;
   `pyproject.toml` reads it via `version = { attr = "kbstatpy.__version__" }`.
2. **Add the `CHANGELOG.md` entry** — `## [X.Y.Z] - YYYY-MM-DD` at the top, with
   `### Fixed` / `### Changes` sections. The entry becomes the GitHub release
   notes verbatim.

   **Keep the visible part short.** One bold headline sentence per change, then
   at most two or three sentences: what was wrong, what it does now. A reader
   skimming the release page should get the whole entry in under a minute.

   Depth is not dropped, it is folded. Where the reasoning is genuinely worth
   recording — why it went unnoticed, a rejected alternative, a non-obvious
   mechanism, a caveat — put it in a collapsed block under the bullet:

   ```markdown
   - **One-sentence headline.** Two sentences of what changed.

     <details><summary>Why it went unnoticed</summary>

     The detail, as long as it needs to be.
     </details>
   ```

   This renders collapsed both in `CHANGELOG.md` on GitHub and in the release
   notes. Entries before 1.9.0 predate the convention and are already terse;
   1.9.0 onward were rewritten to it in 1.15.5.
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
