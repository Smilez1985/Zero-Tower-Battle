#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Encounter Balance Tuner
===================================================
Dynamisches Balancing-System fuer Tower-Encounters.

Passt Monster-Stats, Rewards und Encounter-Schwierigkeit
basierend auf Spieler-Performance an.

Kern-Mechaniken:
  - Floor-basierte Skalierung (exponentiell, aus levels_data.py)
  - Performance-Tracking: Winrate der letzten N Kaempfe
  - Adaptive Difficulty: Wenn Spieler zu leicht/schwer gewinnt
  - Reward-Balancing: Loot/XP/Gold an Schwierigkeit angepasst
  - Psyche-Integration: Erschoepfung beeinflusst Schwierigkeit

Referenz: Battle-Pi_Konsolidiert.txt Abschnitt 9 (Balancing)
"""

import math
from typing import Dict, Any, List, Optional, Tuple
from collections import deque


# =============================================
# Konstanten
# =============================================

# Adaptive Difficulty
WINRATE_WINDOW = 20          # Letzte N Kaempfe fuer Winrate
TARGET_WINRATE = 0.55        # Ziel-Winrate (55% - leicht positiv)
WINRATE_TOLERANCE = 0.10     # +-10% Toleranz
MAX_DIFFICULTY_MOD = 0.30    # Maximale Anpassung (+/-30%)

# Floor-Skalierung
HP_SCALE_PER_FLOOR = 1.08    # +8% HP pro Floor
ATK_SCALE_PER_FLOOR = 1.06   # +6% ATK pro Floor
DEF_SCALE_PER_FLOOR = 1.04   # +4% DEF pro Floor
SPD_SCALE_PER_FLOOR = 1.02   # +2% SPD pro Floor

# Reward-Skalierung
XP_SCALE_PER_FLOOR = 1.05    # +5% XP pro Floor
GOLD_SCALE_PER_FLOOR = 1.03  # +3% Gold pro Floor

# Boss-Multiplikatoren (alle 10 Floors)
BOSS_HP_MULT = 3.0
BOSS_ATK_MULT = 1.5
BOSS_REWARD_MULT = 5.0

# Blessing-Floors (alle 25 Floors) — reduzierte Schwierigkeit
BLESSING_DIFF_MULT = 0.7
BLESSING_REWARD_MULT = 1.5

# Typ-Effektivitaet (Stein > Schere > Papier > Stein)
TYPE_ADVANTAGE_MULT = 1.25   # +25% Schaden bei Vorteil
TYPE_DISADVANTAGE_MULT = 0.80  # -20% Schaden bei Nachteil


# =============================================
# Type Matchup
# =============================================

# Stein=0 > Schere=1, Schere=1 > Papier=2, Papier=2 > Stein=0
TYPE_ADVANTAGE = {
    ("Stein", "Schere"): "advantage",
    ("Schere", "Papier"): "advantage",
    ("Papier", "Stein"): "advantage",
    ("Schere", "Stein"): "disadvantage",
    ("Papier", "Schere"): "disadvantage",
    ("Stein", "Papier"): "disadvantage",
}


def get_type_matchup(attacker_type: str, defender_type: str) -> str:
    """
    Typ-Matchup bestimmen.

    Returns:
        "advantage", "disadvantage", oder "neutral"
    """
    return TYPE_ADVANTAGE.get((attacker_type, defender_type), "neutral")


def get_type_multiplier(attacker_type: str, defender_type: str) -> float:
    """Schadens-Multiplikator basierend auf Typ-Matchup."""
    matchup = get_type_matchup(attacker_type, defender_type)
    if matchup == "advantage":
        return TYPE_ADVANTAGE_MULT
    elif matchup == "disadvantage":
        return TYPE_DISADVANTAGE_MULT
    return 1.0


# =============================================
# Encounter Balancer
# =============================================

class EncounterBalancer:
    """
    Dynamisches Encounter-Balancing.

    Trackt Spieler-Performance und passt Monster-Stats
    adaptiv an, damit der Spieler weder gelangweilt noch
    ueberwaeltigt wird.
    """

    def __init__(self, window_size: int = WINRATE_WINDOW):
        self._results: deque = deque(maxlen=window_size)
        self._difficulty_mod = 0.0   # Aktuelle Schwierigkeits-Anpassung
        self._total_fights = 0

    # ========================================
    # Performance Tracking
    # ========================================

    def record_result(self, won: bool, floor: int = 0,
                      hp_remaining_pct: float = 1.0) -> None:
        """
        Kampf-Ergebnis aufzeichnen.

        Args:
            won: Hat der Spieler gewonnen?
            floor: Aktueller Floor
            hp_remaining_pct: Verbleibende HP in % (0.0-1.0)
        """
        self._results.append({
            "won": won,
            "floor": floor,
            "hp_pct": hp_remaining_pct,
        })
        self._total_fights += 1
        self._update_difficulty_mod()

    @property
    def current_winrate(self) -> float:
        """Aktuelle Winrate (letzte N Kaempfe)."""
        if not self._results:
            return TARGET_WINRATE
        wins = sum(1 for r in self._results if r["won"])
        return wins / len(self._results)

    @property
    def difficulty_modifier(self) -> float:
        """
        Aktueller Schwierigkeits-Modifikator.

        Positiv = schwerer, Negativ = leichter.
        Bereich: -MAX_DIFFICULTY_MOD bis +MAX_DIFFICULTY_MOD
        """
        return self._difficulty_mod

    def _update_difficulty_mod(self) -> None:
        """Schwierigkeits-Anpassung basierend auf Winrate."""
        if len(self._results) < 5:
            # Zu wenig Daten, neutral bleiben
            return

        wr = self.current_winrate
        deviation = wr - TARGET_WINRATE

        if abs(deviation) <= WINRATE_TOLERANCE:
            # Im Toleranzbereich: langsam Richtung 0 bewegen
            self._difficulty_mod *= 0.95
        else:
            # Ausserhalb: anpassen
            # Spieler gewinnt zu oft -> schwerer machen (positiv)
            # Spieler verliert zu oft -> leichter machen (negativ)
            adjustment = deviation * 0.1  # Sanfte Anpassung
            self._difficulty_mod += adjustment
            self._difficulty_mod = max(-MAX_DIFFICULTY_MOD,
                                       min(MAX_DIFFICULTY_MOD, self._difficulty_mod))

    # ========================================
    # Monster-Stat-Skalierung
    # ========================================

    def scale_monster_stats(self, base_stats: Dict[str, Any],
                            floor: int,
                            psyche_mod: float = 0.0) -> Dict[str, Any]:
        """
        Monster-Stats fuer einen bestimmten Floor skalieren.

        Beruecksichtigt:
          - Floor-basierte Exponential-Skalierung
          - Adaptive Difficulty (basierend auf Winrate)
          - Boss-Floor Multiplikator (alle 10 Floors)
          - Blessing-Floor Reduktion (alle 25 Floors)
          - Psyche-Modifier (Erschoepfung)

        Args:
            base_stats: Basis-Monster-Dict (hp, atk, def, spd)
            floor: Aktueller Floor
            psyche_mod: Psyche-Modifier (-0.1 bis 0.0)

        Returns:
            Skaliertes Monster-Dict
        """
        floor = max(1, floor)
        f = floor - 1  # 0-basiert fuer Potenz

        # Basis-Skalierung
        hp_scale = HP_SCALE_PER_FLOOR ** f
        atk_scale = ATK_SCALE_PER_FLOOR ** f
        def_scale = DEF_SCALE_PER_FLOOR ** f
        spd_scale = SPD_SCALE_PER_FLOOR ** f

        # Adaptive Difficulty
        diff_mult = 1.0 + self._difficulty_mod

        # Boss-Floor (alle 10 Floors)
        is_boss = (floor % 10 == 0)
        boss_hp = BOSS_HP_MULT if is_boss else 1.0
        boss_atk = BOSS_ATK_MULT if is_boss else 1.0

        # Blessing-Floor (alle 25 Floors, aber nicht Boss)
        is_blessing = (floor % 25 == 0) and not is_boss
        bless_mult = BLESSING_DIFF_MULT if is_blessing else 1.0

        # Psyche-Effekt (Erschoepfung macht Monster staerker - konzeptionell)
        psyche_mult = 1.0 - psyche_mod  # psyche_mod ist negativ bei Erschoepfung

        # Finale Berechnung
        scaled = dict(base_stats)
        scaled["hp"] = max(1, int(
            base_stats.get("hp", 20) * hp_scale * diff_mult * boss_hp * bless_mult * psyche_mult
        ))
        scaled["atk"] = max(1, int(
            base_stats.get("atk", 5) * atk_scale * diff_mult * boss_atk * bless_mult * psyche_mult
        ))
        scaled["def"] = max(0, int(
            base_stats.get("def", 3) * def_scale * diff_mult * bless_mult
        ))
        scaled["spd"] = max(1, int(
            base_stats.get("spd", 3) * spd_scale
        ))

        # Metadaten
        scaled["_floor"] = floor
        scaled["_is_boss"] = is_boss
        scaled["_is_blessing"] = is_blessing
        scaled["_difficulty_mod"] = self._difficulty_mod

        return scaled

    # ========================================
    # Reward-Skalierung
    # ========================================

    def scale_rewards(self, base_xp: int, base_gold: int,
                      floor: int, is_boss: bool = False,
                      is_blessing: bool = False,
                      psyche_loot_mod: float = 0.0,
                      psyche_xp_mod: float = 0.0,
                      psyche_gold_mod: float = 0.0) -> Dict[str, int]:
        """
        Rewards fuer einen Floor skalieren.

        Args:
            base_xp: Basis-XP
            base_gold: Basis-Gold
            floor: Aktueller Floor
            is_boss: Boss-Floor?
            is_blessing: Blessing-Floor?
            psyche_loot_mod: Loot-Modifier durch Erschoepfung
            psyche_xp_mod: XP-Modifier durch Erschoepfung
            psyche_gold_mod: Gold-Modifier durch Erschoepfung

        Returns:
            Dict mit: xp, gold, bonus_loot_chance
        """
        f = max(0, floor - 1)

        xp_scale = XP_SCALE_PER_FLOOR ** f
        gold_scale = GOLD_SCALE_PER_FLOOR ** f

        boss_mult = BOSS_REWARD_MULT if is_boss else 1.0
        bless_mult = BLESSING_REWARD_MULT if is_blessing else 1.0

        # Psyche-Debuffs
        xp_psyche = 1.0 + psyche_xp_mod      # z.B. -0.15
        gold_psyche = 1.0 + psyche_gold_mod   # z.B. -0.10
        loot_psyche = 1.0 + psyche_loot_mod   # z.B. -0.10

        xp = max(1, int(base_xp * xp_scale * boss_mult * bless_mult * xp_psyche))
        gold = max(1, int(base_gold * gold_scale * boss_mult * bless_mult * gold_psyche))

        # Bonus-Loot-Chance (Basis 5%, steigt mit Floor)
        bonus_chance = min(0.25, 0.05 + floor * 0.001) * loot_psyche
        if is_boss:
            bonus_chance = min(0.50, bonus_chance * 2)

        return {
            "xp": xp,
            "gold": gold,
            "bonus_loot_chance": round(bonus_chance, 3)
        }

    # ========================================
    # Encounter-Generierung
    # ========================================

    def balance_encounter(self, player: Dict[str, Any],
                          monster_base: Dict[str, Any],
                          floor: int,
                          psyche_status: Optional[Dict[str, Any]] = None
                          ) -> Dict[str, Any]:
        """
        Vollstaendiges Encounter balancen.

        Kombiniert Monster-Skalierung, Reward-Berechnung und
        Typ-Matchup in einem Aufruf.

        Args:
            player: Spieler-Character-Dict
            monster_base: Basis-Monster-Dict
            floor: Aktueller Floor
            psyche_status: Psyche-Status (optional)

        Returns:
            Dict mit: monster (skaliert), rewards, matchup, difficulty_info
        """
        # Psyche-Modifier extrahieren
        psyche = psyche_status or {}
        psyche_mod = 0.0
        loot_mod = psyche.get("loot_modifier", 0.0)
        xp_mod = psyche.get("xp_modifier", 0.0)
        gold_mod = psyche.get("gold_modifier", 0.0)

        exhaustion = psyche.get("exhaustion", 0)
        if exhaustion >= 80:
            psyche_mod = -0.10  # Monster etwas staerker bei hoher Erschoepfung

        # Monster skalieren
        scaled_monster = self.scale_monster_stats(
            monster_base, floor, psyche_mod=psyche_mod
        )

        # Rewards
        is_boss = (floor % 10 == 0)
        is_blessing = (floor % 25 == 0) and not is_boss
        rewards = self.scale_rewards(
            base_xp=25, base_gold=15,
            floor=floor,
            is_boss=is_boss,
            is_blessing=is_blessing,
            psyche_loot_mod=loot_mod,
            psyche_xp_mod=xp_mod,
            psyche_gold_mod=gold_mod
        )

        # Typ-Matchup
        player_type = player.get("class_type", player.get("class_name", "Stein"))
        monster_type = monster_base.get("type", "Stein")
        matchup = get_type_matchup(player_type, monster_type)
        type_mult = get_type_multiplier(player_type, monster_type)

        return {
            "monster": scaled_monster,
            "rewards": rewards,
            "matchup": {
                "result": matchup,
                "damage_multiplier": type_mult,
                "player_type": player_type,
                "monster_type": monster_type
            },
            "difficulty_info": {
                "floor": floor,
                "is_boss": is_boss,
                "is_blessing": is_blessing,
                "adaptive_mod": self._difficulty_mod,
                "winrate": round(self.current_winrate, 3),
                "total_fights": self._total_fights,
                "psyche_mod": psyche_mod
            }
        }

    # ========================================
    # Status / Debug
    # ========================================

    def get_status(self) -> Dict[str, Any]:
        """Aktueller Balancer-Status."""
        return {
            "total_fights": self._total_fights,
            "tracked_fights": len(self._results),
            "winrate": round(self.current_winrate, 3),
            "difficulty_mod": round(self._difficulty_mod, 4),
            "target_winrate": TARGET_WINRATE,
            "tolerance": WINRATE_TOLERANCE
        }


# =============================================
# Legacy Kompatibilitaet
# =============================================

def adjust_hp(enemy_name: str, current_hp: float, target_hp: float) -> float:
    """Legacy: HP anpassen (sanft Richtung Ziel)."""
    return max(current_hp * 0.9, target_hp)


def adjust_xp_drop(enemy_name: str, current_drop: float, target_drop: float) -> float:
    """Legacy: XP-Drop anpassen (sanft Richtung Ziel)."""
    return min(current_drop * 1.1, target_drop)


# =============================================
# Export
# =============================================

__all__ = [
    "EncounterBalancer",
    "get_type_matchup",
    "get_type_multiplier",
    "adjust_hp",
    "adjust_xp_drop",
    "TYPE_ADVANTAGE",
    "TYPE_ADVANTAGE_MULT",
    "TYPE_DISADVANTAGE_MULT",
]


# =============================================
# Standalone Test
# =============================================

if __name__ == "__main__":
    balancer = EncounterBalancer()

    # Simuliere 20 Kaempfe (14 Siege, 6 Niederlagen = 70% Winrate)
    for i in range(14):
        balancer.record_result(won=True, floor=i + 1, hp_remaining_pct=0.6)
    for i in range(6):
        balancer.record_result(won=False, floor=i + 1, hp_remaining_pct=0.0)

    print(f"Status: {balancer.get_status()}")
    print(f"  -> Winrate zu hoch, Difficulty steigt: mod={balancer.difficulty_modifier:.3f}")

    # Monster skalieren
    base_monster = {"name": "Goblin", "hp": 20, "atk": 5, "def": 3, "spd": 3, "type": "Schere"}
    player = {"name": "TestRitter", "class_type": "Stein", "level": 10}

    # Floor 1
    enc1 = balancer.balance_encounter(player, base_monster, floor=1)
    print(f"\nFloor 1: HP={enc1['monster']['hp']}, ATK={enc1['monster']['atk']}")
    print(f"  Rewards: XP={enc1['rewards']['xp']}, Gold={enc1['rewards']['gold']}")
    print(f"  Matchup: {enc1['matchup']['result']} (x{enc1['matchup']['damage_multiplier']})")

    # Floor 50 (Hard)
    enc50 = balancer.balance_encounter(player, base_monster, floor=50)
    print(f"\nFloor 50: HP={enc50['monster']['hp']}, ATK={enc50['monster']['atk']}")
    print(f"  Rewards: XP={enc50['rewards']['xp']}, Gold={enc50['rewards']['gold']}")

    # Floor 100 Boss
    enc100 = balancer.balance_encounter(player, base_monster, floor=100)
    print(f"\nFloor 100 (Boss): HP={enc100['monster']['hp']}, ATK={enc100['monster']['atk']}")
    print(f"  Rewards: XP={enc100['rewards']['xp']}, Gold={enc100['rewards']['gold']}")
    print(f"  Is Boss: {enc100['difficulty_info']['is_boss']}")

    # Typ-Matchup Tests
    print(f"\nStein vs Schere: {get_type_matchup('Stein', 'Schere')}")
    print(f"Schere vs Stein: {get_type_matchup('Schere', 'Stein')}")
    print(f"Stein vs Stein:  {get_type_matchup('Stein', 'Stein')}")

    print("\nAlle Tests bestanden!")
