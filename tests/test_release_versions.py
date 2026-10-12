"""The manifest owns release identity; schema/protocol versions are independent."""

import json

import pytest

from scripts.check_package import check_release_versions


@pytest.fixture
def release_project(tmp_path):
    integration = tmp_path / "custom_components/ovapi"
    integration.mkdir(parents=True)
    (integration / "manifest.json").write_text('{"version": "1.2.3"}')
    (integration / "const.py").write_text('VERSION = "1.2.3"\n')
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n')
    return tmp_path


@pytest.mark.parametrize("release", ["0.2.0", "1.0.0", "2.3.4rc1"])
def test_coherent_release_bump_passes(release_project, release):
    root = release_project
    (root / "custom_components/ovapi/manifest.json").write_text(
        json.dumps({"version": release})
    )
    (root / "custom_components/ovapi/const.py").write_text(
        f"VERSION = {release!r}\nAPI_URL = 'http://v0.ovapi.nl/tpc'\n"
    )
    (root / "pyproject.toml").write_text(f"[project]\nversion = {release!r}\n")
    assert check_release_versions(root) == release


@pytest.mark.parametrize(
    "release",
    [
        None,
        123,
        "",
        "invalid",
        "v1.2.3",
        "1.2",
        "1.2.3.4",
        "01.2.3",
        "1!1.2.3",
        "1.2.3+local",
    ],
)
def test_invalid_manifest_release(release_project, release):
    (release_project / "custom_components/ovapi/manifest.json").write_text(
        json.dumps({"version": release})
    )
    with pytest.raises(ValueError, match="canonical three-part PEP 440"):
        check_release_versions(release_project)


def test_project_version_mismatch(release_project):
    (release_project / "pyproject.toml").write_text('[project]\nversion = "1.2.4"\n')
    with pytest.raises(ValueError, match="project.version must match manifest"):
        check_release_versions(release_project)


@pytest.mark.parametrize(
    "source",
    [
        'VERSION = "1.2.4"\n',
        "VERSION = 123\n",
        "VERSION = get_version()\n",
        'VERSION = "1.2.3"\nVERSION = "1.2.4"\n',
        'API_URL = "http://v0.ovapi.nl/tpc"\n',
    ],
)
def test_constant_mismatch_or_dynamic_value(release_project, source):
    (release_project / "custom_components/ovapi/const.py").write_text(source)
    with pytest.raises(ValueError, match="const.py VERSION must be a literal matching"):
        check_release_versions(release_project)


def test_does_not_import_integration_or_synchronize_protocols(release_project):
    integration = release_project / "custom_components/ovapi"
    (integration / "__init__.py").write_text('raise RuntimeError("must not import")\n')
    (integration / "const.py").write_text(
        'VERSION = "1.2.3"\nAPI_URL = "http://v0.ovapi.nl/tpc"\n'
    )
    (integration / "config_flow.py").write_text("class ConfigFlow:\n    VERSION = 1\n")
    (release_project / "hacs.json").write_text('{"homeassistant": "2026.10.0"}')
    assert check_release_versions(release_project) == "1.2.3"
