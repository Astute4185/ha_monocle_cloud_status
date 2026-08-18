# Monocle Cloud Status for Home Assistant

Unofficial Home Assistant integration for Monocle / Catch Power cloud status and hot-water
override controls. It has primarily been developed against a two-channel Solar Catch
Control installation; six-channel hardware has not been validated.

This project is not affiliated with or endorsed by Catch Power, Solar Analytics, or the
Monocle vendor.

## Features

- Live mains, solar, house, and battery power telemetry
- Device online state and hot-water/load state
- Current override state and expiry
- Draft override mode/duration controls with an explicit Apply button
- Home Assistant config-flow setup
- Push telemetry using the Monocle Socket.IO service

## Installation with HACS

1. In HACS, open **Integrations** and add this repository as a custom repository.
2. Select **Integration**, install **Monocle Cloud Status**, and restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**.
4. Search for **Monocle Cloud Status** and enter the credentials used by the Monocle app.

The development and CI baseline is Home Assistant 2026.8 or later.

## Development

Python 3.14 is required for the current Home Assistant development baseline.

```bash
./scripts/bootstrap
source .venv/bin/activate
./scripts/check
```

Individual checks are available for code linting, workflow linting, tests, the network-free
Home Assistant runtime smoke, and dependency auditing. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the commands and CI gates.

## Compatibility monitoring

CI performs three layers of compatibility checking:

- official Home Assistant `hassfest` plus HACS validation;
- actionlint, Ruff, unit/coverage, and dependency checks against the current HA test stack;
- a scheduled network-free runtime/coordinator smoke against Home Assistant Core `dev`.

The private `ha_monocle_cloud_status_intelli` companion is protected by a public extension
contract and unit tests without requiring the vendor Basic Authorization credential. See
[INTELLI_COMPATIBILITY.md](INTELLI_COMPATIBILITY.md).

## Home Assistant Core readiness

The repository tracks the current Integration Quality Scale in
`custom_components/ha_monocle_cloud_status/quality_scale.yaml`. It deliberately does not
claim Bronze yet. Before proposing this for Home Assistant Core, the main outstanding work
is:

1. Extract vendor/API-specific HTTP and Socket.IO communication into a separately packaged
   Python library.
2. Add Home Assistant Brands assets.
3. Add the official Home Assistant integration documentation contribution.
4. Complete the remaining quality-scale items, notably diagnostics, reconfiguration, repair
   issues, strict typing, and the greater-than-95-percent Silver test-coverage target.
5. Resolve licensing for a Core contribution; the current repository license statement is
   CC BY-NC 4.0 and should not be changed without confirming rights/intent.

## Security

Credentials are stored in the Home Assistant config entry like other integration secrets.
Do not commit Monocle credentials, tokens, event captures containing secrets, or the private
Intelli Basic Authorization credential to this repository.

## License

Original material in this repository is provided under the
Creative Commons Attribution-NonCommercial 4.0 International license
(CC BY-NC 4.0), except where otherwise stated.

See the repository [LICENSE](LICENSE) for the applicable license terms.

The license is intentionally non-commercial and does not imply ownership of, or grant
rights to, any vendor software, service, protocol, trademark, branding, or other
third-party intellectual property referenced by this project
