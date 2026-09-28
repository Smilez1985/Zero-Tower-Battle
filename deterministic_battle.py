#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Deterministisches Battle-System
============================================================

Stellt sicher, dass PVP-Kaempfe und Weltboss-Raids auf JEDEM
teilnehmenden Geraet exakt dasselbe Ergebnis liefern.

Seed-Zusammensetzung:
  PVP:  SHA256(sorted_macs_by_ip_suffix + ble_handshake_token)
  RAID: SHA256(sorted_macs_by_ip_suffix + ble_handshake_token + boss_id)

IP-Kollisionsvermeidung:
  - Letzte Zahl der IP (10.42.0.X) ist Teil des BLE-Tokens
  - Bei gleicher IP-Endung: neue IP auswuerfeln, neuen Handshake starten
  - IP-Suffix wird im 31-Byte BLE-Beacon uebertragen (Byte 18)

MAC-Sortierung:
  - MACs werden nach ihrem IP-Suffix (aufsteigend) sortiert
  - Dadurch: identische Reihenfolge auf beiden Geraeten
  - Format: "MAC1|MAC2|...|TOKEN" -> SHA256 -> Seed

Alle Berechnungen integer-basiert fuer absolute Reproduzierbarkeit.
"""

import hashlib
import random
import struct
from typing import Dict, Any, List, Tuple, Optional


# =============================================
# IP-Kollisionsvermeidung
# =============================================

def check_ip_collision(local_ip_suffix: int,
                       remote_ip_suffix: int) -> Dict[str, Any]:
    """
    Prueft ob eine IP-Kollision vorliegt und generiert ggf.
    eine neue IP-Endung.

    Das letzte Oktett der IP (10.42.0.X) ist Teil des BLE-Tokens.
    Bei Kollision wird ein neues Suffix gewuerfelt.

    Args:
        local_ip_suffix: Eigenes IP-Suffix (1-254)
        remote_ip_suffix: IP-Suffix des Gegners (aus BLE-Beacon)

    Returns:
        Dict mit:
          collision: bool
          new_suffix: int (nur bei Kollision, sonst None)
          needs_new_handshake: bool
    """
    if local_ip_suffix == remote_ip_suffix:
        # Kollision! Neues Suffix wuerfeln
        # Seed aus beiden MACs damit beide Seiten verschiedene Suffixe bekommen
        import os
        new_suffix = _generate_new_ip_suffix(local_ip_suffix)
        return {
            "collision": True,
            "new_suffix": new_suffix,
            "needs_new_handshake": True,
            "message": f"IP-Kollision! .{local_ip_suffix} == .{remote_ip_suffix} "
                       f"-> Neues Suffix: .{new_suffix}"
        }

    return {
        "collision": False,
        "new_suffix": None,
        "needs_new_handshake": False,
    }


def _generate_new_ip_suffix(old_suffix: int) -> int:
    """
    Generiert ein neues IP-Suffix das vom alten verschieden ist.
    Verwendet os.urandom fuer echte Zufaelligkeit.

    Returns:
        Neues IP-Suffix (1-254, verschieden vom alten)
    """
    import os
    while True:
        raw = os.urandom(1)
        new = (raw[0] % 253) + 1  # 1-254
        if new != old_suffix:
            return new


def resolve_ip_collision_deterministic(local_mac: str,
                                        remote_mac: str,
                                        local_suffix: int,
                                        remote_suffix: int) -> Tuple[int, int]:
    """
    Deterministische IP-Kollisionsaufloesung.
    Beide Seiten koennen das Ergebnis unabhaengig berechnen.

    Regel: Der MAC mit dem kleineren Hashwert behaelt sein Suffix,
    der andere bekommt Suffix + 1 (mod 254, +1 um 0 zu vermeiden).

    Args:
        local_mac: Eigene MAC-Adresse
        remote_mac: MAC des Gegners
        local_suffix: Eigenes aktuelles Suffix
        remote_suffix: Gegner-Suffix (gleich bei Kollision)

    Returns:
        Tuple (neues_local_suffix, neues_remote_suffix)
    """
    if local_suffix != remote_suffix:
        # Keine Kollision
        return local_suffix, remote_suffix

    # Deterministische Entscheidung: wer behaelt das Suffix?
    local_hash = hashlib.sha256(local_mac.encode()).digest()
    remote_hash = hashlib.sha256(remote_mac.encode()).digest()

    if local_hash < remote_hash:
        # Lokal behaelt, Remote bekommt neues
        new_remote = (remote_suffix % 253) + 1
        if new_remote == local_suffix:
            new_remote = (new_remote % 253) + 1
        return local_suffix, new_remote
    else:
        # Remote behaelt, Lokal bekommt neues
        new_local = (local_suffix % 253) + 1
        if new_local == remote_suffix:
            new_local = (new_local % 253) + 1
        return new_local, remote_suffix


# =============================================
# Battle Seed Generator
# =============================================

def generate_pvp_seed(mac_addresses: List[str],
                      ip_suffixes: List[int],
                      handshake_token: bytes) -> int:
    """
    Generiert einen deterministischen Battle-Seed fuer PVP.

    Seed = SHA256(sorted_macs_by_ip_suffix + handshake_token)

    Die MACs werden nach ihrem IP-Suffix (aufsteigend) sortiert,
    sodass beide Geraete die identische Reihenfolge verwenden.

    Args:
        mac_addresses: Liste der MAC-Adressen (mindestens 2)
        ip_suffixes: IP-Suffixe passend zu den MACs (gleiche Reihenfolge)
        handshake_token: BLE-Handshake-Token (aus ECDH, mindestens 16 Bytes)

    Returns:
        Deterministischer Integer-Seed (64-bit)
    """
    if len(mac_addresses) != len(ip_suffixes):
        raise ValueError("mac_addresses und ip_suffixes muessen gleich lang sein")

    if len(mac_addresses) < 2:
        raise ValueError("Mindestens 2 Teilnehmer noetig")

    # MAC-IP-Paare erstellen und nach IP-Suffix aufsteigend sortieren
    pairs = list(zip(ip_suffixes, mac_addresses))
    pairs.sort(key=lambda x: x[0])  # Aufsteigend nach IP-Suffix

    # Seed-String zusammensetzen
    seed_parts = []
    for ip_suffix, mac in pairs:
        # Normalisierte MAC (uppercase, Doppelpunkt-getrennt)
        mac_normalized = mac.upper().replace("-", ":")
        seed_parts.append(f"{mac_normalized}:{ip_suffix}")

    seed_string = "|".join(seed_parts)

    # Handshake-Token anhaengen
    seed_data = seed_string.encode("utf-8") + b"|" + handshake_token

    # SHA256-Hash -> 64-bit Integer
    hash_bytes = hashlib.sha256(seed_data).digest()
    seed_int = int.from_bytes(hash_bytes[:8], byteorder="big")

    return seed_int


def generate_raid_seed(mac_addresses: List[str],
                       ip_suffixes: List[int],
                       handshake_token: bytes,
                       boss_id: str = "") -> int:
    """
    Generiert einen deterministischen Battle-Seed fuer Weltboss-Raids.

    Wie PVP-Seed, aber mit zusaetzlicher Boss-ID fuer Eindeutigkeit.

    Seed = SHA256(sorted_macs_by_ip_suffix + handshake_token + boss_id)

    Args:
        mac_addresses: Liste der MAC-Adressen (3+ Spieler)
        ip_suffixes: IP-Suffixe passend zu den MACs
        handshake_token: BLE-Handshake-Token
        boss_id: Eindeutige Boss-Kennung (z.B. Timestamp)

    Returns:
        Deterministischer Integer-Seed (64-bit)
    """
    if len(mac_addresses) != len(ip_suffixes):
        raise ValueError("mac_addresses und ip_suffixes muessen gleich lang sein")

    # MAC-IP-Paare sortiert nach IP-Suffix
    pairs = list(zip(ip_suffixes, mac_addresses))
    pairs.sort(key=lambda x: x[0])

    seed_parts = []
    for ip_suffix, mac in pairs:
        mac_normalized = mac.upper().replace("-", ":")
        seed_parts.append(f"{mac_normalized}:{ip_suffix}")

    seed_string = "|".join(seed_parts)

    # Boss-ID anhaengen
    seed_data = (
        seed_string.encode("utf-8") + b"|"
        + handshake_token + b"|"
        + boss_id.encode("utf-8")
    )

    hash_bytes = hashlib.sha256(seed_data).digest()
    seed_int = int.from_bytes(hash_bytes[:8], byteorder="big")

    return seed_int


# =============================================
# Deterministische Battle-Engine
# =============================================

class DeterministicBattle:
    """
    Fuehrt einen Kampf mit einem gemeinsamen Seed durch.
    Ergebnis ist auf jedem Geraet identisch.

    Alle Berechnungen integer-basiert (kein float!).
    """

    MAX_ROUNDS = 30

    # Balance-Konstanten - MUESSEN mit engine/battle_engine.py uebereinstimmen,
    # sonst rechnen PVE und PVP unterschiedlich (Bug bis 2026-09).
    MIN_DAMAGE = 3           # Minimum-Schaden pro Treffer
    LEVEL_AMP_PER_LEVEL = 5  # +5 % Schaden pro Level (ab Level 2)
    DEFENSE_SOFTCAP = 50     # DEF/(DEF+50) = asymptotische Reduktion
    HP_PER_LEVEL = 17        # Max-HP-Wachstum pro Level
    HP_BASE = 100            # Basis-HP auf Level 1
    HP_DEF_FACTOR = 3        # HP-Bonus = DEF x 3 // 2
    SPD_EXTRA_PER_POINT = 15 # Promille Extra-Angriff pro SPD-Punkt Vorsprung
    SPD_EXTRA_CAP = 450      # max. 45 % Chance auf Extra-Angriff

    def __init__(self, seed: int):
        """
        Args:
            seed: Gemeinsamer Seed (aus generate_pvp_seed/generate_raid_seed)
        """
        self._rng = random.Random(seed)
        self._seed = seed

    def run_pvp(self, player_a: Dict[str, Any],
                player_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deterministischer PVP-Kampf.

        Beide Seiten fuehren diesen Kampf mit demselben Seed aus
        und erhalten exakt dasselbe Ergebnis.

        Args:
            player_a: Erster Spieler (sortiert nach IP-Suffix: kleineres IP = A)
            player_b: Zweiter Spieler

        Returns:
            Dict mit: winner, rounds, log, damage_dealt, seed
        """
        # Stats extrahieren (integer!)
        a_hp = self._get_effective_hp(player_a)
        b_hp = self._get_effective_hp(player_b)
        a_max_hp = a_hp
        b_max_hp = b_hp

        a_atk = player_a.get("total_atk", 25)
        a_def = player_a.get("total_def", 25)
        a_spd = player_a.get("total_spd", 25)
        a_luk = player_a.get("total_luk", 15)
        a_type = player_a.get("type", player_a.get("klasse_type", "Stein"))
        a_level = player_a.get("level", 1)

        b_atk = player_b.get("total_atk", 25)
        b_def = player_b.get("total_def", 25)
        b_spd = player_b.get("total_spd", 25)
        b_luk = player_b.get("total_luk", 15)
        b_type = player_b.get("type", player_b.get("klasse_type", "Stein"))
        b_level = player_b.get("level", 1)

        # Typ-Vorteil berechnen
        a_type_factor = self._type_factor(a_type, b_type)
        b_type_factor = self._type_factor(b_type, a_type)

        # Kampf-Log
        battle_log = []
        rounds = 0

        for rnd in range(1, self.MAX_ROUNDS + 1):
            rounds = rnd

            # Initiative: hoechster SPD geht zuerst
            # Bei Gleichstand: deterministisch per Seed
            a_goes_first = a_spd > b_spd
            if a_spd == b_spd:
                a_goes_first = self._rng.randint(0, 1) == 0

            if a_goes_first:
                order = [
                    ("A", a_atk, a_luk, a_level, a_type_factor, "B", a_spd, b_spd),
                    ("B", b_atk, b_luk, b_level, b_type_factor, "A", b_spd, a_spd),
                ]
            else:
                order = [
                    ("B", b_atk, b_luk, b_level, b_type_factor, "A", b_spd, a_spd),
                    ("A", a_atk, a_luk, a_level, a_type_factor, "B", a_spd, b_spd),
                ]

            for (attacker_id, atk, luk, level, type_fac, defender_id,
                 own_spd, foe_spd) in order:
                if attacker_id == "A":
                    defender_def = b_def
                    defender_hp_ref = "b_hp"
                else:
                    defender_def = a_def
                    defender_hp_ref = "a_hp"

                # SPD-Vorteil: Chance auf einen Extra-Angriff.
                # Ohne diese Mechanik entscheidet SPD nur die Zugreihenfolge
                # und ist damit praktisch wertlos -> der Schurke (SPD 40)
                # verlor systematisch. Chance = SPD-Differenz x 1,5 %,
                # gedeckelt bei 45 %.
                extra_attacks = 1
                spd_diff = own_spd - foe_spd
                if spd_diff > 0:
                    extra_chance = min(self.SPD_EXTRA_CAP,
                                       spd_diff * self.SPD_EXTRA_PER_POINT)
                    if self._rng.randint(1, 1000) <= extra_chance:
                        extra_attacks = 2

                for _hit in range(extra_attacks):
                    # Schaden berechnen (integer!)
                    damage = self._calc_damage(atk, defender_def, level,
                                               type_fac, luk)

                    # Anwenden
                    if defender_hp_ref == "a_hp":
                        a_hp = max(0, a_hp - damage)
                    else:
                        b_hp = max(0, b_hp - damage)

                    # Krit-Heuristik an die V2-Formel angepasst (vorher basierte
                    # sie auf der alten, level-multiplikativen Rohschadensformel).
                    _amp = 100 + max(0, level - 1) * self.LEVEL_AMP_PER_LEVEL
                    is_crit = damage > (atk * _amp // 100) * type_fac // 100

                    battle_log.append({
                        "round": rnd,
                        "attacker": attacker_id,
                        "damage": damage,
                        "crit": is_crit,
                        "extra_attack": _hit > 0,
                        "a_hp": a_hp,
                        "b_hp": b_hp,
                    })

                    # KO-Check
                    if a_hp <= 0 or b_hp <= 0:
                        break

                # KO-Check
                if a_hp <= 0 or b_hp <= 0:
                    break

            if a_hp <= 0 or b_hp <= 0:
                break

        # Ergebnis
        if a_hp <= 0 and b_hp <= 0:
            winner = "DRAW"
        elif a_hp <= 0:
            winner = "B"
        elif b_hp <= 0:
            winner = "A"
        else:
            # Timeout: wer mehr % HP hat gewinnt
            a_pct = a_hp * 100 // a_max_hp
            b_pct = b_hp * 100 // b_max_hp
            if a_pct > b_pct:
                winner = "A"
            elif b_pct > a_pct:
                winner = "B"
            else:
                winner = "DRAW"

        return {
            "seed": self._seed,
            "winner": winner,
            "rounds": rounds,
            "a_hp_remaining": a_hp,
            "b_hp_remaining": b_hp,
            "a_max_hp": a_max_hp,
            "b_max_hp": b_max_hp,
            "log": battle_log,
            "result": "WIN" if winner != "DRAW" else "DRAW",
        }

    def run_raid(self, players: List[Dict[str, Any]],
                 boss: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deterministischer Weltboss-Raid.

        Alle Spieler greifen den Boss rundenweise an.
        Boss greift einen zufaelligen Spieler pro Runde an.
        Ergebnis ist auf jedem Geraet identisch.

        Args:
            players: Liste der Spieler-Dicts
            boss: Weltboss-Dict (aus monster_generator.generate_worldboss)

        Returns:
            Dict mit: boss_defeated, rounds, survivors, damage_dealt, rewards
        """
        boss_hp = boss.get("hp", 5000)
        boss_max_hp = boss_hp
        boss_atk = boss.get("total_atk", 40)
        boss_def = boss.get("total_def", 30)
        boss_type = boss.get("type", "Stein")

        # Spieler-Status
        player_states = []
        for i, p in enumerate(players):
            player_states.append({
                "index": i,
                "name": p.get("name", f"Spieler{i+1}"),
                "hp": self._get_effective_hp(p),
                "max_hp": self._get_effective_hp(p),
                "atk": p.get("total_atk", 25),
                "def": p.get("total_def", 25),
                "spd": p.get("total_spd", 25),
                "luk": p.get("total_luk", 15),
                "level": p.get("level", 1),
                "type": p.get("type", p.get("klasse_type", "Stein")),
                "alive": True,
                "damage_dealt": 0,
            })

        raid_log = []
        rounds = 0
        max_rounds = 50

        for rnd in range(1, max_rounds + 1):
            rounds = rnd
            alive_players = [ps for ps in player_states if ps["alive"]]

            if not alive_players:
                break

            # Spieler greifen an (sortiert nach SPD, deterministisch)
            alive_players.sort(key=lambda x: (-x["spd"], x["index"]))

            for ps in alive_players:
                type_fac = self._type_factor(ps["type"], boss_type)
                damage = self._calc_damage(ps["atk"], boss_def, ps["level"],
                                           type_fac, ps["luk"])
                boss_hp = max(0, boss_hp - damage)
                ps["damage_dealt"] += damage

                raid_log.append({
                    "round": rnd,
                    "attacker": ps["name"],
                    "target": "BOSS",
                    "damage": damage,
                    "boss_hp": boss_hp,
                })

                if boss_hp <= 0:
                    break

            if boss_hp <= 0:
                break

            # Boss greift zufaelligen lebenden Spieler an
            if alive_players:
                target_idx = self._rng.randint(0, len(alive_players) - 1)
                target = alive_players[target_idx]
                boss_damage = self._calc_damage(boss_atk, target["def"],
                                                boss.get("level", 1),
                                                self._type_factor(boss_type, target["type"]),
                                                boss.get("total_luk", 10))
                target["hp"] = max(0, target["hp"] - boss_damage)

                if target["hp"] <= 0:
                    target["alive"] = False

                raid_log.append({
                    "round": rnd,
                    "attacker": "BOSS",
                    "target": target["name"],
                    "damage": boss_damage,
                    "target_hp": target["hp"],
                })

        boss_defeated = boss_hp <= 0
        survivors = [ps for ps in player_states if ps["alive"]]

        # Schadensranking
        damage_ranking = sorted(player_states,
                                key=lambda x: x["damage_dealt"],
                                reverse=True)

        return {
            "seed": self._seed,
            "boss_defeated": boss_defeated,
            "rounds": rounds,
            "boss_hp_remaining": boss_hp,
            "boss_max_hp": boss_max_hp,
            "survivors": len(survivors),
            "total_players": len(players),
            "damage_ranking": [
                {"name": ps["name"], "damage": ps["damage_dealt"],
                 "alive": ps["alive"]}
                for ps in damage_ranking
            ],
            "log": raid_log,
            # Rewards (nur bei Sieg)
            "rewards_eligible": boss_defeated,
            "gold_reward": boss.get("gold_reward", 0) if boss_defeated else 0,
            "diamond_reward": boss.get("diamond_reward", 0) if boss_defeated else 0,
            "xp_reward": boss.get("xp_reward", 0) if boss_defeated else 0,
        }

    # ---- Hilfsmethoden (integer!) ----

    @staticmethod
    def _get_effective_hp(entity: Dict[str, Any]) -> int:
        """HP berechnen. Fallback auf Level-basierte Berechnung."""
        hp = entity.get("hp", 0)
        if hp > 0:
            return hp
        level = entity.get("level", 1)
        total_def = entity.get("total_def", entity.get("def_base", 0))
        # Identisch zu BattleEngine.calculate_max_hp()
        return (DeterministicBattle.HP_BASE
                + max(0, level - 1) * DeterministicBattle.HP_PER_LEVEL
                + total_def * DeterministicBattle.HP_DEF_FACTOR // 2)

    def _calc_damage(self, atk: int, defender_def: int, level: int,
                     type_factor: int, luk: int) -> int:
        """
        Integer-basierte Schadensberechnung (V2, identisch zu BattleEngine).

        Formel:
          1. Raw       = ATK x (100 + (Level-1) x 5) // 100
          2. DefPct    = DEF x 100 // (DEF + DEFENSE_SOFTCAP)   [asymptotisch]
          3. Schaden   = max(MIN_DAMAGE, Raw x (100 - DefPct) // 100)
          4. Varianz   = 90-110 %
          5. Typ       = x1.25 / x0.8
          6. Krit      = LUK x 5 / 1000 Chance -> x2

        WICHTIG (Fix 2026-09): Frueher skalierte ATK mit `x Level`, die
        Verteidigung war aber ein fester Abzug (`DEF x 50 // 100`). Dadurch
        wurde DEF ab ca. Level 8 wirkungslos, Kaempfe endeten nach einem
        einzigen Schlag und der Gewinner stand allein ueber SPD fest.
        Die asymptotische Reduktion DEF/(DEF+K) haelt Verteidigung auf jedem
        Level relevant, ohne je 100 % zu erreichen.

        Args:
            atk: Angreifer ATK
            defender_def: Verteidiger DEF
            level: Angreifer Level
            type_factor: Typ-Faktor (100=neutral, 125=Vorteil, 80=Nachteil)
            luk: Angreifer LUK (fuer Krit-Chance)

        Returns:
            Schaden (integer, mindestens MIN_DAMAGE)
        """
        # 1. Basisschaden: ATK ist Hauptfaktor, Level verstaerkt um +5 %/Level
        level_amp = 100 + max(0, level - 1) * self.LEVEL_AMP_PER_LEVEL
        raw = atk * level_amp // 100

        # 2. Verteidigung: asymptotisch, nie 100 %
        defense_pct = defender_def * 100 // (defender_def + self.DEFENSE_SOFTCAP)
        base_damage = max(self.MIN_DAMAGE, raw * (100 - defense_pct) // 100)

        # 3. Varianz: 90-110 % (deterministisch!)
        variance = self._rng.randint(90, 110)
        base_damage = max(self.MIN_DAMAGE, base_damage * variance // 100)

        # 4. Typ-Faktor anwenden (100=neutral)
        base_damage = base_damage * type_factor // 100

        # 5. Krit-Check (LUK x 5 / 1000 = Krit-Chance)
        crit_roll = self._rng.randint(1, 1000)
        if crit_roll <= luk * 5:
            base_damage = base_damage * 2  # Krit = Doppelschaden

        return max(self.MIN_DAMAGE, base_damage)

    @staticmethod
    def _type_factor(attacker_type: str, defender_type: str) -> int:
        """
        Typ-Vorteil als Integer-Faktor.
        Stein > Schere > Papier > Stein (Schere-Stein-Papier)

        Returns:
            125 = Vorteil (x1.25)
            80  = Nachteil (x0.80)
            100 = Neutral
        """
        advantages = {
            "Stein": "Schere",
            "Schere": "Papier",
            "Papier": "Stein",
        }

        if advantages.get(attacker_type) == defender_type:
            return 125  # Vorteil
        elif advantages.get(defender_type) == attacker_type:
            return 80   # Nachteil
        else:
            return 100  # Neutral


# =============================================
# Handshake-Token Integration
# =============================================

def create_handshake_token_from_ecdh(session_key: bytes,
                                      local_mac: str,
                                      remote_mac: str,
                                      local_ip_suffix: int,
                                      remote_ip_suffix: int) -> bytes:
    """
    Erstellt einen Handshake-Token aus dem ECDH-Session-Key
    und den Verbindungsdaten.

    Wird verwendet um den Battle-Seed zu generieren.

    Args:
        session_key: ECDH-abgeleiteter Session-Key (32 Bytes)
        local_mac: Eigene MAC-Adresse
        remote_mac: MAC des Gegners
        local_ip_suffix: Eigenes IP-Suffix
        remote_ip_suffix: IP-Suffix des Gegners

    Returns:
        32-Byte Handshake-Token
    """
    # Kombiniere alle Eingaben deterministisch
    token_data = (
        session_key
        + local_mac.upper().encode()
        + remote_mac.upper().encode()
        + struct.pack(">BB", local_ip_suffix, remote_ip_suffix)
    )

    return hashlib.sha256(token_data).digest()


# =============================================
# Test / Demo
# =============================================

if __name__ == "__main__":
    print("=" * 60)
    print("  DETERMINISTISCHES BATTLE-SYSTEM TEST")
    print("=" * 60)

    # Test-Daten
    mac_a = "AA:BB:CC:DD:EE:01"
    mac_b = "AA:BB:CC:DD:EE:02"
    ip_a = 10
    ip_b = 20
    token = b"test_handshake_token_1234567890"

    # 1. IP-Kollisionstest
    print("\n  1. IP-Kollisionstest:")
    result = check_ip_collision(10, 20)
    print(f"     .10 vs .20: Kollision={result['collision']}")
    result = check_ip_collision(10, 10)
    print(f"     .10 vs .10: Kollision={result['collision']}, "
          f"Neues Suffix={result['new_suffix']}")

    # Deterministische Aufloesung
    new_a, new_b = resolve_ip_collision_deterministic(mac_a, mac_b, 10, 10)
    print(f"     Deterministisch: A=.{new_a}, B=.{new_b}")

    # 2. Seed-Generierung
    print("\n  2. PVP-Seed (identisch auf beiden Seiten):")
    seed1 = generate_pvp_seed([mac_a, mac_b], [ip_a, ip_b], token)
    seed2 = generate_pvp_seed([mac_b, mac_a], [ip_b, ip_a], token)  # Umgekehrte Reihenfolge!
    print(f"     Seite A: {seed1}")
    print(f"     Seite B: {seed2}")
    print(f"     Identisch: {seed1 == seed2}")

    # 3. PVP-Kampf (identisch auf beiden Seiten)
    print("\n  3. PVP-Kampf (deterministisch):")
    player_a = {
        "name": "Krieger", "type": "Stein", "level": 5,
        "total_atk": 28, "total_def": 42, "total_spd": 20, "total_luk": 17,
        "hp": 130,
    }
    player_b = {
        "name": "Magier", "type": "Papier", "level": 5,
        "total_atk": 50, "total_def": 12, "total_spd": 23, "total_luk": 27,
        "hp": 110,
    }

    battle1 = DeterministicBattle(seed1)
    result1 = battle1.run_pvp(player_a, player_b)

    battle2 = DeterministicBattle(seed2)
    result2 = battle2.run_pvp(player_a, player_b)

    print(f"     Seite A: Winner={result1['winner']}, "
          f"Runden={result1['rounds']}, "
          f"A-HP={result1['a_hp_remaining']}, B-HP={result1['b_hp_remaining']}")
    print(f"     Seite B: Winner={result2['winner']}, "
          f"Runden={result2['rounds']}, "
          f"A-HP={result2['a_hp_remaining']}, B-HP={result2['b_hp_remaining']}")
    identical = (result1['winner'] == result2['winner'] and
                 result1['rounds'] == result2['rounds'])
    print(f"     Identisch: {identical}")

    # 4. Raid-Seed
    print("\n  4. Raid-Seed (3 Spieler):")
    mac_c = "AA:BB:CC:DD:EE:03"
    ip_c = 30
    raid_seed = generate_raid_seed(
        [mac_a, mac_b, mac_c], [ip_a, ip_b, ip_c],
        token, boss_id="worldboss_001"
    )
    print(f"     Raid-Seed: {raid_seed}")

    # 5. Raid-Kampf
    print("\n  5. Raid-Kampf:")
    from monster_generator import generate_worldboss
    players = [player_a, player_b, {
        "name": "Schurke", "type": "Schere", "level": 5,
        "total_atk": 30, "total_def": 18, "total_spd": 45, "total_luk": 22,
        "hp": 120,
        "base_atk": 25, "base_def": 15, "base_spd": 40, "base_luk": 20,
        "extra_atk": 5, "extra_def": 3, "extra_spd": 5, "extra_luk": 2,
    }]

    boss = generate_worldboss(players, trigger_floor=50)
    raid_battle = DeterministicBattle(raid_seed)
    raid_result = raid_battle.run_raid(players, boss)
    print(f"     Boss besiegt: {raid_result['boss_defeated']}")
    print(f"     Runden: {raid_result['rounds']}")
    print(f"     Ueberlebende: {raid_result['survivors']}/{raid_result['total_players']}")
    print(f"     Schadensranking:")
    for entry in raid_result["damage_ranking"]:
        alive_str = " [OK]" if entry["alive"] else " [KO]"
        print(f"       {entry['name']:15s}: {entry['damage']:6d} DMG{alive_str}")
    if raid_result["rewards_eligible"]:
        print(f"     Rewards: {raid_result['gold_reward']} Gold, "
              f"{raid_result['diamond_reward']} Diamanten, "
              f"{raid_result['xp_reward']} XP")
