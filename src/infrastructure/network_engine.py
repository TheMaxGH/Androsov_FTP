from __future__ import annotations

import asyncio
import fnmatch
import ipaddress
import logging
import platform
import re
import socket
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from time import perf_counter, sleep

from src.core.entities import READ_ONLY_PERMISSIONS, ScanResult, ServerConfig, ServerRuntimeInfo

log = logging.getLogger(__name__)


class FastLANScanner:
    """Быстрый TCP-сканер локальной подсети.

    Сканирование идет через asyncio: вместо последовательной проверки 254 адресов
    приложение держит множество TCP-попыток одновременно и ограничивает их семафором.
    Таймаут 100-200 мс не дает недоступным адресам блокировать весь процесс, поэтому
    GUI получает результаты через worker-сигналы и не зависает.
    """

    def __init__(self, timeout: float = 0.18, concurrency: int = 128) -> None:
        self.timeout = timeout
        self.concurrency = concurrency

    def default_subnet(self) -> str:
        host_ip = _get_lan_ip()
        return str(ipaddress.ip_network(f"{host_ip}/24", strict=False))

    async def scan(
        self,
        subnet: str | None = None,
        ports: tuple[int, ...] = (21, 2121),
        on_result: Callable[[ScanResult], None] | None = None,
    ) -> list[ScanResult]:
        network = ipaddress.ip_network(subnet or self.default_subnet(), strict=False)
        semaphore = asyncio.Semaphore(self.concurrency)
        tasks = [
            self._probe(str(host), port, semaphore, on_result)
            for host in network.hosts()
            for port in ports
        ]
        results = await asyncio.gather(*tasks)
        return sorted((item for item in results if item), key=lambda r: (r.host, r.port))

    def scan_sync(
        self,
        subnet: str | None = None,
        ports: tuple[int, ...] = (21, 2121),
        on_result: Callable[[ScanResult], None] | None = None,
    ) -> list[ScanResult]:
        return asyncio.run(self.scan(subnet=subnet, ports=ports, on_result=on_result))

    async def _probe(
        self,
        host: str,
        port: int,
        semaphore: asyncio.Semaphore,
        on_result: Callable[[ScanResult], None] | None,
    ) -> ScanResult | None:
        async with semaphore:
            started = perf_counter()
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=self.timeout)
                banner = ""
                try:
                    raw = await asyncio.wait_for(reader.read(128), timeout=0.05)
                    banner = raw.decode("utf-8", errors="replace").strip()
                except Exception:
                    pass
                writer.close()
                await writer.wait_closed()
                result = ScanResult(host, port, (perf_counter() - started) * 1000, banner)
                if on_result:
                    on_result(result)
                return result
            except (TimeoutError, OSError, asyncio.TimeoutError):
                return None


