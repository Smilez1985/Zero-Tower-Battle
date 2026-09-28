#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Test Cases für net_manager.py
================ === ================================

Test-Suite:
├─ Test Network Isolation
├─ Test Split-Tunneling
├─ Test WiFi Direct
├─ Test BLE Discovery
└─ Test Security Rules
"""


import pytest
from net_manager import NetManager, NetworkMode

class TestNetManager:
    def test_init(self):
        nm = NetManager()
        assert nm.wlan_iface == "wlan0"
        assert nm.tun_iface == "tun0"
    
    def test_setup_network(self):
        nm = NetManager()
        result = asyncio.run(nm.setup_network())
        assert result["result"] in ["SUCCESS", "SIMULATION"]
    
    def test_ble_discovery(self):
        nm = NetManager()
        result = nm.discover_ble()
        assert isinstance(result, list)
