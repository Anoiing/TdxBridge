from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.serializers import normalize_value


def read_payload() -> dict[str, object]:
    input_path_text = os.environ.get("TDX_BRIDGE_INPUT")
    input_path = Path(input_path_text) if input_path_text else None
    if input_path is not None:
        raw = input_path.read_text(encoding="utf-8").strip()
    else:
        raw = sys.stdin.read().strip()
    if not raw:
        raise ValueError("未收到子进程输入参数。")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("子进程输入参数格式错误。")
    return payload


def write_result(payload: dict[str, object]) -> None:
    output_path_text = os.environ.get("TDX_BRIDGE_OUTPUT")
    output_path = Path(output_path_text) if output_path_text else None
    text = json.dumps(payload, ensure_ascii=False)
    if output_path is not None:
        output_path.write_text(text, encoding="utf-8")
        return
    sys.__stdout__.write(text)
    sys.__stdout__.flush()


def extend_sys_path(install_dir: str) -> None:
    user_path = Path(install_dir) / "PYPlugins" / "user"
    if not user_path.exists():
        raise FileNotFoundError(f"未找到通达信 Python 插件目录：{user_path}")
    user_path_text = str(user_path)
    if user_path_text not in sys.path:
        sys.path.insert(0, user_path_text)


def main() -> int:
    method: str | None = None
    try:
        payload = read_payload()
        install_dir = str(payload.get("tdx_install_dir") or "")
        method = str(payload.get("method") or "")
        params = payload.get("params") or {}

        if not method:
            raise ValueError("method 不能为空。")
        if not isinstance(params, dict):
            raise ValueError("params 必须是对象。")

        extend_sys_path(install_dir)

        from tqcenter import tq  # type: ignore

        tq.initialize(str(Path(__file__).resolve()))
        target = getattr(tq, method, None)
        if target is None:
            raise AttributeError(f"tqcenter.tq 中不存在方法：{method}")

        result = target(**params)
        write_result(
            {
                "ok": True,
                "backend": "python",
                "method": method,
                "data": normalize_value(result),
                "error": None,
            }
        )
        return 0
    except Exception as exc:
        write_result(
            {
                "ok": False,
                "backend": "python",
                "method": method,
                "data": None,
                "error": str(exc),
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