class OptiFTPServer:
    """FTP/FTPS-сервер на pyftpdlib с запуском из GUI или CLI.

    pyftpdlib использует асинхронную модель select/poll: один служебный поток
    мультиплексирует клиентские сокеты, а не создает отдельный поток на каждое
    подключение. Это уменьшает потребление памяти и переключения контекста.
    """

    def __init__(self, event_callback: Callable[[str], None] | None = None) -> None:
        self._server = None
        self._thread: threading.Thread | None = None
        self._config: ServerConfig | None = None
        self._started_at = 0.0
        self._active_sessions = 0
        self._lock = threading.Lock()
        self._event_callback = event_callback
        self.public_address = ""
        self.last_error = ""

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    @property
    def active_sessions(self) -> int:
        with self._lock:
            return self._active_sessions

    def start(self, config: ServerConfig) -> None:
        if self.is_running:
            return

        from pyftpdlib.authorizers import DummyAuthorizer
        from pyftpdlib.handlers import FTPHandler, ThrottledDTPHandler
        from pyftpdlib.servers import FTPServer

        root = Path(config.root_path).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        self._validate_tls(config)

        authorizer = DummyAuthorizer()
        if config.allow_anonymous:
            authorizer.add_anonymous(str(root), perm=READ_ONLY_PERMISSIONS)
        for user in config.normalized_users():
            user_root = Path(user.root_path or root).expanduser().resolve()
            user_root.mkdir(parents=True, exist_ok=True)
            authorizer.add_user(user.username, user.password, str(user_root), perm=user.permissions)

        base_handler = _tls_handler_class() if config.tls_enabled else FTPHandler
        server_ref = self
        ip_allow = list(config.ip_filter.allow)
        ip_deny = list(config.ip_filter.deny)

        class VALLHALAHandler(base_handler):  # type: ignore[misc, valid-type]
            pass

        def on_connect(handler) -> None:
            remote_ip = getattr(handler, "remote_ip", "")
            if _ip_blocked(remote_ip, ip_allow, ip_deny):
                server_ref._emit(f"Соединение отклонено IP-фильтром: {remote_ip}")
                handler.close_when_done()
                return
            with server_ref._lock:
                server_ref._active_sessions += 1
            server_ref._emit(f"FTP session opened: {remote_ip}")

        def on_disconnect(handler) -> None:
            with server_ref._lock:
                server_ref._active_sessions = max(0, server_ref._active_sessions - 1)
            server_ref._emit(f"FTP session closed: {getattr(handler, 'remote_ip', '')}")

        def on_login(handler, username) -> None:
            server_ref._emit(f"Пользователь вошел: {username}")

        def on_login_failed(handler, username, password) -> None:
            server_ref._emit(f"Ошибка входа: {username}")

        VALLHALAHandler.authorizer = authorizer
        VALLHALAHandler.passive_ports = range(config.passive_ports[0], config.passive_ports[1] + 1)
        VALLHALAHandler.banner = "VALLHALA FTP ready"
        VALLHALAHandler.on_connect = on_connect
        VALLHALAHandler.on_disconnect = on_disconnect
        VALLHALAHandler.on_login = on_login
        VALLHALAHandler.on_login_failed = on_login_failed

        if config.tls_enabled:
            VALLHALAHandler.certfile = str(Path(config.certfile or "").expanduser().resolve())
            VALLHALAHandler.keyfile = str(Path(config.keyfile or "").expanduser().resolve()) if config.keyfile else None
            VALLHALAHandler.tls_control_required = True
            VALLHALAHandler.tls_data_required = True

        if config.limits.upload_limit_kbps or config.limits.download_limit_kbps:
            dtp_handler = ThrottledDTPHandler
            if config.limits.upload_limit_kbps:
                dtp_handler.read_limit = config.limits.upload_limit_kbps * 1024
            if config.limits.download_limit_kbps:
                dtp_handler.write_limit = config.limits.download_limit_kbps * 1024
            VALLHALAHandler.dtp_handler = dtp_handler

        try:
            self._server = FTPServer((config.host, config.port), VALLHALAHandler)
        except OSError as exc:
            self.last_error = (
                f"Не удалось запустить FTP-сервер на {config.host}:{config.port}. "
                "Этот IP/порт уже занят другим сервером или приложением. "
                "Выберите другой порт, например 2122, или остановите процесс, который уже слушает этот адрес."
            )
            raise RuntimeError(self.last_error) from exc

        self._server.max_cons = config.limits.max_connections
        self._server.max_cons_per_ip = config.limits.max_connections_per_ip
        self._config = config
        self.public_address = f"{'ftps' if config.tls_enabled else 'ftp'}://{_get_lan_ip()}:{config.port}"
        self.last_error = ""
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True, name=f"ftp-{config.name}")
        self._thread.start()
        self._started_at = perf_counter()
        log.info("FTP server started at %s", self.public_address)
        self._emit(f"Сервер запущен: {self.public_address}")

    def stop(self) -> None:
        if self._thread and self._thread.is_alive() and perf_counter() - self._started_at < 0.1:
            sleep(0.1)
        if self._server:
            self._server.close_all()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._server = None
        self._thread = None
        with self._lock:
            self._active_sessions = 0
        log.info("FTP server stopped")
        self._emit("Сервер остановлен")

    def info(self, name: str | None = None) -> ServerRuntimeInfo:
        uptime = perf_counter() - self._started_at if self.is_running else 0.0
        return ServerRuntimeInfo(
            name=name or (self._config.name if self._config else ""),
            status="Запущен" if self.is_running else ("Ошибка" if self.last_error else "Остановлен"),
            address=self.public_address if self.is_running else "",
            error=self.last_error,
            active_sessions=self.active_sessions,
            uptime_seconds=uptime,
        )

    def _emit(self, message: str) -> None:
        if self._event_callback:
            self._event_callback(message)

    @staticmethod
    def _validate_tls(config: ServerConfig) -> None:
        if not config.tls_enabled:
            return
        if not config.certfile:
            raise RuntimeError("Для FTPS укажите путь к TLS-сертификату.")
        certfile = Path(config.certfile).expanduser()
        if not certfile.exists():
            raise RuntimeError(f"TLS-сертификат не найден: {certfile}")
        if config.keyfile and not Path(config.keyfile).expanduser().exists():
            raise RuntimeError(f"TLS-ключ не найден: {config.keyfile}")


