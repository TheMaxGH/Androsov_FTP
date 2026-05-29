from __future__ import annotations

import unittest

from src.infrastructure.network_engine import UPnPManager


class UPnPTests(unittest.TestCase):
    def test_upnp_manager_returns_status_tuple(self) -> None:
        ok, message = UPnPManager().open_port(9, description="OptiFTP test")
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(message, str)
        self.assertTrue(message)


if __name__ == "__main__":
    unittest.main()
