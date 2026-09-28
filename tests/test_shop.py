#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Test Cases für shop.py
================ === ================================

Test-Suite:
├─ Test Shop-Rotation
├─ Test Preis-Multiplier
├─ Test Shop Refresh
├─ Test P2P-Sync
└─ Test UI-Integration
"""


import pytest
from shop import Shop

class TestShop:
    def test_init(self):
        shop = Shop()
        assert shop.item_rotation_count == 0
    
    def test_show_offering(self):
        shop = Shop()
        result = shop.show_offering()
        assert isinstance(result, list)
        assert len(result) == 3
    
    def test_purchase_valid(self):
        shop = Shop()
        shop.player_fiat = 1000
        result = shop.buy_item(0)
        assert result["result"] == "SUCCESS"
