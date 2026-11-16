# Development and validation

The supported development baseline is the current Home Assistant Python baseline (Python
3.14). Do not add a runtime package to `manifest.json` if Home Assistant Core already
provides it.

## Bootstrap

```bash
./scripts/bootstrap
source .venv/bin/activate
```

## Local checks

```bash
./scripts/lint          # metadata, Ruff and compile checks
./scripts/workflow-lint # GitHub Actions syntax/semantic checks via actionlint
./scripts/test          # pytest + coverage
./scripts/smoke         # network-free HA runtime/coordinator smoke test
./scripts/dependencies  # pip dependency consistency + vulnerability audit
./scripts/check         # lint + tests + smoke + dependency checks
```

Equivalent Make targets are provided for every command above. `workflow-lint` requires
either a local `actionlint` binary or Docker; it is therefore kept separate from `check`.

## CI gates

Every pull request to `main` (including all Dependabot PRs) runs **independent** jobs:

- `CI / lint`: actionlint, repository metadata invariants, Ruff, formatting and compile checks.
- `CI / tests`: the entire pytest suite on the latest published matched Home Assistant
  and `pytest-homeassistant` pair, with the mandatory 80% coverage threshold and `pip check`.
- `CI / dependency-audit`: a `pip-audit` of runtime dependencies.
- `Home Assistant compatibility / ha-smoke (minimum-supported)`,
  `ha-smoke (previous-stable)` and `ha-smoke (latest-stable)`: isolated Home Assistant
  runtime/coordinator checks against exact published patch versions. Version selection
  uses PyPI at workflow execution, so previous/latest roll forward each month while the
  advertised minimum (currently **2026.8**) remains fixed. If the same series has two
  labels, the job is deduplicated. Older HA releases use smoke checks because the official
  `pytest-homeassistant` fixtures were first released for the 2026.11 series.
- `Home Assistant validation / hassfest` and `/ hacs`: official repository checks.

`Home Assistant dev smoke` runs daily against Home Assistant's development branch.
It is **advisory**, not a required PR gate, because upstream changes may be unstable.

The official `pytest-homeassistant` fixtures are now used for all unit tests. They must
match the installed Home Assistant version. Do **not** install
`pytest-homeassistant-custom-component` in the same environment.

### Automated runtime dependency updates

Dependabot continues to update Python **development/test dependencies** and GitHub
Actions each week. The `python-socketio` runtime pin is intentionally excluded from
Dependabot because Home Assistant also requires an exact copy of this pin in
`manifest.json`.

A separate scheduled `Synchronized runtime dependency updates` workflow checks PyPI
weekly and creates a **reviewable PR** that changes `requirements-runtime.txt` and
`manifest.json` together. It updates within the pinned major version; major upgrades
require manual review. The workflow explicitly dispatches the CI, compatibility and
HACS validation workflows against its bot branch, since changes pushed with the
`GITHUB_TOKEN` do not automatically trigger workflow runs.

For this PR automation, enable **Settings → Actions → General → Workflow permissions →
Allow GitHub Actions to create and approve pull requests**. The workflow grants itself
only the repository scopes needed for branch, PR and workflow-dispatch operations.
If branch protection prevents automation from opening its branch, adjust the rules for
that bot branch rather than weakening the CI checks.

To update an existing runtime pin manually, edit both files to the same exact pinned
requirement (the `scripts/validate_repo.py` invariant remains mandatory).

### Required branch protection checks

Once the new workflows have run, set the following checks as required on `main`:

- `lint`, `tests`, `dependency-audit`
- `select-versions`, `ha-smoke (minimum-supported)`, `ha-smoke (previous-stable)`,
  `ha-smoke (latest-stable)`
- `hassfest`, `hacs`

Keep the daily HA `dev` job advisory. Require pull requests, and avoid enabling
Dependabot auto-merge without the test and compatibility checks passing.

When upgrading the minimum HA version, update the `--minimum` argument in
`.github/workflows/ha-compatibility.yml` and the minimum version in `README.md`.

## Private Intelli companion

The private companion is not a CI dependency and no vendor credential is required.
Parent/companion compatibility is defined in `INTELLI_COMPATIBILITY.md` and enforced by
`tests/test_intelli_contract.py`.

## Core contribution boundary

This repository is hardened to make Core-readiness gaps explicit, but it is not yet ready
for direct inclusion in Home Assistant Core. The main remaining architectural task is to
extract Monocle API/Socket.IO protocol code into a separately packaged Python library.
Brand assets and official Home Assistant documentation also need separate contributions.
See `custom_components/ha_monocle_cloud_status/quality_scale.yaml` for the tracked gaps.