class MultiFTPServerManager:
    """Менеджер нескольких FTP-серверов в одном Python-процессе."""

    def __init__(self, event_callback: Callable[[str], None] | None = None) -> None:
        self._servers: dict[str, OptiFTPServer] = {}
        self._event_callback = event_callback

    def start(self, name: str, config: ServerConfig) -> str:
        if name in self._servers and self._servers[name].is_running:
            raise RuntimeError(f"Сервер '{name}' уже запущен")
        if self._endpoint_in_use(name, config.host, config.port):
            raise RuntimeError(f"Порт уже занят другим профилем VALLHALA FTP: {config.host}:{config.port}")
        server = OptiFTPServer(self._prefixed_callback(name))
        config.name = name
        server.start(config)
        self._servers[name] = server
        return server.public_address

    def stop(self, name: str) -> None:
        server = self._servers.pop(name, None)
        if server:
            server.stop()

    def stop_all(self) -> None:
        for name in list(self._servers):
            self.stop(name)

    def running(self) -> list[str]:
        return [name for name, server in self._servers.items() if server.is_running]

    def info(self, name: str) -> ServerRuntimeInfo:
        server = self._servers.get(name)
        if not server:
            return ServerRuntimeInfo(name=name, status="Остановлен")
        return server.info(name)

    def infos(self, names: list[str]) -> list[ServerRuntimeInfo]:
        return [self.info(name) for name in names]

    def _endpoint_in_use(self, current_name: str, host: str, port: int) -> bool:
        for name, server in self._servers.items():
            config = server._config
            if name != current_name and server.is_running and config and config.host == host and config.port == port:
                return True
        return False

    def _prefixed_callback(self, name: str) -> Callable[[str], None] | None:
        if not self._event_callback:
            return None
        return lambda message: self._event_callback(f"[{name}] {message}")


class UPnPManager:
    def open_port(self, port: int, protocol: str = "TCP", description: str = "VALLHALA FTP") -> tuple[bool, str]:
        try:
            import miniupnpc
        except ImportError:
            return False, (
                "Модуль miniupnpc не установлен. Локальный FTP работает; "
                "для доступа из интернета настройте проброс порта на роутере вручную."
            )

        try:
            upnp = miniupnpc.UPnP()
            upnp.discoverdelay = 200
            devices = upnp.discover()
            if not devices:
                return False, "UPnP-роутер не найден."
            upnp.selectigd()
            local_ip = upnp.lanaddr
            upnp.addportmapping(port, protocol, local_ip, port, description, "")
            return True, f"Проброшен {protocol}-порт {port} на {local_ip}:{port}"
        except Exception as exc:
            return False, f"UPnP не сработал: {exc}"

    def close_port(self, port: int, protocol: str = "TCP") -> tuple[bool, str]:
        try:
            import miniupnpc

            upnp = miniupnpc.UPnP()
            upnp.discoverdelay = 200
            if not upnp.discover():
                return False, "UPnP-роутер не найден."
            upnp.selectigd()
            upnp.deleteportmapping(port, protocol)
            return True, f"Проброс {protocol}-порта {port} удален"
        except Exception as exc:
            return False, f"Не удалось удалить UPnP-проброс: {exc}"


def _ip_blocked(remote_ip: str, allow: list[str], deny: list[str]) -> bool:
    if any(_ip_matches(remote_ip, rule) for rule in deny):
        return True
    if allow and not any(_ip_matches(remote_ip, rule) for rule in allow):
        return True
    return False


def _tls_handler_class():
    try:
        from pyftpdlib.handlers import TLS_FTPHandler

        return TLS_FTPHandler
    except ImportError as exc:
        raise RuntimeError("Для FTPS установите зависимость pyOpenSSL: python -m pip install pyOpenSSL") from exc


def _ip_matches(remote_ip: str, rule: str) -> bool:
    rule = rule.strip()
    if not rule:
        return False
    try:
        if "/" in rule:
            return ipaddress.ip_address(remote_ip) in ipaddress.ip_network(rule, strict=False)
        return ipaddress.ip_address(remote_ip) == ipaddress.ip_address(rule)
    except ValueError:
        return fnmatch.fnmatch(remote_ip, rule)


def _get_lan_ip() -> str:
    for ip in _windows_ipconfig_addresses():
        return ip

    candidates: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if _is_usable_lan_ip(ip):
                candidates.append(ip)
    except OSError:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if _is_usable_lan_ip(ip):
                candidates.append(ip)
    except OSError:
        pass

    if candidates:
        return _prefer_home_lan(candidates)
    return "127.0.0.1"


def _windows_ipconfig_addresses() -> list[str]:
    if platform.system().lower() != "windows":
        return []
    try:
        output = subprocess.check_output(["ipconfig"], text=True, encoding="cp866", errors="ignore")
    except Exception:
        return []

    addresses: list[str] = []
    skip_words = ("virtual", "vmware", "virtualbox", "docker", "wsl", "hyper-v", "ветернет", "vEthernet")
    for section in re.split(r"\r?\n\r?\n", output):
        header = section.splitlines()[0].lower() if section.splitlines() else ""
        if any(word.lower() in header for word in skip_words):
            continue
        for match in re.finditer(r"IPv4[^:]*:\s*([0-9.]+)", section):
            ip = match.group(1)
            if _is_usable_lan_ip(ip):
                addresses.append(ip)
    return [_prefer_home_lan(addresses)] if addresses else []


def _is_usable_lan_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return bool(ip.version == 4 and ip.is_private and not ip.is_loopback and not ip.is_link_local)


def _prefer_home_lan(addresses: list[str]) -> str:
    unique = list(dict.fromkeys(addresses))
    for prefix in ("192.168.", "10."):
        for ip in unique:
            if ip.startswith(prefix):
                return ip
    return unique[0]
