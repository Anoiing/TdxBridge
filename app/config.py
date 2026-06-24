from __future__ import annotations

import json
import ipaddress
import secrets
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.tdx_paths import detect_tdx_install_dir


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
LOGS_DIR = PROJECT_ROOT / "logs"
RUNTIME_DIR = PROJECT_ROOT / "runtime"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "bridge.json"
EXAMPLE_CONFIG_PATH = CONFIG_DIR / "bridge.example.json"
PLACEHOLDER_TOKENS = {"replace-with-generated-token", "auto-generated-token"}


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 18888


@dataclass
class LocalRpcConfig:
    base_url: str = "http://127.0.0.1:17709/"
    timeout_sec: int = 15


@dataclass
class AuthConfig:
    token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    allow_anonymous_health: bool = True
    allow_anonymous_capabilities: bool = False


@dataclass
class NetworkConfig:
    allowed_cidrs: list[str] = field(default_factory=list)


@dataclass
class TdxConfig:
    install_dir: str = r"C:\tdx64"


@dataclass
class PythonRuntimeConfig:
    mode: str = "subprocess-per-call"
    timeout_sec: int = 20
    python_executable: str = "python"


@dataclass
class RiskControlConfig:
    enable_trading: bool = False
    enable_block_push: bool = False
    enable_warn_send: bool = False
    enable_backtest_send: bool = False


@dataclass
class LoggingConfig:
    level: str = "INFO"
    retain_days: int = 14


@dataclass
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    local_rpc: LocalRpcConfig = field(default_factory=LocalRpcConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    tdx: TdxConfig = field(default_factory=TdxConfig)
    python_runtime: PythonRuntimeConfig = field(default_factory=PythonRuntimeConfig)
    risk_control: RiskControlConfig = field(default_factory=RiskControlConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _merge_dataclass(dataclass_type: type, data: dict[str, Any] | None):
    base = dataclass_type()
    if not data:
        return base
    for key, value in data.items():
        if hasattr(base, key):
            setattr(base, key, value)
    return base


def _validate_config(config: AppConfig) -> list[str]:
    errors: list[str] = []

    if not config.server.host or not str(config.server.host).strip():
        errors.append("server.host 不能为空。")
    if not isinstance(config.server.host, str):
        errors.append("server.host 必须是字符串。")
    if not isinstance(config.server.port, int) or not (1 <= config.server.port <= 65535):
        errors.append("server.port 必须在 1 到 65535 之间。")

    token = str(config.auth.token or "").strip()
    if not token:
        errors.append("auth.token 不能为空。")
    if token in PLACEHOLDER_TOKENS:
        errors.append("auth.token 不能使用占位值，请替换为实际随机 Token。")

    local_rpc_url = str(config.local_rpc.base_url or "").strip()
    if not (local_rpc_url.startswith("http://") or local_rpc_url.startswith("https://")):
        errors.append("local_rpc.base_url 必须是 http:// 或 https:// 开头的地址。")
    if not isinstance(config.local_rpc.timeout_sec, int) or config.local_rpc.timeout_sec <= 0:
        errors.append("local_rpc.timeout_sec 必须是大于 0 的整数。")

    python_executable = str(config.python_runtime.python_executable or "").strip()
    if not python_executable:
        errors.append("python_runtime.python_executable 不能为空。")
    if not isinstance(config.python_runtime.mode, str):
        errors.append("python_runtime.mode 必须是字符串。")
    if not isinstance(config.python_runtime.timeout_sec, int) or config.python_runtime.timeout_sec <= 0:
        errors.append("python_runtime.timeout_sec 必须是大于 0 的整数。")

    if not isinstance(config.auth.allow_anonymous_health, bool):
        errors.append("auth.allow_anonymous_health 必须是布尔值。")
    if not isinstance(config.auth.allow_anonymous_capabilities, bool):
        errors.append("auth.allow_anonymous_capabilities 必须是布尔值。")

    if not isinstance(config.network.allowed_cidrs, list):
        errors.append("network.allowed_cidrs 必须是列表。")
    else:
        for cidr in config.network.allowed_cidrs:
            try:
                ipaddress.ip_network(str(cidr).strip(), strict=False)
            except ValueError:
                errors.append(f"network.allowed_cidrs 中存在非法网段：{cidr}")
            except TypeError:
                errors.append(f"network.allowed_cidrs 中存在非法网段：{cidr}")

    if not isinstance(config.logging.retain_days, int) or config.logging.retain_days < 1:
        errors.append("logging.retain_days 必须是大于 0 的整数。")
    if not isinstance(config.logging.level, str):
        errors.append("logging.level 必须是字符串。")

    for key in ("enable_trading", "enable_block_push", "enable_warn_send", "enable_backtest_send"):
        if not isinstance(getattr(config.risk_control, key), bool):
            errors.append(f"risk_control.{key} 必须是布尔值。")


    return errors


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        config = AppConfig()
        detected_tdx_dir = detect_tdx_install_dir(config.tdx.install_dir)
        if detected_tdx_dir:
            config.tdx.install_dir = detected_tdx_dir
        _write_json(config_path, config.to_dict())
        return config

    raw = _read_json(config_path)
    config = AppConfig(
        server=_merge_dataclass(ServerConfig, raw.get("server")),
        local_rpc=_merge_dataclass(LocalRpcConfig, raw.get("local_rpc")),
        auth=_merge_dataclass(AuthConfig, raw.get("auth")),
        network=_merge_dataclass(NetworkConfig, raw.get("network")),
        tdx=_merge_dataclass(TdxConfig, raw.get("tdx")),
        python_runtime=_merge_dataclass(PythonRuntimeConfig, raw.get("python_runtime")),
        risk_control=_merge_dataclass(RiskControlConfig, raw.get("risk_control")),
        logging=_merge_dataclass(LoggingConfig, raw.get("logging")),
    )
    detected_tdx_dir = detect_tdx_install_dir(config.tdx.install_dir)
    if detected_tdx_dir:
        config.tdx.install_dir = detected_tdx_dir
    errors = _validate_config(config)
    if errors:
        raise ValueError("配置文件校验失败：" + "；".join(errors))
    return config


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return load_config()


def reload_config() -> AppConfig:
    get_config.cache_clear()
    return get_config()


def ensure_example_config() -> None:
    if EXAMPLE_CONFIG_PATH.exists():
        return
    _write_json(EXAMPLE_CONFIG_PATH, AppConfig().to_dict())


def ensure_runtime_dirs() -> None:
    for path in (CONFIG_DIR, LOGS_DIR, RUNTIME_DIR):
        path.mkdir(parents=True, exist_ok=True)


def get_config_warnings(config: AppConfig) -> list[str]:
    warnings: list[str] = []
    token = str(config.auth.token or "").strip()
    if token in PLACEHOLDER_TOKENS:
        warnings.append("auth.token 仍然是占位值，正式部署前请先运行安装脚本或手动替换。")
    if not config.network.allowed_cidrs:
        warnings.append("network.allowed_cidrs 为空，当前仅允许 127.0.0.1 本机访问；如需局域网调用，请重新运行安装脚本填写来源网段。")
    if not str(config.tdx.install_dir or "").strip():
        warnings.append("tdx.install_dir 当前为空，启动前需要先运行安装脚本或手动填写通达信目录。")
    elif not detect_tdx_install_dir(config.tdx.install_dir):
        warnings.append("当前 tdx.install_dir 未通过自动探测校验，请确认目录是否正确。")
    return warnings
