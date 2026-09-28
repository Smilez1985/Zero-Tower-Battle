#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Level-Up System
==========================================

Level-Up Progression:
  - Alle 500 EXP -> Level-Up
  - +5 Bonuspunkte pro Level (frei verteilbar)
  - Max 50 Bonuspunkte pro Stat
  - Basis-Stats (100-Punkte-Gesetz) bleiben unveraendert
"""

from typing import Dict, Any, List, Optional


class LevelUp:
    """
    Level-Up System mit interaktiver Bonuspunkt-Verteilung.

    Regeln:
      - 500 EXP pro Level
      - +5 Bonuspunkte pro Level-Up
      - Max 50 Extra-Punkte pro Stat
      - Basis-Stats (ATK/DEF/SPD/LUK = 100) aendern sich NIE
    """

    XP_PER_LEVEL = 500
    BONUS_PER_LEVEL = 5
    MAX_BONUS_PER_STAT = 50
    STAT_NAMES = ["ATK", "DEF", "SPD", "LUK"]

    def __init__(self):
        pass

    def check_level_up(self, character: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pruefe ob Level-Up moeglich ist.

        Args:
            character: Charakter-Dict mit xp, level

        Returns:
            Dict mit: can_level_up, xp_current, xp_needed, xp_remaining
        """
        xp = character.get("xp", 0)
        level = character.get("level", 1)
        xp_needed = self.XP_PER_LEVEL

        return {
            "can_level_up": xp >= xp_needed,
            "xp_current": xp,
            "xp_needed": xp_needed,
            "xp_remaining": max(0, xp_needed - xp),
            "current_level": level
        }

    def perform_level_up(self, character: Dict[str, Any],
                         distribution: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        """
        Level-Up durchfuehren mit Bonuspunkt-Verteilung.

        Args:
            character: Charakter-Dict
            distribution: Dict mit Stat-Verteilung, z.B. {"ATK": 3, "SPD": 2}
                          Wenn None: gleichmaessige Verteilung

        Returns:
            Dict mit: result, new_level, bonus_applied, message
        """
        check = self.check_level_up(character)
        if not check["can_level_up"]:
            return {
                "result": "INSUFFICIENT_XP",
                "message": f"Noch {check['xp_remaining']} EXP noetig",
                "level_up": False
            }

        # XP abziehen
        character["xp"] = character.get("xp", 0) - self.XP_PER_LEVEL
        old_level = character.get("level", 1)
        new_level = old_level + 1
        character["level"] = new_level

        # Bonuspunkte verteilen
        bonus = self.BONUS_PER_LEVEL
        if distribution is None:
            distribution = self._auto_distribute(character, bonus)
        else:
            # Validiere manuelle Verteilung
            validation = self._validate_distribution(character, distribution, bonus)
            if validation["result"] != "VALID":
                # Fallback auf Auto-Verteilung
                distribution = self._auto_distribute(character, bonus)

        # Bonuspunkte anwenden
        applied = {}
        for stat_name, points in distribution.items():
            if points > 0:
                key = f"extra_{stat_name.lower()}"
                old_val = character.get(key, 0)
                new_val = min(self.MAX_BONUS_PER_STAT, old_val + points)
                actually_added = new_val - old_val
                character[key] = new_val
                if actually_added > 0:
                    applied[stat_name] = actually_added

        # Bell-Audio
        print("\a", end="", flush=True)

        return {
            "result": "SUCCESS",
            "level_up": True,
            "old_level": old_level,
            "new_level": new_level,
            "bonus_applied": applied,
            "total_bonus": bonus,
            "message": f"Level-Up! Lv.{old_level} -> Lv.{new_level} (+{bonus} Bonuspunkte)"
        }

    def _auto_distribute(self, character: Dict[str, Any], bonus: int) -> Dict[str, int]:
        """
        Gleichmaessige Bonuspunkt-Verteilung.
        Ueberspringt Stats die bereits am Max sind.
        """
        distribution = {}
        available_stats = []

        for stat in self.STAT_NAMES:
            key = f"extra_{stat.lower()}"
            current = character.get(key, 0)
            if current < self.MAX_BONUS_PER_STAT:
                available_stats.append(stat)
            distribution[stat] = 0

        if not available_stats:
            return distribution

        remaining = bonus
        idx = 0
        while remaining > 0 and available_stats:
            stat = available_stats[idx % len(available_stats)]
            key = f"extra_{stat.lower()}"
            current = character.get(key, 0) + distribution[stat]
            if current < self.MAX_BONUS_PER_STAT:
                distribution[stat] += 1
                remaining -= 1
            else:
                available_stats.remove(stat)
                if not available_stats:
                    break
                continue
            idx += 1

        return distribution

    def _validate_distribution(self, character: Dict[str, Any],
                               distribution: Dict[str, int],
                               bonus: int) -> Dict[str, Any]:
        """
        Manuelle Verteilung validieren.

        Returns:
            Dict mit: result, message
        """
        total = sum(distribution.values())
        if total != bonus:
            return {
                "result": "INVALID",
                "message": f"Summe {total} != {bonus} Bonuspunkte"
            }

        for stat_name, points in distribution.items():
            if points < 0:
                return {
                    "result": "INVALID",
                    "message": f"{stat_name}: Negative Punkte nicht erlaubt"
                }
            key = f"extra_{stat_name.lower()}"
            current = character.get(key, 0)
            if current + points > self.MAX_BONUS_PER_STAT:
                return {
                    "result": "INVALID",
                    "message": f"{stat_name}: Max {self.MAX_BONUS_PER_STAT} Extra (aktuell {current})"
                }

        return {"result": "VALID"}

    def get_pending_points(self, character: Dict[str, Any]) -> int:
        """
        Anzahl wartender Bonuspunkte abfragen.

        Args:
            character: Charakter-Dict

        Returns:
            Anzahl unverteilter Bonuspunkte
        """
        return character.get("pending_bonus_points", 0)

    def apply_pending_points(self, character: Dict[str, Any],
                             distribution: Dict[str, int]) -> Dict[str, Any]:
        """
        Wartende Bonuspunkte manuell verteilen (War Room).

        Der Spieler waehlt selbst wie viele Punkte auf welchen
        Stat verteilt werden. Teilweise Verteilung ist erlaubt
        (Rest bleibt als pending erhalten).

        Args:
            character: Charakter-Dict
            distribution: Dict z.B. {"ATK": 3, "SPD": 2}

        Returns:
            Dict mit: result, applied, remaining_pending, message
        """
        pending = character.get("pending_bonus_points", 0)
        if pending <= 0:
            return {
                "result": "NO_POINTS",
                "message": "Keine Bonuspunkte zum Verteilen verfuegbar.",
                "remaining_pending": 0
            }

        total_requested = sum(distribution.values())
        if total_requested <= 0:
            return {
                "result": "NOTHING_SELECTED",
                "message": "Keine Punkte ausgewaehlt.",
                "remaining_pending": pending
            }

        if total_requested > pending:
            return {
                "result": "TOO_MANY",
                "message": f"Nur {pending} Punkte verfuegbar, "
                           f"aber {total_requested} angefordert.",
                "remaining_pending": pending
            }

        # Validierung: keine negativen Werte, kein Max-Ueberschreitung
        for stat_name, points in distribution.items():
            if stat_name not in self.STAT_NAMES:
                return {
                    "result": "INVALID_STAT",
                    "message": f"Unbekannter Stat: {stat_name}. "
                               f"Erlaubt: {', '.join(self.STAT_NAMES)}",
                    "remaining_pending": pending
                }
            if points < 0:
                return {
                    "result": "NEGATIVE",
                    "message": f"{stat_name}: Negative Punkte nicht erlaubt.",
                    "remaining_pending": pending
                }
            key = f"extra_{stat_name.lower()}"
            current = character.get(key, 0)
            if current + points > self.MAX_BONUS_PER_STAT:
                return {
                    "result": "STAT_MAXED",
                    "message": f"{stat_name}: Max {self.MAX_BONUS_PER_STAT} Extra "
                               f"(aktuell {current}, +{points} = {current + points}).",
                    "remaining_pending": pending
                }

        # Punkte anwenden
        applied = {}
        for stat_name, points in distribution.items():
            if points > 0:
                key = f"extra_{stat_name.lower()}"
                old_val = character.get(key, 0)
                character[key] = old_val + points
                applied[stat_name] = points

        # Pending aktualisieren
        character["pending_bonus_points"] = pending - total_requested

        # Bell
        print("\a", end="", flush=True)

        applied_str = ", ".join(f"{k}+{v}" for k, v in applied.items() if v > 0)
        remaining = character["pending_bonus_points"]

        return {
            "result": "SUCCESS",
            "applied": applied,
            "total_applied": total_requested,
            "remaining_pending": remaining,
            "message": f"Verteilt: {applied_str}. "
                       f"Noch {remaining} Punkte wartend."
        }

    def get_bonus_overview(self, character: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uebersicht aller Bonuspunkte.

        Returns:
            Dict mit Stats und deren Bonus-Verteilung
        """
        overview = {}
        total_extra = 0

        for stat in self.STAT_NAMES:
            base_key = f"base_{stat.lower()}"
            extra_key = f"extra_{stat.lower()}"
            base = character.get(base_key, 0)
            extra = character.get(extra_key, 0)
            total_extra += extra
            overview[stat] = {
                "base": base,
                "extra": extra,
                "total": base + extra,
                "max_extra": self.MAX_BONUS_PER_STAT,
                "remaining": self.MAX_BONUS_PER_STAT - extra
            }

        return {
            "stats": overview,
            "total_extra_used": total_extra,
            "level": character.get("level", 1)
        }

    def get_interactive_prompt(self, character: Dict[str, Any],
                               bonus: int) -> str:
        """
        Interaktives Prompt fuer SSH-Menue.

        Returns:
            Formatierter String fuer Terminal-Anzeige
        """
        lines = []
        lines.append("=" * 50)
        lines.append(f"  LEVEL-UP! +{bonus} Bonuspunkte verteilen")
        lines.append("=" * 50)

        for stat in self.STAT_NAMES:
            base_key = f"base_{stat.lower()}"
            extra_key = f"extra_{stat.lower()}"
            base = character.get(base_key, 0)
            extra = character.get(extra_key, 0)
            remaining = self.MAX_BONUS_PER_STAT - extra
            bar = "#" * min(20, extra) + "." * min(20, remaining)
            lines.append(f"  {stat:3s}: {base:2d} + {extra:2d} = {base + extra:3d}  [{bar}]")

        lines.append("")
        lines.append(f"  Verfuegbar: {bonus} Punkte")
        lines.append("  Format: ATK=2,SPD=3  (Summe muss {bonus} sein)")
        lines.append("  Oder ENTER fuer gleichmaessige Verteilung")
        lines.append("=" * 50)

        return "\n".join(lines)

    def parse_distribution_input(self, user_input: str,
                                 bonus: int) -> Optional[Dict[str, int]]:
        """
        Benutzereingabe parsen.
        Format: "ATK=2,SPD=3" oder "" fuer Auto.

        Returns:
            Dict mit Verteilung oder None fuer Auto
        """
        user_input = user_input.strip()
        if not user_input:
            return None

        distribution = {stat: 0 for stat in self.STAT_NAMES}

        try:
            parts = user_input.upper().replace(" ", "").split(",")
            for part in parts:
                if "=" not in part:
                    return None
                stat_name, value_str = part.split("=", 1)
                stat_name = stat_name.strip()
                if stat_name not in self.STAT_NAMES:
                    return None
                distribution[stat_name] = int(value_str.strip())

            if sum(distribution.values()) != bonus:
                return None

            return distribution

        except (ValueError, KeyError):
            return None


if __name__ == "__main__":
    levelup = LevelUp()

    # Test-Charakter
    char = {
        "name": "TestHeld",
        "level": 1,
        "xp": 600,
        "base_atk": 25, "base_def": 40, "base_spd": 20, "base_luk": 15,
        "extra_atk": 0, "extra_def": 0, "extra_spd": 0, "extra_luk": 0
    }

    check = levelup.check_level_up(char)
    print(f"Level-Up moeglich: {check['can_level_up']}")

    result = levelup.perform_level_up(char)
    print(f"Ergebnis: {result['message']}")
    print(f"Bonus: {result.get('bonus_applied', {})}")
    print(f"Level: {char['level']}, XP: {char['xp']}")
