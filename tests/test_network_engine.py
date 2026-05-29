from __future__ import annotations

import socket
import threading
import unittest
from socketserver import BaseRequestHandler, TCPServer

from src.infrastructure.network_engine import FastLANScanner


class BannerHandler(BaseRequestHandler):
    def handle(self) -> None:
        self.request.sendall(b"220 test ftp\r\n")


class FastLANScannerTests(unittest.TestCase):
    def test_finds_open_local_port(self) -> None:
        with TCPServer(("127.0.0.1", 0), BannerHandler) as server:
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                scanner = FastLANScanner(timeout=0.1, concurrency=16)
                results = scanner.scan_sync(subnet="127.0.0.1/32", ports=(port,))
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0].host, "127.0.0.1")
                self.assertEqual(results[0].port, port)
                self.assertIn("220", results[0].banner)
            finally:
                server.shutdown()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


if __name__ == "__main__":
    unittest.main()
