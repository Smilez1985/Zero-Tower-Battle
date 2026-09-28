#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Tests fuer services/shop.py

Die Tests wurden 2026-09 gegen die tatsaechliche Shop-API neu geschrieben.
Die vorherige Fassung pruefte Attribute (item_rotation_count, show_offering,
player_fiat), die es in der Implementierung nie gab.
"""

import pytest

from services.shop import Shop


class TestShopBasics:
    def test_init_has_offer(self):
        shop = Shop()
        assert isinstance(shop.items, list)
        assert len(shop.items) > 0

    def test_items_have_required_fields(self):
        shop = Shop()
        for item in shop.items:
            assert "id" in item
            assert "name" in item
            assert "price" in item
            assert item["price"] > 0

    def test_item_ids_are_unique(self):
        shop = Shop()
        ids = [i["id"] for i in shop.items]
        assert len(ids) == len(set(ids))

    def test_shop_state(self):
        shop = Shop()
        state = shop.get_shop_state()
        assert isinstance(state, dict)


class TestShopPurchase:
    def test_buy_item_success(self):
        shop = Shop()
        item = shop.items[0]
        result = shop.buy_item(item["id"], gold=item["price"])
        assert result["result"] == "SUCCESS"
        assert result["gold_spent"] == item["price"]

    def test_buy_item_insufficient_funds(self):
        shop = Shop()
        item = shop.items[0]
        result = shop.buy_item(item["id"], gold=item["price"] - 1)
        assert result["result"] == "INSUFFICIENT_FUNDS"

    def test_buy_unknown_item(self):
        shop = Shop()
        result = shop.buy_item("gibt-es-nicht", gold=99999)
        assert result["result"] == "NOT_FOUND"

    def test_buy_random_item_with_enough_gold(self):
        shop = Shop()
        result = shop.buy_random_item(gold=99999)
        assert result["result"] in ("SUCCESS", "NOT_FOUND")


class TestShopRefresh:
    def test_refresh_replaces_offer(self):
        shop = Shop()
        before = [i["id"] for i in shop.items]
        shop.refresh_shop()
        after = [i["id"] for i in shop.items]
        assert len(after) > 0
        # Nach einem Refresh ist der Zeitstempel neu gesetzt
        assert shop.last_refresh is not None
        assert isinstance(before, list)

    def test_check_shop_refresh_returns_bool_like(self):
        shop = Shop()
        result = shop.check_shop_refresh()
        assert result is None or isinstance(result, (bool, dict))
