from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.serializers import normalize_value


def _read_payload() -> dict[str, object]:
    input_path = Path(sys.argv[1]) if len(sys.argv) >= 2 else None
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


def _write_result(payload: dict[str, object], real_stdout) -> None:
    output_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else None
    text = json.dumps(payload, ensure_ascii=False)
    if output_path is not None:
        output_path.write_text(text, encoding="utf-8")
        return
    real_stdout.write(text)
    real_stdout.flush()


def _extend_sys_path(install_dir: str) -> None:
    base = Path(install_dir)
    user_path = base / "PYPlugins" / "user"
    if not user_path.exists():
        raise FileNotFoundError(f"未找到通达信 Python 插件目录：{user_path}")
    user_path_text = str(user_path)
    if user_path_text not in sys.path:
        sys.path.insert(0, user_path_text)


def main() -> int:
    method: str | None = None
    real_stdout = sys.__stdout__
    try:
        payload = _read_payload()
        install_dir = str(payload.get("tdx_install_dir") or "")
        method = str(payload.get("method") or "")
        params = payload.get("params") or {}

        if not method:
            raise ValueError("method 不能为空。")
        if not isinstance(params, dict):
            raise ValueError("params 必须是对象。")

        _extend_sys_path(install_dir)
        strategy_entry = PROJECT_ROOT / "runtime" / "tq_strategy_entry.py"
        strategy_entry.parent.mkdir(parents=True, exist_ok=True)
        if not strategy_entry.exists():
            strategy_entry.write_text("# TQ-Python strategy entry for bridge worker.\n", encoding="utf-8")

        from tqcenter import tq  # type: ignore

        tq.initialize(str(strategy_entry.resolve()))
        target = getattr(tq, method, None)
        if target is None:
            raise AttributeError(f"tqcenter.tq 中不存在方法：{method}")

        result = target(**params)
        _write_result(
            {
                "ok": True,
                "backend": "python",
                "method": method,
                "data": normalize_value(result),
                "error": None,
            },
            real_stdout,
        )
        return 0
    except Exception as exc:
        _write_result(
            {
                "ok": False,
                "backend": "python",
                "method": method,
                "data": None,
                "error": str(exc),
            },
            real_stdout,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
