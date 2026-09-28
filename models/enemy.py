#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Enemy Model
======================================
Zentrales Gegner-Datenmodell.
"""

from typing import Dict, Any


class Enemy:
    """Gegner-Modell mit KI und Kampflogik."""

    def __init__(self, enemy_id: str = "0", name: str = None,
                 health: int = 50, atk: int = 10, xp_reward: int = 25,
                 gold_reward: int = 10, loot_rate: float = 0.1):
        self.id = enemy_id
        self.name = name or f"Enemy-{enemy_id}"
        self.health = health
        self.max_health = health
        self.atk = atk
        self.score = 0
        self.xp_reward = xp_reward
        self.gold_reward = gold_reward
        self.loot_rate = loot_rate
        self.is_alive = True

    def take_damage(self, amount: int) -> bool:
        """Schaden nehmen. Gibt True zurueck wenn besiegt."""
        self.health = max(0, self.health - amount)
        if self.health <= 0:
            self.is_alive = False
            self.score += 100
            return True
        return False

    def reset(self):
        """Gegner zuruecksetzen."""
        self.health = self.max_health
        self.is_alive = True

    def get_stats(self) -> Dict[str, Any]:
        """Gegner-Stats als Dict."""
        return {
            "id": self.id,
            "name": self.name,
            "health": self.health,
            "max_health": self.max_health,
            "atk": self.atk,
            "is_alive": self.is_alive,
            "xp_reward": self.xp_reward,
            "gold_reward": self.gold_reward,
            "loot_rate": self.loot_rate
        }
