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

- `Home Assistant validation`: official hassfest and HACS repository validation.
- `Lint and test`: actionlint, Ruff, repository invariants, pytest/coverage, `pip check`,
  and `pip-audit`.
- `Home Assistant dev smoke`: daily network-free runtime/coordinator smoke against the
  `dev` branch of Home Assistant Core. A scheduled failure is intentional: it is an early
  compatibility signal that should be investigated, even if the root cause turns out to
  be temporary upstream breakage.
- Dependabot watches both Python and GitHub Actions dependencies weekly.

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
