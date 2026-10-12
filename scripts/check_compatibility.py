"""Check HACS support claims against the actual, dependency-consistent HA runtime."""

import argparse
import json
import re
import tomllib
from importlib.metadata import requires, version
from pathlib import Path

from packaging.requirements import Requirement

FIXTURE = "pytest-homeassistant-custom-component"


def stable_version(value: object) -> tuple[int, int, int]:
    """Require Home Assistant's stable YYYY.M.P form, not prereleases or ranges."""
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}\.(?:[1-9]|1[0-2])\.(?:0|[1-9][0-9]*)", value
    ):
        raise ValueError(
            f"Expected a stable Home Assistant YYYY.M.P version, got {value!r}"
        )
    year, month, patch = value.split(".")
    return int(year), int(month), int(patch)


def check_compatibility(profile: str = "dev", root: Path = Path(".")) -> None:
    """Fail closed on stale fixture selection, incompatible HA, or an untested floor."""
    minimum = json.loads((root / "hacs.json").read_text()).get("homeassistant")
    floor = stable_version(minimum)
    runtime = version("homeassistant")
    tested = stable_version(runtime)
    if floor > tested:
        raise ValueError(
            f"Declared minimum {minimum} is newer than tested HA {runtime}"
        )
    if profile == "minimum" and floor != tested:
        raise ValueError(
            f"Minimum test runtime {runtime} must equal hacs.json "
            f"homeassistant {minimum}; "
            "select a compatible fixture release and update uv.lock deliberately"
        )

    project = tomllib.loads((root / "pyproject.toml").read_text())
    selected = [
        Requirement(item)
        for item in project["dependency-groups"][profile]
        if isinstance(item, str) and Requirement(item).name == FIXTURE
    ]
    fixture_version = version(FIXTURE)
    if len(selected) != 1 or str(selected[0].specifier) != f"=={fixture_version}":
        raise ValueError(
            f"Installed {FIXTURE} {fixture_version} does not match the exact "
            f"{profile} group pin; synchronize the correct locked environment"
        )
    ha_requirements = [
        Requirement(item)
        for item in requires(FIXTURE) or []
        if Requirement(item).name == "homeassistant"
    ]
    if len(ha_requirements) != 1 or str(ha_requirements[0].specifier) != f"=={runtime}":
        raise ValueError(
            f"Fixture {fixture_version} does not require installed HA {runtime}; "
            "do not override fixture dependencies to claim compatibility"
        )
    print(
        f"Compatibility ({profile}): declared minimum {minimum}, "
        f"installed HA {runtime}, fixture {fixture_version}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=("dev", "minimum"))
    args = parser.parse_args()
    try:
        check_compatibility(args.profile)
    except ValueError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
