from __future__ import annotations

import tempfile
import time
import unittest
from contextlib import redirect_stdout
from io import StringIO
from ftplib import FTP, error_perm
from pathlib import Path

from src.cli_client import run_cli_client
from src.core.entities import ServerConfig, UserAccount
from src.infrastructure.config_store import ConfigStore, default_app_config
from src.infrastructure.ftp_client import OptimizedFTPClient
from src.infrastructure.network_engine import MultiFTPServerManager, OptiFTPServer
from tests.test_network_engine import free_port


class FTPServerTests(unittest.TestCase):
    def test_server_accepts_client_upload_and_list(self) -> None:
        port = free_port()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_file = root / "sample.txt"
            local_file.write_text("hello optiftp", encoding="utf-8")

            server = OptiFTPServer()
            server.start(ServerConfig(host="127.0.0.1", port=port, root_path=root))
            time.sleep(0.25)
            client = OptimizedFTPClient()
            try:
                client.connect("127.0.0.1", port, "user", "password")
                names = client.list_dir()
                self.assertIn("sample.txt", names)
                upload = root / "uploaded.txt"
                upload.write_text("uploaded through client", encoding="utf-8")
                client.upload(upload, "remote_uploaded.txt")
                self.assertIn("remote_uploaded.txt", client.list_dir())
            finally:
                client.disconnect()
                server.stop()

    def test_port_conflict_returns_clear_error(self) -> None:
        port = free_port()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = OptiFTPServer()
            second = OptiFTPServer()
            first.start(ServerConfig(host="127.0.0.1", port=port, root_path=root))
            try:
                with self.assertRaisesRegex(RuntimeError, "уже занят"):
                    second.start(ServerConfig(host="127.0.0.1", port=port, root_path=root))
            finally:
                first.stop()
                second.stop()

    def test_manager_can_run_multiple_servers_on_different_ports(self) -> None:
        manager = MultiFTPServerManager()
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            first_port = free_port()
            second_port = free_port()
            try:
                manager.start("one", ServerConfig(host="127.0.0.1", port=first_port, root_path=Path(one)))
                manager.start("two", ServerConfig(host="127.0.0.1", port=second_port, root_path=Path(two)))
                self.assertEqual(set(manager.running()), {"one", "two"})
            finally:
                manager.stop_all()

    def test_multiple_users_can_login_with_different_passwords(self) -> None:
        port = free_port()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            server = OptiFTPServer()
            config = ServerConfig(
                host="127.0.0.1",
                port=port,
                root_path=root,
                users=[
                    UserAccount("alice", "one"),
                    UserAccount("bob", "two"),
                ],
            )
            server.start(config)
            time.sleep(0.25)
            try:
                first = OptimizedFTPClient()
                second = OptimizedFTPClient()
                first.connect("127.0.0.1", port, "alice", "one")
                second.connect("127.0.0.1", port, "bob", "two")
                first.disconnect()
                second.disconnect()
            finally:
                server.stop()

    def test_anonymous_is_read_only(self) -> None:
        port = free_port()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "public.txt").write_text("public", encoding="utf-8")
            server = OptiFTPServer()
            server.start(ServerConfig(host="127.0.0.1", port=port, root_path=root, allow_anonymous=True))
            time.sleep(0.25)
            ftp = FTP()
            try:
                ftp.connect("127.0.0.1", port, timeout=5)
                ftp.login("anonymous", "guest@example.com")
                self.assertIn("public.txt", ftp.nlst())
                with tempfile.NamedTemporaryFile() as handle:
                    handle.write(b"blocked")
                    handle.flush()
                    handle.seek(0)
                    with self.assertRaises(error_perm):
                        ftp.storbinary("STOR blocked.txt", handle)
            finally:
                try:
                    ftp.quit()
                except Exception:
                    ftp.close()
                server.stop()

    def test_cli_client_uses_profile_from_config(self) -> None:
        port = free_port()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "from_profile.txt").write_text("ok", encoding="utf-8")
            config = default_app_config()
            config.servers[0].host = "127.0.0.1"
            config.servers[0].port = port
            config.servers[0].root_path = root
            config.client_profiles[0].host = "127.0.0.1"
            config.client_profiles[0].port = port
            config_path = root / "vallhala.json"
            ConfigStore(config_path).save(config)

            server = OptiFTPServer()
            server.start(config.servers[0])
            time.sleep(0.25)
            output = StringIO()
            try:
                with redirect_stdout(output):
                    run_cli_client(["--ftp", "list", "--config", str(config_path), "--profile", "local"])
                self.assertIn("from_profile.txt", output.getvalue())
            finally:
                server.stop()

    def test_ftps_without_certificate_has_readable_error(self) -> None:
        port = free_port()
        with tempfile.TemporaryDirectory() as tmp:
            server = OptiFTPServer()
            with self.assertRaisesRegex(RuntimeError, "TLS-сертификат"):
                server.start(ServerConfig(host="127.0.0.1", port=port, root_path=Path(tmp), protocol="ftps"))


if __name__ == "__main__":
    unittest.main()
