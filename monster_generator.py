#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Prozeduraler Monster-Generator
==========================================================

Erzeugt unendlich viele verschiedene Monster mit:
  - Namensgenerierung aus Silben-Kombination (deterministisch)
  - Stat-Skalierung angepasst an Spieler-Level UND Klasse
  - Typ-System (Stein/Schere/Papier) mit strategischer Verteilung
  - Spezialfaehigkeiten basierend auf Floor-Bereich (Biome)
  - Boss-Monster alle 25 Floors (1.5x Stats, 2x HP)
  - Weltbosse skaliert auf Spieleranzahl und Quersumme der addierten Stats

Alle Berechnungen integer-basiert fuer P2P-Konsistenz.
"""

import hashlib
import random
from typing import Dict, Any, List, Optional


# =============================================
# Silben-Pools fuer Namensgenerierung
# =============================================

# Praefix-Silben (Anfang des Namens)
_PREFIXES = [
    "Gor", "Kra", "Zel", "Vor", "Dra", "Nex", "Sha", "Thr",
    "Fen", "Mor", "Kal", "Zer", "Bra", "Gri", "Nar", "Sar",
    "Dul", "Fal", "Hel", "Isk", "Jor", "Lun", "Mal", "Oni",
    "Pyr", "Rav", "Sko", "Tor", "Umb", "Val", "Wyr", "Xar",
    "Yth", "Zar", "Ash", "Bel", "Cyr", "Dun", "Esk", "Fro",
    "Gul", "Hex", "Ilk", "Jar", "Kol", "Lyr", "Mur", "Nul",
]

# Mittlere Silben (optional, fuer laengere Namen)
_MIDDLES = [
    "ath", "gor", "mar", "ven", "dra", "kel", "nor", "sha",
    "tor", "zul", "kan", "ral", "mir", "oth", "gra", "fen",
    "bal", "dor", "isk", "lun", "nar", "pyr", "sar", "val",
    "wyr", "zel", "ark", "bel", "cyr", "dul", "esk", "fal",
]

# Suffix-Silben (Ende des Namens)
_SUFFIXES = [
    "ax", "or", "is", "ul", "on", "ar", "ek", "im",
    "os", "ur", "an", "el", "ik", "om", "us", "en",
    "ak", "ol", "in", "um", "as", "er", "il", "op",
    "ux", "at", "ov", "iz", "uk", "ot", "alf", "orn",
]

# Titel fuer Bosse
_BOSS_TITLES = [
    "der Unerbittliche", "der Verzweifelte", "der Ewige",
    "der Verdorbene", "der Ruhelose", "der Entfesselte",
    "der Verfluchte", "der Uralte", "der Tosende",
    "der Verschlingende", "der Finstere", "der Brennende",
    "der Gefrorene", "der Stille", "der Wuetende",
    "der Zerbrecher", "der Schattenwandler", "der Traumfresser",
]

# Weltboss-Titel
_WORLDBOSS_TITLES = [
    "Erzfeind der Tuerme", "Verschlinger der Welten",
    "Herrscher des Abgrunds", "Zerstoerer der Hoffnung",
    "Schatten des Endes", "Wille der Finsternis",
    "Stimme des Chaos", "Auge der Leere",
]

# Typ-spezifische Beschreibungen
_TYPE_DESCRIPTORS = {
    "Stein": ["Erd", "Fels", "Granit", "Eisen", "Kristall", "Basalt", "Obsidian", "Magma"],
    "Schere": ["Schatten", "Klinge", "Dorn", "Gift", "Nebel", "Wind", "Blitz", "Stahl"],
    "Papier": ["Flamm", "Frost", "Aether", "Arkane", "Seelen", "Geist", "Licht", "Runen"],
}

# Biome nach Floor-Bereich
_BIOMES = {
    (1, 24): {"name": "Keller", "hp_mod": 100, "atk_mod": 100},
    (25, 49): {"name": "Katakomben", "hp_mod": 110, "atk_mod": 105},
    (50, 99): {"name": "Hoehlen", "hp_mod": 120, "atk_mod": 110},
    (100, 199): {"name": "Vulkan", "hp_mod": 135, "atk_mod": 120},
    (200, 399): {"name": "Eiswueste", "hp_mod": 150, "atk_mod": 130},
    (400, 699): {"name": "Schattenreich", "hp_mod": 170, "atk_mod": 145},
    (700, 999): {"name": "Aethersturm", "hp_mod": 200, "atk_mod": 165},
    (1000, 99999): {"name": "Endlosturm", "hp_mod": 250, "atk_mod": 200},
}


def _get_biome(floor: int) -> Dict[str, Any]:
    """Biome fuer einen Floor bestimmen."""
    for (low, high), biome in _BIOMES.items():
        if low <= floor <= high:
            return biome
    return {"name": "Unbekannt", "hp_mod": 100, "atk_mod": 100}


def _digit_sum(n: int) -> int:
    """Quersumme einer Zahl berechnen (rekursiv bis einstellig)."""
    n = abs(n)
    while n >= 10:
        n = sum(int(d) for d in str(n))
    return n


# =============================================
# Monster Name Generator
# =============================================

def generate_monster_name(floor: int, index: int = 0,
                          monster_type: str = "Stein",
                          is_boss: bool = False) -> str:
    """
    Deterministisch einen einzigartigen Monsternamen generieren.

    Verwendet Floor + Index als Seed fuer reproduzierbare Namen.
    Silben-Kombination ergibt Millionen moeglicher Kombinationen:
      48 Prefixes x 32 Middles x 32 Suffixes = 49.152 Basisnamen
      x 8 Typ-Deskriptoren = 393.216 Varianten
      x floor-basierte Variation = praktisch unendlich

    Args:
        floor: Aktuelles Stockwerk
        index: Laufender Index (fuer mehrere Monster pro Floor)
        monster_type: Stein/Schere/Papier
        is_boss: Ob Boss-Titel angehaengt werden soll

    Returns:
        Einzigartiger Monstername
    """
    # Deterministischer Seed aus Floor + Index
    seed = floor * 7919 + index * 3571
    rng = random.Random(seed)

    # Typ-Deskriptor waehlen
    descriptors = _TYPE_DESCRIPTORS.get(monster_type, _TYPE_DESCRIPTORS["Stein"])
    descriptor = descriptors[rng.randint(0, len(descriptors) - 1)]

    # Silben kombinieren
    prefix = _PREFIXES[rng.randint(0, len(_PREFIXES) - 1)]
    suffix = _SUFFIXES[rng.randint(0, len(_SUFFIXES) - 1)]

    # Mittlere Silbe nur bei jedem 3. Monster (Varianz in Namenlaenge)
    if rng.randint(0, 2) == 0:
        middle = _MIDDLES[rng.randint(0, len(_MIDDLES) - 1)]
        base_name = f"{prefix}{middle}{suffix}"
    else:
        base_name = f"{prefix}{suffix}"

    # Zusammensetzen: "Flamm-Gorax" oder "Schatten-Zelmaris"
    full_name = f"{descriptor}-{base_name}"

    # Boss-Titel
    if is_boss:
        title = _BOSS_TITLES[rng.randint(0, len(_BOSS_TITLES) - 1)]
        full_name = f"{full_name}, {title}"

    return full_name


# =============================================
# PVE Monster Generator
# =============================================

def generate_pve_monster(floor: int, player: Dict[str, Any],
                         index: int = 0) -> Dict[str, Any]:
    """
    Generiert einen PVE-Gegner angepasst an Floor UND Spieler-Stats.

    Skalierung:
      - Basis-Stats aus Floor-Nummer (linear + Biome-Modifier)
      - Anpassung an Spieler-Level (Monster waechst mit)
      - Typ-Wahl basierend auf Floor mit strategischer Verteilung:
        60% neutral, 20% Vorteil fuer Monster, 20% Vorteil fuer Spieler
      - HP skaliert mit Floor-Bereich (Biome)
      - Boss alle 25 Floors: 1.5x Stats, 2x HP, Boss-Titel

    Alle Werte integer-basiert.

    Args:
        floor: Aktuelles Stockwerk (1-unendlich)
        player: Spieler-Dict mit klasse, level, base_atk, extra_atk, etc.
        index: Index fuer mehrere Monster pro Floor

    Returns:
        Vollstaendiges Monster-Dict
    """
    seed = floor * 7919 + index * 3571
    rng = random.Random(seed)

    player_level = player.get("level", 1)
    player_class = player.get("klasse", "Krieger")

    # ---- Typ-Zuweisung ----
    # Spieler-Typ bestimmen
    class_to_type = {
        "Krieger": "Stein",
        "Schurke": "Schere",
        "Magier": "Papier"
    }
    player_type = class_to_type.get(player_class, "Stein")

    # Typ-Advantage-Map: welcher Typ schlaegt wen
    advantage_map = {
        "Stein": "Schere",   # Stein schlaegt Schere
        "Schere": "Papier",  # Schere schlaegt Papier
        "Papier": "Stein"    # Papier schlaegt Stein
    }
    # Welcher Typ ist schwach gegen den Spieler
    weak_to_player = advantage_map.get(player_type, "Schere")
    # Welcher Typ ist stark gegen den Spieler
    types_list = ["Stein", "Schere", "Papier"]
    strong_vs_player = [t for t in types_list if advantage_map.get(t) == player_type]
    strong_vs_player = strong_vs_player[0] if strong_vs_player else "Stein"

    # Strategische Verteilung: 40% neutral, 35% Vorteil Monster, 25% Vorteil Spieler
    roll = rng.randint(1, 100)
    if roll <= 40:
        # Neutral (gleicher Typ oder der schwache)
        enemy_type = player_type
    elif roll <= 75:
        # Monster hat Vorteil (herausfordernd)
        enemy_type = strong_vs_player
    else:
        # Spieler hat Vorteil (Belohnung)
        enemy_type = weak_to_player

    # ---- Biome-Modifier ----
    biome = _get_biome(floor)

    # ---- Basis-Stats aus Floor + Spieler-Level ----
    # V2 BALANCED: floor_factor waechst moderat-aggressiv
    # Idle-Wall: ~Floor 20-25 (ohne Equipment/Management)
    # F1=5 | F10=9 | F15=11 | F20=13 | F30=17 | F50=25 | F100=45
    floor_factor = 5 + floor * 2 // 5
    # Spieler-Anpassung: Monster-Stats orientieren sich am Spieler-Level
    level_factor = max(1, player_level * 3 // 2)

    # Effektive Spieler-Stats als Referenz (NUR Basis+Extra, KEIN Equipment)
    p_atk = player.get("base_atk", player.get("atk_base", 25)) + \
            player.get("extra_atk", player.get("atk_extra", 0))
    p_def = player.get("base_def", player.get("def_base", 25)) + \
            player.get("extra_def", player.get("def_extra", 0))
    p_spd = player.get("base_spd", player.get("spd_base", 25)) + \
            player.get("extra_spd", player.get("spd_extra", 0))
    p_luk = player.get("base_luk", player.get("luk_base", 25)) + \
            player.get("extra_luk", player.get("luk_extra", 0))

    # V2 BALANCED: Hybrides Monster-Stat-System
    #
    # PROBLEM: Wenn Monster-ATK auf Spieler-ATK basiert, haben
    # Glaskanonen (Magier ATK 45) übermächtige Gegner (ATK 42).
    # Mit DEF 10 stirbt der Magier sofort.
    #
    # LÖSUNG: Monster-ANGRIFF ist Floor-basiert (gleich für alle Klassen)
    #         Monster-VERTEIDIGUNG passt sich dem Spieler an (Blend)
    #         Monster-SPD/LUK passen sich an (Blend)
    #
    # So gilt: Krieger tankt gut (hohe DEF vs floor-ATK)
    #          Magier killt schnell (hohe ATK vs angepasste DEF)
    #          Schurke critted oft (hoher LUK) und ist schnell
    balanced_ref = 25  # Durchschnitt aus 100 Punkte / 4 Attribute
    # Blend: 40% Spieler + 60% Durchschnitt → moderierte Konvergenz
    # Krieger-Monster: DEF 31 (statt 32) → etwas leichter zu toeten
    # Schurke-Monster: DEF 21 (statt 20) → minimal schwerer
    # Magier-Monster: DEF 19 (statt 17) → etwas schwerer zu toeten
    blend_def = (p_def * 40 + balanced_ref * 60) // 100
    blend_spd = (p_spd * 40 + balanced_ref * 60) // 100
    blend_luk = (p_luk * 40 + balanced_ref * 60) // 100

    stat_ratio = rng.randint(70, 95)

    # ATK: Partielles Blend (30%) + Klassen-Identitaets-Modifier
    # Basis-Blend gleich fuer alle, dann klassenspezifische Anpassung:
    #   Krieger (Tank): Monster schlagen SCHWAECHER → ueberlebt am laengsten
    #   Schurke (Speed): Neutral
    #   Magier (Glaskanone): Monster schlagen STAERKER → stirbt am schnellsten
    # Erzeugt natuerliche Idle-Wall-Staffelung: Krieger > Schurke > Magier
    blend_atk = (p_atk + balanced_ref) // 2

    # ATK: Blend, OHNE kuenstlichen Klassen-Modifier auf Monster-ATK
    # Klassenidentitaet entsteht ueber Monster-HP-Kompensation (siehe unten)
    raw_atk = (blend_atk * 30 // 100) + floor_factor + 3 + rng.randint(-3, 5)

    # DEF: Spieler-angepasst (Blend). Magier-Monster haben weniger DEF,
    # Krieger-Monster haben mehr DEF → Magier killt schneller.
    raw_def = (blend_def * stat_ratio // 100) + floor_factor + rng.randint(-3, 5)

    # SPD/LUK: Blend-basiert
    raw_spd = (blend_spd * stat_ratio // 100) + floor_factor + rng.randint(-3, 5)
    raw_luk = (blend_luk * stat_ratio // 100) + floor_factor // 2 + rng.randint(-2, 3)

    # Typ-spezifische Gewichtung
    if enemy_type == "Stein":
        # Stein = hohe DEF, moderate ATK
        raw_def = raw_def * 120 // 100
        raw_atk = raw_atk * 95 // 100
    elif enemy_type == "Schere":
        # Schere = hohe SPD, hohe ATK
        raw_spd = raw_spd * 115 // 100
        raw_atk = raw_atk * 110 // 100
    elif enemy_type == "Papier":
        # Papier = hohe ATK (Magie), hohe LUK
        raw_atk = raw_atk * 115 // 100
        raw_luk = raw_luk * 120 // 100

    # Biome-ATK-Modifier anwenden
    raw_atk = raw_atk * biome["atk_mod"] // 100

    # V2 BALANCED: KEIN oberer Cap mehr! Monster duerfen mit Floors wachsen.
    # Nur Minimum-Werte um kaputte Kaempfe zu verhindern.
    total_atk = max(5, raw_atk)
    total_def = max(5, raw_def)
    total_spd = max(5, raw_spd)
    total_luk = max(3, raw_luk)

    # ---- HP berechnen ----
    # V2 BALANCED: Monster-HP wachsen mit Floor + Spieler-ATK-Kompensation
    # Monster-HP KOMPENSATION basierend auf Glaskanonen-Faktor
    # Je hoeher ATK vs DEF, desto mehr HP haben Monster
    # → Glaskanone: Burst wird durch laengere Kaempfe neutralisiert
    # → Tank: weniger HP = kuerzere Kaempfe = ATK-Nachteil ausgeglichen
    # Glaskanonen-Kompensation: ATK-DEF-Differenz → mehr Monster-HP
    # Glaskanonen-Kompensation auf Monster-HP:
    # Krieger (ATK 25, DEF 40): gc=0  → Monster-HP ×100% (Tank-Vorteil!)
    # Schurke (ATK 25, DEF 15): gc=10 → Monster-HP ×107% (leicht mehr)
    # Magier  (ATK 45, DEF 10): gc=35 → Monster-HP ×126% (signifikant mehr!)
    # → Magier-Burst wird durch laengere Kaempfe neutralisiert
    # → Tank-Ausdauer (hohe DEF) wird ueber mehr Runden belohnt
    base_hp = 45 + floor * 3 + level_factor * 3
    glass_cannon_factor = max(0, p_atk - p_def)
    hp_compensation = 100 + glass_cannon_factor * 2 // 3
    base_hp = base_hp * hp_compensation // 100
    hp = base_hp * biome["hp_mod"] // 100
    # Varianz: +-10%
    hp = hp + rng.randint(-hp // 10, hp // 10)
    hp = max(30, hp)

    # ---- Monster-Level ----
    monster_level = max(1, (floor + 4) // 5)

    # ---- Boss Check ----
    is_boss = (floor % 25 == 0) and (floor > 0)
    if is_boss:
        # V2 BALANCED: Boss-Spike reduziert (war 1.5x/2.0x, jetzt 1.35x/1.75x)
        # Bosse sind herausfordernd, aber nicht unmoeglicher Spike
        total_atk = total_atk * 135 // 100
        total_def = total_def * 135 // 100
        total_spd = total_spd * 120 // 100
        total_luk = total_luk * 130 // 100
        hp = hp * 175 // 100
        monster_level = max(monster_level, player_level)

    # ---- Name generieren ----
    name = generate_monster_name(floor, index, enemy_type, is_boss)

    # ---- Spezialfaehigkeit (Biome-abhaengig) ----
    special = _generate_special_ability(floor, enemy_type, rng)

    return {
        "name": name,
        "type": enemy_type,
        "level": monster_level,
        "total_atk": total_atk,
        "total_def": total_def,
        "total_spd": total_spd,
        "total_luk": total_luk,
        "hp": hp,
        "max_hp": hp,
        "is_boss": is_boss,
        "biome": biome["name"],
        "floor": floor,
        "special": special,
    }


def _generate_special_ability(floor: int, monster_type: str,
                               rng: random.Random) -> Optional[Dict[str, Any]]:
    """
    Spezialfaehigkeit basierend auf Floor-Bereich und Typ.
    Nur bei 30% der Monster (ab Floor 10).
    """
    if floor < 10 or rng.randint(1, 100) > 30:
        return None

    abilities_by_type = {
        "Stein": [
            {"name": "Steinschild", "effect": "def_boost", "value": 15,
             "desc": "+15% DEF fuer 3 Runden"},
            {"name": "Erdstoss", "effect": "stun", "value": 1,
             "desc": "Gegner verliert 1 Runde"},
            {"name": "Hartnaeckig", "effect": "hp_regen", "value": 5,
             "desc": "+5% HP-Regeneration pro Runde"},
        ],
        "Schere": [
            {"name": "Giftklinge", "effect": "dot", "value": 3,
             "desc": "3% HP Schaden pro Runde"},
            {"name": "Schattenhieb", "effect": "crit_boost", "value": 20,
             "desc": "+20% Krit-Chance"},
            {"name": "Blitzangriff", "effect": "first_strike", "value": 1,
             "desc": "Immer erster Angriff"},
        ],
        "Papier": [
            {"name": "Feuerball", "effect": "atk_boost", "value": 15,
             "desc": "+15% ATK fuer 3 Runden"},
            {"name": "Manaschild", "effect": "absorb", "value": 10,
             "desc": "Absorbiert 10% des Schadens"},
            {"name": "Fluch", "effect": "debuff", "value": 10,
             "desc": "-10% ATK des Gegners"},
        ],
    }

    abilities = abilities_by_type.get(monster_type, abilities_by_type["Stein"])
    return abilities[rng.randint(0, len(abilities) - 1)].copy()


# =============================================
# Weltboss Generator
# =============================================

def generate_worldboss(players: List[Dict[str, Any]],
                       trigger_floor: int = 0,
                       boss_index: int = 0) -> Dict[str, Any]:
    """
    Generiert einen Weltboss skaliert auf:
      - Anzahl der teilnehmenden Spieler
      - Quersumme der addierten Stats aller Spieler
      - Mittlerer Level der Gruppe

    Skalierungsformel:
      HP = Basis × Spieleranzahl × (1 + Quersumme/10)
      ATK = Mittelwert-ATK × 150% × (1 + Spieleranzahl × 10%)
      DEF = Mittelwert-DEF × 130%
      SPD = Mittelwert-SPD × 80% (Bosse sind langsamer)
      LUK = Mittelwert-LUK × 60%

    Der Boss soll so stark sein, dass alle Spieler zusammen
    ca. 2-5 Minuten brauchen (je nach DPS).

    Args:
        players: Liste der Spieler-Dicts mit Stats
        trigger_floor: Floor auf dem der Boss getriggert wurde
        boss_index: Index fuer verschiedene Bosse

    Returns:
        Weltboss-Dict mit skalierten Stats
    """
    if not players:
        return _generate_fallback_worldboss(trigger_floor)

    num_players = len(players)

    # ---- Spieler-Stats summieren ----
    sum_atk = 0
    sum_def = 0
    sum_spd = 0
    sum_luk = 0
    sum_levels = 0

    for p in players:
        sum_atk += p.get("base_atk", 25) + p.get("extra_atk", 0)
        sum_def += p.get("base_def", 25) + p.get("extra_def", 0)
        sum_spd += p.get("base_spd", 25) + p.get("extra_spd", 0)
        sum_luk += p.get("base_luk", 25) + p.get("extra_luk", 0)
        sum_levels += p.get("level", 1)

    # Gesamtsumme aller Stats
    total_stats_sum = sum_atk + sum_def + sum_spd + sum_luk

    # Quersumme der addierten Stats
    cross_sum = _digit_sum(total_stats_sum)

    # Mittelwerte
    avg_atk = sum_atk // num_players
    avg_def = sum_def // num_players
    avg_spd = sum_spd // num_players
    avg_luk = sum_luk // num_players
    avg_level = sum_levels // num_players

    # ---- Seed fuer deterministische Generierung ----
    # Seed aus Quersumme + Spieleranzahl + Floor + Index
    seed = cross_sum * 10007 + num_players * 7919 + trigger_floor * 3571 + boss_index
    rng = random.Random(seed)

    # ---- Boss-Stats berechnen ----
    # HP: massiv skaliert - mehr Spieler = mehr HP
    # Basis: 500 HP pro Spieler × Level-Faktor × Quersumme-Bonus
    base_hp = 500 * num_players * max(1, avg_level)
    cross_sum_factor = 100 + cross_sum * 10  # +10% pro Quersumme-Punkt
    boss_hp = base_hp * cross_sum_factor // 100
    # Varianz: +-5%
    boss_hp = boss_hp + rng.randint(-boss_hp // 20, boss_hp // 20)
    boss_hp = max(1000, boss_hp)

    # ATK: gefaehrlich genug um Spieler unter Druck zu setzen
    # 150% des Durchschnitts × Spieler-Skalierung
    player_scale = 100 + num_players * 10  # +10% pro Spieler
    boss_atk = avg_atk * 150 * player_scale // 10000
    boss_atk = max(20, min(99, boss_atk))  # Bosse duerfen ueber 50 gehen!

    # DEF: 130% des Durchschnitts
    boss_def = avg_def * 130 // 100
    boss_def = max(15, min(80, boss_def))

    # SPD: Bosse sind langsamer (80%)
    boss_spd = avg_spd * 80 // 100
    boss_spd = max(5, min(40, boss_spd))

    # LUK: Bosse haben weniger Glueck (60%)
    boss_luk = avg_luk * 60 // 100
    boss_luk = max(3, min(30, boss_luk))

    # ---- Boss-Level ----
    boss_level = max(avg_level, trigger_floor // 5, 1)

    # ---- Name generieren ----
    boss_type = ["Stein", "Schere", "Papier"][rng.randint(0, 2)]
    base_name = generate_monster_name(trigger_floor + 10000, boss_index,
                                      boss_type, is_boss=False)
    title = _WORLDBOSS_TITLES[rng.randint(0, len(_WORLDBOSS_TITLES) - 1)]
    boss_name = f"{base_name}, {title}"

    # ---- Belohnungs-Multiplikator ----
    # Mehr Spieler + hoehere Stats = bessere Belohnungen
    reward_multiplier = 100 + num_players * 25 + cross_sum * 5  # in Prozent

    # ---- Spezialfaehigkeiten (Bosse haben immer 2) ----
    specials = []
    all_types = ["Stein", "Schere", "Papier"]
    for i in range(2):
        t = all_types[rng.randint(0, 2)]
        special = _generate_special_ability(trigger_floor + 100, t, rng)
        if special:
            specials.append(special)

    return {
        "name": boss_name,
        "type": boss_type,
        "level": boss_level,
        "total_atk": boss_atk,
        "total_def": boss_def,
        "total_spd": boss_spd,
        "total_luk": boss_luk,
        "hp": boss_hp,
        "max_hp": boss_hp,
        "is_boss": True,
        "is_worldboss": True,
        "num_players": num_players,
        "total_stats_sum": total_stats_sum,
        "cross_sum": cross_sum,
        "reward_multiplier": reward_multiplier,
        "specials": specials,
        "trigger_floor": trigger_floor,
        # Rewards pro Spieler
        "gold_reward": 100 * num_players * avg_level * reward_multiplier // 100,
        "diamond_reward": 10 * num_players + cross_sum * 5,
        "xp_reward": 200 * avg_level * reward_multiplier // 100,
    }


def _generate_fallback_worldboss(trigger_floor: int) -> Dict[str, Any]:
    """Fallback-Weltboss wenn keine Spielerdaten vorhanden."""
    rng = random.Random(trigger_floor * 10007)
    boss_type = ["Stein", "Schere", "Papier"][rng.randint(0, 2)]
    name = generate_monster_name(trigger_floor + 10000, 0, boss_type, is_boss=False)
    title = _WORLDBOSS_TITLES[rng.randint(0, len(_WORLDBOSS_TITLES) - 1)]

    return {
        "name": f"{name}, {title}",
        "type": boss_type,
        "level": max(1, trigger_floor // 5),
        "total_atk": 40,
        "total_def": 35,
        "total_spd": 20,
        "total_luk": 15,
        "hp": 5000,
        "max_hp": 5000,
        "is_boss": True,
        "is_worldboss": True,
        "num_players": 1,
        "total_stats_sum": 100,
        "cross_sum": 1,
        "reward_multiplier": 100,
        "specials": [],
        "trigger_floor": trigger_floor,
        "gold_reward": 500,
        "diamond_reward": 20,
        "xp_reward": 500,
    }


# =============================================
# Test / Demo
# =============================================

if __name__ == "__main__":
    # Test-Spieler (Krieger)
    test_player = {
        "name": "TestHeld",
        "klasse": "Krieger",
        "level": 5,
        "base_atk": 25, "base_def": 40, "base_spd": 20, "base_luk": 15,
        "extra_atk": 3, "extra_def": 2, "extra_spd": 0, "extra_luk": 0,
    }

    print("=" * 60)
    print("  MONSTER-GENERATOR TEST")
    print("=" * 60)

    # Verschiedene Floors testen
    for floor in [1, 5, 10, 25, 50, 100, 200, 500]:
        m = generate_pve_monster(floor, test_player)
        boss_str = " [BOSS]" if m["is_boss"] else ""
        spec_str = f" Spezial: {m['special']['name']}" if m.get("special") else ""
        print(f"  Floor {floor:4d}: {m['name']:40s} "
              f"Typ={m['type']:7s} Lv.{m['level']:3d} "
              f"HP={m['hp']:5d} ATK={m['total_atk']:2d} "
              f"DEF={m['total_def']:2d} SPD={m['total_spd']:2d} "
              f"LUK={m['total_luk']:2d}{boss_str}{spec_str}")

    print()
    print("  DETERMINISTIK-TEST (gleicher Floor = gleicher Gegner):")
    m1 = generate_pve_monster(42, test_player)
    m2 = generate_pve_monster(42, test_player)
    print(f"  Floor 42 (1): {m1['name']} HP={m1['hp']}")
    print(f"  Floor 42 (2): {m2['name']} HP={m2['hp']}")
    print(f"  Identisch: {m1 == m2}")

    print()
    print("  WELTBOSS-TEST (3 Spieler):")
    players = [
        {"name": "Spieler1", "klasse": "Krieger", "level": 10,
         "base_atk": 25, "base_def": 40, "base_spd": 20, "base_luk": 15,
         "extra_atk": 10, "extra_def": 5, "extra_spd": 3, "extra_luk": 2},
        {"name": "Spieler2", "klasse": "Magier", "level": 8,
         "base_atk": 45, "base_def": 10, "base_spd": 20, "base_luk": 25,
         "extra_atk": 5, "extra_def": 2, "extra_spd": 3, "extra_luk": 0},
        {"name": "Spieler3", "klasse": "Schurke", "level": 12,
         "base_atk": 25, "base_def": 15, "base_spd": 40, "base_luk": 20,
         "extra_atk": 8, "extra_def": 3, "extra_spd": 7, "extra_luk": 2},
    ]
    wb = generate_worldboss(players, trigger_floor=50)
    print(f"  Name: {wb['name']}")
    print(f"  Typ: {wb['type']} | Lv.{wb['level']}")
    print(f"  HP: {wb['hp']} | ATK: {wb['total_atk']} | DEF: {wb['total_def']}")
    print(f"  Spieler: {wb['num_players']} | Stats-Summe: {wb['total_stats_sum']}")
    print(f"  Quersumme: {wb['cross_sum']}")
    print(f"  Belohnungs-Multiplikator: {wb['reward_multiplier']}%")
    print(f"  Gold: {wb['gold_reward']} | Diamanten: {wb['diamond_reward']}")
    print(f"  Spezial: {[s['name'] for s in wb.get('specials', [])]}")

    print()
    print("  SKALIERUNGS-TEST (1 vs 3 vs 5 Spieler):")
    for n in [1, 3, 5]:
        p_list = players[:min(n, len(players))]
        # Dupliziere wenn noetig
        while len(p_list) < n:
            p_list.append(players[0])
        wb_n = generate_worldboss(p_list, trigger_floor=50)
        print(f"  {n} Spieler: HP={wb_n['hp']:7d} ATK={wb_n['total_atk']:2d} "
              f"Reward={wb_n['reward_multiplier']}%")
