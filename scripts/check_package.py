"""Validate and build an installation archive without publishing anything."""

import ast
import json
import tomllib
import zipfile
from pathlib import Path

import yaml
from packaging.version import InvalidVersion, Version
from PIL import Image

from scripts.check_compatibility import check_compatibility

ROOT = Path("custom_components/ovapi")


def check_release_versions(root: Path = Path(".")) -> str:
    """Validate release identity statically, without importing the HA integration."""
    release = json.loads((root / ROOT / "manifest.json").read_text()).get("version")
    try:
        parsed = Version(release) if isinstance(release, str) else None
    except InvalidVersion:
        parsed = None
    if (
        parsed is None
        or str(parsed) != release
        or len(parsed.release) != 3
        or parsed.epoch
        or parsed.local is not None
    ):
        raise ValueError(
            "manifest.json version must be canonical three-part PEP 440 "
            f"(for example 1.2.3 or 1.2.3rc1), got {release!r}"
        )
    project = tomllib.loads((root / "pyproject.toml").read_text())
    if project["project"].get("version") != release:
        raise ValueError(
            "pyproject.toml project.version must match manifest.json version"
        )
    constants = ast.parse((root / ROOT / "const.py").read_text())
    versions = [
        node.value
        for node in constants.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "VERSION"
            for target in node.targets
        )
    ]
    if (
        len(versions) != 1
        or not isinstance(versions[0], ast.Constant)
        or versions[0].value != release
    ):
        raise ValueError(
            "const.py VERSION must be a literal matching manifest.json version"
        )
    print(
        "Release identity: manifest.json, const.VERSION and project.version "
        f"= {release}"
    )
    return release


def keys(value: object, prefix: str = "") -> set[str]:
    if not isinstance(value, dict):
        return {prefix}
    return {
        key for name, child in value.items() for key in keys(child, f"{prefix}.{name}")
    }


def main(profile: str = "dev", destination: Path = Path("dist/ovapi.zip")) -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text())
    assert manifest["domain"] == ROOT.name
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "cloud_polling"
    check_release_versions()
    assert manifest["requirements"] == []
    check_compatibility(profile)
    strings = json.loads((ROOT / "strings.json").read_text())
    assert "https://" not in json.dumps(strings), "Use translation URL placeholders"
    assert json.loads((ROOT / "translations/en.json").read_text()) == strings
    assert keys(json.loads((ROOT / "translations/nl.json").read_text())) == keys(
        strings
    )
    assert yaml.safe_load((ROOT / "quality_scale.yaml").read_text())["rules"]
    for module in ROOT.glob("*.py"):
        ast.parse(module.read_text(), filename=str(module))
    for dark in ("", "dark_"):
        for kind in ("icon", "logo"):
            for suffix, size in (("", 256), ("@2x", 512)):
                path = ROOT / "brand" / f"{dark}{kind}{suffix}.png"
                with Image.open(path) as image:
                    assert image.format == "PNG"
                    assert image.height == size
                    assert image.width == (size if kind == "icon" else size * 7 // 2)
                    assert image.mode == "RGBA"
                    image.verify()
    files = sorted(
        path
        for path in ROOT.rglob("*")
        if path.suffix in {".py", ".json", ".yaml"}
        or (path.parent == ROOT / "brand" and path.suffix == ".png")
    )
    destination.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.as_posix())
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == [path.as_posix() for path in files]
    print(f"Validated {len(files)} integration files; created {destination}")


if __name__ == "__main__":
    main()
