"""Validate and build an installation archive without publishing anything."""

import ast
import json
import zipfile
from pathlib import Path

import yaml

ROOT = Path("custom_components/ovapi")


def keys(value: object, prefix: str = "") -> set[str]:
    if not isinstance(value, dict):
        return {prefix}
    return {
        key for name, child in value.items() for key in keys(child, f"{prefix}.{name}")
    }


def main() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text())
    assert manifest["domain"] == ROOT.name
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "cloud_polling"
    assert manifest["version"] == "0.1.0"
    assert manifest["requirements"] == []
    assert json.loads(Path("hacs.json").read_text())["homeassistant"] == "2026.10.0"
    strings = json.loads((ROOT / "strings.json").read_text())
    assert json.loads((ROOT / "translations/en.json").read_text()) == strings
    assert keys(json.loads((ROOT / "translations/nl.json").read_text())) == keys(
        strings
    )
    assert yaml.safe_load((ROOT / "quality_scale.yaml").read_text())["rules"]
    for module in ROOT.glob("*.py"):
        ast.parse(module.read_text(), filename=str(module))
    files = sorted(
        path for path in ROOT.rglob("*") if path.suffix in {".py", ".json", ".yaml"}
    )
    destination = Path("dist/ovapi.zip")
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
