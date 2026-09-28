#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Battle Visualizer
=============================================
Kampf-Replay mit ASCII-HP-Balken fuer SSH-Terminal.

Features:
  - HP-Balken (ASCII, 20 Zeichen breit)
  - Runden-Replay mit Schadens-Anzeige
  - Krit-Hervorhebung
  - Typ-Vorteil-Anzeige
  - Shiny-Indikator
  - Zusammenfassung am Ende

Kein Rich-Dependency noetig (laeuft auf purem Terminal).
Optional: Rich-HP-Balken wenn verfuegbar.

Referenz: Battle-Pi_Konsolidiert.txt Abschnitt 7
"""

import time
from typing import Dict, Any, List, Optional


# =============================================
# Konstanten
# =============================================

BAR_WIDTH = 20           # Breite des HP-Balkens in Zeichen
REPLAY_DELAY = 0.3       # Sekunden zwischen Runden (0 = sofort)
CRIT_SYMBOL = "!!"       # Krit-Anzeige
TYPE_ADV_SYMBOL = ">>>"  # Typ-Vorteil
TYPE_DIS_SYMBOL = "<<<"  # Typ-Nachteil


# =============================================
# HP-Balken (ASCII)
# =============================================

def hp_bar(current: int, maximum: int, width: int = BAR_WIDTH) -> str:
    """
    ASCII-HP-Balken erzeugen.

    Beispiel: [################    ] 80/100

    Args:
        current: Aktuelle HP
        maximum: Maximale HP
        width: Balkenbreite in Zeichen

    Returns:
        Formatierter HP-Balken als String
    """
    if maximum <= 0:
        maximum = 1
    current = max(0, min(current, maximum))

    filled = int((current / maximum) * width)
    empty = width - filled

    # Farblose Variante (Terminal-kompatibel)
    bar = "#" * filled + " " * empty

    return f"[{bar}] {current}/{maximum}"


def hp_bar_rich(current: int, maximum: int, width: int = BAR_WIDTH) -> str:
    """
    HP-Balken mit ANSI-Farben (optional).
    Gruen (>50%), Gelb (25-50%), Rot (<25%).

    Args:
        current: Aktuelle HP
        maximum: Maximale HP
        width: Balkenbreite

    Returns:
        ANSI-farbiger HP-Balken
    """
    if maximum <= 0:
        maximum = 1
    current = max(0, min(current, maximum))
    ratio = current / maximum

    filled = int(ratio * width)
    empty = width - filled

    # ANSI-Farbcodes
    if ratio > 0.5:
        color = "\033[32m"   # Gruen
    elif ratio > 0.25:
        color = "\033[33m"   # Gelb
    else:
        color = "\033[31m"   # Rot
    reset = "\033[0m"

    bar = "#" * filled + " " * empty
    return f"[{color}{bar}{reset}] {current}/{maximum}"


# =============================================
# Battle Visualizer
# =============================================

class BattleVisualizer:
    """
    Kampf-Replay fuer SSH-Terminal.

    Nimmt einen battle_log aus BattleEngine.run_pve_battle()
    und gibt ihn Runde fuer Runde mit HP-Balken aus.
    """

    def __init__(self, use_color: bool = True, delay: float = REPLAY_DELAY):
        """
        Args:
            use_color: ANSI-Farben verwenden?
            delay: Verzoegerung zwischen Runden (Sekunden)
        """
        self.use_color = use_color
        self.delay = delay

    def _bar(self, current: int, maximum: int) -> str:
        """HP-Balken (mit oder ohne Farbe)."""
        if self.use_color:
            return hp_bar_rich(current, maximum)
        return hp_bar(current, maximum)

    # -----------------------------------------
    # Kampf-Header
    # -----------------------------------------

    def print_header(self, player_name: str, enemy_name: str,
                     player_type: str = "", enemy_type: str = "",
                     is_shiny: bool = False) -> None:
        """Kampf-Header ausgeben."""
        shiny_tag = " [SHINY!]" if is_shiny else ""
        print()
        print("=" * 50)
        print(f"  KAMPF: {player_name} ({player_type})")
        print(f"     vs  {enemy_name} ({enemy_type}){shiny_tag}")
        print("=" * 50)

    # -----------------------------------------
    # Runden-Replay
    # -----------------------------------------

    def replay_battle(self, battle_result: Dict[str, Any],
                      player_name: str = "Spieler",
                      player_max_hp: int = 100,
                      enemy_name: str = "Gegner",
                      enemy_max_hp: int = 100) -> None:
        """
        Komplettes Kampf-Replay abspielen.

        Args:
            battle_result: Ergebnis von BattleEngine.run_pve_battle()
            player_name: Name des Spielers
            player_max_hp: Max-HP Spieler
            enemy_name: Name des Gegners
            enemy_max_hp: Max-HP Gegner
        """
        log = battle_result.get("log", [])
        is_shiny = battle_result.get("is_shiny", False)

        # Header
        self.print_header(
            player_name, enemy_name,
            player_type=battle_result.get("player_type", ""),
            enemy_type=battle_result.get("enemy_type", ""),
            is_shiny=is_shiny
        )

        if not log:
            print("  (Kein Kampf-Log vorhanden)")
            return

        # Runden durchgehen
        current_round = 0
        for entry in log:
            round_num = entry.get("round", 0)

            # Neue Runde?
            if round_num != current_round:
                current_round = round_num
                print(f"\n--- Runde {round_num} ---")

                if self.delay > 0:
                    time.sleep(self.delay)

            # Angriff anzeigen
            attacker = entry.get("attacker", "?")
            damage = entry.get("damage", 0)
            is_crit = entry.get("is_crit", False)
            type_adv = entry.get("type_advantage", 0)

            # Angreifer-Name
            atk_name = player_name if attacker == "player" else enemy_name

            # Extras
            extras = []
            if is_crit:
                extras.append(f"{CRIT_SYMBOL} KRIT")
            if type_adv == 1:
                extras.append(f"{TYPE_ADV_SYMBOL} Typ-Vorteil")
            elif type_adv == -1:
                extras.append(f"{TYPE_DIS_SYMBOL} Typ-Nachteil")

            extra_str = f" ({', '.join(extras)})" if extras else ""

            print(f"  {atk_name} -> {damage} Schaden{extra_str}")

            # HP-Balken
            p_hp = entry.get("player_hp", 0)
            e_hp = entry.get("enemy_hp", 0)

            print(f"    {player_name:>12}: {self._bar(p_hp, player_max_hp)}")
            print(f"    {enemy_name:>12}: {self._bar(e_hp, enemy_max_hp)}")

        # Ergebnis
        self._print_result(battle_result, player_name, enemy_name)

    # -----------------------------------------
    # Ergebnis-Zusammenfassung
    # -----------------------------------------

    def _print_result(self, battle_result: Dict[str, Any],
                      player_name: str, enemy_name: str) -> None:
        """Kampfergebnis ausgeben."""
        result = battle_result.get("result", "DRAW")
        rounds = battle_result.get("rounds", 0)
        p_hp = battle_result.get("player_hp_remaining", 0)
        e_hp = battle_result.get("enemy_hp_remaining", 0)

        print()
        print("=" * 50)

        if result == "WIN":
            print(f"  SIEG! {player_name} gewinnt in Runde {rounds}!")
            print(f"  HP verbleibend: {p_hp}")
            if battle_result.get("survived_barely"):
                print("  Knapp ueberlebt! (<10% HP)")
            print("\a", end="", flush=True)  # Bell: Sieg!
        elif result == "LOSS":
            print(f"  NIEDERLAGE. {enemy_name} gewinnt in Runde {rounds}.")
            print(f"  Gegner HP verbleibend: {e_hp}")
        elif result == "DRAW":
            print(f"  UNENTSCHIEDEN nach {rounds} Runden.")
            print(f"  {player_name}: {p_hp} HP | {enemy_name}: {e_hp} HP")
        elif result == "BLOCKED":
            print(f"  KAMPF BLOCKIERT: {battle_result.get('message', 'Erschoepfung')}")

        print("=" * 50)

    # -----------------------------------------
    # Kompakt-Anzeige (ohne Replay)
    # -----------------------------------------

    @staticmethod
    def print_summary(battle_result: Dict[str, Any],
                      player_name: str = "Spieler",
                      enemy_name: str = "Gegner") -> None:
        """Kompakte Kampfzusammenfassung (eine Zeile)."""
        result = battle_result.get("result", "?")
        rounds = battle_result.get("rounds", 0)
        p_hp = battle_result.get("player_hp_remaining", 0)
        e_hp = battle_result.get("enemy_hp_remaining", 0)

        # Krit-Zaehler
        log = battle_result.get("log", [])
        crits = sum(1 for e in log if e.get("is_crit"))

        result_text = {
            "WIN": "SIEG",
            "LOSS": "NIEDERLAGE",
            "DRAW": "UNENTSCHIEDEN",
            "BLOCKED": "BLOCKIERT"
        }.get(result, result)

        shiny = " [SHINY!]" if battle_result.get("is_shiny") else ""
        print(f"[{result_text}] {player_name} vs {enemy_name} | "
              f"Runden: {rounds} | HP: {p_hp}/{e_hp} | "
              f"Krits: {crits}{shiny}")

    # -----------------------------------------
    # Reward-Anzeige
    # -----------------------------------------

    @staticmethod
    def print_rewards(reward_result: Dict[str, Any]) -> None:
        """Reward-Zusammenfassung nach Kampf."""
        gold = reward_result.get("gold_earned", 0)
        diamonds = reward_result.get("diamonds_earned", 0)
        soul_shards = reward_result.get("soul_shards_earned", 0)
        exp = reward_result.get("exp_earned", 0)
        scrap = reward_result.get("scrap_earned", 0)

        print("\n  Belohnungen:")
        if gold > 0:
            print(f"    Gold: +{gold}")
        if diamonds > 0:
            print(f"    Diamanten: +{diamonds}")
        if soul_shards > 0:
            print(f"    Seelen-Scherben: +{soul_shards}")
        if exp > 0:
            print(f"    EXP: +{exp}")
        if scrap > 0:
            print(f"    Schrott: +{scrap}")

        # Level-Up?
        level_up = reward_result.get("level_up", {})
        if level_up.get("leveled_up"):
            new_level = level_up.get("new_level", "?")
            print(f"\n    LEVEL UP! -> Level {new_level} (+5 Bonuspunkte)")
            print("\a", end="", flush=True)  # Bell: Level-Up!

        # Psyche-Modifikatoren?
        mods = reward_result.get("psyche_modifiers", {})
        if mods:
            for key, val in mods.items():
                if isinstance(val, (int, float)) and val != 0:
                    print(f"    Psyche ({key}): {val:+.0f}%")


# =============================================
# Standalone-Test
# =============================================

if __name__ == "__main__":
    # Simulated battle log
    fake_log = [
        {"round": 1, "attacker": "player", "damage": 15, "is_crit": False,
         "type_advantage": 1, "player_hp": 100, "enemy_hp": 65},
        {"round": 1, "attacker": "enemy", "damage": 12, "is_crit": False,
         "type_advantage": -1, "player_hp": 88, "enemy_hp": 65},
        {"round": 2, "attacker": "player", "damage": 30, "is_crit": True,
         "type_advantage": 1, "player_hp": 88, "enemy_hp": 35},
        {"round": 2, "attacker": "enemy", "damage": 10, "is_crit": False,
         "type_advantage": -1, "player_hp": 78, "enemy_hp": 35},
        {"round": 3, "attacker": "player", "damage": 18, "is_crit": False,
         "type_advantage": 1, "player_hp": 78, "enemy_hp": 17},
        {"round": 3, "attacker": "enemy", "damage": 8, "is_crit": False,
         "type_advantage": -1, "player_hp": 70, "enemy_hp": 17},
        {"round": 4, "attacker": "player", "damage": 17, "is_crit": False,
         "type_advantage": 1, "player_hp": 70, "enemy_hp": 0},
    ]

    fake_result = {
        "result": "WIN",
        "rounds": 4,
        "log": fake_log,
        "player_hp_remaining": 70,
        "enemy_hp_remaining": 0,
        "is_shiny": False,
        "survived_barely": False,
        "player_type": "Stein",
        "enemy_type": "Schere"
    }

    viz = BattleVisualizer(use_color=True, delay=0.1)
    viz.replay_battle(fake_result, "TestHeld", 100, "Goblin", 80)

    print()
    BattleVisualizer.print_summary(fake_result, "TestHeld", "Goblin")

    # Test rewards display
    fake_rewards = {
        "gold_earned": 45,
        "diamonds_earned": 3,
        "soul_shards_earned": 0,
        "exp_earned": 100,
        "scrap_earned": 0,
        "level_up": {"leveled_up": True, "new_level": 6},
        "psyche_modifiers": {"loot_reduction": -10}
    }
    BattleVisualizer.print_rewards(fake_rewards)
