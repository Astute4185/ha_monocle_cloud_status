# Monocle Cloud Status for Home Assistant

Unofficial Home Assistant integration for Monocle / Catch Power cloud status and hot-water
override controls.

The integration has primarily been developed and tested against a two-channel Solar Catch
Control installation. Six-channel hardware has not been validated.

> [!IMPORTANT]
> This project is independently developed and is not affiliated with, endorsed by, or
> supported by Catch Power, Solar Analytics, or the Monocle vendor.

## Features

- Live mains, solar, house, and battery power telemetry
- Device online state and hot-water/load state
- Current override state and expiry
- Draft override mode and duration controls with an explicit Apply action
- Home Assistant config-flow setup and reauthentication
- Push telemetry using the Monocle Socket.IO service
- Network-free Home Assistant runtime smoke testing for compatibility monitoring

## Installation with HACS

1. In HACS, open **Integrations** and add this repository as a custom repository.
2. Select **Integration**, install **Monocle Cloud Status**, and restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**.
4. Search for **Monocle Cloud Status** and enter the credentials used by the Monocle app.

The current development and CI baseline is Home Assistant 2026.8 or later.

## Development

Python 3.14 is required for the current Home Assistant development baseline.

```bash
./scripts/bootstrap
source .venv/bin/activate
./scripts/check
```

Individual checks are also available:

```bash
./scripts/lint              # repository metadata, Ruff, formatting and compile checks
./scripts/lint --fix        # apply supported Ruff/formatting fixes
./scripts/workflow-lint     # GitHub Actions validation with actionlint
./scripts/test              # pytest and coverage
./scripts/smoke             # network-free Home Assistant runtime/coordinator smoke test
./scripts/dependencies      # pip consistency and vulnerability checks
```

Equivalent Make targets are provided where applicable. See
[CONTRIBUTING.md](CONTRIBUTING.md) for development workflow and CI details.

## Compatibility monitoring

CI provides several layers of regression detection:

- official Home Assistant `hassfest` validation;
- HACS repository validation;
- `actionlint` validation for GitHub Actions workflows;
- Ruff linting and formatting checks;
- unit tests and coverage reporting;
- Python dependency consistency and vulnerability checks;
- a scheduled network-free runtime/coordinator smoke test against Home Assistant Core
  `dev`.

The intent is to identify Home Assistant changes that break the integration before they
reach a stable Home Assistant release.

## Intelli companion compatibility

The private `ha_monocle_cloud_status_intelli` companion is not required by this repository
or its CI pipeline.

Compatibility between the public integration and the private companion is maintained
through a small public extension contract and is covered by
`tests/test_intelli_contract.py`. No private vendor Basic Authorization credential is
required to execute these contract tests.

See [INTELLI_COMPATIBILITY.md](INTELLI_COMPATIBILITY.md) for the supported interface.

## Home Assistant Core readiness

The repository tracks Home Assistant Integration Quality Scale work in
`custom_components/ha_monocle_cloud_status/quality_scale.yaml`.

The project does not currently claim Home Assistant Core inclusion readiness. Remaining
work includes:

1. Extract Monocle-specific HTTP and Socket.IO communication into a separately packaged
   Python library suitable for use as an integration dependency.
2. Complete and maintain the required Home Assistant/HACS brand assets.
3. Add official Home Assistant integration documentation if pursuing Core inclusion.
4. Complete the remaining quality-scale items, including diagnostics, reconfiguration,
   repair issues, strict typing, and module-level test coverage targets.

## Reverse-engineering and third-party rights

This integration interoperates with Monocle services using behavior and interfaces derived
from independent analysis of the vendor application and service traffic. It does not
contain or distribute the vendor application itself.

Vendor names, trademarks, service marks, artwork, software, APIs, protocols, and other
third-party material remain the property of their respective owners. References to those
names are solely for identification and interoperability.

The original source code in this repository is distributed under the GNU General Public
License v3.0. This licensing choice applies only to material in this repository that the
contributors have the right to license. It does not assert ownership of, or grant rights
to, vendor software, services, protocols, trademarks, branding, artwork, or other
third-party intellectual property.

The integration was developed for interoperability through independent analysis of a
third-party application and service behavior. That development history and the GPL-3.0
license are separate matters: the license governs redistribution and modification of the
project's original source code, while third-party rights remain with their respective
owners.

## Security

Credentials are stored in the Home Assistant config entry in the same manner as other
integration secrets.

Do not commit any of the following to this repository:

- Monocle usernames or passwords
- authentication tokens or session cookies
- captured service traffic containing credentials or personal information
- the private Intelli vendor Basic Authorization credential

If sensitive data is accidentally committed, rotate the affected credential and remove the
secret from repository history rather than only deleting it in a later commit.

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE). The license applies only to material the contributors have the right to license; third-party rights are not included.