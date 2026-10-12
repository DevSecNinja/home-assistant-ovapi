"""Enforce coverage per integration module, never only the aggregate."""

import json
from pathlib import Path


def main() -> None:
    report = json.loads(Path("coverage.json").read_text())
    failures = []
    modules = sorted(Path("custom_components/ovapi").glob("*.py"))
    for module in modules:
        summary = report["files"].get(module.as_posix(), {}).get("summary")
        if summary is None:
            failures.append(f"{module}: absent from coverage report")
            continue
        statements = summary["num_statements"]
        branches = summary["num_branches"]
        lines = 100 * summary["covered_lines"] / statements if statements else 100
        branch = 100 * summary["covered_branches"] / branches if branches else 100
        full = module.name == "config_flow.py"
        passed = lines == branch == 100 if full else lines > 95 and branch > 95
        print(f"{module.name}: statements {lines:.2f}%, branches {branch:.2f}%")
        if not passed:
            failures.append(f"{module}: requires {'100%' if full else '>95%'} in both")
    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
