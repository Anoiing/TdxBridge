from __future__ import annotations

import ipaddress
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.config import AppConfig, get_config
from app.security import extract_token


def get_app_config() -> AppConfig:
    return get_config()


def _path_allows_anonymous(request: Request, config: AppConfig) -> bool:
    if request.url.path == "/health":
        return config.auth.allow_anonymous_health
    if request.url.path == "/capabilities":
        return config.auth.allow_anonymous_capabilities
    return False


def _client_ip_allowed(request: Request, config: AppConfig) -> bool:
    client = request.client
    if client is None or not client.host:
        return False

    try:
        host_ip = ipaddress.ip_address(client.host)
    except ValueError:
        return False

    if host_ip.is_loopback:
        return True

    if not config.network.allowed_cidrs:
        return False

    for cidr in config.network.allowed_cidrs:
        try:
            if host_ip in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


def enforce_access(
    request: Request,
    token: Annotated[str | None, Depends(extract_token)],
    config: Annotated[AppConfig, Depends(get_app_config)],
) -> None:
    if not _client_ip_allowed(request, config):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前来源 IP 不在允许范围内。",
        )

    if _path_allows_anonymous(request, config):
        return

    expected = config.auth.token.strip()
    provided = (token or "").strip()
    if not expected or not provided or not secrets.compare_digest(expected, provided):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="鉴权失败，请提供有效的 Bearer Token 或 X-Tdx-Token。",
        )
