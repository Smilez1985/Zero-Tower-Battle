#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Battle Engine for PVE/PVP Combat
============================================================

CRITICAL: 100-Punkte-Gesetz (Hart codiert!)
├─ 4 Attribute: ATK/DEF/SPD/LUK (Summe = 100 HARDCODED!)
├─ Klassensumme: FIXED AT INIT
├─ Level-Up: +5 Bonus (extra Feld, NICHT Teil der 100)
└─ Type-Vorteil: ×1.25 (Integer: // 100)

Deterministisch für P2P:
├─ Gleicher Input = gleiches Ergebnis
├─ Seed = Unix-Timestamp (UTC) + Spieler+Gegner Namen
├─ Gleicher Seed auf beiden Pis (Timestamp Synchronisiert!)
└─ Gleicher Seed = Gleicher Seed auf beiden Pis (keine FP-Fehler)

Kampfformel (Integer-basiert für P2P, V2 Balanced):
├─ Initiative: erste Attacke bei SPD >= Gegner
├─ Basisschaden: ATK × (100 + (Level-1) × 5) ÷ 100 (ATK ist Hauptfaktor!)
├─ Verteidigung: asymptotisch DEF × 100 ÷ (DEF + 50), max ~60% Reduktion
├─ Varianz: ±10% (randint 90-110)
├─ Krit: LUK × 5 ÷ 1000 = LUK × 0.005 (50 LUK = 25% Crit)
└─ HP wächst mit Level: 100 + (Level-1) × 8 + DEF÷2

Floating-Point Vermeidung:
├─ Typ-Vorteil: ×125 ÷ 100 (Integer Division!)
├─ LUK Crit: LUK × 5 ÷ 1000
├─ Defense: DEF × 100 ÷ (DEF + 50) = prozentuale Reduktion
└─ Damage Calc: max(3, raw × (100 - def_pct) ÷ 100)
"""


import random
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
# pylint: disable=import-error, unused-import


# ========================================
# VALIDIERT: 100-Punkte-Gesetz (HART CODED!)
# ========================================
CLASSES = {
    "Krieger": {
        "type": "Stein",
        "atk_base": 25,   # 25+40+20+15 = 100 ✅
        "def_base": 40,
        "spd_base": 20,
        "luk_base": 15,
        "focus": "Defensive"
        # Summe = 100 HARD CODED!
    },
    "Schurke": {
        "type": "Schere",
        "atk_base": 25,
        "def_base": 15,
        "spd_base": 40,  # 25+15+40+20 = 100 ✅
        "luk_base": 20,
        "focus": "Tempo"
        # Summe = 100 HARD CODED!
    },
    "Magier": {
        "type": "Papier",
        "atk_base": 45,
        "def_base": 10,  # 45+10+20+25 = 100 ✅
        "spd_base": 20,
        "luk_base": 25,
        "focus": "Glaskanone"
        # Summe = 100 HARD CODED!
    }
}

# Typ-Vorteil (Schere-Stein-Papier):
TYPE_ADVANTAGE_MAP = {
    "Stein": {"beats": "Schere", "loses_to": "Papier"},
    "Schere": {"beats": "Papier", "loses_to": "Stein"},
    "Papier": {"beats": "Stein", "loses_to": "Schere"}
}

# Type-Vorteil Multiplier (Integer Division für P2P!)
TYPE_MULTIPLIER = 125  # ×125 ÷ 100 = ×1.25
TYPE_DIVISOR = 100


# ========================================
# KAMPF-SYSTEM
# ========================================
class BattleEngine:
    """PVE & PVP Kampf-Engine mit 100-Punkte-Gesetz!"""
    
    SHINY_CHANCE = 1 << 13  # 8192 = 2^13
    DEFAULT_HP = 100
    HP_PER_LEVEL = 17       # +17 Max-HP pro Level
    MAX_ROUNDS = 30
    VARIANCE_FACTOR = 0.1   # ±10%
    LEVEL_AMP_PER_LEVEL = 5 # +5% Schaden pro Level (ab Level 2)
    DEFENSE_SOFTCAP = 50    # DEF/(DEF+50) = asymptotische Reduktion
    MIN_DAMAGE = 3          # Minimum-Schaden pro Hit

    # VALIDATION: 100-Punkte-Summe
    STAT_TARGET = 100  # Summe = 100 HARD CODED!

    def __init__(self, world_boss_enabled: bool = True):
        """
        Initialisiere Battle Engine.
        
        Args:
            world_boss_enabled: Weltboss-Raid aktivieren?
        """
        self.world_boss_enabled = world_boss_enabled
        self._rng = random.Random()  # Lokaler RNG für Testing
    
    def init_stats(self, level: int = 1, class_name: str = "Krieger",
                   extra_points: int = 0) -> Dict[str, int]:
        """
        Initialisiere Stats nach 100-Punkte-Gesetz!
        
        VALIDATION:
        ├─ Stat Summe = 100 (nie überschritten!)
        ├─ Extra-Punkte: max 50 pro stat
        ├─ Level-Up: +5 Bonus (extra Feld)
        
        Args:
            level: Charakter-Level
            class_name: Klassename
            extra_points: Bonuspunkte von Level-Up
        
        Returns:
            Dict mit atk_base, def_base, spd_base, luk_base,
            atk_extra, def_extra, spd_extra, luk_extra,
            total_atk, total_def, total_spd, total_luk
        
        """
        # Basiswerte aus Klassen-Definition (Summe = 100 HARDCODED!)
        class_data = CLASSES.get(class_name, CLASSES["Krieger"])
        
        # VALIDATE: Summe = 100
        stat_sum = (
            class_data["atk_base"] +
            class_data["def_base"] +
            class_data["spd_base"] +
            class_data["luk_base"]
        )
        
        assert stat_sum == self.STAT_TARGET, \
            f"STAT VALIDATION FAILED: {class_name} sum={stat_sum}, MUST = {self.STAT_TARGET}"
        
        # Extra-Stats (Bonuspunkte, NICHT Teil der 100)
        extras = {
            "atk_extra": 0,
            "def_extra": 0,
            "spd_extra": 0,
            "luk_extra": 0
        }

        # Level-Up: +5 Bonus pro Level (extra Feld)
        level_bonus = (level - 1) * 5  # Level 2 = +5 extra points
        total_bonus = min(level_bonus, extra_points)

        # Verteile Extra-Punkte gleichmaessig (max 50 pro Stat)
        if total_bonus > 0:
            keys = ["atk_extra", "def_extra", "spd_extra", "luk_extra"]
            per_stat = total_bonus // 4
            remainder = total_bonus % 4

            for i, key in enumerate(keys):
                share = min(per_stat + (1 if i < remainder else 0), 50)
                extras[key] = share

        atk_extra = extras["atk_extra"]
        def_extra = extras["def_extra"]
        spd_extra = extras["spd_extra"]
        luk_extra = extras["luk_extra"]

        total_atk = class_data["atk_base"] + atk_extra
        total_def = class_data["def_base"] + def_extra
        total_spd = class_data["spd_base"] + spd_extra
        total_luk = class_data["luk_base"] + luk_extra
        
        # VALIDATE: Summe nach Level-Up (Basis 100 + Extra)
        total_stats_sum = total_atk + total_def + total_spd + total_luk
        
        return {
            "class": class_name,
            "tier": level,
            "atk_base": class_data["atk_base"],
            "def_base": class_data["def_base"],
            "spd_base": class_data["spd_base"],
            "luk_base": class_data["luk_base"],
            "bonus_per_level": 5,
            "level": level,
            "atk_extra": atk_extra,
            "def_extra": def_extra,
            "spd_extra": spd_extra,
            "luk_extra": luk_extra,
            "total_atk": total_atk,
            "total_def": total_def,
            "total_spd": total_spd,
            "total_luk": total_luk,
            "total_stats_sum": total_stats_sum,  # Track total
            "type": class_data["type"],
            "focus": class_data["focus"],
            "level_bonus": level_bonus
        }

    # ========================================
    # ERSCHOEPFUNGS-CHECK
    # ========================================

    @staticmethod
    def check_exhaustion(character: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pruefe ob Charakter kampffaehig ist (Erschoepfungs-System).

        Erschoepfung 100% = 1h Tower-Pause, dann Reset auf 80%.
        KEINE Stat-Nerfs (mild, nur Loot/XP-Reduktion via Psyche).

        Args:
            character: Charakter-Dict mit 'exhaustion'-Feld

        Returns:
            Dict mit: can_fight, exhaustion, message
        """
        exhaustion = character.get("exhaustion", 0.0)

        if exhaustion >= 100.0:
            return {
                "can_fight": False,
                "exhaustion": exhaustion,
                "message": "Champion ist erschoepft! Tower pausiert fuer max. 1 Stunde."
            }

        return {
            "can_fight": True,
            "exhaustion": exhaustion,
            "message": f"Erschoepfung: {exhaustion:.0f}%"
        }

    # ========================================
    # DETERMINISTISCHE SEED-ERZEUGUNG (P2P)
    # ========================================

    @staticmethod
    def generate_battle_seed(player_name: str, enemy_name: str,
                             timestamp: int = None) -> int:
        """
        Deterministischer Seed fuer P2P-Kampf.
        Gleicher Input = gleicher Kampfverlauf auf beiden Pis.

        Args:
            player_name: Name Spieler A
            enemy_name: Name Spieler B (oder Monster-ID)
            timestamp: Unix-Timestamp UTC (oder auto)

        Returns:
            int: Seed fuer random.Random()
        """
        if timestamp is None:
            timestamp = int(datetime.now(timezone.utc).timestamp())

        # Sortierte Namen = gleicher Seed egal wer Client/Server ist
        names_sorted = "".join(sorted([player_name, enemy_name]))
        raw = f"{names_sorted}:{timestamp}"
        seed_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        # Erste 8 hex Zeichen als int (32 bit reicht)
        return int(seed_hash[:8], 16)

    # ========================================
    # TYP-VORTEIL
    # ========================================

    @staticmethod
    def check_type_advantage(attacker_type: str, defender_type: str) -> int:
        """
        Pruefe Schere-Stein-Papier Typ-Vorteil.

        Returns:
            1 = Vorteil, -1 = Nachteil, 0 = Neutral
        """
        if attacker_type == defender_type:
            return 0

        advantage = TYPE_ADVANTAGE_MAP.get(attacker_type, {})
        if advantage.get("beats") == defender_type:
            return 1
        elif advantage.get("loses_to") == defender_type:
            return -1
        return 0

    # ========================================
    # HP-SKALIERUNG MIT LEVEL
    # ========================================

    @staticmethod
    def calculate_max_hp(level: int, total_def: int = 0, bonus_hp: int = 0) -> int:
        """
        Max-HP berechnen basierend auf Level + DEF-Bonus.

        Formel: 100 + (Level-1) × 8 + DEF//2 + Bonus-HP

        DEF-Bonus konvergiert Idle-Walls:
          Krieger (DEF 40) → +20 HP  (Tank profitiert)
          Schurke (DEF 15) → +7 HP   (Mittelfeld)
          Magier  (DEF 10) → +5 HP   (Glaskanone bleibt fragil)

        Lv1 Krieger: 100+0+20 = 120 | Lv5: 148+22 = 170
        Lv1 Magier:  100+0+5  = 105 | Lv5: 148+5  = 153

        Args:
            level: Charakter-Level (ab 1)
            total_def: Gesamte DEF (base + extra + equipment)
            bonus_hp: Zusaetzliche HP durch Buffs

        Returns:
            int: Maximale Lebenspunkte
        """
        # DEF × 3÷2 statt DEF÷2 → Tank profitiert MASSIV
        # Krieger DEF 48: +72 HP | Schurke DEF 21: +31 HP | Magier DEF 16: +24 HP
        return 100 + max(0, level - 1) * BattleEngine.HP_PER_LEVEL + total_def * 3 // 2 + bonus_hp

    # ========================================
    # SCHADENSBERECHNUNG (INTEGER-BASIERT! V2)
    # ========================================

    def calculate_damage(self, attacker: Dict[str, Any],
                         defender: Dict[str, Any],
                         rng: random.Random = None) -> Dict[str, Any]:
        """
        Berechne Schaden (Integer-basiert fuer P2P-Konsistenz).

        V2 Balanced Formula:
          1. Raw Damage = ATK x (100 + (Level-1) x 5) // 100
             -> ATK ist der HAUPTFAKTOR, Level verstaerkt um +5% pro Level
             -> ATK 25 Lv1 = 25, ATK 25 Lv10 = 36, ATK 60 Lv10 = 87
          2. Defense % = DEF x 100 // (DEF + 50)
             -> Asymptotisch: DEF 20 = 28%, DEF 40 = 44%, DEF 80 = 61%
             -> Verteidigung wird NIE 100%, immer durchdringbar
          3. Schaden = max(3, Raw x (100 - DefPct) // 100)
          4. Varianz: ±10%
          5. Typ-Vorteil: x1.25 / x0.8
          6. Krit: LUK x 5 / 1000 Chance, 2x Schaden

        Args:
            attacker: Angreifer-Dict (atk, luk, type, level)
            defender: Verteidiger-Dict (def, type)
            rng: Optional deterministischer RNG

        Returns:
            Dict mit: damage, is_crit, type_advantage, raw_damage,
            defense_pct
        """
        if rng is None:
            rng = self._rng

        atk = attacker.get("total_atk", attacker.get("atk_base", 25))
        def_ = defender.get("total_def", defender.get("def_base", 25))
        luk = attacker.get("total_luk", attacker.get("luk_base", 15))
        level = attacker.get("level", 1)

        # 1. Basisschaden: ATK × Level-Amplifier (Integer!)
        level_amp = 100 + max(0, level - 1) * self.LEVEL_AMP_PER_LEVEL
        raw_damage = atk * level_amp // 100

        # 2. Verteidigung: asymptotische Reduktion (kein Hardcap!)
        #    DEF 20 -> 28% | DEF 40 -> 44% | DEF 60 -> 54% | DEF 100 -> 66%
        defense_pct = def_ * 100 // (def_ + self.DEFENSE_SOFTCAP)

        # 3. Schaden nach Verteidigung
        after_def = max(self.MIN_DAMAGE,
                        raw_damage * (100 - defense_pct) // 100)

        # 4. Varianz ±10% (Integer: 90-110)
        variance = rng.randint(90, 110)
        damage = max(self.MIN_DAMAGE, after_def * variance // 100)

        # 5. Typ-Vorteil (Schere-Stein-Papier)
        attacker_type = attacker.get("type", "Stein")
        defender_type = defender.get("type", "Stein")
        type_adv = self.check_type_advantage(attacker_type, defender_type)

        if type_adv == 1:
            # x1.25 (Integer: ×125 ÷ 100)
            damage = damage * TYPE_MULTIPLIER // TYPE_DIVISOR
        elif type_adv == -1:
            # x0.8 Nachteil (Integer: ×80 ÷ 100)
            damage = damage * 80 // 100

        # 6. Krit-Check (LUK × 5 / 1000)
        is_crit = False
        crit_roll = rng.randint(1, 1000)
        if crit_roll <= luk * 5:
            damage = damage * 2  # Krit = Doppelschaden
            is_crit = True

        # Minimum-Schaden garantieren
        damage = max(self.MIN_DAMAGE, damage)

        return {
            "damage": damage,
            "is_crit": is_crit,
            "type_advantage": type_adv,
            "raw_damage": raw_damage,
            "defense_pct": defense_pct
        }

    # ========================================
    # KAMPF-ABLAUF (PVE)
    # ========================================

    def run_pve_battle(self, player: Dict[str, Any],
                       enemy: Dict[str, Any],
                       seed: int = None) -> Dict[str, Any]:
        """
        Fuehre einen PVE-Kampf durch.

        Args:
            player: Spieler-Charakter-Dict
            enemy: Gegner-Dict (name, atk_base, def_base, spd_base, luk_base, hp, type)
            seed: Deterministischer Seed (optional)

        Returns:
            Dict mit: result (WIN/LOSS/DRAW), rounds, log, rewards_eligible,
            player_hp_remaining, enemy_hp_remaining, is_shiny
        """
        # Erschoepfungs-Check
        exh_check = self.check_exhaustion(player)
        if not exh_check["can_fight"]:
            return {
                "result": "BLOCKED",
                "reason": "exhaustion",
                "message": exh_check["message"],
                "rounds": 0,
                "log": [],
                "rewards_eligible": False
            }

        # RNG mit Seed initialisieren
        if seed is not None:
            rng = random.Random(seed)
        else:
            rng = random.Random()

        # HP initialisieren (Spieler-HP skaliert mit Level + DEF!)
        player_level = player.get("level", 1)
        player_total_def = player.get("total_def", player.get("def_base", 25))
        player_max_hp = self.calculate_max_hp(player_level, player_total_def)
        player_hp = min(player.get("hp", player_max_hp), player_max_hp)
        # Max-HP im Player-Dict aktualisieren (fuer Konsistenz)
        player["max_hp"] = player_max_hp
        enemy_hp = enemy.get("hp", self.DEFAULT_HP)
        enemy_max_hp = enemy.get("max_hp", self.DEFAULT_HP)

        # Shiny-Check (1:8192)
        is_shiny = rng.randint(1, self.SHINY_CHANCE) == 1

        # Initiative: SPD-Vergleich
        player_spd = player.get("total_spd", player.get("spd_base", 20))
        enemy_spd = enemy.get("total_spd", enemy.get("spd_base", 20))
        player_goes_first = player_spd >= enemy_spd

        # Kampf-Log
        battle_log: List[Dict[str, Any]] = []
        rounds = 0

        for round_num in range(1, self.MAX_ROUNDS + 1):
            rounds = round_num

            if player_goes_first:
                order = [("player", player, "enemy"), ("enemy", enemy, "player")]
            else:
                order = [("enemy", enemy, "player"), ("player", player, "enemy")]

            for attacker_name, attacker_data, defender_name in order:
                if attacker_name == "player":
                    atk_hp_ref = "player_hp"
                    def_hp_ref = "enemy_hp"
                else:
                    atk_hp_ref = "enemy_hp"
                    def_hp_ref = "player_hp"

                # Ist Angreifer noch am Leben?
                current_atk_hp = player_hp if attacker_name == "player" else enemy_hp
                if current_atk_hp <= 0:
                    continue

                # Schaden berechnen
                dmg_result = self.calculate_damage(attacker_data,
                                                    enemy if attacker_name == "player" else player,
                                                    rng)

                # Schaden anwenden
                if defender_name == "enemy":
                    enemy_hp = max(0, enemy_hp - dmg_result["damage"])
                else:
                    player_hp = max(0, player_hp - dmg_result["damage"])

                # Log-Eintrag
                battle_log.append({
                    "round": round_num,
                    "attacker": attacker_name,
                    "damage": dmg_result["damage"],
                    "is_crit": dmg_result["is_crit"],
                    "type_advantage": dmg_result["type_advantage"],
                    "player_hp": player_hp,
                    "enemy_hp": enemy_hp
                })

                # Kampf vorbei?
                if player_hp <= 0 or enemy_hp <= 0:
                    break

            if player_hp <= 0 or enemy_hp <= 0:
                break

        # Ergebnis bestimmen
        if player_hp > 0 and enemy_hp <= 0:
            result = "WIN"
        elif player_hp <= 0 and enemy_hp > 0:
            result = "LOSS"
        elif player_hp <= 0 and enemy_hp <= 0:
            result = "DRAW"
        else:
            result = "DRAW"  # Max Runden erreicht

        # Trauma-Check: Ueberlebt mit <10% HP?
        survived_barely = (result == "WIN" and
                           player_hp < player_max_hp * 0.1)

        return {
            "result": result,
            "rounds": rounds,
            "log": battle_log,
            "rewards_eligible": result in ("WIN", "LOSS", "DRAW"),
            "player_hp_remaining": player_hp,
            "enemy_hp_remaining": enemy_hp,
            "is_shiny": is_shiny,
            "survived_barely": survived_barely,
            "enemy_name": enemy.get("name", "Unbekannt"),
            "enemy_type": enemy.get("type", "Stein")
        }

    # ========================================
    # KAMPF-ABLAUF (PVP)
    # ========================================

    def run_pvp_battle(self, player_a: Dict[str, Any],
                       player_b: Dict[str, Any],
                       timestamp: int = None) -> Dict[str, Any]:
        """
        Fuehre einen PVP-Kampf durch (deterministisch fuer P2P).

        Args:
            player_a: Spieler A (lokal)
            player_b: Spieler B (remote)
            timestamp: UTC-Timestamp fuer Seed

        Returns:
            Dict mit: result (WIN/LOSS/DRAW fuer player_a), rounds, log
        """
        seed = self.generate_battle_seed(
            player_a.get("name", "A"),
            player_b.get("name", "B"),
            timestamp
        )

        battle_result = self.run_pve_battle(player_a, player_b, seed)

        # PVP-spezifische Felder
        battle_result["mode"] = "PVP"
        battle_result["seed"] = seed
        battle_result["opponent"] = player_b.get("name", "Unbekannt")

        return battle_result

    # ========================================
    # REWARD-AUSSCHUETTUNG (3 WAEHRUNGEN)
    # ========================================

    @staticmethod
    def distribute_rewards(character: Dict[str, Any],
                           battle_result: Dict[str, Any],
                           floor: int = 1,
                           ascension: int = 1) -> Dict[str, Any]:
        """
        Berechne und verteile Rewards nach Kampf.
        Nutzt das Drei-Waehrungs-System: Gold, Diamonds, Soul Shards.

        Lazy-Load von rewards.py und champion_psyche.py.

        Args:
            character: Charakter-Dict (wird IN-PLACE modifiziert!)
            battle_result: Ergebnis von run_pve_battle/run_pvp_battle
            floor: Aktueller Tower-Floor
            ascension: Aktuelle Ascension-Stufe

        Returns:
            Dict mit: gold_earned, diamonds_earned, soul_shards_earned,
            exp_earned, level_up, items_dropped, psyche_modifiers
        """
        try:
            from rewards import RewardCalculator
        except ImportError:
            # Fallback: Keine Rewards
            return {"gold_earned": 0, "exp_earned": 0, "error": "rewards.py not found"}

        calc = RewardCalculator()
        result_str = battle_result.get("result", "LOSS")

        # PVE oder PVP?
        mode = battle_result.get("mode", "PVE")
        is_shiny = battle_result.get("is_shiny", False)

        if mode == "PVP":
            rewards = calc.calculate_pvp_rewards(
                result=result_str,
                player_floor=floor,
                opponent_floor=battle_result.get("opponent_floor", 1)
            )
        else:
            rewards = calc.calculate_tower_rewards(
                floor=floor,
                result=result_str,
                ascension=ascension,
                is_boss_floor=(floor % 25 == 0)
            )

        # Psyche-Modifikatoren anwenden (Loot/XP-Reduktion bei Erschoepfung)
        psyche_modifiers = {}
        try:
            from champion_psyche import ChampionPsyche
            psyche = ChampionPsyche()
            psyche.load_from_character(character)
            psyche_modifiers = psyche.apply_psyche_modifiers(character, rewards)
        except ImportError:
            pass

        # Waehrungen auf Charakter anwenden
        character["gold"] = character.get("gold", 0) + rewards.get("gold", 0)
        character["diamonds"] = character.get("diamonds", 0) + rewards.get("diamonds", 0)
        character["soul_shards"] = character.get("soul_shards", 0) + rewards.get("soul_shards", 0)
        character["exp"] = character.get("exp", 0) + rewards.get("exp", 0)

        # Scrap bei Verlust
        if result_str == "LOSS" and rewards.get("scrap", 0) > 0:
            character["scrap"] = character.get("scrap", 0) + rewards.get("scrap", 0)

        # Level-Up pruefen
        level_up_info = calc.check_level_up(
            current_exp=character.get("exp", 0),
            current_level=character.get("level", 1)
        )
        if level_up_info.get("leveled_up"):
            char_def = character.get("total_def", character.get("def_base", 25))
            old_max_hp = BattleEngine.calculate_max_hp(character.get("level", 1), char_def)
            character["level"] = level_up_info["new_level"]
            character["exp"] = level_up_info["remaining_exp"]
            # HP wachsen mit Level (+8 pro Level) + DEF-Bonus
            new_max_hp = BattleEngine.calculate_max_hp(character["level"], char_def)
            hp_gain = new_max_hp - old_max_hp
            character["max_hp"] = new_max_hp
            character["hp"] = min(
                character.get("hp", 100) + hp_gain, new_max_hp
            )

        # Erschoepfung erhoehen (nur PVE Tower)
        if mode != "PVP":
            exhaustion = character.get("exhaustion", 0.0)
            character["exhaustion"] = min(100.0, exhaustion + 2.0)

        return {
            "gold_earned": rewards.get("gold", 0),
            "diamonds_earned": rewards.get("diamonds", 0),
            "soul_shards_earned": rewards.get("soul_shards", 0),
            "exp_earned": rewards.get("exp", 0),
            "scrap_earned": rewards.get("scrap", 0),
            "level_up": level_up_info,
            "is_shiny": is_shiny,
            "psyche_modifiers": psyche_modifiers,
            "mode": mode,
            "result": result_str
        }
