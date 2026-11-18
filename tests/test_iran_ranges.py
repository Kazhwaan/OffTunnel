import json
import tempfile
import unittest
from pathlib import Path

from offtunnel.iran_ranges import RangeSnapshot, load_snapshot, save_snapshot


class TestSnapshot(unittest.TestCase):
    def test_roundtrip(self):
        from ipaddress import IPv4Network

        snap = RangeSnapshot(
            country="IR",
            source_url="https://example.invalid/delegated",
            source_sha256="abc123",
            fetched_at=1700000000.0,
            rows=2,
            networks=[IPv4Network("2.144.0.0/14"), IPv4Network("5.1.43.0/24")],
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "iran_snapshot.json"
            save_snapshot(snap, path)
            loaded = load_snapshot(path)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.country, "IR")
            self.assertEqual(loaded.rows, 2)
            self.assertEqual(loaded.networks, snap.networks)
            self.assertEqual(loaded.total_addresses, 262144 + 256)
            # The file on disk is plain JSON with string CIDRs.
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["networks"], ["2.144.0.0/14", "5.1.43.0/24"])

    def test_load_missing_returns_none(self):
        self.assertIsNone(load_snapshot(Path("/nonexistent/offtunnel-test.json")))

    def test_load_corrupt_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            self.assertIsNone(load_snapshot(path))


if __name__ == "__main__":
    unittest.main()
