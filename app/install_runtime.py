from __future__ import annotations

import importlib.metadata
import importlib.util
import ipaddress
import json
import re
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.tdx_paths import detect_tdx_install_dir, list_common_tdx_candidates

try:
    from packaging.requirements import InvalidRequirement, Requirement
    from packaging.version import InvalidVersion, Version
    HAS_PACKAGING = True
except Exception:  # pragma: no cover - packaging 可能未预装
    HAS_PACKAGING = False
    class _FallbackRequirementError(ValueError):
        pass
    class InvalidRequirement(_FallbackRequirementError):
        pass
    class InvalidVersion(_FallbackRequirementError):
        pass

    class Requirement:
        def __init__(self, raw: str):
            self.raw = raw
            self.specifier = self._extract_spec(raw)

        @staticmethod
        def _extract_spec(raw: str):
            raw = raw.strip()
            if "[" in raw and "]" in raw:
                raw = raw[raw.index("]") + 1 :]
            for operator in (">=", "<=", "==", "!=", "~=", ">", "<"):
                position = raw.find(operator)
                if position >= 0:
                    return raw[position:].strip()
            return raw

RUNTIME_DEPENDENCIES = [
    {
        "name": "fastapi",
        "module": "fastapi",
        "distribution": "fastapi",
        "requirement": "fastapi>=0.116,<1.0",
    },
    {
        "name": "uvicorn",
        "module": "uvicorn",
        "distribution": "uvicorn",
        "requirement": "uvicorn[standard]>=0.35,<1.0",
    },
    {
        "name": "psutil",
        "module": "psutil",
        "distribution": "psutil",
        "requirement": "psutil>=7.0,<8.0",
    },
    {
        "name": "pydantic",
        "module": "pydantic",
        "distribution": "pydantic",
        "requirement": "pydantic>=2.11,<3.0",
    },
    {
        "name": "requests",
        "module": "requests",
        "distribution": "requests",
        "requirement": "requests>=2.32,<3.0",
    },
    {
        "name": "numpy",
        "module": "numpy",
        "distribution": "numpy",
        "requirement": "numpy>=2.2,<3.0",
    },
    {
        "name": "pandas",
        "module": "pandas",
        "distribution": "pandas",
        "requirement": "pandas>=2.3,<3.0",
    },
    {
        "name": "tzdata",
        "module": "tzdata",
        "distribution": "tzdata",
        "requirement": "tzdata>=2025.2",
    },
]


def _parse_version_tuple(raw: str) -> tuple[int, ...]:
    if not raw:
        return ()
    numbers: list[int] = []
    for part in re.split(r"[.+_-]", raw):
        match = re.match(r"(\d+)", str(part).strip())
        if match:
            numbers.append(int(match.group(1)))
    return tuple(numbers)


def _compare_versions(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    max_len = max(len(left), len(right))
    left_values = left + (0,) * (max_len - len(left))
    right_values = right + (0,) * (max_len - len(right))
    if left_values < right_values:
        return -1
    if left_values > right_values:
        return 1
    return 0


def _satisfy_single_spec(version: str, spec: str) -> bool:
    spec = spec.strip()
    if not spec:
        return True
    match = re.match(r"^(>=|<=|==|!=|~=|>|<)\s*([^\s]+)$", spec)
    if not match:
        return False

    op, target = match.group(1), match.group(2)
    if not target:
        return False

    installed = _parse_version_tuple(version)
    target_tuple = _parse_version_tuple(target)
    if not installed:
        return False

    if op == ">=":
        return _compare_versions(installed, target_tuple) >= 0
    if op == ">":
        return _compare_versions(installed, target_tuple) > 0
    if op == "<=":
        return _compare_versions(installed, target_tuple) <= 0
    if op == "<":
        return _compare_versions(installed, target_tuple) < 0
    if op == "==":
        if target.endswith(".*"):
            prefix = _parse_version_tuple(target[:-2])
            return _compare_versions(installed[: len(prefix)], prefix) == 0 if prefix else False
        return _compare_versions(installed, target_tuple) == 0
    if op == "!=":
        if target.endswith(".*"):
            prefix = _parse_version_tuple(target[:-2])
            return not (
                _compare_versions(installed[: len(prefix)], prefix) == 0 if prefix else False
            )
        return _compare_versions(installed, target_tuple) != 0
    if op == "~=":
        if not target_tuple:
            return False
        left_ok = _compare_versions(installed, target_tuple) >= 0
        major = target_tuple[0] + 1
        upper = (major,)
        return left_ok and _compare_versions(installed, upper) < 0
    return False


def is_requirement_satisfied(installed_version: str | None, requirement: str) -> bool:
    if not installed_version:
        return False

    if HAS_PACKAGING:
        try:
            parsed = Requirement(requirement)
            version = Version(installed_version)
        except (InvalidRequirement, InvalidVersion, ValueError, TypeError):
            return False
        return version in parsed.specifier

    try:
        parsed = Requirement(requirement)
        requirement = parsed.specifier
    except Exception:
        return False

    if not requirement:
        return True

    for spec in str(requirement).split(","):
        if not _satisfy_single_spec(installed_version, spec):
            return False
    return True


def cmd_detect_tdx() -> int:
    print(
        json.dumps(
            {
                "detected": detect_tdx_install_dir(anchor=PROJECT_ROOT),
                "candidates": list_common_tdx_candidates(PROJECT_ROOT),
            },
            ensure_ascii=False,
        )
    )
    return 0


def cmd_validate_cidr(argv: list[str]) -> int:
    if len(argv) < 1 or not str(argv[0]).strip():
        return 1
    try:
        ipaddress.ip_network(argv[0], strict=False)
    except ValueError:
        return 1
    return 0


def cmd_check_runtime_deps() -> int:
    deps: list[dict[str, object]] = []
    missing: list[str] = []
    for item in RUNTIME_DEPENDENCIES:
        module_name = str(item["module"])
        installed = importlib.util.find_spec(module_name) is not None
        version = None
        requirement = str(item["requirement"])
        version_ok = False
        if installed:
            try:
                version = importlib.metadata.version(str(item["distribution"]))
            except importlib.metadata.PackageNotFoundError:
                version = None
            else:
                version_ok = is_requirement_satisfied(version, requirement)
        dep = {
            "name": item["name"],
            "module": module_name,
            "distribution": item["distribution"],
            "requirement": item["requirement"],
            "installed": installed,
            "version": version,
            "requirement_satisfied": version_ok,
        }
        deps.append(dep)
        if (not installed) or (not version_ok):
            missing.append(str(item["name"]))

    print(
        json.dumps(
            {
                "ready": len(missing) == 0,
                "total": len(deps),
                "installed_count": len(deps) - len(missing),
                "missing_count": len(missing),
                "missing": missing,
                "deps": deps,
            },
            ensure_ascii=False,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("missing command", file=sys.stderr)
        return 2

    command = args.pop(0)
    if command == "detect_tdx":
        return cmd_detect_tdx()
    if command == "validate_cidr":
        return cmd_validate_cidr(args)
    if command == "check_runtime_deps":
        return cmd_check_runtime_deps()

    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
