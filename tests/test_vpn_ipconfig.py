import unittest

from offtunnel.vpn import parse_ipconfig_interfaces, vpn_interface_ips

SAMPLE_IPCONFIG = """\
Windows IP Configuration

NordLynx adapter NordLynx:

   Connection-specific DNS Suffix  . :
   IPv4 Address. . . . . . . . . . . : 10.8.0.2
   Subnet Mask . . . . . . . . . . . : 255.255.255.0

Wireless LAN adapter Wi-Fi:

   IPv4 Address. . . . . . . . . . . : 192.168.1.10
   Subnet Mask . . . . . . . . . . . : 255.255.255.0

Ethernet adapter Windscribe:

   IPv4 Address. . . . . . . . . . . : 10.200.0.5
"""


class TestIpconfigParsing(unittest.TestCase):
    def test_pairs(self):
        pairs = parse_ipconfig_interfaces(SAMPLE_IPCONFIG)
        self.assertIn(("NordLynx", "10.8.0.2"), pairs)
        self.assertIn(("Wi-Fi", "192.168.1.10"), pairs)
        self.assertIn(("Windscribe", "10.200.0.5"), pairs)

    def test_vpn_ips_only(self):
        pairs = parse_ipconfig_interfaces(SAMPLE_IPCONFIG)
        ips = vpn_interface_ips(pairs)
        self.assertEqual(sorted(ips), ["10.200.0.5", "10.8.0.2"])
        self.assertNotIn("192.168.1.10", ips)


if __name__ == "__main__":
    unittest.main()
