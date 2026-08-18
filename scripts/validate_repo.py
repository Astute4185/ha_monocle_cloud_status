#!/usr/bin/env python3
"""Validate static repository invariants without starting Home Assistant."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "ha_monocle_cloud_status"
MANIFEST = INTEGRATION / "manifest.json"
RUNTIME_REQUIREMENTS = ROOT / "requirements-runtime.txt"


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as file_handle:
        return json.load(file_handle)


def main() -> int:
    """Run repository-level checks."""
    errors: list[str] = []

    manifest = _load_json(MANIFEST)
    _load_json(INTEGRATION / "strings.json")
    _load_json(INTEGRATION / "icons.json")
    _load_json(ROOT / "hacs.json")

    required_manifest_keys = {
        "codeowners",
        "config_flow",
        "documentation",
        "domain",
        "iot_class",
        "name",
        "requirements",
        "version",
    }
    missing = sorted(required_manifest_keys - manifest.keys())
    if missing:
        errors.append(f"manifest.json missing keys: {', '.join(missing)}")

    if manifest.get("domain") != "ha_monocle_cloud_status":
        errors.append("manifest domain does not match integration directory")

    runtime_requirements = [
        line.strip()
        for line in RUNTIME_REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if manifest.get("requirements") != runtime_requirements:
        errors.append(
            "requirements-runtime.txt must exactly match manifest.json requirements"
        )

    if "aiohttp" in " ".join(runtime_requirements).lower():
        errors.append("aiohttp is supplied by Home Assistant and must not be declared")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Repository metadata validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
