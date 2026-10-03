---
description: "Use when CI checks are failing on a PR — fetches failure logs, diagnoses root causes, implements fixes, pushes until CI is green."
model: opus
argument-hint: "PR number (e.g., 1690 or #1690)"
allowed-tools: Bash(gh pr view:*), Bash(gh pr checks:*), Bash(gh pr diff:*), Bash(gh api:*), Bash(gh run view:*), Bash(git log:*), Bash(git diff:*), Bash(git push:*), Bash(git commit:*), Bash(git add:*), Bash(pytest:*), Bash(ruff:*), Bash(mypy:*), Bash(python:*), Bash(pip:*), Read, Write, Edit, Glob, Grep, Agent
---

# Fix GitHub CI Failures: $ARGUMENTS

Diagnose and fix CI failures. Work systematically: identify failures → read logs → diagnose root cause → fix locally → verify → push.

## Phase 0: Determine the PR

Number → PR. `#N` → strip `#`. Empty → current branch (`gh pr view --json number`).

## Phase 1: Inventory failures

```bash
gh pr checks <PR>
```

For each failing check, get the run id and load the failed logs:

```bash
gh run view <run-id> --log-failed
```

Categorize:
- **Test failures** — assertion failed, `filterwarnings = error` turned a warning into an error
- **Lint failures** — ruff rule violation, unsorted imports, unused imports
- **Typecheck failures** — `mypy` strict errors in `src/manza`
- **Cassette fetch failures** — `python scripts/fetch_cassettes.py` could not resolve or download the manza-ruby tarball
- **Cassette replay failures** — `AssertionError: No cassette interaction matched ...` from `tests/cassette_replay.py`
- **Toolchain install failures** — `pip install -e ".[dev]"` failed on one Python version
- **Release / publish failures** — tag != package version, PyPI trusted-publishing OIDC binding

## Phase 2: Diagnose

Read the actual error message, not the surrounding noise. The first stacktrace line that points at our code is usually the culprit.

For each failure:

### Reproduce locally

```bash
# One-time setup (matches CI)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python scripts/fetch_cassettes.py

# Test
pytest tests/path/to/test_file.py

# Lint
ruff check

# Typecheck
mypy

# Full pipeline
ruff check && mypy && pytest
```

If you can't reproduce locally, the failure is environmental (CI-only):
- Different Python version → CI runs 3.11, 3.12 and 3.13; reproduce with that interpreter (`python3.11 -m venv .venv`)
- Missing dependency → did `pip install -e ".[dev]"` run before the failing step?
- Stale cassettes → your local `tests/fixtures/cassettes/` came from an older manza-ruby release; re-run `python scripts/fetch_cassettes.py`
- Network → github.com hiccup while fetching the cassette tarball (the script already retries 8 times)
- Secret missing → e.g. trusted-publishing OIDC environment `pypi` not configured

Never call a live Manza API to reproduce a failure. Cassettes are the only source of responses here, and only manza-ruby records them.

### Find the root cause

Apply the five-whys ladder until you reach a fix point that prevents the same class of failure recurring. Don't:

- Disable the failing test
- Add a `# noqa` to silence the linter
- Add a `# type: ignore` or `cast(Any, ...)` to silence mypy
- `pip install` a missing transitive dep instead of declaring it in `pyproject.toml` or fixing your import

These hide the failure; the underlying bug returns elsewhere.

## Phase 3: Fix and verify

### 3.1 Implement the fix

Touch only what the failure cites, plus what the fix requires.

### 3.2 Run the equivalent local check

The CI step that failed has a local equivalent — run it, get green:

| CI step | Local equivalent |
|---|---|
| Install | `pip install -e ".[dev]"` |
| Fetch cassettes | `python scripts/fetch_cassettes.py` |
| Lint | `ruff check` |
| Typecheck | `mypy` |
| Test | `pytest` |
| Release build / publish | requires PyPI OIDC, skip locally, verify via the tag's workflow run |

### 3.3 Run the full pipeline

```bash
ruff check && mypy && pytest
```

### 3.4 Commit + push

```bash
git add <files>
git commit -m "fix(ci): <what was failing>

<root cause and how this addresses it>"
git push origin <branch>
```

Use `fix:` for prod fixes, `chore(ci):` for workflow / config changes.

## Phase 4: Watch the next run

```bash
gh pr checks <PR> --watch
# or
gh run watch <run-id> --exit-status
```

Track until green. If the same step fails again with a different error, repeat. If it fails the same way, your fix is wrong — revert and rethink.

## Phase 5: Verify and document

```bash
gh pr checks <PR>            # all green
gh pr view <PR> --json mergeable,reviewDecision
```

If the failure was CI-config drift (workflow YAML out of sync with reality), also update relevant docs:
- `.python-version`
- `pyproject.toml` `requires-python` and classifiers
- `CLAUDE.md` if a convention changed

## Common patterns and fixes

### `No cassette interaction matched <METHOD> <URL>`

The request the SDK sent no longer matches what manza-ruby recorded. Check, in order:
- The test loads more than one cassette that shares method + URI (`transfer_drafts/authorize` vs `authorize_same_key`, `create` vs `create_duplicate`): load one cassette per test.
- The cassettes are stale: `python scripts/fetch_cassettes.py` (the manza-ruby release pinned in `PINNED_TAG`).
- Path, query or host drifted: replay URIs use `https://ma.manza.dev`; query params match sorted.
- A body-matched test (`body_match="exact"` or `"without_signature"`) sends a different body: request bodies are compact JSON in recorded key order (byte-identical to manza-ruby's `JSON.generate`). Fix the SDK, not the cassette.
- A genuinely new request shape means a coordinated change: re-record in manza-ruby and ship a new release first.

### `fetch_cassettes.py` fails or finds no tag

It downloads `cassettes-<PINNED_TAG>.tar.gz` from the `REPO` release (`getmanza/manza-ruby`), or the tag passed as an argument. A transient 503 is retried up to 8 times. If the tarball is missing, manza-ruby's release workflow did not finish for that tag: pass another tag explicitly only to unblock, then fix forward.

### `ruff` or `mypy` fails only on one Python version

CI runs 3.11, 3.12 and 3.13 with `fail-fast: false`. Reproduce with that interpreter before changing code.

### Release workflow: `Tag vX.Y.Z does not match package version`

`release.yml` gates on tag == `scripts/version`. `bin/release` writes the version through `scripts/version`; don't tag by hand or edit `src/manza/_version.py` separately.

### Trusted publishing rejected by PyPI

The trusted-publisher binding on PyPI must match `(repo getmanza/manza-python, workflow release.yml, environment pypi)` exactly. Check https://pypi.org/manage/project/manza/settings/publishing/.

## Karpathy guidelines

- **Think before coding** — read the actual error, don't pattern-match on the first guess.
- **Goal-driven execution** — the green CI check is the verification.
- **Surgical changes** — fix the failing class of error, not adjacent things.
