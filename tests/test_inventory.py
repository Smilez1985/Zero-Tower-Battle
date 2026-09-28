#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Test Cases für inventory.py
================ ====================================

Test-Suite:
├─ Test Items
├─ Test Inventory-Slots
├─ Test Potions System
├─ Test Value Calculation
└─ Test Integration mit shop.py
"""


import pytest
from inventory import Inventory
from models.character_db import Champion

class TestInventory:
    def test_init(self):
        inv = Inventory()
        assert len(inv.slots) == 9
        assert inv.max_slots == 50
    
    def test_add_item(self):
        inv = Inventory()
        item = {"name": "Test Waffe", "type": "Waffe", "tier": 1, "stats": {"ATK": 10}, "price": 100}
        result = inv.add_item("slot_1", item)
        assert result["result"] == "SUCCESS"
        assert inv.slots["slot_1"] == item
    
    def test_add_too_many_items(self):
        inv = Inventory()
        # Füge 50 Items hinzu
        for i in range(50):
            item = {"name": f"Item {i}", "type": "Waffe", "stats": {"ATK": 10}}
            inv.add_item(f"slot_{i%9}", item)
        # 51. Item soll scheitern
        item = {"name": "Item 50", "type": "Waffe", "stats": {"ATK": 10}}
        result = inv.add_item("slot_0", item)
        assert result["result"] == "FULL"
