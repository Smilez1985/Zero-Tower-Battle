#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Champion-Psyche-System
==================================================
Verwaltet Erschoepfung, Moral und Trauma des Champions.

Design-Philosophie: MILD, NICHT BESTRAFEND.
  - Kein harter Stat-Nerf (ATK/DEF/SPD/LUK bleiben unberuehrt)
  - Nur Loot/XP-Reduktion als Debuff
  - Bei 100% Erschoepfung: 1h Tower-Pause, dann automatisch auf 80%
  - PVP bleibt IMMER moeglich (auch bei 100%)
  - Trauma = narrativer Flavour + leichter Loot-Malus

Erschoepfung (0-100%):
  - +2 pro Turm-Kampf
  - -5 pro 90s PVE-Cooldown (passive Regeneration)
  - Reset bei 8h Idle ("Schlaf")
  - 0-49%:  Kein Effekt
  - 50-74%: -10% Loot-Chance
  - 75-89%: -10% Loot + -15% XP
  - 90-99%: -10% Loot + -15% XP + -10% Gold
  - 100%:   PVE-Tower pausiert fuer max 1h, dann -> 80%

Moral (0-100%):
  - +25 pro SSH-Login (mit 1h Cooldown zwischen Boni)
  - +2 pro PVP-Sieg
  - Ueber 80%: +5% Crit-Chance
  - Unter 30%: -5% Crit-Chance

Trauma:
  - Entsteht bei <10% HP Ueberleben
  - -5% Loot-Chance gegen den verursachenden Monster-Typ
  - Heilt nach 10 Siegen gegen diesen Typ
  - Rein narrativ im Kampf-Log

