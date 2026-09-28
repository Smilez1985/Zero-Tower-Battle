#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Inventory System
===========================================
Zentrales Inventar-Management mit Slot-System,
Gold-Verwaltung, Persistenz und Auto-Verwertung.

Features:
- Unbegrenztes Inventar (dynamisch wachsend)
- Auto-Verwertungsvorschlag fuer schlechte Items
- Item-Ausruestung/Verkauf/Zerlegung
- Gold & XP Management
- Persistenz via JSON
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime


class Inventory:
    """
    Spielerinventar mit unbegrenzten Slots.
    Schlechte Items werden automatisch zur Verwertung vorgeschlagen.
    """

    ITEM_TYPES = ["Waffe", "Ruestung", "Rune", "Potion"]
    ITEM_QUALITY = {
        "Gewoehnlich": {"min": 2, "max": 7, "sell_multiplier": 0.3},
        "Selten": {"min": 8, "max": 14, "sell_multiplier": 0.5},
        "Legendaer": {"min": 15, "max": 25, "sell_multiplier": 0.8}
    }
    AUTO_SALVAGE_THRESHOLD = 5  # Items mit Stats <= diesem Wert vorschlagen

    def __init__(self, player_name: str = "Unknown"):
        """
        Initialize Inventory.

        Args:
            player_name: Spieler-Name
        """
        self.player_name = player_name
        self.items: List[Dict[str, Any]] = []
        self.gold: int = 500
        self.xp: int = 0
        self.stats = {
            "wins": 0,
            "losses": 0,
            "killed": 0,
            "assists": 0,
            "level_ups": 0,
            "items_bought": 0,
            "items_salvaged": 0
        }

    # ===========================
    # Item Management
    # ===========================

    def add_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Item zum Inventar hinzufuegen (unbegrenzt).
        Prueft automatisch ob Item zur Verwertung vorgeschlagen wird.

        Args:
            item: Item-Daten Dict

        Returns:
            Dict mit: result, item, salvage_suggestion
        """
        if item is None:
            return {"result": "ERROR", "message": "Kein Item angegeben"}

        item_entry = {
            **item,
            "equipped": False,
            "added_at": datetime.now().isoformat()
        }
        self.items.append(item_entry)
        self.stats["items_bought"] += 1

        # Auto-Verwertungsvorschlag
        salvage_suggestion = self._check_auto_salvage(item_entry)

        return {
            "result": "SUCCESS",
            "message": f"Item '{item.get('name', 'Unbekannt')}' hinzugefuegt",
            "item": item_entry,
            "salvage_suggestion": salvage_suggestion
        }

    def remove_item(self, index: int) -> Dict[str, Any]:
        """Item aus Inventar entfernen."""
        if index < 0 or index >= len(self.items):
            return {"result": "ERROR", "message": f"Ungueltiger Index: {index}"}

        item = self.items.pop(index)
        return {"result": "SUCCESS", "item": item}

    def equip_item(self, index: int) -> Dict[str, Any]:
        """Item ausruesten."""
        if index < 0 or index >= len(self.items):
            return {"result": "ERROR", "message": f"Ungueltiger Index: {index}"}

        item = self.items[index]
        item_type = item.get("type", "")

        # Vorheriges Item desselben Typs entruesten
        for other in self.items:
            if other.get("type") == item_type and other.get("equipped"):
                other["equipped"] = False

        item["equipped"] = True
        return {
            "result": "SUCCESS",
            "message": f"'{item.get('name', '')}' ausgeruestet!",
            "index": index
        }

    def unequip_item(self, index: int) -> Dict[str, Any]:
        """Item entruesten."""
        if index < 0 or index >= len(self.items):
            return {"result": "ERROR", "message": f"Ungueltiger Index: {index}"}

        item = self.items[index]
        if not item.get("equipped"):
            return {"result": "NOT_EQUIPPED", "message": "Item ist nicht ausgeruestet"}

        item["equipped"] = False
        return {"result": "SUCCESS", "message": "Item entruested!"}

    def sell_item(self, index: int, value_multiplier: float = 1.0) -> Dict[str, Any]:
        """
        Item verkaufen fuer Gold.

        Args:
            index: Item-Index
            value_multiplier: Preismultiplikator

        Returns:
            Dict mit: result, gold
        """
        if index < 0 or index >= len(self.items):
            return {"result": "ERROR", "message": f"Ungueltiger Index: {index}"}

        item = self.items[index]
        if item.get("equipped"):
            return {"result": "CANNOT_SELL_EQUIPPED", "message": "Ausgeruestetes Item kann nicht verkauft werden"}

        # Wert berechnen
        stats_value = item.get("stats", {})
        if isinstance(stats_value, dict):
            item_value = sum(stats_value.values())
        elif isinstance(stats_value, (int, float)):
            item_value = stats_value
        else:
            item_value = 5

        gold_earned = max(1, int(item_value * value_multiplier))
        self.gold += gold_earned
        self.items.pop(index)

        return {
            "result": "SUCCESS",
            "message": f"Item verkauft fuer {gold_earned} Gold!",
            "gold_earned": gold_earned,
            "total_gold": self.gold
        }

    # ===========================
    # Auto-Verwertung
    # ===========================

    def _check_auto_salvage(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Pruefe ob Item zur automatischen Verwertung vorgeschlagen werden soll.

        Args:
            item: Das zu pruefende Item

        Returns:
            Verwertungsvorschlag oder None
        """
        stats = item.get("stats", {})
        if isinstance(stats, dict):
            total_stats = sum(stats.values())
        elif isinstance(stats, (int, float)):
            total_stats = stats
        else:
            return None

        if total_stats <= self.AUTO_SALVAGE_THRESHOLD:
            salvage_value = max(1, total_stats)
            return {
                "suggestion": "SALVAGE",
                "reason": f"Schwaches Item (Stats: {total_stats})",
                "salvage_gold": salvage_value,
                "item_name": item.get("name", "Unbekannt")
            }
        return None

    def get_salvage_suggestions(self) -> List[Dict[str, Any]]:
        """
        Alle Items auflisten die zur Verwertung vorgeschlagen werden.

        Returns:
            Liste von Verwertungsvorschlaegen mit Index
        """
        suggestions = []
        for i, item in enumerate(self.items):
            if item.get("equipped"):
                continue
            suggestion = self._check_auto_salvage(item)
            if suggestion:
                suggestion["index"] = i
                suggestions.append(suggestion)
        return suggestions

    def auto_salvage(self, confirm: bool = False) -> Dict[str, Any]:
        """
        Alle vorgeschlagenen Items verwerten.

        Args:
            confirm: Muss True sein um tatsaechlich zu verwerten

        Returns:
            Dict mit: result, salvaged_count, gold_earned
        """
        if not confirm:
            suggestions = self.get_salvage_suggestions()
            return {
                "result": "PENDING_CONFIRMATION",
                "suggestions": suggestions,
                "message": f"{len(suggestions)} Items zur Verwertung vorgeschlagen"
            }

        suggestions = self.get_salvage_suggestions()
        total_gold = 0
        salvaged_count = 0

        # Rueckwaerts iterieren um Indexverschiebung zu vermeiden
        for suggestion in sorted(suggestions, key=lambda s: s["index"], reverse=True):
            idx = suggestion["index"]
            if idx < len(self.items):
                total_gold += suggestion["salvage_gold"]
                self.items.pop(idx)
                salvaged_count += 1

        self.gold += total_gold
        self.stats["items_salvaged"] += salvaged_count

        return {
            "result": "SUCCESS",
            "salvaged_count": salvaged_count,
            "gold_earned": total_gold,
            "total_gold": self.gold
        }

    # ===========================
    # Gold & XP
    # ===========================

    def add_gold(self, amount: int):
        """Gold hinzufuegen."""
        self.gold += amount

    def spend_gold(self, amount: int) -> bool:
        """Gold ausgeben. False wenn nicht genug."""
        if self.gold >= amount:
            self.gold -= amount
            return True
        return False

    def add_xp(self, amount: int):
        """XP hinzufuegen."""
        self.xp += amount

    # ===========================
    # Abfragen
    # ===========================

    def get_equipped_items(self) -> List[Dict[str, Any]]:
        """Alle ausgeruesteten Items."""
        return [item for item in self.items if item.get("equipped")]

    def get_inventory_state(self) -> Dict[str, Any]:
        """Aktueller Inventar-Status."""
        equipped = self.get_equipped_items()
        return {
            "player": self.player_name,
            "item_count": len(self.items),
            "equipped_count": len(equipped),
            "gold": self.gold,
            "xp": self.xp,
            "items": self.items,
            "equipped_items": equipped,
            "stats": self.stats
        }

    def get_items_by_type(self, item_type: str) -> List[Dict[str, Any]]:
        """Items nach Typ filtern."""
        return [item for item in self.items if item.get("type") == item_type]

    # ===========================
    # Dict-Serialisierung (fuer Orchestrator)
    # ===========================

    def to_dict(self) -> Dict[str, Any]:
        """
        Inventar als Dict serialisieren (fuer Hot/Cold Storage).
        Wird vom Orchestrator genutzt um Inventar im Character-Dict
        zu speichern ohne separate Datei.

        Returns:
            Dict mit allen Inventar-Daten
        """
        return {
            "player_name": self.player_name,
            "gold": self.gold,
            "xp": self.xp,
            "items": list(self.items),
            "stats": dict(self.stats)
        }

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """
        Inventar aus Dict laden (fuer Hot/Cold Storage).
        Wird vom Orchestrator genutzt um Inventar aus Character-Dict
        wiederherzustellen.

        Args:
            data: Dict mit Inventar-Daten (von to_dict())
        """
        if not data or not isinstance(data, dict):
            return

        self.player_name = data.get("player_name", self.player_name)
        self.gold = data.get("gold", self.gold)
        self.xp = data.get("xp", self.xp)
        self.items = data.get("items", [])

        # Stats mergen (fehlende Keys behalten Default)
        saved_stats = data.get("stats", {})
        if isinstance(saved_stats, dict):
            for key in self.stats:
                if key in saved_stats:
                    self.stats[key] = saved_stats[key]

    # ===========================
    # Persistenz (Datei)
    # ===========================

    def save_to_file(self, filename: str) -> Dict[str, Any]:
        """Inventar in JSON-Datei speichern."""
        try:
            data = {
                "player_name": self.player_name,
                "gold": self.gold,
                "xp": self.xp,
                "items": self.items,
                "stats": self.stats,
                "saved_at": datetime.now().isoformat()
            }
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
            return {"result": "SUCCESS", "saved": True}
        except Exception as e:
            return {"result": "ERROR", "error": str(e)}

    def load_from_file(self, filename: str) -> Dict[str, Any]:
        """Inventar aus JSON-Datei laden."""
        try:
            with open(filename, "r") as f:
                data = json.load(f)
            self.player_name = data.get("player_name", self.player_name)
            self.gold = data.get("gold", self.gold)
            self.xp = data.get("xp", self.xp)
            self.items = data.get("items", [])
            self.stats = data.get("stats", self.stats)
            return {"result": "SUCCESS", "loaded": len(self.items)}
        except FileNotFoundError:
            return {"result": "NOT_FOUND", "loaded": 0}
        except Exception as e:
            return {"result": "ERROR", "error": str(e)}
