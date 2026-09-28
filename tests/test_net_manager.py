#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Tests fuer controllers/net_manager.py

Die Tests wurden 2026-09 korrigiert: `asyncio` wurde verwendet ohne
importiert zu sein, und `discover_ble()` existiert in NetManager nicht
(BLE-Discovery liegt in game/ble_beacon.py).

Hinweis: setup_network() ruft `ip`/`iptables` auf. Auf einem Rechner ohne
diese Werkzeuge bzw. ohne root laufen die Kommandos ins Leere
(check=False) — der Test prueft deshalb nur, dass ein strukturiertes
Ergebnis zurueckkommt, nicht der tatsaechliche Netzwerkzustand.
"""

import asyncio

import pytest

from controllers.net_manager import NetManager, NetworkMode


class TestNetManagerInit:
    def test_default_interfaces(self):
        nm = NetManager()
        assert nm.wlan_iface == "wlan0"
        assert nm.tun_iface == "tun0"

    def test_custom_interfaces(self):
        nm = NetManager(wlan_iface="wlan1", tun_iface="tun9", ip_suffix=7)
        assert nm.wlan_iface == "wlan1"
        assert nm.tun_iface == "tun9"


class TestNetworkMode:
    def test_modes_exist(self):
        assert NetworkMode.P2P.value == "p2p"
        assert NetworkMode.PVE.value == "pve"

    def test_mode_lookup(self):
        assert NetworkMode("p2p") is NetworkMode.P2P


class TestSetupNetwork:
    def test_returns_dict(self):
        nm = NetManager()
        result = asyncio.run(nm.setup_network(NetworkMode.PVE))
        assert isinstance(result, dict)

    def test_disconnect_is_awaitable(self):
        nm = NetManager()
        asyncio.run(nm.disconnect())
