#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Shop System

Features:
- Rotierendes Angebot (3 Items)
- Kauf/Verkauf Logik
- Preis-Multiplier
- Shop Refresh
- Potions-System
"""

from datetime import datetime
from typing import Dict, List, Any
import random


class Shop:
    """Shop System fuer P2P-Encounters."""
    
    ITEM_TYPES = ["Waffe", "Ruestung", "Rune", "Potions"]
    
    SHOP_ITEMS = {
        "Waffe": [
            {"name": "Eiserner Speer", "type": "Waffe", "tier": 1, "price": 100, "stats": 10.0},
            {"name": "Rostiger Dolch", "type": "Waffe", "tier": 2, "price": 200, "stats": 15.0},
            {"name": "Mythische Klinge", "type": "Waffe", "tier": 3, "price": 500, "stats": 25.0},
            {"name": "Legendares Schwert", "type": "Waffe", "tier": 4, "price": 1000, "stats": 40.0}
        ],
        "Ruestung": [
            {"name": "Lederpanzer", "type": "Ruestung", "tier": 1, "price": 70, "stats": 15.0},
            {"name": "Stahlhaube", "type": "Ruestung", "tier": 2, "price": 150, "stats": 20.0},
            {"name": "Mythische Ruestung", "type": "Ruestung", "tier": 3, "price": 400, "stats": 30.0},
            {"name": "Legendare Ruestung", "type": "Ruestung", "tier": 4, "price": 800, "stats": 45.0}
        ],
        "Rune": [
            {"name": "Fackel Runa", "type": "Rune", "tier": 1, "price": 50, "stats": 12.0},
            {"name": "Strom Runa", "type": "Rune", "tier": 2, "price": 100, "stats": 18.0},
            {"name": "Feuer Runa", "type": "Rune", "tier": 3, "price": 250, "stats": 28.0},
            {"name": "Gotterliche Runa", "type": "Rune", "tier": 4, "price": 500, "stats": 40.0}
        ],
        "Potions": [
            {"name": "Eisern Elixier", "type": "Potion", "tier": 1, "price": 30, "stats": 50.0, "effect": "heal"},
            {"name": "Feuer Elixier", "type": "Potion", "tier": 2, "price": 50, "stats": 75.0, "effect": "buff"},
            {"name": "Sturm Elixier", "type": "Potion", "tier": 3, "price": 120, "stats": 100.0, "effect": "heal"},
            {"name": "Gotterliche Elixier", "type": "Potion", "tier": 4, "price": 300, "stats": 150.0, "effect": "buff"}
        ]
    }
    
    REFRESH_INTERVAL = 24 * 60 * 60  # 24h in Sekunden
    
    def __init__(self, refresh_interval: int = REFRESH_INTERVAL):
        self.items = self._generate_current_offer()
        self.refresh_interval = refresh_interval
        self.last_refresh = datetime.now()
        self._is_active = True
        
    def _generate_current_offer(self):
        categories = list(self.SHOP_ITEMS.keys())
        items = []
        for i in range(min(3, len(categories))):
            category = categories[i % len(categories)]
            category_items = self.SHOP_ITEMS[category]
            item = random.choice(category_items).copy()
            item["id"] = f"{category}_{random.randint(1000, 9999)}"
            items.append(item)
        return items
    
    def refresh_shop(self):
        """Refresh shop rotation."""
        self.items = self._generate_current_offer()
        self.last_refresh = datetime.now()
        return {"result": "SUCCESS", "items": self.items}
    
    def buy_item(self, item_id: str, gold: int):
        """Buy item from shop."""
        item = next((i for i in self.items if i["id"] == item_id), None)
        
        if not item:
            return {
                "result": "NOT_FOUND", 
                "message": f"Item '{item_id}' nicht im Shop"
            }
        
        if gold < item["price"]:
            return {
                "result": "INSUFFICIENT_FUNDS", 
                "message": f"Benotigt {item['price']} gold, hast {gold}"
            }
        
        return {
            "result": "SUCCESS",
            "item": item.copy(),
            "gold_spent": item["price"],
            "message": f"{item['name']} gekauft"
        }
    
    def buy_random_item(self, gold: int):
        """Buy random item from shop."""
        if not self.items:
            return {"result": "EMPTY_SHOP"}
        
        item = random.choice(self.items)
        return {
            "result": "SUCCESS",
            "item": item.copy(),
            "gold_spent": item["price"]
        }
    
    def sell_item(self, item_id: str, value_multiplier: float = 1.0):
        """Sell item for gold."""
        item = next((i for i in self.items if i["id"] == item_id), None)
        
        if not item:
            return {
                "result": "NOT_FOUND",
                "message": f"Item '{item_id}' nicht gefunden"
            }
        
        value = item["price"] * value_multiplier
        return {
            "result": "SUCCESS",
            "gold": value,
            "message": f"{item['name']} verkauft fuer {value} gold"
        }
    
    def check_shop_refresh(self):
        """Check if shop needs refresh."""
        if datetime.now() - self.last_refresh > self.refresh_interval:
            self.refresh_shop()
            return {"needs_refresh": True}
        return {"needs_refresh": False}
    
    def get_shop_state(self):
        """Get current shop state."""
        return {
            "active": self._is_active,
            "refresh_time": self.last_refresh.isoformat(),
            "items": self.items
        }
    
    def get_available_categories(self):
        """Get available categories."""
        return list(self.SHOP_ITEMS.keys())
    
    def get_random_item_preview(self):
        """Get random item preview."""
        categories = list(self.SHOP_ITEMS.keys())
        category = random.choice(categories)
        item = random.choice(self.SHOP_ITEMS[category]).copy()
        item["id"] = f"{category}_{random.randint(1000, 9999)}"
        return {
            "item": item,
            "category": category
        }
    
    def get_potions(self):
        """Get available potions."""
        return self.SHOP_ITEMS["Potions"]
    
    def use_potion(self, potion_id: str):
        """Use potion (effect simulation)."""
        potion = next((p for p in self.get_potions() if p["id"] == potion_id), None)
        
        if not potion:
            return {
                "result": "NOT_FOUND",
                "message": "Potion nicht gefunden"
            }
        
        return {
            "result": "SUCCESS",
            "effect": potion["effect"],
            "heal_amount": int(potion["stats"]),
            "message": potion["name"]
        }


if __name__ == "__main__":
    # Test shop.py
    shop = Shop()
    print("Shop initialisiert!")
    print(f"Item-Anzahl: {len(shop.items)}")
    print(f"Kategorien: {shop.get_available_categories()}")
