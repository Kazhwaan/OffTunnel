import ipaddress
import unittest

from offtunnel.routes import (
    RouteExecutor,
    find_regular_gateway,
    parse_route_print,
)

# Realistic (shortened) `route print -4` output: default route via
# the VPN interface (10.8.0.1 / 10.8.0.2, metric 5) and a second
# default via the regular gateway (192.168.1.1, metric 25).
SAMPLE_ROUTE_PRINT = """\
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
===========================================================================
"""


class TestRoutes(unittest.TestCase):
    def test_parse_route_print(self):
        routes = parse_route_print(SAMPLE_ROUTE_PRINT)
        # Only the two default routes have a gateway IP; the two
        # "On-link" rows have no gateway and are correctly skipped.
        self.assertEqual(len(routes), 2)
        self.assertEqual(str(routes[0].destination), "0.0.0.0/0")
        self.assertEqual(str(routes[0].gateway), "10.8.0.1")
        self.assertEqual(str(routes[1].gateway), "192.168.1.1")

    def test_find_regular_gateway_skips_vpn_interface(self):
        routes = parse_route_print(SAMPLE_ROUTE_PRINT)
        gw = find_regular_gateway(routes, [ipaddress.IPv4Address("10.8.0.2")])
        self.assertIsNotNone(gw)
        assert gw is not None
        self.assertEqual(str(gw.gateway), "192.168.1.1")

    def test_find_regular_gateway_none_when_all_vpn(self):
        routes = parse_route_print(SAMPLE_ROUTE_PRINT)
        gw = find_regular_gateway(
            routes,
            [ipaddress.IPv4Address("10.8.0.2"), ipaddress.IPv4Address("192.168.1.10")],
        )
        self.assertIsNone(gw)

    def test_dry_run_executor_records_but_does_not_run(self):
        ex = RouteExecutor(dry_run=True)
        net = ipaddress.IPv4Network("2.144.0.0/14")
        gw = ipaddress.IPv4Address("192.168.1.1")
        self.assertEqual(ex.add_route(net, gw), 0)
        self.assertEqual(ex.delete_route(net, gw), 0)
        self.assertEqual(
            ex.executed[0],
            ["route", "add", "2.144.0.0", "mask", "255.252.0.0", "192.168.1.1", "metric", "5"],
        )

    def test_apply_diff_only_touches_changes(self):
        ex = RouteExecutor(dry_run=True)
        gw = ipaddress.IPv4Address("192.168.1.1")
        old = [ipaddress.IPv4Network("10.0.0.0/24")]
        new = [ipaddress.IPv4Network("10.0.0.0/24"), ipaddress.IPv4Network("10.0.1.0/24")]
        added, removed, failed = ex.apply_diff(old, new, gw)
        self.assertEqual(added, [ipaddress.IPv4Network("10.0.1.0/24")])
        self.assertEqual(removed, [])
        self.assertEqual(failed, [])
        self.assertEqual(len(ex.executed), 1)  # only the new network
        # No change -> no commands at all.
        ex2 = RouteExecutor(dry_run=True)
        added2, removed2, failed2 = ex2.apply_diff(old, old, gw)
        self.assertEqual((added2, removed2, failed2), ([], [], []))
        self.assertEqual(ex2.executed, [])

    def test_apply_diff_reports_failures(self):
        # A non-dry-run executor on Linux is forced to dry-run, so
        # simulate a failure with a subclass that returns non-zero.
        class Failing(RouteExecutor):
            def run(self, cmd):
                self.executed.append(list(cmd))
                return 1

        ex = Failing(dry_run=False)
        gw = ipaddress.IPv4Address("192.168.1.1")
        added, removed, failed = ex.apply_diff([], [ipaddress.IPv4Network("10.0.0.0/24")], gw)
        self.assertEqual(added, [])
        self.assertEqual(len(failed), 1)
        self.assertIn("10.0.0.0/24", failed[0])


if __name__ == "__main__":
    unittest.main()
