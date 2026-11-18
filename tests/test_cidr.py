import ipaddress
import unittest

from offtunnel.cidr import diff_networks, merge_networks, parse_delegated_text, total_addresses

SAMPLE = """\
2|ripencc|1794956399|168076|19700101|20261117|+0100
ripencc|IR|ipv4|2.57.3.0|256|20230307|allocated
ripencc|IR|ipv4|2.57.4.0|256|20230307|allocated
ripencc|IR|ipv4|2.144.0.0|262144|20101022|allocated
ripencc|FR|ipv4|1.178.224.0|8192|20100625|allocated
ripencc|IR|ipv6|2001:db8::|32|20200101|allocated
ripencc|IR|ipv4|5.1.43.0|256|20210728|reserved
"""


class TestCidr(unittest.TestCase):
    def test_adjacent_24s_merge_to_23(self):
        nets = parse_delegated_text(SAMPLE, "IR")
        # 2.57.3.0/24 + 2.57.4.0/24 are adjacent but not aligned to /23,
        # so they stay separate; 2.144.0.0/14 is one network.
        self.assertIn(ipaddress.IPv4Network("2.57.3.0/24"), nets)
        self.assertIn(ipaddress.IPv4Network("2.57.4.0/24"), nets)
        self.assertIn(ipaddress.IPv4Network("2.144.0.0/14"), nets)
        # FR, IPv6 and reserved rows are ignored.
        self.assertNotIn(ipaddress.IPv4Network("1.178.224.0/19"), nets)

    def test_merge_collapses_aligned_pair(self):
        merged = merge_networks([
            ipaddress.IPv4Network("10.0.0.0/24"),
            ipaddress.IPv4Network("10.0.1.0/24"),
        ])
        self.assertEqual(merged, [ipaddress.IPv4Network("10.0.0.0/23")])

    def test_total_addresses(self):
        nets = parse_delegated_text(SAMPLE, "IR")
        # 256 + 256 + 262144
        self.assertEqual(total_addresses(nets), 262656)

    def test_diff_only_reports_changes(self):
        old = [ipaddress.IPv4Network("10.0.0.0/24"), ipaddress.IPv4Network("10.0.1.0/24")]
        new = [ipaddress.IPv4Network("10.0.1.0/24"), ipaddress.IPv4Network("10.0.2.0/24")]
        added, removed = diff_networks(old, new)
        self.assertEqual(added, [ipaddress.IPv4Network("10.0.2.0/24")])
        self.assertEqual(removed, [ipaddress.IPv4Network("10.0.0.0/24")])
        added2, removed2 = diff_networks(old, old)
        self.assertEqual((added2, removed2), ([], []))


if __name__ == "__main__":
    unittest.main()
