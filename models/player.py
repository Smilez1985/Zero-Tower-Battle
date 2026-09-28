#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Player Model
=======================================
Zentrales Spieler-Datenmodell.
"""

from typing import Dict, Any


class Player:
    """Spieler-Modell mit Stats und Skills."""

    def __init__(self, player_id: str = "default", username: str = "Held"):
        self.id = player_id
        self.username = username
        self.score = 0
        self.level = 1
        self.health = 100
        self.max_health = 100
        self.rank = 1
        self.gold = 0
        self.xp = 0
        self.atk = 25
        self.defense = 40
        self.spd = 20
        self.luk = 15
        self.character_class = "Krieger"

    def update_score(self, points: int):
        """Score aktualisieren."""
        self.score += points
        self.level = min(100, self.level + 1)

    def take_damage(self, amount: int) -> bool:
        """Schaden nehmen. Gibt True zurueck wenn besiegt."""
        self.health = max(0, self.health - amount)
        return self.health <= 0

    def heal(self, amount: int):
        """Heilen bis max_health."""
        self.health = min(self.max_health, self.health + amount)

    def add_gold(self, amount: int):
        """Gold hinzufuegen."""
        self.gold += amount

    def spend_gold(self, amount: int) -> bool:
        """Gold ausgeben. Gibt False zurueck wenn nicht genug."""
        if self.gold >= amount:
            self.gold -= amount
            return True
        return False

    def add_xp(self, amount: int) -> bool:
        """XP hinzufuegen. Gibt True zurueck bei Level-Up."""
        self.xp += amount
        xp_needed = 100 * self.level
        if self.xp >= xp_needed:
            self.xp -= xp_needed
            self.level += 1
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Spieler-Stats als Dict."""
        return {
            "id": self.id,
            "username": self.username,
            "score": self.score,
            "level": self.level,
            "health": self.health,
            "max_health": self.max_health,
            "gold": self.gold,
            "xp": self.xp,
            "atk": self.atk,
            "defense": self.defense,
            "spd": self.spd,
            "luk": self.luk,
            "class": self.character_class,
            "rank": self.rank
        }

    def get_total_stats(self) -> int:
        """100-Punkte-Gesetz: Summe aller Kampf-Attribute."""
        return self.atk + self.defense + self.spd + self.luk
