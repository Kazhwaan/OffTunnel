"""OffTunnel — Windows VPN split tunneling, Iranian-first.

Original code, written from scratch for this project. OffTunnel is
inspired by the *behaviour* of greggubarev/DirectLane (route selected
destinations through the regular gateway while a VPN stays on), but it
is not a fork and contains no DirectLane source code.

v1 is route-based only: it manages Windows IPv4 routes. It does not
install a kernel driver and does not intercept packets per application
(that is a possible v2, see README.md).
"""

from .config import APP_NAME, APP_VERSION

__version__ = APP_VERSION
__app_name__ = APP_NAME
