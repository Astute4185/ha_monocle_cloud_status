#!/usr/bin/env python3
"""Select rolling Home Assistant smoke-test releases from official PyPI data.

One release is selected for each of the declared minimum, previous stable
monthly series and current stable monthly series. The highest published patch
in each series is used. Betas, release candidates and yanked versions are ignored.
"""

import argparse
import json
import os
from pathlib import Path
import re
from urllib.request import urlopen

HA_PYPI = "https://pypi.org/pypi/homeassistant/json"
STABLE_VERSION = re.compile(r"^(\d{4})\.(\d{1,2})\.(\d+)$")


def released_versions(releases: dict) -> dict[tuple[int, int], tuple[int, int, int]]:
    """Return the highest non-yanked patch within each HA monthly series."""
    monthly: dict[tuple[int, int], tuple[int, int, int]] = {}
    for version, distributions in releases.items():
        matched = STABLE_VERSION.fullmatch(version)
        if not matched or not distributions:
            continue
        if all(distribution.get("yanked", False) for distribution in distributions):
            continue
        year, month, patch = (int(part) for part in matched.groups())
        if not 1 <= month <= 12:
            continue
        key = (year, month)
        monthly[key] = max(monthly.get(key, (0, 0, 0)), (year, month, patch))
    return monthly


def make_matrix(releases: dict, minimum: str) -> dict:
    """Select minimum supported, previous stable and latest stable releases."""
    if not re.fullmatch(r"\d{4}\.\d{1,2}", minimum):
        raise ValueError(f"Invalid minimum version: {minimum}")
    year, month = (int(part) for part in minimum.split("."))
    monthly = released_versions(releases)
    keys = sorted(monthly)
    if (year, month) not in monthly or not keys:
        raise ValueError(f"Minimum Home Assistant {minimum} is not on PyPI")
    if (year, month) > keys[-1]:
        raise ValueError("Minimum cannot be newer than latest stable")

    versions = [("minimum-supported", monthly[(year, month)])]
    if len(keys) > 1:
        versions.append(("previous-stable", monthly[keys[-2]]))
    versions.append(("latest-stable", monthly[keys[-1]]))
    # Reuse one job when a release series fills two roles.
    seen = set()
    include = []
    for label, version in versions:
        if version in seen:
            continue
        seen.add(version)
        include.append({"label": label, "ha_version": ".".join(map(str, version))})
    return {"include": include}


def main() -> None:
    """Resolve the matrix and optionally export it to GitHub Actions."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimum", required=True)
    parser.add_argument("--github-output", action="store_true")
    args = parser.parse_args()

    with urlopen(HA_PYPI, timeout=20) as response:
        releases = json.load(response)["releases"]
    matrix = make_matrix(releases, args.minimum)
    encoded = json.dumps(matrix, separators=(",", ":"))
    print(encoded)
    if args.github_output:
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
            output.write(f"matrix={encoded}\n")


if __name__ == "__main__":
    main()
