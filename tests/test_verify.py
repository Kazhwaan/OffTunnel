import ipaddress
import unittest

from offtunnel.routes import Route, parse_route_print
from offtunnel.verify import check_target, longest_prefix_route, verify_applied

SAMPLE = """\
===========================================================================
Interface List
  7...........................NordLynx
 12...........................Intel(R) Ethernet
===========================================================================
IPv4 Route Table
===========================================================================
Active Routes:
Network Destination        Netmask          Gateway       Interface  Metric
          0.0.0.0          0.0.0.0         10.8.0.1         10.8.0.2      5
          0.0.0.0          0.0.0.0      192.168.1.1     192.168.1.10     25
        10.8.0.0    255.255.255.0         On-link          10.8.0.2    261
      192.168.1.0    255.255.255.0         On-link      192.168.1.10    281
       2.144.0.0       255.252.0.0      192.168.1.1     192.168.1.10      5
===========================================================================
"""


def _routes():
    return parse_route_print(SAMPLE)


class TestVerifyApplied(unittest.TestCase):
    def test_counts_applied_missing_and_wrong_gateway(self):
        routes = _routes()
        expected = [
            ipaddress.IPv4Network("2.144.0.0/14"),   # present, right gateway
            ipaddress.IPv4Network("5.112.0.0/16"),   # missing
            ipaddress.IPv4Network("185.120.0.0/22"), # missing
        ]
        result = verify_applied(expected, routes, gateway="192.168.1.1")
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["applied"], 1)
        self.assertEqual(result["missing"], 2)
        self.assertEqual(result["wrong_gateway"], 0)

    def test_wrong_gateway_does_not_count(self):
        routes = _routes()
        result = verify_applied([ipaddress.IPv4Network("2.144.0.0/14")], routes, gateway="10.8.0.1")
        self.assertEqual(result["applied"], 0)
        self.assertEqual(result["wrong_gateway"], 1)


class TestLongestPrefix(unittest.TestCase):
    def test_specific_route_beats_default(self):
        routes = _routes()
        route = longest_prefix_route(routes, ipaddress.IPv4Address("2.144.5.6"))
        self.assertIsNotNone(route)
        assert route is not None
        self.assertEqual(str(route.destination), "2.144.0.0/14")
        self.assertEqual(str(route.gateway), "192.168.1.1")


class TestCheckTarget(unittest.TestCase):
    def test_direct_ip(self):
        routes = _routes()
        check = check_target("2.144.5.6", "192.168.1.1", routes)
        self.assertEqual(check.via, "direct")
        self.assertEqual(check.resolved_ip, "2.144.5.6")

    def test_vpn_ip(self):
        routes = _routes()
        check = check_target("8.8.8.8", "192.168.1.1", routes)
        # 8.8.8.8 falls to the VPN default (lowest metric).
        self.assertEqual(check.via, "vpn")

    def test_unresolvable_domain(self):
        # A hostname with spaces can never resolve (the VM's DNS
        # wildcard-resolves even .invalid, so a real-looking name
        # would not test the failure path here).
        check = check_target("not a domain!!", "192.168.1.1", [])
        self.assertEqual(check.via, "unknown")
        self.assertIsNone(check.resolved_ip)
        self.assertIn("Could not resolve", check.message)


if __name__ == "__main__":
    unittest.main()
