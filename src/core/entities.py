from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import time


READ_ONLY_PERMISSIONS = "elr"
READ_WRITE_PERMISSIONS = "elradfmwMT"


@dataclass(slots=True)
class UserAccount:
    username: str = "user"
    password: str = "password"
    root_path: Path | None = None
    permissions: str = READ_WRITE_PERMISSIONS
    enabled: bool = True


@dataclass(slots=True)
class ServerLimits:
    max_connections: int = 128
    max_connections_per_ip: int = 8
    upload_limit_kbps: int = 0
    download_limit_kbps: int = 0


@dataclass(slots=True)
class IPFilter:
    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ServerConfig:
    name: str = "Default"
    host: str = "0.0.0.0"
    port: int = 2121
    root_path: Path = field(default_factory=lambda: Path.cwd())
    allow_anonymous: bool = False
    passive_ports: tuple[int, int] = (60000, 60100)
    protocol: str = "ftp"
    certfile: Path | None = None
    keyfile: Path | None = None
    users: list[UserAccount] = field(default_factory=lambda: [UserAccount()])
    limits: ServerLimits = field(default_factory=ServerLimits)
    ip_filter: IPFilter = field(default_factory=IPFilter)

    # Backward-compatible quick-mode fields used by older tests/callers.
    username: str = "user"
    password: str = "password"

    def normalized_users(self) -> list[UserAccount]:
        users = [user for user in self.users if user.enabled and user.username.strip()]
        if (
            len(users) == 1
            and users[0].username == "user"
            and users[0].password == "password"
            and (self.username != "user" or self.password != "password")
        ):
            return [UserAccount(self.username or "user", self.password or "password")]
        if users:
            return users
        return [UserAccount(self.username or "user", self.password or "password")]

    @property
    def tls_enabled(self) -> bool:
        return self.protocol.lower() == "ftps"


@dataclass(slots=True)
class ServerRuntimeInfo:
    name: str
    status: str
    address: str = ""
    error: str = ""
    active_sessions: int = 0
    uptime_seconds: float = 0.0


@dataclass(slots=True)
class ClientProfile:
    name: str = "local"
    host: str = "127.0.0.1"
    port: int = 2121
    username: str = "user"
    password: str = "password"
    protocol: str = "ftp"


@dataclass(slots=True)
class AppConfig:
    servers: list[ServerConfig] = field(default_factory=list)
    client_profiles: list[ClientProfile] = field(default_factory=list)


@dataclass(slots=True)
class ScanResult:
    host: str
    port: int
    latency_ms: float
    banner: str = ""


@dataclass(slots=True)
class FileItem:
    name: str
    size: int
    is_dir: bool = False
    modified_at: float = field(default_factory=time)


@dataclass(slots=True)
class TransferProgress:
    filename: str
    transferred: int
    total: int

    @property
    def percent(self) -> float:
        if self.total <= 0:
            return 0.0
        return min(100.0, self.transferred / self.total * 100.0)
