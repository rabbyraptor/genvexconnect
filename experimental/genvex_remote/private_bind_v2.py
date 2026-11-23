"""Explicit v2-only private network bind policy; no sockets or imports with side effects.

A private IPv4 address is not itself proof of network isolation. The enclosing
HAOS App must separately ensure the listener is not host-published, routed to
untrusted clients, or exposed outside its trusted Supervisor network.
"""
from __future__ import annotations

from ipaddress import IPv4Address, ip_address

INTERNAL_PORT = 18275
LOOPBACK = "127.0.0.1"


def validate_v2_bind(bind_host: str, port: int, *, private_opt_in: bool = False) -> None:
    """Fail closed unless loopback or explicitly opted-in RFC1918 interface."""
    if type(bind_host) is not str or type(port) is not int:
        raise ValueError("Invalid v2 bind")
    if bind_host == LOOPBACK and (port == 0 or 1024 <= port <= 65535):
        return
    if not private_opt_in or port != INTERNAL_PORT:
        raise ValueError("Private v2 binding requires explicit opt-in and fixed port")
    try:
        address = ip_address(bind_host)
    except ValueError:
        raise ValueError("Invalid private v2 interface address") from None
    from ipaddress import ip_network
    if type(address) is not IPv4Address or not any(
        address in network for network in (
            ip_network("10.0.0.0/8"),
            ip_network("172.16.0.0/12"),
            ip_network("192.168.0.0/16"),
        )
    ):
        raise ValueError("Only explicit RFC1918 IPv4 interface addresses permitted")
