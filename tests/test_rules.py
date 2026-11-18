import tempfile
import unittest
from pathlib import Path

from offtunnel.rules import Rule, RuleStore, resolve_rule, rule_networks, validate_rule


def fake_resolver(domain):
    return {"example.ir": ["185.10.20.30", "185.10.20.31"]}.get(domain, [])


class TestRules(unittest.TestCase):
    def test_validate(self):
        self.assertIsNone(validate_rule("domain", "snapp.ir"))
        self.assertIsNotNone(validate_rule("domain", "not a domain"))
        self.assertIsNone(validate_rule("ip", "8.8.8.8"))
        self.assertIsNotNone(validate_rule("ip", "999.1.1.1"))
        self.assertIsNone(validate_rule("cidr", "185.120.0.0/22"))
        self.assertIsNotNone(validate_rule("cidr", "185.120.0.0/33"))
        self.assertIsNotNone(validate_rule("bogus", "x"))

    def test_domain_rule_resolves_to_32s(self):
        rule = Rule(kind="domain", value="example.ir")
        resolve_rule(rule, resolver=fake_resolver)
        nets = rule_networks(rule)
        self.assertEqual([str(n) for n in nets], ["185.10.20.30/32", "185.10.20.31/32"])

    def test_cidr_rule_expands_as_is(self):
        rule = Rule(kind="cidr", value="185.120.0.0/22")
        self.assertEqual([str(n) for n in rule_networks(rule)], ["185.120.0.0/22"])

    def test_disabled_rule_expands_to_nothing(self):
        rule = Rule(kind="ip", value="8.8.8.8", resolved_ips=["8.8.8.8"], enabled=False)
        self.assertEqual(rule_networks(rule), [])

    def test_store_roundtrip_and_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RuleStore(Path(tmp) / "rules.json")
            store.add("domain", "snapp.ir")
            self.assertEqual(len(store.rules), 1)
            with self.assertRaises(ValueError):
                store.add("domain", "snapp.ir")
            store2 = RuleStore(Path(tmp) / "rules.json")
            self.assertEqual(len(store2.rules), 1)
            self.assertTrue(store2.remove("domain", "snapp.ir"))
            self.assertFalse(store2.remove("domain", "snapp.ir"))


if __name__ == "__main__":
    unittest.main()
