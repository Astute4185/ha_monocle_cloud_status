#!/usr/bin/env python3
"""Atomically synchronize python-socketio runtime pins and the HA manifest.

Uses the highest non-yanked stable release within the currently pinned major
version. Major upgrades must be reviewed and initiated manually.
"""

import json
from pathlib import Path
import re
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements-runtime.txt"
MANIFEST = ROOT / "custom_components/ha_monocle_cloud_status/manifest.json"
PACKAGE = "python-socketio"
REQUIREMENT = "python-socketio[asyncio-client]"
PYPI_URL = "https://pypi.org/pypi/python-socketio/json"
VERSION_PATTERN = re.compile(r"^\d+(?:\.\d+)+$")
PIN_PATTERN = re.compile(r"^(python-socketio\[asyncio-client\]==)(\d+(?:\.\d+)+)$")


def latest_in_major(releases: dict, major: int) -> str:
    """Get the latest stable, non-yanked python-socketio release in a major."""
    eligible = []
    for version, distributions in releases.items():
        if not VERSION_PATTERN.fullmatch(version) or not distributions:
            continue
        parts = tuple(int(part) for part in version.split("."))
        if parts[0] != major or all(
            file.get("yanked", False) for file in distributions
        ):
            continue
        eligible.append((parts, version))
    if not eligible:
        raise ValueError(f"No stable {PACKAGE} releases for major {major}")
    return max(eligible)[1]


def synchronize(requirements: str, manifest: dict, latest: str) -> tuple[str, dict]:
    """Return updated data, rejecting any unexpected runtime dependencies."""
    active = [
        line.strip()
        for line in requirements.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(active) != 1 or not (match := PIN_PATTERN.fullmatch(active[0])):
        raise ValueError("Unexpected runtime requirement: manual review required")
    if manifest.get("requirements") != active:
        raise ValueError("Manifest and runtime requirement differ before update")
    new_pin = f"{REQUIREMENT}=={latest}"
    if int(latest.split(".")[0]) != int(match.group(2).split(".")[0]):
        raise ValueError("Major version updates must be reviewed manually")
    if tuple(map(int, latest.split("."))) < tuple(map(int, match.group(2).split("."))):
        raise ValueError("Refusing to downgrade the runtime dependency")
    updated_requirements = requirements.replace(active[0], new_pin)
    updated_manifest = dict(manifest)
    updated_manifest["requirements"] = [new_pin]
    return updated_requirements, updated_manifest


def main() -> None:
    """Synchronize both requirements sources after validating current state."""
    requirements = REQUIREMENTS.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    # Validate both files before querying remote versions or writing anything.
    current_pin = manifest.get("requirements", [""])
    if len(current_pin) != 1 or not PIN_PATTERN.fullmatch(current_pin[0]):
        raise ValueError("Unexpected manifest runtime requirements")
    current_version = current_pin[0].split("==")[1]
    current, _ = synchronize(requirements, manifest, current_version)
    if current != requirements:
        raise ValueError("Runtime requirements are not already synchronized")

    with urlopen(PYPI_URL, timeout=20) as response:
        releases = json.load(response)["releases"]
    old_version = current_version
    latest = latest_in_major(releases, int(old_version.split(".")[0]))
    new_requirements, new_manifest = synchronize(requirements, manifest, latest)
    if new_requirements == requirements:
        print(f"Already current: {PACKAGE}=={latest}")
        return

    # Compute/validate all content before writing either output.
    REQUIREMENTS.write_text(new_requirements, encoding="utf-8")
    MANIFEST.write_text(json.dumps(new_manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {PACKAGE}: {old_version} -> {latest} (both files)")


if __name__ == "__main__":
    main()
