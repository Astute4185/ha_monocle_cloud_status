"""Fast network-free checks for CI release selection and runtime pin updates."""

import pytest
from scripts.select_ha_versions import make_matrix, released_versions
from scripts.update_runtime import latest_in_major, synchronize


def test_ha_matrix_uses_latest_patches_and_ignores_prereleases():
    """Select the minimum, previous and current monthly stable releases."""
    data = {
        "2026.8.0": [{"yanked": False}],
        "2026.8.3": [{"yanked": False}],
        "2026.10.4": [{"yanked": False}],
        "2026.11.0b6": [{"yanked": False}],
        "2026.11.1": [{"yanked": False}],
        "2026.11.2": [{"yanked": True}],
    }
    assert len(released_versions(data)) == 3
    assert make_matrix(data, "2026.8") == {
        "include": [
            {"label": "minimum-supported", "ha_version": "2026.8.3"},
            {"label": "previous-stable", "ha_version": "2026.10.4"},
            {"label": "latest-stable", "ha_version": "2026.11.1"},
        ]
    }


def test_ha_matrix_avoids_duplicate_series():
    """Latest and minimum series may be the same at project launch."""
    assert make_matrix({"2026.8.1": [{"yanked": False}]}, "2026.8") == {
        "include": [{"label": "minimum-supported", "ha_version": "2026.8.1"}]
    }


def test_ha_matrix_rejects_unsupported_minimum():
    """CI must fail clearly if the minimum cannot be resolved."""
    with pytest.raises(ValueError, match="not on PyPI"):
        make_matrix({"2026.11.1": [{"yanked": False}]}, "2026.8")


def test_runtime_updater_preserves_manifest_and_comment():
    """Only the dependency version changes; both pins remain identical."""
    initial = "# runtime requirements\npython-socketio[asyncio-client]==5.16.4\n"
    manifest = {
        "version": "1.2.0",
        "requirements": ["python-socketio[asyncio-client]==5.16.4"],
    }
    updated, new_manifest = synchronize(initial, manifest, "5.17.0")
    assert updated == (
        "# runtime requirements\npython-socketio[asyncio-client]==5.17.0\n"
    )
    assert new_manifest["requirements"] == ["python-socketio[asyncio-client]==5.17.0"]
    assert manifest["requirements"] == ["python-socketio[asyncio-client]==5.16.4"]
    assert new_manifest["version"] == "1.2.0"


def test_runtime_updater_rejects_mismatch_and_major_upgrade():
    """An unexpected or breaking change must not be silently applied."""
    manifest = {"requirements": ["python-socketio[asyncio-client]==5.16.4"]}
    with pytest.raises(ValueError, match="differ"):
        synchronize("python-socketio[asyncio-client]==5.15.0\n", manifest, "5.17.0")
    with pytest.raises(ValueError, match="Major"):
        synchronize("python-socketio[asyncio-client]==5.16.4\n", manifest, "6.0.0")


def test_runtime_updater_ignores_yanked_and_other_major():
    """Updates remain within the approved major release line."""
    assert (
        latest_in_major(
            {
                "5.16.4": [{"yanked": False}],
                "5.17.0": [{"yanked": False}],
                "5.17.1": [{"yanked": True}],
                "6.0.0": [{"yanked": False}],
                "5.18.0rc1": [{"yanked": False}],
            },
            5,
        )
        == "5.17.0"
    )
