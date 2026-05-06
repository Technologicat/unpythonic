# Fleet sweep: coverage hygiene + dev-deps-via-pdm

Two related but distinct cleanups, queued from the unpythonic 2026-05-06 session
(see `briefs/2.2.0-remaining-issues.md` "Fleet-wide follow-ups"). Read this whole
spec before starting; the two sweeps interact in places and the verification
recipe is shared.

## Scope

The fleet projects targeted are PDM-managed Python projects with CI / coverage
workflows. Inferring from `~/.claude/CLAUDE.md` "Active projects":

- **pylu, pydgq, wlsqm** — Cython projects.
- **pyan3** — pure Python; uses `pytest-cov`.
- **mcpyrate** — pure Python; macro-using.
- **raven** — DPG app, pure Python.
- **unpythonic** — already updated this session; reference implementation.
- **arxiv-api-search** — minimal pure-Python reference; check if active.
- **substrate-independent** — *writing project, not Python*; out of scope unless
  its embedded Python tool has its own pyproject.toml.

For each project: verify it has a `pyproject.toml`, then check whether CI
actually runs coverage (look for `.github/workflows/coverage.yml`, or `--cov`
flags / `coverage run` invocations in `ci.yml`). **Both sweeps are about
coverage tooling**, so projects with no coverage in CI fall out of scope
entirely — there's nothing to align. The broader cleanup of non-coverage
`pip install` lines (sphinx, etc.) is explicitly deferred (see "Out of
scope" below).

Survey result for the current fleet (2026-05-06): `pylu`, `pydgq`, `wlsqm`
have no coverage in CI and are out of scope — these are Cython projects, and
coverage on Cython modules requires `linetrace=True` plus a separate tracing
build, which none of them set up (the Python-level wrapping is thin enough
that line coverage of the `.py` glue would mostly measure the test scaffolding
anyway). `pyan3`, `mcpyrate`, `raven` are in scope.

## Sweep A: `[tool.coverage.run]` configuration

### Why

Two reasons, in priority order:

1. **Coverage signal is about which lines of *production code* run.** Tests
   are excluded from analysis because their pass/fail/error/total is already
   reported by the test runner. Coverage of test files adds rows to the report
   without insight.
2. **For projects whose test files use macros that produce invalid surface
   Python, this is also a correctness fix.** Coverage.py's report step
   (`coverage xml` / `coverage html`) parses each file as standard Python to
   map line numbers. If a test uses a macro that rewrites the AST in a way
   that yields invalid surface Python (e.g. `nonlocal x` after `x = None`,
   which is legal post-`continuations`-macro because the body is split into
   separate functions, but rejected by Python's parser as written),
   `coverage xml` fails with `Couldn't parse '...' as Python source`.
   Excluding tests sidesteps the parse step entirely. **Reason 2 only applies
   to projects whose tests use such macros — primarily unpythonic itself, and
   any downstream consumer of `unpythonic.syntax.continuations` *in tests*.**
   For most projects, Reason 1 is the operative one.

Canonical pattern documented at `~/.claude/CI-SETUP-NOTES.md` §4a.

### What

Add to `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["<package>"]   # e.g. "pylu", "raven", "pyan"
omit = [
    "*/tests/*",         # OR "*/test/*" — match the project's actual layout
]
```

**Path varies by project — there is no fleet convention.** The naming drifted
organically: unpythonic uses `tests/` (plural) because `unpythonic.test` is
reserved for the test framework module (`unpythonic.test.fixtures`); the other
projects' current testsuites were written without an explicit convention being
set, so each picked a locally sensible name. Survey result for the current
in-scope set: pyan uses `tests/` (plural, top-level), raven uses `tests/`
(plural, scattered under `raven/<subpkg>/tests/`), mcpyrate uses `test/`
(singular, at `mcpyrate/test/`). Pick the glob that matches the project's
actual layout, and don't add the *other* one as a precaution: in unpythonic,
`*/test/*` would mistakenly omit the framework, which *is* production code.

The `omit` config applies even when the CI workflow uses `--source=.` from the
command line — config-level omit is composed with whatever source is active.

### Verify

Locally, after applying:

```bash
python -m coverage erase
python -m coverage run --source=. -m <test-runner-invocation>
python -m coverage xml
```

`coverage xml` should write `coverage.xml` without parse errors. Open the XML
and confirm the test-file paths are absent from `<class>` entries.

## Sweep B: declare `coverage` / `pytest-cov` in `[dependency-groups].dev`

### Why

The fleet's current practice is inconsistent: most projects do `pip install
<tool>` in `coverage.yml` ad hoc, which bypasses the `pyproject.toml`
declaration. This:

- Leaves the local dev env inconsistent with CI (a fresh `pdm install` doesn't
  give you the tools CI uses).
- Hides the dependency from `pdm.lock` reproducibility (for app-class projects
  that commit `pdm.lock`).
- Violates the rule recently codified in `~/.claude/CLAUDE.md` ("Dev deps go
  in `pyproject.toml`, installed via the project's package manager").

### What

For each project that uses `coverage` (or `pytest-cov`) in CI:

1. Add the tool to `[dependency-groups].dev` in `pyproject.toml`. Use the same
   version-pin style as the other dev deps in that project (often unpinned for
   leaf tools, sometimes minimum-pinned).
2. Update `.github/workflows/coverage.yml` (and `ci.yml` if relevant) to
   install via `pdm install` (which picks up dev deps from
   `[dependency-groups].dev`) instead of `pip install <tool>`.

The shared baseline in `~/.claude/PROJECT-SETUP-NOTES.md` was updated this
session to include `coverage` — so when you `pdm install` on a project whose
dev deps match the baseline, you'll get coverage automatically.

**Projects using pytest-cov** (currently `pyan3`, `raven`, possibly others)
need `pytest-cov` declared in addition to / instead of `coverage` — pick what
the workflow actually uses.

**Exception — raven:** raven's CI deliberately uses ad-hoc `pip install` lines
*because* a full `pdm install` would pull in the project's torch/torchvision
ML stack (multi-gigabyte, and the workflow already takes pains to use the
CPU-only PyTorch wheel index). For raven, do **only the declaration half** of
Sweep B: add `pytest-cov` to `[dependency-groups].dev` so a fresh local
`pdm install` includes it, but **leave the coverage workflow's ad-hoc install
in place** — just keep `pytest-cov` in the explicit `pip install` list. The
per-project `CLAUDE.md` (or a comment in `coverage.yml`) should note why the
workflow doesn't use `pdm install`.

### Verify

Locally:

```bash
pdm install                         # installs dev deps from pyproject.toml
which coverage                      # should resolve into .venv/
coverage --version                  # should match what's in pdm.lock (if committed)
```

In CI: the `coverage.yml` step that previously did `pip install coverage`
should be removed; only `pdm install` should remain on the dependency-install
side. After pushing, verify the coverage workflow still passes.

## Per-project survey checklist

Run this from each project root before changing anything, to surface the
project's current state:

```bash
echo "=== $(basename $PWD) ==="
echo "--- pyproject.toml: dependency-groups ---"
grep -A 20 '\[dependency-groups\]' pyproject.toml | sed -n '/dev = \[/,/^]/p'
echo "--- pyproject.toml: coverage config ---"
grep -A 10 '\[tool.coverage' pyproject.toml || echo "(none)"
echo "--- coverage.yml: install lines ---"
grep -E 'pip install|pdm install|coverage' .github/workflows/coverage.yml 2>/dev/null || echo "(no coverage.yml)"
echo "--- ci.yml: install lines ---"
grep -E 'pip install|pdm install|coverage' .github/workflows/ci.yml 2>/dev/null | head -10 || echo "(no ci.yml)"
echo "--- test directory name (depth ≤ 3) ---"
find . -maxdepth 3 -type d \( -name tests -o -name test \) \
    -not -path '*/.venv/*' -not -path '*/__pycache__/*' 2>/dev/null | head -10
```

The `find` form (vs the simpler `ls -d */tests */test`) is needed because some
projects scatter test directories deeper — raven has them at
`raven/<subpkg>/tests/`, three levels down. A depth-1 glob would miss those
entirely and you'd write the wrong `omit` glob.

Use the output to decide:

- If `[tool.coverage.run]` already exists, sweep A may be partial — verify it
  has the `omit` clause.
- If `coverage` / `pytest-cov` is already in dev deps, sweep B may be partial —
  verify the workflow no longer pip-installs it.
- If both look right, the project is already done; skip it.

## Order of operations

For each project, in order:

1. Run the survey checklist; capture output.
2. Apply sweep A (coverage config in pyproject.toml).
3. Verify coverage runs locally.
4. Apply sweep B (dev deps + workflow update).
5. Verify `pdm install` brings the tool in.
6. Commit each project's changes as a single commit
   (`pyproject, .github/workflows: align with fleet coverage convention` or similar).
7. Push, verify CI green.
8. Move to the next project.

Bundling A+B per project keeps each commit atomic and bisectable. Avoid sweeping
all projects in one mega-commit — if one breaks, the bisect needs per-project
granularity.

## References

- `~/.claude/CI-SETUP-NOTES.md` §4a — `[tool.coverage.run]` canonical pattern.
- `~/.claude/PROJECT-SETUP-NOTES.md` — Shared dev dependency baseline (now
  includes `coverage`).
- `~/.claude/CLAUDE.md` — "Dev deps go in `pyproject.toml`" rule.
- `unpythonic/pyproject.toml` (commit `5715d88`) — reference implementation
  for sweep A. The detailed comment in the `[tool.coverage.run]` section
  explains both reasons.
- `unpythonic/briefs/2.2.0-remaining-issues.md` — where this sweep was queued.

## Out of scope (explicitly)

- **Migrating from `pip install` to `pdm install` for non-coverage tools in
  CI.** Many projects also `pip install` other things (sphinx, etc.). That's
  a broader cleanup; only do it if it falls naturally out of touching the
  workflow file anyway. If it expands the scope, defer to a separate session.
- **Pinning coverage versions.** The baseline doesn't pin and neither should
  we, unless a project has a specific version constraint. Lockfile-committing
  app-class projects will pin via `pdm.lock` automatically.
- **substrate-independent and arxiv-api-search.** Verify they're in scope
  (have pyproject.toml, have CI) before touching.
