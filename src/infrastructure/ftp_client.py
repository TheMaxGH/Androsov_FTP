from __future__ import annotations

import ftplib
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from src.core.entities import TransferProgress


class OptimizedFTPClient:
    def __init__(self, workers: int = 4) -> None:
        self._ftp: ftplib.FTP | None = None
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ftp-io")

    @property
    def connected(self) -> bool:
        return self._ftp is not None

    def connect(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        timeout: float = 8.0,
        protocol: str = "ftp",
    ) -> None:
        ftp = ftplib.FTP_TLS() if protocol.lower() == "ftps" else ftplib.FTP()
        ftp.connect(host, port, timeout=timeout)
        ftp.login(username, password)
        if isinstance(ftp, ftplib.FTP_TLS):
            ftp.prot_p()
        ftp.set_pasv(True)
        self._ftp = ftp

    def disconnect(self) -> None:
        with self._lock:
            if not self._ftp:
                return
            try:
                self._ftp.quit()
            except Exception:
                self._ftp.close()
            finally:
                self._ftp = None

    def list_dir(self, path: str = ".") -> list[str]:
        ftp = self._require()
        with self._lock:
            try:
                return [name for name, _facts in ftp.mlsd(path) if name not in (".", "..")]
            except Exception:
                return [Path(name).name for name in ftp.nlst(path) if Path(name).name not in (".", "..")]

    def upload_async(
        self,
        local_path: Path,
        remote_name: str | None = None,
        on_progress: Callable[[TransferProgress], None] | None = None,
    ) -> Future[None]:
        return self._executor.submit(self.upload, local_path, remote_name, on_progress)

    def download_async(
        self,
        remote_name: str,
        local_path: Path,
        on_progress: Callable[[TransferProgress], None] | None = None,
    ) -> Future[None]:
        return self._executor.submit(self.download, remote_name, local_path, on_progress)

    def upload(
        self,
        local_path: Path,
        remote_name: str | None = None,
        on_progress: Callable[[TransferProgress], None] | None = None,
    ) -> None:
        ftp = self._require()
        local_path = Path(local_path)
        total = local_path.stat().st_size
        sent = 0
        blocksize = _buffer_for_size(total)

        def callback(block: bytes) -> None:
            nonlocal sent
            sent += len(block)
            if on_progress:
                on_progress(TransferProgress(local_path.name, sent, total))

        with self._lock:
            with local_path.open("rb") as handle:
                ftp.storbinary(f"STOR {remote_name or local_path.name}", handle, blocksize=blocksize, callback=callback)

    def download(
        self,
        remote_name: str,
        local_path: Path,
        on_progress: Callable[[TransferProgress], None] | None = None,
    ) -> None:
        ftp = self._require()
        local_path = Path(local_path)
        total = 0
        with self._lock:
            try:
                total = ftp.size(remote_name) or 0
            except Exception:
                pass
            received = 0
            blocksize = _buffer_for_size(total)

            def callback(block: bytes) -> None:
                nonlocal received
                received += len(block)
                handle.write(block)
                if on_progress:
                    on_progress(TransferProgress(remote_name, received, total))

            with local_path.open("wb") as handle:
                ftp.retrbinary(f"RETR {remote_name}", callback, blocksize=blocksize)

    def _require(self) -> ftplib.FTP:
        if not self._ftp:
            raise RuntimeError("FTP-клиент не подключен")
        return self._ftp


def _buffer_for_size(size: int) -> int:
    if size >= 64 * 1024 * 1024:
        return 128 * 1024
    if size >= 8 * 1024 * 1024:
        return 64 * 1024
    return 16 * 1024
