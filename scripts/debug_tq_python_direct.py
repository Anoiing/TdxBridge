from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="直接诊断 tqcenter Python 通道")
    parser.add_argument("--tdx-root", default=r"C:\tdx64", help="通达信根目录")
    parser.add_argument("--strategy-path", default="", help="传给 tq.initialize(path) 的策略路径")
    parser.add_argument("--method", default="get_user_sector", help="要调用的 tq 方法")
    parser.add_argument("--params", default="{}", help="JSON 格式的参数对象")
    parser.add_argument("--dll-path", default="", help="可选：覆盖传给 tq.initialize 的 dll_path")
    args = parser.parse_args(argv)

    tdx_root = Path(args.tdx_root)
    user_path = tdx_root / "PYPlugins" / "user"
    strategy_path = Path(args.strategy_path).resolve() if args.strategy_path else Path(__file__).resolve()

    print(json.dumps(
        {
            "python": sys.executable,
            "cwd": os.getcwd(),
            "argv": sys.argv,
            "tdxRoot": str(tdx_root),
            "userPath": str(user_path),
            "userPathExists": user_path.exists(),
            "strategyPath": str(strategy_path),
            "strategyExists": strategy_path.exists(),
            "dllPathOverride": args.dll_path,
        },
        ensure_ascii=False,
    ))

    if str(user_path) not in sys.path:
        sys.path.insert(0, str(user_path))

    try:
        params = json.loads(args.params)
        if not isinstance(params, dict):
            raise ValueError("params 必须是 JSON 对象")

        from tqcenter import tq  # type: ignore

        print(
            json.dumps(
                {
                    "stage": "import",
                    "defaultDllPath": str(getattr(tq, "dll_path", "")),
                    "runMode": getattr(tq, "run_mode", None),
                    "initialized": getattr(tq, "_initialized", None),
                    "connectionPathBefore": getattr(tq, "_connection_path", None),
                },
                ensure_ascii=False,
            )
        )

        if args.dll_path:
            tq.initialize(str(strategy_path), dll_path=args.dll_path)
        else:
            tq.initialize(str(strategy_path))

        print(
            json.dumps(
                {
                    "stage": "initialized",
                    "connectionPathAfter": getattr(tq, "_connection_path", None),
                    "dllPathAfter": str(getattr(tq, "dll_path", "")),
                    "runId": getattr(tq, "run_id", None),
                    "initializedFlag": getattr(tq, "_initialized", None),
                },
                ensure_ascii=False,
            )
        )

        target = getattr(tq, args.method, None)
        if target is None:
            raise AttributeError(f"tqcenter.tq 中不存在方法：{args.method}")
        result = target(**params)
        print(json.dumps({"stage": "result", "ok": True, "data": result}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"stage": "result", "ok": False, "error": str(exc)}, ensure_ascii=False))
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
