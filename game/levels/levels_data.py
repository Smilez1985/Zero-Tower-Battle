#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Level Data
=====================================
Endlose Floor-Progression mit skalierender Schwierigkeit.
Keine feste Obergrenze - Schwierigkeit steigt dynamisch.
"""

from typing import Dict, Any


class Levels:
    """Endloses Level-System mit dynamischer Skalierung."""

    # Basis-Werte fuer Floor 1
    BASE_BOSS_HP = 50
    BASE_ENEMY_COUNT = 3
    BASE_ENEMY_HP = 20
    BASE_XP_REWARD = 25
    BASE_GOLD_REWARD = 15

    # Skalierungsfaktoren
    BOSS_HP_SCALE = 1.15        # +15% pro Floor
    ENEMY_COUNT_SCALE = 0.05    # +1 Gegner alle 20 Floors
    ENEMY_HP_SCALE = 1.08       # +8% pro Floor
    XP_REWARD_SCALE = 1.05      # +5% pro Floor
    GOLD_REWARD_SCALE = 1.03    # +3% pro Floor

    # Schwierigkeitsstufen (automatisch basierend auf Floor)
    DIFFICULTY_TIERS = [
        (1, "EASY"),
        (10, "MEDIUM"),
        (25, "HARD"),
        (50, "VERY_HARD"),
        (100, "NIGHTMARE"),
        (200, "INFERNO"),
        (500, "MYTHIC"),
    ]

    def get_level(self, floor: int) -> Dict[str, Any]:
        """
        Generiere Level-Daten fuer beliebigen Floor.
        Keine Obergrenze - skaliert endlos.

        Args:
            floor: Floor-Nummer (1+)

        Returns:
            Dict mit Level-Daten
        """
        floor = max(1, floor)

        boss_hp = int(self.BASE_BOSS_HP * (self.BOSS_HP_SCALE ** (floor - 1)))
        enemy_count = self.BASE_ENEMY_COUNT + int(floor * self.ENEMY_COUNT_SCALE)
        enemy_hp = int(self.BASE_ENEMY_HP * (self.ENEMY_HP_SCALE ** (floor - 1)))
        xp_reward = int(self.BASE_XP_REWARD * (self.XP_REWARD_SCALE ** (floor - 1)))
        gold_reward = int(self.BASE_GOLD_REWARD * (self.GOLD_REWARD_SCALE ** (floor - 1)))

        difficulty = "EASY"
        for threshold, tier_name in self.DIFFICULTY_TIERS:
            if floor >= threshold:
                difficulty = tier_name

        is_boss_floor = (floor % 10 == 0)
        is_blessing_floor = (floor % 25 == 0)

        return {
            "floor": floor,
            "boss_hp": boss_hp if is_boss_floor else 0,
            "enemy_count": enemy_count,
            "enemy_hp": enemy_hp,
            "difficulty": difficulty,
            "xp_reward": xp_reward,
            "gold_reward": gold_reward,
            "is_boss_floor": is_boss_floor,
            "is_blessing_floor": is_blessing_floor
        }

    def get_difficulty_name(self, floor: int) -> str:
        """Schwierigkeitsname fuer Floor."""
        name = "EASY"
        for threshold, tier_name in self.DIFFICULTY_TIERS:
            if floor >= threshold:
                name = tier_name
        return name

    def get_floor_range(self, start: int, end: int):
        """Generator fuer Floor-Range."""
        for floor in range(start, end + 1):
            yield self.get_level(floor)

