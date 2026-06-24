from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from app.config import AppConfig
from app.serializers import normalize_value
from app.tdx_paths import detect_tdx_install_dir


class TqPythonRuntime:
    """以子进程隔离方式执行通达信 Python 接口。"""

    def __init__(self, config: AppConfig):
        self._config = config

    def _resolve_python_executable(self) -> str:
        configured = self._config.python_runtime.python_executable
        resolved = shutil.which(configured)
        if resolved:
            return resolved
        return sys.executable

    @staticmethod
    def _parse_worker_output(raw_stdout: str) -> dict[str, Any]:
        text = raw_stdout.strip()
        if not text:
            raise json.JSONDecodeError("empty output", raw_stdout, 0)

        decoder = json.JSONDecoder()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in reversed(lines):
            if not (line.startswith("{") and line.endswith("}")):
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

        for start, char in enumerate(text):
            if char != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(text[start:])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

        raise json.JSONDecodeError("no valid json object found", raw_stdout, 0)

    def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        del trace_id
        install_dir = detect_tdx_install_dir(self._config.tdx.install_dir) or self._config.tdx.install_dir
        runtime_dir = Path(__file__).resolve().parent.parent / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        worker_path = Path(__file__).resolve().parent / "tqPythonWorker.py"
        with tempfile.NamedTemporaryFile("w", delete=False, dir=runtime_dir, encoding="utf-8", suffix=".json") as input_file:
            input_path = Path(input_file.name)
        with tempfile.NamedTemporaryFile("w", delete=False, dir=runtime_dir, encoding="utf-8", suffix=".json") as output_file:
            output_path = Path(output_file.name)
        input_path.write_text(
            json.dumps(
                {
                    "tdx_install_dir": install_dir,
                    "method": method,
                    "params": params or {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        command = [self._resolve_python_executable(), str(worker_path), str(input_path), str(output_path)]

        try:
            completed = subprocess.run(
                command,
                timeout=self._config.python_runtime.timeout_sec,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "backend": "python",
                "method": method,
                "data": None,
                "error": "TQ-Python 子进程执行超时。",
            }
        except OSError as exc:
            return {
                "ok": False,
                "backend": "python",
                "method": method,
                "data": None,
                "error": f"TQ-Python 子进程启动失败：{exc}",
            }
        finally:
            if input_path.exists():
                input_path.unlink()
            if "completed" not in locals() and output_path.exists():
                output_path.unlink()

        raw_output = ""
        try:
            if output_path.exists():
                raw_output = output_path.read_text(encoding="utf-8").strip()
        finally:
            if output_path.exists():
                output_path.unlink()

        if not raw_output:
            stderr_text = (completed.stderr or "").strip()
            stdout_text = (completed.stdout or "").strip()
            details = []
            if stdout_text:
                details.append(f"stdout={stdout_text[:300]}")
            if stderr_text:
                details.append(f"stderr={stderr_text[:300]}")
            detail_text = f"；{'；'.join(details)}" if details else ""
            return {
                "ok": False,
                "backend": "python",
                "method": method,
                "data": None,
                "error": f"TQ-Python 子进程无有效输出，退出码={completed.returncode}{detail_text}",
            }

        try:
            result = self._parse_worker_output(raw_output)
        except json.JSONDecodeError as exc:
            return {
                "ok": False,
                "backend": "python",
                "method": method,
                "data": None,
                "error": f"TQ-Python 输出不是合法 JSON：{exc}",
            }

        result["data"] = normalize_value(result.get("data"))
        result.setdefault("backend", "python")
        result.setdefault("method", method)
        return result
