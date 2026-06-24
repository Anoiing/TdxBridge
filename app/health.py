from __future__ import annotations

import platform
import socket
from pathlib import Path
from urllib.parse import urlsplit

import psutil

from app.config import AppConfig
from app.tdx_paths import inspect_tdx_install_dir


def _can_connect(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _is_process_running(name: str) -> bool:
    target = name.lower()
    for process in psutil.process_iter(attrs=["name"]):
        process_name = (process.info.get("name") or "").lower()
        if process_name == target:
            return True
    return False


def _parse_local_rpc_host_port(base_url: str, default_host: str = "127.0.0.1", default_port: int = 17709) -> tuple[str, int]:
    url_text = str(base_url or "").strip()
    if not url_text:
        return default_host, default_port
    try:
        parsed = urlsplit(url_text)
        host = parsed.hostname
        port = parsed.port
    except Exception:
        return default_host, default_port
    if not host:
        return default_host, default_port
    if port is None:
        scheme = (parsed.scheme or "").lower()
        if scheme == "https":
            port = 443
        elif scheme == "http":
            port = 80
        else:
            port = default_port
    return host, int(port)


def collect_health(config: AppConfig) -> dict[str, object]:
    inspection = inspect_tdx_install_dir(config.tdx.install_dir)
    install_dir = Path(inspection.path)
    local_host, local_port = _parse_local_rpc_host_port(config.local_rpc.base_url, "127.0.0.1", 17709)

    return {
        "service": "ok",
        "platform": platform.system(),
        "tdx": {
            "installDir": inspection.path,
            "autoDetected": inspection.is_valid,
        },
        "pythonRuntime": {
            "mode": config.python_runtime.mode,
            "pythonExecutable": config.python_runtime.python_executable,
            "timeoutSec": config.python_runtime.timeout_sec,
        },
        "checks": {
            "isWindows": platform.system() == "Windows",
            "tdxInstallDirExists": inspection.exists,
            "tqcenterExists": inspection.has_tqcenter,
            "tpythDllExists": inspection.has_tpyth_dll,
            "tpythClientDllExists": inspection.has_tpythclient_dll,
            "tdxExecutableExists": inspection.has_tdxw_exe,
            "tdxProcessRunning": _is_process_running("TdxW.exe"),
            "localRpcReachable": _can_connect(local_host, local_port),
        },
    }
