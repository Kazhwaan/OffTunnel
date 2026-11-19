import ipaddress
import tempfile
import unittest
from pathlib import Path

from offtunnel.apply import (
    apply_all,
    load_applied,
    remove_all,
)
from offtunnel.iran_ranges import RangeSnapshot
from offtunnel.routes import RouteExecutor
from offtunnel.rules import Rule, RuleStore, resolve_rule


def _snapshot():
    return RangeSnapshot(
        country="IR",
        fetched_at=1780000000.0,
        source_url="https://example.invalid/delegated-ripencc-latest",
        source_sha256="abc",
        rows=2,
        networks=[
            ipaddress.IPv4Network("2.144.0.0/14"),
            ipaddress.IPv4Network("5.112.0.0/16"),
        ],
    )


class TestApplyAll(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.store = RuleStore(self.dir / "rules.json")
        self.state_path = self.dir / "applied.json"
        self.gw = ipaddress.IPv4Address("192.168.1.1")

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_iran_and_manual_rules(self):
        # v0.1.0 bug: manual rules were stored but never applied.
        rule = self.store.add("ip", "8.8.8.8")
        resolve_rule(rule)
        ex = RouteExecutor(dry_run=True)
        report = apply_all(ex, self.gw, _snapshot(), self.store, self.state_path)
        self.assertTrue(report.ok)
        self.assertEqual(report.total_expected, 3)  # 2 Iran + 1 rule
        self.assertEqual(len(report.added), 3)
        state = load_applied(self.state_path)
        self.assertEqual(len(state.iran), 2)
        self.assertEqual(state.rules, [ipaddress.IPv4Network("8.8.8.8/32")])

    def test_apply_is_diff_only(self):
        ex = RouteExecutor(dry_run=True)
        apply_all(ex, self.gw, _snapshot(), self.store, self.state_path)
        ex2 = RouteExecutor(dry_run=True)
        report = apply_all(ex2, self.gw, _snapshot(), self.store, self.state_path)
        self.assertEqual(report.added, [])
        self.assertEqual(ex2.executed, [])

    def test_remove_rule_routes(self):
        rule = self.store.add("ip", "8.8.8.8")
        resolve_rule(rule)
        ex = RouteExecutor(dry_run=True)
        apply_all(ex, self.gw, _snapshot(), self.store, self.state_path)
        self.store.remove("ip", "8.8.8.8")
        ex2 = RouteExecutor(dry_run=True)
        report = apply_all(ex2, self.gw, _snapshot(), self.store, self.state_path)
        self.assertEqual(report.removed, [ipaddress.IPv4Network("8.8.8.8/32")])
        state = load_applied(self.state_path)
        self.assertEqual(state.rules, [])

    def test_remove_all(self):
        ex = RouteExecutor(dry_run=True)
        apply_all(ex, self.gw, _snapshot(), self.store, self.state_path)
        ex2 = RouteExecutor(dry_run=True)
        report = remove_all(ex2, self.gw, self.state_path)
        self.assertEqual(len(report.removed), 2)
        self.assertEqual(load_applied(self.state_path).all_networks, [])

    def test_failed_commands_are_reported(self):
        class Failing(RouteExecutor):
            def run(self, cmd):
                self.executed.append(list(cmd))
                return 1

        ex = Failing(dry_run=False)
        report = apply_all(ex, self.gw, _snapshot(), self.store, self.state_path)
        self.assertFalse(report.ok)
        self.assertEqual(len(report.failed), 2)
        # Failed networks must not be recorded as applied.
        self.assertEqual(load_applied(self.state_path).all_networks, [])


if __name__ == "__main__":
    unittest.main()
