import ipaddress
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from offtunnel import updater
from offtunnel.iran_ranges import RangeSnapshot
from offtunnel.routes import RouteExecutor
from offtunnel.rules import RuleStore


def _snapshot(sha="abc"):
    return RangeSnapshot(
        country="IR",
        fetched_at=1780000000.0,
        source_url="https://example.invalid/delegated-ripencc-latest",
        source_sha256=sha,
        rows=2,
        networks=[ipaddress.IPv4Network("2.144.0.0/14")],
    )


class TestUpdater(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = RuleStore(Path(self.tmp.name) / "rules.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_offline_first_run_uses_shipped_snapshot(self):
        # v0.1.0 bug: a failed fetch on first run applied nothing,
        # even though a shipped snapshot exists.
        calls = {}

        def fake_apply_all(executor, gateway, snapshot, store, state_path=None):
            calls["snapshot"] = snapshot
            from offtunnel.apply import ApplyReport

            return ApplyReport(added=list(snapshot.networks), total_expected=1)

        with mock.patch.object(updater, "fetch_country_snapshot", side_effect=RuntimeError("no network")), \
                mock.patch.object(updater, "load_snapshot", return_value=None), \
                mock.patch.object(updater, "effective_snapshot", return_value=_snapshot()), \
                mock.patch.object(updater, "save_snapshot", lambda *a: None), \
                mock.patch.object(updater, "apply_all", side_effect=fake_apply_all):
            result = updater.check_once(
                RouteExecutor(dry_run=True), "192.168.1.1", log=lambda m: None, store=self.store
            )
        self.assertTrue(result.changed)
        self.assertEqual(result.added, 1)
        self.assertEqual(result.total_networks, 1)
        self.assertIn("snapshot", calls)

    def test_unchanged_snapshot_touches_no_routes(self):
        snap = _snapshot()
        with mock.patch.object(updater, "fetch_country_snapshot", return_value=snap), \
                mock.patch.object(updater, "load_snapshot", return_value=snap):
            ex = RouteExecutor(dry_run=True)
            result = updater.check_once(ex, "192.168.1.1", log=lambda m: None, store=self.store)
        self.assertFalse(result.changed)
        self.assertEqual(ex.executed, [])

    def test_fetch_failure_with_existing_snapshot_keeps_routes(self):
        with mock.patch.object(updater, "fetch_country_snapshot", side_effect=RuntimeError("no network")), \
                mock.patch.object(updater, "load_snapshot", return_value=_snapshot()):
            ex = RouteExecutor(dry_run=True)
            result = updater.check_once(ex, "192.168.1.1", log=lambda m: None, store=self.store)
        self.assertFalse(result.changed)
        self.assertEqual(ex.executed, [])
        self.assertTrue(result.error)


if __name__ == "__main__":
    unittest.main()
