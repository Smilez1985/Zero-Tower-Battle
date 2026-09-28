#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Balancing-Simulation V2
===================================================
Realistische Simulation: 1 Kampf pro Floor, bei Sieg weiter, bei Niederlage
retry (max 3 Versuche). Zeigt wann Idle-Spieler steckenbleiben.

Szenarien:
  idle   - Auto-Punkteverteilung, kein Equipment
  casual - Punkte auf Hauptstat, Equipment alle 10 Floors
  active - Strategische Punkte, Equipment alle 5 Floors
"""

import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.battle_engine import BattleEngine
from monster_generator import generate_pve_monster

# Klassen (aus forge.py)
CLASSES = {
    "Krieger": {"atk": 25, "def": 40, "spd": 20, "luk": 15, "type": "Stein"},
    "Schurke": {"atk": 25, "def": 15, "spd": 40, "luk": 20, "type": "Schere"},
    "Magier":  {"atk": 45, "def": 10, "spd": 20, "luk": 25, "type": "Papier"},
}

EXP_WIN = 100
EXP_LOSS = 30
XP_PER_LEVEL = 500
BONUS_PER_LEVEL = 5
MAX_RETRIES = 3  # Versuche pro Floor bevor "steckengeblieben"


def distribute_points(player, class_name, scenario, points):
    """Level-Up Bonuspunkte verteilen."""
    while points >= BONUS_PER_LEVEL:
        points -= BONUS_PER_LEVEL
        if scenario == "idle":
            player["atk_extra"] += 1
            player["def_extra"] += 2
            player["spd_extra"] += 1
            player["luk_extra"] += 1
        elif scenario == "casual":
            if class_name == "Krieger":
                player["def_extra"] += 3
                player["atk_extra"] += 2
            elif class_name == "Schurke":
                player["spd_extra"] += 2
                player["atk_extra"] += 2
                player["luk_extra"] += 1
            elif class_name == "Magier":
                player["atk_extra"] += 3
                player["luk_extra"] += 2
        elif scenario == "active":
            if class_name == "Krieger":
                player["atk_extra"] += 3
                player["def_extra"] += 2
            elif class_name == "Schurke":
                player["atk_extra"] += 3
                player["spd_extra"] += 1
                player["luk_extra"] += 1
            elif class_name == "Magier":
                player["atk_extra"] += 4
                player["def_extra"] += 1
    return points


def simulate_progression(class_name, scenario, max_floor=80):
    """Realistische Simulation: 1 Kampf pro Floor."""
    base = CLASSES[class_name]
    engine = BattleEngine()

    player = {
        "name": f"Test{class_name}",
        "klasse": class_name,
        "type": base["type"],
        "level": 1,
        "exp": 0,
        "atk_base": base["atk"],
        "def_base": base["def"],
        "spd_base": base["spd"],
        "luk_base": base["luk"],
        "atk_extra": 0, "def_extra": 0, "spd_extra": 0, "luk_extra": 0,
        "total_atk": base["atk"], "total_def": base["def"],
        "total_spd": base["spd"], "total_luk": base["luk"],
        "hp": 100, "max_hp": 100,
        "exhaustion": 0.0,
        "gold": 100,
    }

    equip_atk = 0
    equip_def = 0
    pending_pts = 0
    stuck_floors = []
    total_battles = 0
    total_wins = 0
    total_losses = 0

    print(f"\n{'='*80}")
    print(f"  {class_name.upper()} - Szenario: {scenario.upper()}")
    print(f"{'='*80}")
    print(f"{'Floor':>5} {'Boss':>4} {'Lv':>3} {'pHP':>4} {'pATK':>4} {'pDEF':>4} "
          f"{'mATK':>4} {'mDEF':>4} {'mHP':>5} "
          f"{'Result':>6} {'HP%':>4} {'Gold':>6}")
    print(f"{'-'*80}")

    for floor in range(1, max_floor + 1):
        # Level-Up Punkte verteilen
        pending_pts = distribute_points(player, class_name, scenario, pending_pts)

        # Equipment (nur in casual/active)
        if scenario == "casual":
            if floor >= 10 and floor % 10 == 0:
                equip_atk += 5
                equip_def += 4
        elif scenario == "active":
            if floor >= 5 and floor % 5 == 0:
                equip_atk += 5
                equip_def += 4

        # Effektive Stats
        player["total_atk"] = player["atk_base"] + player["atk_extra"] + equip_atk
        player["total_def"] = player["def_base"] + player["def_extra"] + equip_def
        player["total_spd"] = player["spd_base"] + player["spd_extra"]
        player["total_luk"] = player["luk_base"] + player["luk_extra"]
        player["max_hp"] = engine.calculate_max_hp(player["level"], player["total_def"])
        player["hp"] = player["max_hp"]

        # Monster generieren (nur Basis+Extra als Referenz, KEIN Equipment)
        monster_ref = {
            "klasse": class_name,
            "level": player["level"],
            "base_atk": player["atk_base"] + player["atk_extra"],
            "base_def": player["def_base"] + player["def_extra"],
            "base_spd": player["spd_base"] + player["spd_extra"],
            "base_luk": player["luk_base"] + player["luk_extra"],
            "extra_atk": 0, "extra_def": 0, "extra_spd": 0, "extra_luk": 0,
        }
        monster = generate_pve_monster(floor, monster_ref, index=0)
        is_boss = monster.get("is_boss", False)

        # Kampf (max 3 Versuche)
        won = False
        attempts = 0
        last_result = None
        for attempt in range(MAX_RETRIES):
            attempts += 1
            total_battles += 1
            player["hp"] = player["max_hp"]
            result = engine.run_pve_battle(player, monster,
                                           seed=floor * 1000 + attempt)
            last_result = result

            if result["result"] == "WIN":
                won = True
                total_wins += 1
                player["exp"] += EXP_WIN
                player["gold"] += floor * 10
                break
            else:
                total_losses += 1
                player["exp"] += EXP_LOSS

        # Level-Up Check
        while player["exp"] >= XP_PER_LEVEL:
            player["exp"] -= XP_PER_LEVEL
            player["level"] += 1
            pending_pts += BONUS_PER_LEVEL
            player["max_hp"] = engine.calculate_max_hp(player["level"], player["total_def"])

        if not won:
            stuck_floors.append(floor)

        # Ergebnis-Text
        if won:
            hp_pct = last_result["player_hp_remaining"] * 100 // player["max_hp"]
            res_text = f"WIN({attempts})"
        else:
            hp_pct = 0
            res_text = "STUCK!"

        # Ausgabe: Alle 5 Floors, Bosse, Stuck, und erste 5
        show = (floor % 5 == 0 or floor <= 5 or is_boss or not won
                or floor in [10, 15, 20])
        if show:
            boss_str = "BOSS" if is_boss else ""
            print(f"{floor:5d} {boss_str:>4} {player['level']:3d} "
                  f"{player['max_hp']:4d} "
                  f"{player['total_atk']:4d} {player['total_def']:4d} "
                  f"{monster['total_atk']:4d} {monster['total_def']:4d} "
                  f"{monster['hp']:5d} "
                  f"{res_text:>6} {hp_pct:3d}% "
                  f"{player['gold']:6d}")

    # Zusammenfassung
    print(f"\n  Kaempfe: {total_battles} | Siege: {total_wins} | "
          f"Niederlagen: {total_losses}")
    print(f"  End-Level: {player['level']} | End-Gold: {player['gold']}")
    if stuck_floors:
        print(f"  STECKENGEBLIEBEN bei Floors: {stuck_floors}")
        # Ersten Stuck-Floor finden der kein Boss ist
        non_boss_stuck = [f for f in stuck_floors if f % 25 != 0]
        boss_stuck = [f for f in stuck_floors if f % 25 == 0]
        if non_boss_stuck:
            print(f"  >>> IDLE-WALL (normal): Floor {non_boss_stuck[0]}")
        if boss_stuck:
            print(f"  >>> BOSS-WALL: Floors {boss_stuck}")
    else:
        print(f"  >>> Keine Wall bis Floor {max_floor}!")


def damage_formula_test():
    """Zeige Damage-Formel Beispielwerte."""
    engine = BattleEngine()
    print("\n--- Damage-Formel V2: ATK × (1 + (Lv-1)×5%) nach DEF/(DEF+50) ---")
    print(f"{'Szenario':40s} {'raw':>4} {'def%':>4} {'dmg':>4} {'pHP':>4}")
    print("-" * 60)

    rng = random.Random(42)
    tests = [
        ("Krieger Lv1 (ATK25) vs DEF 18",
         {"total_atk": 25, "total_luk": 15, "level": 1, "type": "Stein"},
         {"total_def": 18, "type": "Stein"}),
        ("Magier Lv1 (ATK45) vs DEF 18",
         {"total_atk": 45, "total_luk": 25, "level": 1, "type": "Papier"},
         {"total_def": 18, "type": "Stein"}),
        ("Krieger Lv5 (ATK30) vs DEF 25",
         {"total_atk": 30, "total_luk": 15, "level": 5, "type": "Stein"},
         {"total_def": 25, "type": "Stein"}),
        ("Krieger Lv5+Rare (ATK40) vs DEF 25",
         {"total_atk": 40, "total_luk": 15, "level": 5, "type": "Stein"},
         {"total_def": 25, "type": "Stein"}),
        ("Krieger Lv10+Rare (ATK50) vs DEF 35",
         {"total_atk": 50, "total_luk": 20, "level": 10, "type": "Stein"},
         {"total_def": 35, "type": "Stein"}),
        ("Monster ATK 30 Lv3 vs Krieger DEF 42",
         {"total_atk": 30, "total_luk": 10, "level": 3, "type": "Schere"},
         {"total_def": 42, "type": "Stein"}),
        ("Monster ATK 50 Lv8 vs Krieger DEF 45",
         {"total_atk": 50, "total_luk": 10, "level": 8, "type": "Schere"},
         {"total_def": 45, "type": "Stein"}),
    ]

    for desc, atk_dict, def_dict in tests:
        r = engine.calculate_damage(atk_dict, def_dict, rng)
        hp = engine.calculate_max_hp(atk_dict["level"], atk_dict.get("total_def", 0))
        print(f"  {desc:40s} {r['raw_damage']:4d} {r['defense_pct']:3d}% "
              f"{r['damage']:4d} {hp:4d}")


def find_idle_wall(class_name, scenario, max_floor=60, seed_offset=0):
    """Finde die Idle-Wall ohne Ausgabe (fuer Multi-Seed-Analyse)."""
    base = CLASSES[class_name]
    engine = BattleEngine()

    player = {
        "name": f"Test{class_name}",
        "klasse": class_name,
        "type": base["type"],
        "level": 1, "exp": 0,
        "atk_base": base["atk"], "def_base": base["def"],
        "spd_base": base["spd"], "luk_base": base["luk"],
        "atk_extra": 0, "def_extra": 0, "spd_extra": 0, "luk_extra": 0,
        "total_atk": base["atk"], "total_def": base["def"],
        "total_spd": base["spd"], "total_luk": base["luk"],
        "hp": 100, "max_hp": 100,
        "exhaustion": 0.0, "gold": 100,
    }
    pending_pts = 0

    for floor in range(1, max_floor + 1):
        pending_pts = distribute_points(player, class_name, scenario, pending_pts)
        equip_atk, equip_def = 0, 0
        if scenario == "active":
            if floor >= 5 and floor % 5 == 0:
                equip_atk += 5
                equip_def += 4
        elif scenario == "casual":
            if floor >= 10 and floor % 10 == 0:
                equip_atk += 5
                equip_def += 4

        player["total_atk"] = player["atk_base"] + player["atk_extra"] + equip_atk
        player["total_def"] = player["def_base"] + player["def_extra"] + equip_def
        player["total_spd"] = player["spd_base"] + player["spd_extra"]
        player["total_luk"] = player["luk_base"] + player["luk_extra"]
        player["max_hp"] = engine.calculate_max_hp(player["level"], player["total_def"])
        player["hp"] = player["max_hp"]

        monster_ref = {
            "klasse": class_name, "level": player["level"],
            "base_atk": player["atk_base"] + player["atk_extra"],
            "base_def": player["def_base"] + player["def_extra"],
            "base_spd": player["spd_base"] + player["spd_extra"],
            "base_luk": player["luk_base"] + player["luk_extra"],
            "extra_atk": 0, "extra_def": 0, "extra_spd": 0, "extra_luk": 0,
        }
        monster = generate_pve_monster(floor, monster_ref, index=seed_offset)
        is_boss = monster.get("is_boss", False)

        won = False
        for attempt in range(MAX_RETRIES):
            player["hp"] = player["max_hp"]
            result = engine.run_pve_battle(player, monster,
                                           seed=floor * 1000 + attempt + seed_offset * 100)
            if result["result"] == "WIN":
                won = True
                player["exp"] += EXP_WIN
                player["gold"] += floor * 10
                break
            else:
                player["exp"] += EXP_LOSS

        while player["exp"] >= XP_PER_LEVEL:
            player["exp"] -= XP_PER_LEVEL
            player["level"] += 1
            pending_pts += BONUS_PER_LEVEL
            player["max_hp"] = engine.calculate_max_hp(player["level"], player["total_def"])

        if not won and not is_boss:
            return floor  # Idle-Wall gefunden

    return max_floor + 1  # Keine Wall


def multi_seed_analysis(num_seeds=10):
    """Analysiere Idle-Walls ueber mehrere Seeds um RNG-Varianz zu eliminieren."""
    print("\n" + "=" * 80)
    print(f"  MULTI-SEED-ANALYSE ({num_seeds} Durchlaeufe pro Klasse/Szenario)")
    print("  Zeigt Durchschnitt, Min, Max der Idle-Walls")
    print("=" * 80)
    print(f"\n  {'Klasse':10s} {'Szenario':8s}  {'Avg':>5s}  {'Min':>3s}  {'Max':>3s}  Alle Walls")
    print("  " + "-" * 70)

    for cls in ["Krieger", "Schurke", "Magier"]:
        for scn in ["idle"]:
            walls = []
            for seed in range(num_seeds):
                wall = find_idle_wall(cls, scn, max_floor=60, seed_offset=seed)
                walls.append(wall)
            avg = sum(walls) / len(walls)
            print(f"  {cls:10s} {scn:8s}  {avg:5.1f}  {min(walls):3d}  {max(walls):3d}  {walls}")
    print()


def main():
    print("=" * 80)
    print("  ZERO TOWER BATTLE - BALANCING-SIMULATION V2 (Realistisch)")
    print("  1 Kampf pro Floor | Max 3 Retries | Level-Up alle ~5 Siege")
    print("=" * 80)

    damage_formula_test()

    for cls in ["Krieger", "Schurke", "Magier"]:
        for scn in ["idle", "casual", "active"]:
            simulate_progression(cls, scn, max_floor=60)

    # Multi-Seed-Analyse fuer robuste Idle-Wall-Bestimmung
    multi_seed_analysis(num_seeds=20)

    print("=" * 80)
    print("  LEGENDE:")
    print("  pHP/pATK/pDEF = Spieler Stats | mATK/mDEF/mHP = Monster Stats")
    print("  WIN(1) = Sieg im 1. Versuch | WIN(3) = Sieg im 3. Versuch")
    print("  STUCK! = 3 Niederlagen hintereinander (Wall!)")
    print("  Boss-Floors: 25, 50 (hoehere Stats + HP)")
    print("=" * 80)


if __name__ == "__main__":
    main()
