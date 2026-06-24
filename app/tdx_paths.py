from __future__ import annotations

import platform
import string
from dataclasses import dataclass
from pathlib import Path


COMMON_TDX_DIR_NAMES = ("new_tdx64", "tdx64")
COMMON_PROGRAM_FILES_DIR_NAMES = ("Program Files", "Program Files (x86)")


@dataclass
class TdxInstallInspection:
    path: str
    exists: bool
    is_dir: bool
    has_tdxw_exe: bool
    has_tqcenter: bool
    has_tpyth_dll: bool
    has_tpythclient_dll: bool

    @property
    def is_valid(self) -> bool:
        return self.exists and self.is_dir and (
            self.has_tdxw_exe or self.has_tqcenter or self.has_tpyth_dll or self.has_tpythclient_dll
        )


def inspect_tdx_install_dir(path: str | Path | None) -> TdxInstallInspection:
    raw_path = "" if path is None else str(path).strip()
    if not raw_path:
        return TdxInstallInspection(
            path="",
            exists=False,
            is_dir=False,
            has_tdxw_exe=False,
            has_tqcenter=False,
            has_tpyth_dll=False,
            has_tpythclient_dll=False,
        )

    candidate = Path(raw_path)
    tdxw_exe = candidate / "TdxW.exe"
    tqcenter = candidate / "PYPlugins" / "user" / "tqcenter.py"
    tpyth_dll = candidate / "PYPlugins" / "TPyth.dll"
    tpythclient_dll = candidate / "PYPlugins" / "TPythClient.dll"

    return TdxInstallInspection(
        path=str(candidate),
        exists=candidate.exists(),
        is_dir=candidate.is_dir(),
        has_tdxw_exe=tdxw_exe.exists(),
        has_tqcenter=tqcenter.exists(),
        has_tpyth_dll=tpyth_dll.exists(),
        has_tpythclient_dll=tpythclient_dll.exists(),
    )


def _normalize_existing_dir(path: str | Path | None) -> str | None:
    raw_path = "" if path is None else str(path).strip()
    if not raw_path:
        return None

    candidate = Path(raw_path)
    if not candidate.exists() or not candidate.is_dir():
        return None
    return str(candidate)


def list_nearby_tdx_candidates(anchor: str | Path | None = None) -> list[str]:
    normalized_anchor = _normalize_existing_dir(anchor)
    if not normalized_anchor:
        return []

    anchor_path = Path(normalized_anchor)
    parent_dir = anchor_path.parent
    if not parent_dir.exists() or not parent_dir.is_dir():
        return []

    candidates: list[str] = [str(parent_dir)]

    for dir_name in COMMON_TDX_DIR_NAMES:
        candidates.append(str(parent_dir / dir_name))

    try:
        siblings = sorted(
            (entry for entry in parent_dir.iterdir() if entry.is_dir() and entry != anchor_path),
            key=lambda entry: entry.name.lower(),
        )
    except OSError:
        siblings = []

    named_siblings: list[Path] = []
    other_siblings: list[Path] = []
    for sibling in siblings:
        if sibling.name.lower() in COMMON_TDX_DIR_NAMES:
            named_siblings.append(sibling)
        else:
            other_siblings.append(sibling)

    for sibling in named_siblings + other_siblings:
        candidates.append(str(sibling))

    return list(dict.fromkeys(candidates))


def list_common_tdx_candidates(anchor: str | Path | None = None) -> list[str]:
    candidates: list[str] = list_nearby_tdx_candidates(anchor)
    if platform.system() != "Windows":
        return candidates

    for letter in string.ascii_uppercase:
        root = Path(f"{letter}:\\")
        if not root.exists():
            continue

        for dir_name in COMMON_TDX_DIR_NAMES:
            candidates.append(str(root / dir_name))

        for program_dir in COMMON_PROGRAM_FILES_DIR_NAMES:
            for dir_name in COMMON_TDX_DIR_NAMES:
                candidates.append(str(root / program_dir / dir_name))

    # 去重并保持顺序
    return list(dict.fromkeys(candidates))


def detect_tdx_install_dir(preferred: str | Path | None = None, anchor: str | Path | None = None) -> str | None:
    if preferred:
        inspected = inspect_tdx_install_dir(preferred)
        if inspected.is_valid:
            return inspected.path

    effective_anchor = anchor if anchor is not None else Path.cwd()
    for candidate in list_common_tdx_candidates(effective_anchor):
        inspected = inspect_tdx_install_dir(candidate)
        if inspected.is_valid:
            return inspected.path
    return None
