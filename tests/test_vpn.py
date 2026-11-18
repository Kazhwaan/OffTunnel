import unittest

from offtunnel.vpn import describe_interfaces, is_vpn_interface, parse_route_print_interfaces

SAMPLE = """\
===========================================================================
Interface List
  7...........................NordLynx
 12...........................Windscribe VPN
  3...........................Intel(R) Ethernet Connection
  9...........................TorGuard WireGuard
===========================================================================
IPv4 Route Table
"""


class TestVpn(unittest.TestCase):
    def test_known_vpn_names_detected(self):
        for name in ["Windscribe VPN", "TorGuard WireGuard", "NordLynx", "ExpressVPN", "WireGuard Tunnel", "OpenVPN TAP"]:
            self.assertTrue(is_vpn_interface(name), name)

    def test_regular_adapter_not_flagged(self):
        for name in ["Intel(R) Ethernet Connection", "Wi-Fi", "Realtek PCIe GbE"]:
            self.assertFalse(is_vpn_interface(name), name)

    def test_describe_interfaces(self):
        status = describe_interfaces(["NordLynx", "Intel(R) Ethernet Connection"])
        self.assertTrue(status.vpn_connected)
        self.assertEqual(status.vpn_interfaces, ["NordLynx"])
        self.assertTrue(status.notes)  # NordVPN kill-switch caveat

    def test_parse_interface_list(self):
        names = parse_route_print_interfaces(SAMPLE)
        self.assertIn("NordLynx", names)
        self.assertIn("Windscribe VPN", names)
        self.assertIn("TorGuard WireGuard", names)
        self.assertIn("Intel(R) Ethernet Connection", names)


if __name__ == "__main__":
    unittest.main()
