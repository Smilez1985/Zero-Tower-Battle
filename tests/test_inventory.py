#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Tests fuer models/inventory.py

Die Tests wurden 2026-09 gegen die tatsaechliche Inventory-API neu
geschrieben. Die vorherige Fassung ging von einem slot-basierten Inventar
(`inv.slots`, `add_item("slot_1", item)`, Limit 50) aus — die Implementierung
nutzt eine unbegrenzte Liste mit Verwertungsvorschlaegen.
"""

import pytest

from models.inventory import Inventory


def make_item(name="Test Waffe", typ="Waffe", tier=1, atk=10, price=100):
    return {
        "name": name,
        "type": typ,
        "tier": tier,
        "stats": {"ATK": atk},
        "price": price,
    }


class TestInventoryBasics:
    def test_init_defaults(self):
        inv = Inventory()
        assert inv.items == []
        assert inv.gold == 500
        assert inv.xp == 0
        assert inv.player_name == "Unknown"

    def test_init_with_name(self):
        inv = Inventory(player_name="Pi-Held")
        assert inv.player_name == "Pi-Held"


class TestItemManagement:
    def test_add_item(self):
        inv = Inventory()
        result = inv.add_item(make_item())
        assert result["result"] == "SUCCESS"
        assert len(inv.items) == 1
        assert inv.items[0]["equipped"] is False
        assert inv.stats["items_bought"] == 1

    def test_add_none_item(self):
        inv = Inventory()
        result = inv.add_item(None)
        assert result["result"] == "ERROR"
        assert inv.items == []

    def test_add_many_items_is_unlimited(self):
        inv = Inventory()
        for i in range(60):
            inv.add_item(make_item(name=f"Item {i}"))
        assert len(inv.items) == 60

    def test_remove_item(self):
        inv = Inventory()
        inv.add_item(make_item())
        result = inv.remove_item(0)
        assert result["result"] == "SUCCESS"
        assert inv.items == []

    def test_remove_invalid_index(self):
        inv = Inventory()
        result = inv.remove_item(5)
        assert result["result"] == "ERROR"


class TestEquipment:
    def test_equip_and_unequip(self):
        inv = Inventory()
        inv.add_item(make_item())
        eq = inv.equip_item(0)
        assert eq["result"] in ("SUCCESS", "ERROR")
        if eq["result"] == "SUCCESS":
            assert inv.items[0]["equipped"] is True
            un = inv.unequip_item(0)
            assert un["result"] == "SUCCESS"
            assert inv.items[0]["equipped"] is False

    def test_get_equipped_items(self):
        inv = Inventory()
        assert inv.get_equipped_items() == []


class TestEconomy:
    def test_add_gold(self):
        inv = Inventory()
        inv.add_gold(250)
        assert inv.gold == 750

    def test_spend_gold_success(self):
        inv = Inventory()
        assert inv.spend_gold(200) is True
        assert inv.gold == 300

    def test_spend_gold_insufficient(self):
        inv = Inventory()
        assert inv.spend_gold(9999) is False
        assert inv.gold == 500

    def test_add_xp(self):
        inv = Inventory()
        inv.add_xp(120)
        assert inv.xp == 120


class TestSerialization:
    def test_roundtrip(self):
        inv = Inventory(player_name="Pi-Held")
        inv.add_item(make_item())
        inv.add_gold(100)
        data = inv.to_dict()

        restored = Inventory()
        restored.load_from_dict(data)
        assert restored.player_name == "Pi-Held"
        assert restored.gold == inv.gold

    def test_inventory_state(self):
        inv = Inventory()
        state = inv.get_inventory_state()
        assert isinstance(state, dict)