Referenz: Battle-Pi_Konsolidiert.txt Abschnitt 4D
"""

import time
from typing import Dict, Any, Optional, List


# =============================================
# Konstanten
# =============================================

# Erschoepfung
EXHAUSTION_PER_TOWER_FIGHT = 2.0     # +2% pro Turm-Kampf
EXHAUSTION_REGEN_PER_COOLDOWN = 5.0  # -5% pro 90s PVE-Cooldown
EXHAUSTION_SLEEP_HOURS = 8           # 8h Idle = komplett Reset
EXHAUSTION_PAUSE_DURATION = 3600     # 1h Pause bei 100% (Sekunden)
EXHAUSTION_AFTER_PAUSE = 80.0        # Nach Pause -> 80%

# Erschoepfungs-Schwellen (Debuffs)
EXHAUSTION_THRESHOLDS = {
    50.0: {"loot_malus": 0.10, "xp_malus": 0.00, "gold_malus": 0.00},
    75.0: {"loot_malus": 0.10, "xp_malus": 0.15, "gold_malus": 0.00},
    90.0: {"loot_malus": 0.10, "xp_malus": 0.15, "gold_malus": 0.10},
}

# Moral
MORALE_LOGIN_BONUS = 25.0       # +25% pro SSH-Login
MORALE_LOGIN_COOLDOWN = 3600    # 1h Cooldown zwischen Login-Boni (Sekunden)
MORALE_PVP_WIN_BONUS = 2.0      # +2% pro PVP-Sieg
MORALE_PVP_LOSS_PENALTY = 1.0   # -1% pro PVP-Niederlage
MORALE_CRIT_HIGH_THRESHOLD = 80.0   # Ueber 80%: +5% Crit
MORALE_CRIT_LOW_THRESHOLD = 30.0    # Unter 30%: -5% Crit
MORALE_CRIT_BONUS = 0.05        # +5% Crit-Chance
MORALE_CRIT_PENALTY = 0.05      # -5% Crit-Chance
MORALE_DAILY_DECAY = 2.0        # -2% pro Tag ohne Login

# Trauma
TRAUMA_HP_THRESHOLD = 0.10      # Unter 10% HP -> Trauma
TRAUMA_LOOT_MALUS = 0.05        # -5% Loot gegen Trauma-Typ
TRAUMA_HEAL_VICTORIES = 10      # 10 Siege gegen Typ = geheilt


# =============================================
# Champion-Psyche-Manager
# =============================================

class ChampionPsyche:
    """
    Verwaltet den psychischen Zustand des Champions.

    Alle Werte werden im Charakter-Dict gespeichert,
    dieses Modul liest und schreibt darauf.
    """

    def __init__(self):
        self._pause_start_time = None  # Zeitpunkt der Erschoepfungs-Pause
        self._last_login_bonus_time = 0.0  # Letzter Login-Bonus Zeitstempel
        self._character = None  # Referenz auf das Charakter-Dict

    def load_from_character(self, character: Dict[str, Any]) -> None:
        """
        Charakter-Dict laden und internen Zustand initialisieren.

        Wird beim Start vom Orchestrator und GameInitializer aufgerufen.
        Stellt sicher, dass alle Psyche-Felder im Character-Dict vorhanden sind.

        Args:
            character: Das Charakter-Dict mit exhaustion, morale, trauma Feldern
        """
        self._character = character

        # Sicherstellen dass alle Psyche-Felder existieren (Defaults setzen)
        character.setdefault("exhaustion", 0.0)
        character.setdefault("morale", 100.0)
        character.setdefault("trauma", [])

        # Pause-Zustand wiederherstellen falls Erschoepfung >= 100
        if character.get("exhaustion", 0) >= 100.0:
            if self._pause_start_time is None:
                self._pause_start_time = time.time()

    # -----------------------------------------
    # Erschoepfung
    # -----------------------------------------

    def add_exhaustion(self, character: Dict[str, Any], amount: float = None) -> Dict[str, Any]:
        """
        Erschoepfung erhoehen (nach Turm-Kampf).

        Args:
            character: Charakter-Dict
            amount: Erschoepfungs-Punkte (default: 2.0)

        Returns:
            Dict mit new_exhaustion, debuffs, paused
        """
        if amount is None:
            amount = EXHAUSTION_PER_TOWER_FIGHT

        current = character.get("exhaustion", 0.0)
        new_value = min(100.0, current + amount)
        character["exhaustion"] = new_value

        # Bei 100%: Pause starten
        paused = False
        if new_value >= 100.0 and self._pause_start_time is None:
            self._pause_start_time = time.time()
            paused = True

        debuffs = self.get_exhaustion_debuffs(character)

        return {
            "previous": current,
            "new_exhaustion": new_value,
            "debuffs": debuffs,
            "paused": paused,
            "pause_remaining": self.get_pause_remaining()
        }

    def regenerate_exhaustion(self, character: Dict[str, Any], amount: float = None) -> Dict[str, Any]:
        """
        Erschoepfung reduzieren (waehrend PVE-Cooldown).

        Args:
            character: Charakter-Dict
            amount: Regeneration (default: 5.0 pro Cooldown)

        Returns:
            Dict mit new_exhaustion
        """
        if amount is None:
            amount = EXHAUSTION_REGEN_PER_COOLDOWN

        current = character.get("exhaustion", 0.0)
        new_value = max(0.0, current - amount)
        character["exhaustion"] = new_value

        return {
            "previous": current,
            "new_exhaustion": new_value,
            "regenerated": current - new_value
        }

    def check_tower_allowed(self, character: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pruefen ob der Tower-Climb erlaubt ist.

        Bei 100% Erschoepfung: 1h Pause.
        Nach 1h automatisch auf 80% und weiter.
        PVP ist IMMER erlaubt.

        Returns:
            Dict mit allowed, reason, pause_remaining
        """
        exhaustion = character.get("exhaustion", 0.0)

        if exhaustion < 100.0:
            # Pause beenden falls aktiv
            self._pause_start_time = None
            return {
                "allowed": True,
                "reason": None,
                "pause_remaining": 0
            }

        # 100% Erschoepfung: Pause pruefen
        remaining = self.get_pause_remaining()

        if remaining <= 0:
            # Pause abgelaufen -> auf 80% setzen und weitermachen
            character["exhaustion"] = EXHAUSTION_AFTER_PAUSE
            self._pause_start_time = None
            return {
                "allowed": True,
                "reason": "Pause beendet. Champion hat sich erholt (80%).",
                "pause_remaining": 0
            }

        # Noch in der Pause
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        return {
            "allowed": False,
            "reason": (
                f"Champion ist erschoepft! "
                f"Noch {minutes}m {seconds}s bis zur Erholung."
            ),
            "pause_remaining": remaining
        }

    def get_pause_remaining(self) -> float:
        """Verbleibende Pause-Zeit in Sekunden."""
        if self._pause_start_time is None:
            return 0.0
        elapsed = time.time() - self._pause_start_time
        remaining = max(0.0, EXHAUSTION_PAUSE_DURATION - elapsed)
        return remaining

    def get_exhaustion_debuffs(self, character: Dict[str, Any]) -> Dict[str, float]:
        """
        Aktuelle Debuffs basierend auf Erschoepfung.

        Gibt Multiplikatoren zurueck:
        - loot_multiplier: 1.0 = normal, 0.9 = -10%
        - xp_multiplier: 1.0 = normal, 0.85 = -15%
        - gold_multiplier: 1.0 = normal, 0.9 = -10%

        Diese werden von rewards.py angewendet.
        """
        exhaustion = character.get("exhaustion", 0.0)

        loot_malus = 0.0
        xp_malus = 0.0
        gold_malus = 0.0

        for threshold, debuffs in sorted(EXHAUSTION_THRESHOLDS.items()):
            if exhaustion >= threshold:
                loot_malus = debuffs["loot_malus"]
                xp_malus = debuffs["xp_malus"]
                gold_malus = debuffs["gold_malus"]

        return {
            "exhaustion": exhaustion,
            "loot_multiplier": 1.0 - loot_malus,
            "xp_multiplier": 1.0 - xp_malus,
            "gold_multiplier": 1.0 - gold_malus,
            "has_debuff": loot_malus > 0 or xp_malus > 0 or gold_malus > 0
        }

    def sleep_reset(self, character: Dict[str, Any]) -> Dict[str, Any]:
        """
        Voller Erschoepfungs-Reset (8h Idle / Schlafmodus).

        Wird aufgerufen wenn der Pi 8h+ ohne Tower-Kampf war.
        """
        old_value = character.get("exhaustion", 0.0)
        character["exhaustion"] = 0.0
        self._pause_start_time = None

        return {
            "previous": old_value,
            "new_exhaustion": 0.0,
            "message": "Champion hat geschlafen. Volle Energie!"
        }

    # -----------------------------------------
    # Moral
    # -----------------------------------------

    def add_morale(self, character: Dict[str, Any], amount: float) -> Dict[str, Any]:
        """
        Moral erhoehen (Login, PVP-Sieg, etc.).

        Args:
            character: Charakter-Dict
            amount: Moral-Punkte
        """
        current = character.get("morale", 100.0)
        new_value = min(100.0, max(0.0, current + amount))
        character["morale"] = new_value

        return {
            "previous": current,
            "new_morale": new_value,
            "crit_bonus": self.get_crit_modifier(character)
        }

    def on_login(self, character: Dict[str, Any]) -> Dict[str, Any]:
        """
        SSH-Login-Bonus: +25% Moral mit 1h Cooldown.
        Kann nur alle 60 Minuten ausgeloest werden.
        """
        now = time.time()
        elapsed = now - self._last_login_bonus_time
        cooldown_remaining = max(0.0, MORALE_LOGIN_COOLDOWN - elapsed)

        if cooldown_remaining > 0:
            minutes = int(cooldown_remaining // 60)
            return {
                "previous": character.get("morale", 100.0),
                "new_morale": character.get("morale", 100.0),
                "crit_bonus": self.get_crit_modifier(character),
                "bonus_applied": False,
                "cooldown_remaining": cooldown_remaining,
                "message": f"Login-Bonus auf Cooldown (noch {minutes}m)."
            }

        self._last_login_bonus_time = now
        result = self.add_morale(character, MORALE_LOGIN_BONUS)
        result["bonus_applied"] = True
        result["cooldown_remaining"] = MORALE_LOGIN_COOLDOWN
        result["message"] = f"Login-Bonus! +{MORALE_LOGIN_BONUS:.0f}% Moral."
        return result

    def on_pvp_win(self, character: Dict[str, Any]) -> Dict[str, Any]:
        """PVP-Sieg: +2 Moral."""
        return self.add_morale(character, MORALE_PVP_WIN_BONUS)

    def on_pvp_loss(self, character: Dict[str, Any]) -> Dict[str, Any]:
        """PVP-Niederlage: -1 Moral."""
        return self.add_morale(character, -MORALE_PVP_LOSS_PENALTY)

    def apply_daily_decay(self, character: Dict[str, Any]) -> Dict[str, Any]:
        """Taeglicher Moral-Verfall wenn kein Login."""
        return self.add_morale(character, -MORALE_DAILY_DECAY)

    def get_crit_modifier(self, character: Dict[str, Any]) -> float:
        """
        Crit-Chance-Modifikator basierend auf Moral.

        - Ueber 80%: +5% Crit-Chance (return 0.05)
        - Unter 30%: -5% Crit-Chance (return -0.05)
        - Sonst: 0.0 (neutral)
        """
        morale = character.get("morale", 100.0)
        if morale >= MORALE_CRIT_HIGH_THRESHOLD:
            return MORALE_CRIT_BONUS
        elif morale <= MORALE_CRIT_LOW_THRESHOLD:
            return -MORALE_CRIT_PENALTY
        return 0.0

    # -----------------------------------------
    # Trauma (mild, narrativ)
    # -----------------------------------------

    def check_trauma(
        self,
        character: Dict[str, Any],
        remaining_hp: int,
        max_hp: int,
        enemy_type: str
    ) -> Dict[str, Any]:
        """
        Pruefen ob der Kampf ein Trauma ausloest.

        Trauma entsteht bei <10% HP Ueberleben.
        Effekt: -5% Loot-Chance gegen diesen Monster-Typ.
        Heilt nach 10 Siegen gegen den Typ.

        Args:
            character: Charakter-Dict
            remaining_hp: Verbleibende HP nach Kampf
            max_hp: Maximale HP
            enemy_type: Monster-Typ (z.B. "Drache", "Ork")

        Returns:
            Dict mit trauma_triggered, trauma_info
        """
        hp_ratio = remaining_hp / max(1, max_hp)

        if hp_ratio >= TRAUMA_HP_THRESHOLD:
            return {"trauma_triggered": False}

        # Trauma ausloesen
        traumas = character.get("trauma", [])

        # Pruefen ob Trauma gegen diesen Typ schon existiert
        for t in traumas:
            if t["enemy_type"] == enemy_type:
                # Schon vorhanden -> Zaehler zuruecksetzen
                t["victories_to_heal"] = TRAUMA_HEAL_VICTORIES
                return {
                    "trauma_triggered": True,
                    "new_trauma": False,
                    "message": f"Das Trauma gegen {enemy_type} wurde verstaerkt!"
                }

        # Neues Trauma
        trauma_entry = {
            "enemy_type": enemy_type,
            "loot_malus": TRAUMA_LOOT_MALUS,
            "victories_to_heal": TRAUMA_HEAL_VICTORIES,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "narrative": f"Dein Champion zittert beim Anblick von {enemy_type}n."
        }
        traumas.append(trauma_entry)
        character["trauma"] = traumas

        return {
            "trauma_triggered": True,
            "new_trauma": True,
            "trauma": trauma_entry,
            "message": (
                f"TRAUMA! Knapp ueberlebt ({remaining_hp} HP). "
                f"Dein Champion hat nun Angst vor {enemy_type}n. "
                f"(-5% Loot, heilt nach 10 Siegen)"
            )
        }

    def process_victory_against_type(
        self,
        character: Dict[str, Any],
        enemy_type: str
    ) -> Dict[str, Any]:
        """
        Sieg gegen einen Monster-Typ verarbeiten.
        Reduziert Trauma-Zaehler, heilt bei 0.

        Args:
            character: Charakter-Dict
            enemy_type: Besiegter Monster-Typ

        Returns:
            Dict mit healed, remaining
        """
        traumas = character.get("trauma", [])
        healed = False
        message = None

        for i, t in enumerate(traumas):
            if t["enemy_type"] == enemy_type:
                t["victories_to_heal"] -= 1
                if t["victories_to_heal"] <= 0:
                    traumas.pop(i)
                    healed = True
                    message = (
                        f"TRAUMA GEHEILT! Dein Champion hat die Angst "
                        f"vor {enemy_type}n ueberwunden!"
                    )
                else:
                    remaining = t["victories_to_heal"]
                    message = (
                        f"Trauma wird schwaecher... "
                        f"Noch {remaining} Siege gegen {enemy_type} noetig."
                    )
                break

        character["trauma"] = traumas

        return {
            "healed": healed,
            "message": message,
            "active_traumas": len(traumas)
        }

    def get_trauma_loot_malus(
        self,
        character: Dict[str, Any],
        enemy_type: str
    ) -> float:
        """
        Trauma-bedingten Loot-Malus fuer einen Monster-Typ holen.

        Returns:
            Malus als float (z.B. 0.05 = -5% Loot)
        """
        traumas = character.get("trauma", [])
        for t in traumas:
            if t["enemy_type"] == enemy_type:
                return t.get("loot_malus", TRAUMA_LOOT_MALUS)
        return 0.0

    def get_active_traumas(self, character: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Alle aktiven Traumas auflisten."""
        return character.get("trauma", [])

    # -----------------------------------------
    # Gesamt-Status
    # -----------------------------------------

    def get_full_status(self, character: Dict[str, Any]) -> Dict[str, Any]:
        """
        Vollstaendiger Psyche-Status des Champions.

        Wird vom Dashboard und Orchestrator genutzt.
        """
        exhaustion = character.get("exhaustion", 0.0)
        morale = character.get("morale", 100.0)
        traumas = character.get("trauma", [])

        debuffs = self.get_exhaustion_debuffs(character)
        tower_check = self.check_tower_allowed(character)
        crit_mod = self.get_crit_modifier(character)

        # Gesamtzustand beschreiben
        if exhaustion < 25:
            mood = "Energiegeladen"
            mood_en = "Energized"
        elif exhaustion < 50:
            mood = "Wach"
            mood_en = "Alert"
        elif exhaustion < 75:
            mood = "Muede"
            mood_en = "Tired"
        elif exhaustion < 100:
            mood = "Erschoepft"
            mood_en = "Exhausted"
        else:
            mood = "Am Schlafen"
            mood_en = "Sleeping"

        return {
            "exhaustion": round(exhaustion, 1),
            "morale": round(morale, 1),
            "mood_de": mood,
            "mood_en": mood_en,
            "tower_allowed": tower_check["allowed"],
            "tower_pause_remaining": tower_check.get("pause_remaining", 0),
            "crit_modifier": crit_mod,
            "debuffs": debuffs,
            "active_traumas": len(traumas),
            "traumas": [
                {
                    "enemy_type": t["enemy_type"],
                    "victories_remaining": t["victories_to_heal"],
                    "narrative": t.get("narrative", "")
                }
                for t in traumas
            ]
        }

    # -----------------------------------------
    # Reward-Modifikatoren anwenden
    # -----------------------------------------

    def apply_psyche_modifiers(
        self,
        character: Dict[str, Any],
        rewards: Dict[str, Any],
        enemy_type: str = None
    ) -> Dict[str, Any]:
        """
        Psyche-Debuffs auf Belohnungen anwenden.

        Wird von rewards.py / hybrid_orchestrator.py aufgerufen
        NACH der Basis-Belohnungsberechnung.

        Args:
            character: Charakter-Dict
            rewards: Rewards-Dict (aus RewardCalculator)
            enemy_type: Monster-Typ (fuer Trauma-Check)

        Returns:
            Modifiziertes Rewards-Dict
        """
        debuffs = self.get_exhaustion_debuffs(character)

        # Erschoepfungs-Malus anwenden
        if debuffs["has_debuff"]:
            original_gold = rewards.get("gold", 0)
            original_exp = rewards.get("exp", 0)

            rewards["gold"] = int(original_gold * debuffs["gold_multiplier"])
            rewards["exp"] = int(original_exp * debuffs["xp_multiplier"])
            rewards["_exhaustion_applied"] = True
            rewards["_gold_before_debuff"] = original_gold
            rewards["_exp_before_debuff"] = original_exp

        # Trauma-Malus auf Loot-Chance (wird extern geprueft)
        if enemy_type:
            trauma_malus = self.get_trauma_loot_malus(character, enemy_type)
            if trauma_malus > 0:
                rewards["_trauma_loot_malus"] = trauma_malus
                rewards["_trauma_type"] = enemy_type

        return rewards


# =============================================
# Standalone-Test
# =============================================
if __name__ == "__main__":
    psyche = ChampionPsyche()

    # Test-Charakter
    char = {
        "name": "TestHeld",
        "exhaustion": 0.0,
        "morale": 100.0,
        "trauma": [],
        "hp": 100,
        "max_hp": 100
    }

    print("=== ERSCHOEPFUNG ===")
    for i in range(55):
        result = psyche.add_exhaustion(char)
    print(f"  Nach 55 Kaempfen: {char['exhaustion']}%")
    debuffs = psyche.get_exhaustion_debuffs(char)
    print(f"  Debuffs: Loot x{debuffs['loot_multiplier']}, "
          f"XP x{debuffs['xp_multiplier']}, Gold x{debuffs['gold_multiplier']}")

    # Regeneration
    for _ in range(5):
        psyche.regenerate_exhaustion(char)
    print(f"  Nach 5x Cooldown-Regen: {char['exhaustion']}%")

    # 100% Test
    char["exhaustion"] = 100.0
    tower = psyche.check_tower_allowed(char)
    print(f"\n  100% Erschoepfung:")
    print(f"    Tower erlaubt: {tower['allowed']}")
    print(f"    Grund: {tower['reason']}")
    print(f"    Pause: {tower['pause_remaining']:.0f}s")

    # Schlaf-Reset
    result = psyche.sleep_reset(char)
    print(f"  Nach Schlaf-Reset: {char['exhaustion']}%")

    print("\n=== MORAL ===")
    char["morale"] = 70.0
    psyche.on_login(char)
    print(f"  Nach Login: Moral={char['morale']}%")
    psyche.on_pvp_win(char)
    print(f"  Nach PVP-Sieg: Moral={char['morale']}%")
    crit = psyche.get_crit_modifier(char)
    print(f"  Crit-Modifier: {crit:+.0%}")

    char["morale"] = 85.0
    crit = psyche.get_crit_modifier(char)
    print(f"  Bei 85% Moral: Crit-Modifier: {crit:+.0%}")

    char["morale"] = 20.0
    crit = psyche.get_crit_modifier(char)
    print(f"  Bei 20% Moral: Crit-Modifier: {crit:+.0%}")

    print("\n=== TRAUMA ===")
    char["morale"] = 80.0
    char["trauma"] = []

    # Trauma ausloesen (8 HP von 100)
    result = psyche.check_trauma(char, remaining_hp=8, max_hp=100, enemy_type="Drache")
    print(f"  Trauma ausgeloest: {result['trauma_triggered']}")
    if result.get("message"):
        print(f"  {result['message']}")

    # Siege gegen Drachen
    for i in range(1, 12):
        heal = psyche.process_victory_against_type(char, "Drache")
        if heal["healed"]:
            print(f"  Sieg {i}: {heal['message']}")
            break
        elif i % 3 == 0:
            print(f"  Sieg {i}: {heal['message']}")

    print(f"\n=== GESAMT-STATUS ===")
    char["exhaustion"] = 45.0
    char["morale"] = 85.0
    status = psyche.get_full_status(char)
    print(f"  Stimmung: {status['mood_de']}")
    print(f"  Erschoepfung: {status['exhaustion']}%")
    print(f"  Moral: {status['morale']}%")
    print(f"  Tower erlaubt: {status['tower_allowed']}")
    print(f"  Crit-Modifier: {status['crit_modifier']:+.0%}")
    print(f"  Aktive Traumas: {status['active_traumas']}")
