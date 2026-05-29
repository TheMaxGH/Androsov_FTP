from __future__ import annotations

from ipaddress import ip_network
from pathlib import Path


def validate_port(value: int | str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise ValueError("Port must be in range 1..65535")
    return port


def validate_subnet(value: str) -> str:
    ip_network(value, strict=False)
    return value


def validate_existing_dir(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"Directory does not exist: {path}")
    return path
