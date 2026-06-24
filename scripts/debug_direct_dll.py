from __future__ import annotations

import argparse
import ctypes
import json
import sys
from pathlib import Path


def get_python_version_number() -> int:
    return int(f"{sys.version_info.major}{sys.version_info.minor}")


def init_connect(
    dll_path: Path,
    strategy_path: Path,
    run_mode: int,
    pass_dll_path: bool,
    python_version_code: int,
) -> tuple[int, str]:
    dll = ctypes.CDLL(str(dll_path))
    dll.InitConnect.restype = ctypes.c_char_p
    dll.CloseConnect.restype = None
    dll.GetTdxDataStr.restype = ctypes.c_char_p

    @ctypes.CFUNCTYPE(None)
    def reinit_cb():
        return None

    init_ptr = dll.InitConnect(
        str(strategy_path).encode("utf-8"),
        str(dll_path).encode("utf-8") if pass_dll_path else b"",
        run_mode,
        python_version_code,
        reinit_cb,
    )
    init_raw = init_ptr.decode("utf-8", "replace") if init_ptr else ""
    init_json = json.loads(init_raw) if init_raw else {}
    run_id = int(init_json.get("run_id", "-1"))

    print(
        json.dumps(
            {
                "stage": "init",
                "strategyPath": str(strategy_path),
                "runMode": run_mode,
                "passDllPath": pass_dll_path,
                "pythonVersionCode": python_version_code,
                "result": init_json,
            },
            ensure_ascii=False,
        )
    )
    return run_id, init_raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="直接诊断 TPythClient.dll 连接状态")
    parser.add_argument("--tdx-root", default=r"C:\tdx64", help="通达信根目录")
    parser.add_argument("--strategy-path", default="", help="策略脚本路径，默认当前脚本")
    parser.add_argument("--keyword", default="寒武纪", help="用于 type=7 检索的关键字")
    parser.add_argument("--run-mode", type=int, default=-1, help="InitConnect run_mode")
    parser.add_argument("--no-dll-path", action="store_true", help="InitConnect 时不传 dll_path")
    parser.add_argument(
        "--python-version-code",
        type=int,
        default=0,
        help="传给 InitConnect 的 Python 版本号，如 310/311/312/313；默认使用当前解释器版本",
    )
    args = parser.parse_args(argv)

    tdx_root = Path(args.tdx_root)
    dll_path = tdx_root / "PYPlugins" / "TPythClient.dll"
    strategy_path = Path(args.strategy_path).resolve() if args.strategy_path else Path(__file__).resolve()

    python_version_code = args.python_version_code or get_python_version_number()

    print(
        json.dumps(
            {
                "python": sys.executable,
                "pythonVersionCode": python_version_code,
                "dllPath": str(dll_path),
                "dllExists": dll_path.exists(),
                "strategyPath": str(strategy_path),
            },
            ensure_ascii=False,
        )
    )

    if not dll_path.exists():
        print(json.dumps({"stage": "precheck", "error": "missing TPythClient.dll"}, ensure_ascii=False))
        return 2

    dll = ctypes.CDLL(str(dll_path))
    dll.GetTdxDataStr.restype = ctypes.c_char_p
    dll.CloseConnect.restype = None

    run_id, _ = init_connect(
        dll_path,
        strategy_path,
        args.run_mode,
        not args.no_dll_path,
        python_version_code,
    )
    if run_id < 0:
        return 3

    try:
        for request in (
            {"id": run_id, "type": 19},
            {"id": run_id, "type": 7, "key_word": args.keyword},
        ):
            raw_ptr = dll.GetTdxDataStr(run_id, json.dumps(request, ensure_ascii=False).encode("utf-8"), 10000)
            raw = raw_ptr.decode("utf-8", "replace") if raw_ptr else ""
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = raw
            print(
                json.dumps(
                    {
                        "stage": "request",
                        "request": request,
                        "result": parsed,
                    },
                    ensure_ascii=False,
                )
            )
    finally:
        dll.CloseConnect(run_id, args.run_mode)
        print(json.dumps({"stage": "close", "runId": run_id}, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
