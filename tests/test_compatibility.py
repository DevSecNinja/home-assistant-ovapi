"""Guard the advertised support floor using metadata, not duplicated literals."""

import json
import sys

import pytest

from scripts import check_compatibility as compatibility


@pytest.fixture
def compatibility_project(tmp_path, monkeypatch):
    """Small metadata-only project, independent of the active test runtime."""
    (tmp_path / "hacs.json").write_text(json.dumps({"homeassistant": "2026.10.0"}))
    (tmp_path / "pyproject.toml").write_text(
        "[dependency-groups]\n"
        'dev = ["pytest-homeassistant-custom-component==0.13.372"]\n'
        'minimum = ["pytest-homeassistant-custom-component==0.13.371"]\n'
    )
    installed = {
        "homeassistant": "2026.10.1",
        compatibility.FIXTURE: "0.13.372",
    }
    dependencies = ["homeassistant==2026.10.1", "pytest>=9"]
    monkeypatch.setattr(compatibility, "version", installed.__getitem__)
    monkeypatch.setattr(compatibility, "requires", lambda _: dependencies)
    return tmp_path, installed, dependencies


@pytest.mark.parametrize(
    "value",
    [
        None,
        2026.10,
        "",
        "2026.10",
        "2026.10.0b1",
        "2026.10.0.dev1",
        ">=2026.10.0",
        "v2026.10.0",
        "2026.13.0",
        "2026.0.0",
        "2026.010.0",
        "2026.10.00",
        "2026.10.-1",
        " 2026.10.0",
        "2026.10.0\n",
    ],
)
def test_malformed_minimum(compatibility_project, value):
    root, _, _ = compatibility_project
    (root / "hacs.json").write_text(json.dumps({"homeassistant": value}))
    with pytest.raises(ValueError, match="stable Home Assistant"):
        compatibility.check_compatibility(root=root)


def test_current_runtime_can_be_newer(compatibility_project, capsys):
    root, _, _ = compatibility_project
    compatibility.check_compatibility(root=root)
    assert (
        "declared minimum 2026.10.0, installed HA 2026.10.1" in capsys.readouterr().out
    )


def test_matching_minimum(compatibility_project):
    root, installed, dependencies = compatibility_project
    installed.update({"homeassistant": "2026.10.0", compatibility.FIXTURE: "0.13.371"})
    dependencies[0] = "homeassistant==2026.10.0"
    compatibility.check_compatibility("minimum", root)


def test_minimum_newer_than_tested_runtime(compatibility_project):
    root, _, _ = compatibility_project
    (root / "hacs.json").write_text('{"homeassistant": "2026.11.0"}')
    with pytest.raises(ValueError, match="newer than tested HA"):
        compatibility.check_compatibility(root=root)


def test_minimum_must_be_exactly_exercised(compatibility_project):
    root, _, _ = compatibility_project
    with pytest.raises(ValueError, match="must equal hacs.json"):
        compatibility.check_compatibility("minimum", root)


def test_changed_minimum_cannot_leave_stale_fixture(compatibility_project):
    root, installed, dependencies = compatibility_project
    (root / "hacs.json").write_text('{"homeassistant": "2026.9.0"}')
    installed.update({"homeassistant": "2026.10.0", compatibility.FIXTURE: "0.13.371"})
    dependencies[0] = "homeassistant==2026.10.0"
    with pytest.raises(ValueError, match="must equal hacs.json"):
        compatibility.check_compatibility("minimum", root)


def test_stale_lock_or_wrong_group(compatibility_project):
    root, installed, _ = compatibility_project
    installed[compatibility.FIXTURE] = "0.13.371"
    with pytest.raises(ValueError, match="does not match the exact dev group pin"):
        compatibility.check_compatibility(root=root)


@pytest.mark.parametrize(
    "requirements",
    [[], ["homeassistant==2026.10.0"], ["homeassistant>=2026.10.0"]],
)
def test_fixture_dependency_must_not_be_overridden(compatibility_project, requirements):
    root, _, dependencies = compatibility_project
    dependencies[:] = requirements
    with pytest.raises(ValueError, match="do not override fixture dependencies"):
        compatibility.check_compatibility(root=root)


def test_missing_fixture_pin(compatibility_project):
    root, _, _ = compatibility_project
    (root / "pyproject.toml").write_text('[dependency-groups]\ndev = ["pytest"]\n')
    with pytest.raises(ValueError, match="does not match the exact dev group pin"):
        compatibility.check_compatibility(root=root)


def test_order_is_numeric_not_lexical():
    assert compatibility.stable_version("2026.10.0") > compatibility.stable_version(
        "2026.9.12"
    )
    assert compatibility.stable_version("2026.10.10") > compatibility.stable_version(
        "2026.10.2"
    )


def test_prerelease_test_runtime_is_not_stable_evidence(compatibility_project):
    root, installed, _ = compatibility_project
    installed["homeassistant"] = "2026.10.1b1"
    with pytest.raises(ValueError, match="stable Home Assistant"):
        compatibility.check_compatibility(root=root)


def test_cli_reports_selected_runtime(compatibility_project, monkeypatch, capsys):
    root, _, _ = compatibility_project
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", ["check_compatibility.py", "dev"])
    compatibility.main()
    assert "Compatibility (dev)" in capsys.readouterr().out


def test_cli_exits_on_metadata_drift(compatibility_project, monkeypatch):
    root, _, _ = compatibility_project
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", ["check_compatibility.py", "minimum"])
    with pytest.raises(SystemExit, match="must equal hacs.json"):
        compatibility.main()
