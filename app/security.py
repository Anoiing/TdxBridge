from __future__ import annotations

from fastapi import Header


def extract_token(
    authorization: str | None = Header(default=None),
    x_tdx_token: str | None = Header(default=None, alias="X-Tdx-Token"),
) -> str | None:
    if x_tdx_token:
        return x_tdx_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None

