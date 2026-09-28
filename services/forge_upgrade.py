#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Forge Upgrade System
================================================

Schmiede-Upgrade System:
  - Upgrade-System (Schwert +x)
  - Kosten: Level x 15 Scrap (verdoppelt pro Stufe)
  - Effekt: +2 ATK oder +2 DEF pro Upgrade
  - Name-Suffix: "Schwert +1", "Schwert +2"
  - Max Upgrade Level: 5
  - 10 Min Cooldown zwischen Upgrades
"""

from typing import Dict, Any
from datetime import datetime


class ForgeUpgrade:
    """
    Schmiede-Upgrade Manager.

    Features:
      - Upgrade-System mit Kosten-Eskalation
      - Cooldown zwischen Upgrades
      - ATK oder DEF Upgrade pro Stufe
      - Name-Suffix fuer upgegradete Items
    """

    UPGRADE_COST_BASE = 15
    UPGRADE_COST_MULTIPLIER = 2
    UPGRADE_STAT_BONUS = 2
    UPGRADE_LEVEL_CAP = 5
    COOLDOWN_MINUTES = 10

    def __init__(self):
        self.upgrade_count = 0
        self.last_upgrade_time = 0.0

    def upgrade_weapon(
        self,
        weapon_name: str,
        item: Dict[str, Any],
        scrap_currency: int,
        player_level: int,
        mode: str
    ) -> Dict[str, Any]:
        """
        Weapon Upgrade Logic.

        Args:
            weapon_name: Name der Waffe
            item: Item Dictionary (wird in-place modifiziert)
            scrap_currency: Verfuegbare Scrap-Menge
            player_level: Spieler Level
            mode: Upgrade-Modus ("atk" oder "def")

        Returns:
            Dict mit Result + Upgraded Item
        """
        # Aktuelles Upgrade-Level
        current_upgrade = item.get("upgrade_level", 0)
        upgrade_level = current_upgrade + 1

        # Max-Level Check
        if upgrade_level > self.UPGRADE_LEVEL_CAP:
            return {
                "result": "MAX_LEVEL",
                "message": f"Max Upgrade-Level {self.UPGRADE_LEVEL_CAP} erreicht!",
                "item": item
            }

        # Kostenberechnung: Level x 15 x 2^(upgrade-1)
        cost = self.get_upgrade_cost(player_level, upgrade_level)

        # Scrap pruefen
        if scrap_currency < cost:
            return {
                "result": "INSUFFICIENT_SCRAP",
                "required": cost,
                "available": scrap_currency,
                "message": f"Benoetigt {cost} Scrap (hast: {scrap_currency})",
                "item": item
            }

        # Cooldown pruefen
        now = datetime.now().timestamp()
        elapsed = now - self.last_upgrade_time
        cooldown_seconds = self.COOLDOWN_MINUTES * 60

        if self.last_upgrade_time > 0 and elapsed < cooldown_seconds:
            remaining = int((cooldown_seconds - elapsed) / 60)
            return {
                "result": "COOLDOWN",
                "remaining_minutes": remaining,
                "message": f"Schmiede kueht ab: noch {remaining} Min",
                "item": item
            }

        # Modus validieren
        mode_lower = mode.lower()
        if mode_lower == "atk":
            stat_key = "ATK"
        elif mode_lower == "def":
            stat_key = "DEF"
        else:
            return {
                "result": "INVALID_MODE",
                "message": "Modus muss 'atk' oder 'def' sein",
                "item": item
            }

        # Upgrade ausfuehren
        self.last_upgrade_time = now
        self.upgrade_count += 1

        # Stats holen (unterstuetzt dict und flat)
        item_stats = item.get("stats", {})
        if isinstance(item_stats, dict):
            old_stat = item_stats.get(stat_key, 0)
            item_stats[stat_key] = old_stat + self.UPGRADE_STAT_BONUS
            item["stats"] = item_stats
        else:
            old_stat = int(item_stats) if item_stats else 0
            item["stats"] = old_stat + self.UPGRADE_STAT_BONUS

        new_stat = old_stat + self.UPGRADE_STAT_BONUS

        # Name-Update mit Suffix
        base_name = item.get("name", weapon_name)
        # Entferne alten Suffix falls vorhanden
        if " +" in base_name:
            base_name = base_name.rsplit(" +", 1)[0]

        item["name"] = f"{base_name} +{upgrade_level}"
        item["upgrade_level"] = upgrade_level

        return {
            "result": "SUCCESS",
            "upgrade_level": upgrade_level,
            "cost_used": cost,
            "stat_affected": stat_key,
            "old_value": old_stat,
            "new_value": new_stat,
            "item_name": item["name"],
            "message": f"[+{upgrade_level}] {stat_key}: +{self.UPGRADE_STAT_BONUS} ({old_stat} -> {new_stat})",
            "item": item
        }

    def get_upgrade_cost(self, player_level: int, upgrade_level: int) -> int:
        """
        Upgrade-Kosten berechnen.

        Returns:
            Kosten in Scrap
        """
        return int(
            (self.UPGRADE_COST_BASE * max(1, player_level))
            * (self.UPGRADE_COST_MULTIPLIER ** max(0, upgrade_level - 1))
        )

    def get_max_upgrade_level(self) -> int:
        """Max Upgrade Level."""
        return self.UPGRADE_LEVEL_CAP

    def get_upgrade_preview(self, item: Dict[str, Any],
                            player_level: int) -> Dict[str, Any]:
        """
        Vorschau: Was wuerde ein Upgrade kosten/bringen?

        Returns:
            Dict mit: next_level, cost, bonus
        """
        current = item.get("upgrade_level", 0)
        next_level = current + 1

        if next_level > self.UPGRADE_LEVEL_CAP:
            return {
                "can_upgrade": False,
                "message": "Max Level erreicht"
            }

        cost = self.get_upgrade_cost(player_level, next_level)
        return {
            "can_upgrade": True,
            "current_level": current,
            "next_level": next_level,
            "cost_scrap": cost,
            "stat_bonus": self.UPGRADE_STAT_BONUS,
            "max_level": self.UPGRADE_LEVEL_CAP
        }


if __name__ == "__main__":
    forge = ForgeUpgrade()

    test_item = {
        "name": "Eiserner Speer",
        "type": "Waffe",
        "stats": {"ATK": 10, "DEF": 5},
        "upgrade_level": 0
    }

    # Vorschau
    preview = forge.get_upgrade_preview(test_item, player_level=5)
    print(f"Vorschau: {preview}")

    # Upgrade
    result = forge.upgrade_weapon("Eiserner Speer", test_item, scrap_currency=100,
                                  player_level=5, mode="atk")
    print(f"Ergebnis: {result['message']}")
    print(f"Item: {test_item['name']}, Stats: {test_item['stats']}")
