#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Belohnungs-System (Rewards)
======================================================
Zentrales Modul fuer alle Belohnungen nach Kaempfen.

Berechnet:
  - EXP (Erfahrungspunkte)
  - Gold
  - Diamanten (nur PVP + Weltboss)
  - Seelen-Scherben (nur Turm ab SF 100)
  - Item-Drop-Chance + Seltenheit
  - Shiny-Chance (1:8192)
  - Ascension-Multiplikatoren
  - Kompensations-System (Glaskanonen-Ausgleich)
  - Durchbruch-System (Frustrations-Praevention)

Kompensations-System:
  Klassen mit niedrigerer Idle-Wall (hohe ATK, niedrige DEF)
  bekommen automatisch bessere Drops als Ausgleich.

  glass_cannon_factor = max(0, ATK_base - DEF_base)
    Magier  (ATK 45, DEF 10): gc=35 → starke Kompensation
    Schurke (ATK 25, DEF 15): gc=10 → leichte Kompensation
    Krieger (ATK 25, DEF 40): gc=0  → keine Kompensation

Durchbruch-System:
  Erkennt aktives Festhaengen trotz Anpassungen und gibt
  gezielte Hilfs-Items um Frustration zu vermeiden.

  Ablauf:
    1. Spieler haengt auf Floor X fest (idle) → kommt zurueck
    2. Spieler passt Charakter an (Equip, Respec, Upgrade)
    3. Spieler kaempft aktiv weiter → scheitert trotzdem
    4. Nach N aktiven Niederlagen NACH Anpassung → Durchbruch-Item
    5. Item ist gezielt auf die Schwaeche des Spielers abgestimmt

  Eskalation (nach jeder Anpassungsrunde):
    Stufe 1:  3 aktive Fails → seltenes gezieltes Item
    Stufe 2:  5 aktive Fails → legendaeres gezieltes Item
    Stufe 3:  8 aktive Fails → Weltboss-Schmuck-Fragment
    Stufe 4+: 10 aktive Fails → legendaeres gezieltes Item (wiederholt)

  WICHTIG: Nur bei AKTIVEN Sessions, NICHT waehrend Idle!

Referenz: Battle-Pi_Konsolidiert.txt Abschnitt 5B, 6A, 6B, 7
"""

import random
import math
from typing import Dict, Any, Optional, List, Tuple


# =============================================
# Konstanten (aus der Spec)
# =============================================

# EXP (Abschnitt 6B)
EXP_WIN = 100                # Sieg: 100 EXP
EXP_LOSS = 30                # Niederlage: 30 EXP
EXP_PER_LEVEL = 500          # Alle 500 EXP -> Level-Up
LEVELUP_BONUS_POINTS = 5     # +5 Bonuspunkte pro Level-Up

# Gold (Abschnitt 5B + 6B)
GOLD_WIN_MIN = 20            # Sieg: 20-60 Gold
GOLD_WIN_MAX = 60
GOLD_TOWER_MULTIPLIER = 10   # Turm: floor x 10

# Scrap (Abschnitt 6B)
SCRAP_LOSS_MIN = 2           # Niederlage: 2-5 Scrap
SCRAP_LOSS_MAX = 5

# Item-Drop (Abschnitt 6B)
BASE_DROP_CHANCE = 0.15      # 15% Basis-Drop-Chance
LUK_DROP_BONUS = 0.005       # + LUK x 0.5% pro Punkt

# Seltenheit (Abschnitt 6B, beeinflusst durch LUK)
RARITY_COMMON = 0.75         # 75% Gewoehnlich (Stats 2-7)
RARITY_RARE = 0.20           # 20% Selten (Stats 8-14)
RARITY_LEGENDARY = 0.05      # 5% Legendaer (Stats 15-25)

# Shiny (Abschnitt 5B)
SHINY_CHANCE = 8192          # 1:8192
SHINY_GOLD_MULTIPLIER = 10   # 10x Gold bei Shiny

# Diamanten (Abschnitt 6A)
DIAMONDS_PVP_WIN = 3         # PVP-Sieg: 3 Diamanten
DIAMONDS_WORLDBOSS_BASE = 10 # Weltboss: 10+ Diamanten

# Seelen-Scherben (Abschnitt 6A)
SOUL_SHARD_MIN_FLOOR = 100   # Erst ab SF 100 verfuegbar
SOUL_SHARD_BASE = 1          # 1 Scherbe pro Drop
SOUL_SHARD_CHANCE = 0.10     # 10% Chance ab SF 100

# Ascension-Multiplikatoren (Abschnitt 7)
ASCENSION_THRESHOLDS = {
    1000: 1.5,               # SF 1000: x1.5 auf alles
    5000: 2.0,               # SF 5000: x2.0
    10000: 3.0               # SF 10000: x3.0
}

# PVP-Skalierung (Abschnitt 5C)
# PVP-Power = Base-Stats x (1 + log10(SF / 100))
PVP_SCALING_DIVISOR = 100

# PVP-Gold-Bonus (Abschnitt 7)
# Alle 100 SF: +1% PVP-Gold
PVP_GOLD_BONUS_PER_100_FLOORS = 0.01

# =============================================
# Kompensations-System (Glaskanonen-Ausgleich)
# =============================================
COMPENSATION_RARITY_FACTOR = 0.007    # gc × 0.7% = Raritaets-Upgrade-Chance
COMPENSATION_WORLDBOSS_FACTOR = 0.002 # gc × 0.2% = Weltboss-Fragment-Chance
WORLDBOSS_FRAGMENT_STAT_MULT = 70     # 70% der normalen Weltboss-Stats (×70÷100)

# Weltboss-Fragment Stat-Bereiche (70% von normalen Weltboss-Items)
FRAGMENT_RARE_STATS = (6, 10)
FRAGMENT_LEGENDARY_STATS = (11, 18)

# Raritaets-Upgrade-Kette
RARITY_UPGRADE = {
    "common": "rare",
    "rare": "legendary",
    "legendary": "legendary"
}

# =============================================
# Durchbruch-System (Frustrations-Praevention)
# =============================================
# Eskalationsstufen: [aktive_fails_nach_anpassung] → Belohnung
# Stufe 1: 3 Fails  → rare gezieltes Item
# Stufe 2: 5 Fails  → legendary gezieltes Item
# Stufe 3: 8 Fails  → Weltboss-Schmuck-Fragment
# Stufe 4+: 10 Fails → legendary gezieltes Item (wiederholt)
BREAKTHROUGH_ESCALATION = [
    {"fails_needed": 3,  "rarity": "rare",      "type": "targeted_item"},
    {"fails_needed": 5,  "rarity": "legendary",  "type": "targeted_item"},
    {"fails_needed": 8,  "rarity": "legendary",  "type": "worldboss_fragment"},
]
BREAKTHROUGH_REPEAT_FAILS = 10         # Ab Stufe 4: alle 10 Fails
BREAKTHROUGH_REPEAT_RARITY = "legendary"
BREAKTHROUGH_REPEAT_TYPE = "targeted_item"

# Anpassungs-Typen die der Tracker erkennt
ADJUSTMENT_TYPES = {"equip", "respec", "upgrade", "new_item", "forge"}


# =============================================
# Durchbruch-Tracker (State-Machine)
# =============================================

class BreakthroughTracker:
    """
    Trackt den Fortschritt eines Spielers und erkennt Frustrations-Muster.

    Der Tracker unterscheidet zwischen:
      - Idle-Niederlagen (Spieler offline, Bot kaempft) → KEIN Durchbruch
      - Aktive Niederlagen (Spieler online, interagiert) → zaehlt fuer Durchbruch

    Der Durchbruch loest erst aus NACHDEM der Spieler mindestens
    eine Anpassung vorgenommen hat (Equip, Respec, etc.) und
    trotzdem scheitert.

    State wird als Dict im Charakter gespeichert (persistent).

    Typischer Game-Loop:
      1. Spieler loggt ein → tracker.mark_active()
      2. Spieler passt Build an → tracker.record_adjustment("equip")
      3. Spieler kaempft → Niederlage → tracker.record_active_loss(floor)
      4. Tracker prueft: Durchbruch faellig? → gibt Item zurueck
      5. Spieler gewinnt / steigt auf → tracker.record_progress(new_floor)
      6. Spieler loggt aus → tracker.mark_idle()
    """

    def __init__(self, state: Optional[Dict[str, Any]] = None):
        """
        Args:
            state: Bestehender State-Dict (aus Charakter-Daten).
                   Wird None uebergeben, wird ein frischer State erstellt.
        """
        if state is not None:
            self._state = state
        else:
            self._state = self._create_fresh_state()

    @staticmethod
    def _create_fresh_state() -> Dict[str, Any]:
        """Frischen Tracker-State erstellen."""
        return {
            "stuck_floor": 0,              # Floor auf dem der Spieler festhaengt
            "is_active": False,            # Spieler ist aktiv eingeloggt
            "active_fails_on_floor": 0,    # Aktive Niederlagen auf diesem Floor
            "fails_since_adjustment": 0,   # Fails seit letzter Anpassung
            "adjustments_made": 0,         # Anpassungen auf diesem Floor
            "adjustment_history": [],      # Liste der Anpassungstypen
            "breakthroughs_given": 0,      # Bereits gegebene Durchbrueche (Eskalation)
            "total_fails_on_floor": 0,     # Alle Fails (idle + aktiv) zur Info
            "last_active_fail_floor": 0    # Letztes Floor mit aktivem Fail
        }

    def get_state(self) -> Dict[str, Any]:
        """State-Dict zurueckgeben (zum Speichern im Charakter)."""
        return self._state.copy()

    # -----------------------------------------
    # Session-Management
    # -----------------------------------------

    def mark_active(self) -> None:
        """Spieler hat sich eingeloggt / ist aktiv."""
        self._state["is_active"] = True

    def mark_idle(self) -> None:
        """Spieler hat sich ausgeloggt / ist idle."""
        self._state["is_active"] = False

    # -----------------------------------------
    # Anpassungen tracken
    # -----------------------------------------

    def record_adjustment(self, adjustment_type: str) -> None:
        """
        Eine Charakter-Anpassung registrieren.

        Wird aufgerufen wenn der Spieler aktiv seinen Build aendert:
          - "equip": Item an/ausgezogen
          - "respec": Bonuspunkte neu verteilt
          - "upgrade": Item in der Schmiede verbessert
          - "new_item": Neues Item aus Drop/Shop erhalten
          - "forge": Item geschmiedet

        Args:
            adjustment_type: Art der Anpassung (muss in ADJUSTMENT_TYPES sein)
        """
        if adjustment_type not in ADJUSTMENT_TYPES:
            return  # Unbekannter Typ → ignorieren

        self._state["adjustments_made"] += 1
        self._state["fails_since_adjustment"] = 0  # Reset nach Anpassung

        # History begrenzen auf letzte 10 Eintraege
        history = self._state["adjustment_history"]
        history.append(adjustment_type)
        if len(history) > 10:
            self._state["adjustment_history"] = history[-10:]

    # -----------------------------------------
    # Niederlagen tracken
    # -----------------------------------------

    def record_loss(self, floor: int) -> Optional[Dict[str, Any]]:
        """
        Eine Kampf-Niederlage registrieren.

        Unterscheidet automatisch zwischen aktiv und idle
        basierend auf dem is_active Flag.

        Bei einem neuen Floor wird der Tracker zurueckgesetzt.

        Args:
            floor: Das Stockwerk auf dem verloren wurde

        Returns:
            None: Kein Durchbruch
            Dict: Durchbruch-Info mit "stage", "rarity", "type"
                  wenn Durchbruch ausgeloest wurde
        """
        # Floor-Initialisierung vs. Floor-Wechsel unterscheiden
        if floor != self._state["stuck_floor"]:
            was_initialized = self._state["stuck_floor"] > 0
            was_active = self._state["is_active"]
            old_adjustments = self._state["adjustments_made"]
            old_adj_history = self._state["adjustment_history"][:]
            old_fails_since_adj = self._state["fails_since_adjustment"]

            if was_initialized and floor > self._state["stuck_floor"]:
                # Echtes neues Floor (Fortschritt) → komplett zuruecksetzen
                self._state = self._create_fresh_state()
                self._state["stuck_floor"] = floor
                self._state["is_active"] = was_active
            elif was_initialized:
                # Niedrigeres Floor (Rueckfall) → State behalten
                self._state["stuck_floor"] = floor
                self._state["total_fails_on_floor"] = 0
                self._state["active_fails_on_floor"] = 0
            else:
                # Erster Kontakt (stuck_floor war 0) → initialisieren
                # Anpassungen die VOR dem ersten Kampf gemacht wurden bleiben!
                self._state["stuck_floor"] = floor
                self._state["is_active"] = was_active
                self._state["adjustments_made"] = old_adjustments
                self._state["adjustment_history"] = old_adj_history
                self._state["fails_since_adjustment"] = old_fails_since_adj

        # Gesamt-Fails zaehlen (fuer Statistik)
        self._state["total_fails_on_floor"] += 1

        # Idle-Niederlage → nur zaehlen, kein Durchbruch
        if not self._state["is_active"]:
            return None

        # Aktive Niederlage
        self._state["active_fails_on_floor"] += 1
        self._state["fails_since_adjustment"] += 1
        self._state["last_active_fail_floor"] = floor

        # Durchbruch-Check: Nur wenn mindestens 1 Anpassung gemacht wurde
        if self._state["adjustments_made"] < 1:
            return None

        return self._check_breakthrough()

    # -----------------------------------------
    # Fortschritt tracken
    # -----------------------------------------

    def record_progress(self, new_floor: int) -> None:
        """
        Fortschritt registrieren (Spieler hat gewonnen / neues Floor).

        Setzt den Tracker komplett zurueck, da kein Frust mehr vorliegt.

        Args:
            new_floor: Das neue (hoehere) Stockwerk
        """
        self._state = self._create_fresh_state()
        self._state["stuck_floor"] = new_floor
        self._state["is_active"] = True

    # -----------------------------------------
    # Durchbruch-Logik
    # -----------------------------------------

    def _check_breakthrough(self) -> Optional[Dict[str, Any]]:
        """
        Pruefen ob ein Durchbruch ausgeloest wird.

        Eskalationsstufen basierend auf breakthroughs_given:
          Stufe 0 → BREAKTHROUGH_ESCALATION[0]: 3 Fails → rare
          Stufe 1 → BREAKTHROUGH_ESCALATION[1]: 5 Fails → legendary
          Stufe 2 → BREAKTHROUGH_ESCALATION[2]: 8 Fails → Fragment
          Stufe 3+ → BREAKTHROUGH_REPEAT: 10 Fails → legendary

        Returns:
            None oder Dict mit Durchbruch-Info
        """
        stage = self._state["breakthroughs_given"]
        fails = self._state["fails_since_adjustment"]

        # Welche Eskalationsstufe?
        if stage < len(BREAKTHROUGH_ESCALATION):
            needed = BREAKTHROUGH_ESCALATION[stage]["fails_needed"]
            rarity = BREAKTHROUGH_ESCALATION[stage]["rarity"]
            btype = BREAKTHROUGH_ESCALATION[stage]["type"]
        else:
            needed = BREAKTHROUGH_REPEAT_FAILS
            rarity = BREAKTHROUGH_REPEAT_RARITY
            btype = BREAKTHROUGH_REPEAT_TYPE

        # Genug Fails seit letzter Anpassung?
        if fails >= needed:
            self._state["breakthroughs_given"] += 1
            self._state["fails_since_adjustment"] = 0  # Reset nach Durchbruch

            return {
                "stage": stage + 1,
                "rarity": rarity,
                "type": btype,
                "floor": self._state["stuck_floor"],
                "active_fails": self._state["active_fails_on_floor"],
                "adjustments": self._state["adjustments_made"]
            }

        return None

    # -----------------------------------------
    # Debug / Info
    # -----------------------------------------

    def get_info(self) -> str:
        """Lesbarer Status-String fuer Debugging."""
        s = self._state
        stage = s["breakthroughs_given"]
        if stage < len(BREAKTHROUGH_ESCALATION):
            next_at = BREAKTHROUGH_ESCALATION[stage]["fails_needed"]
        else:
            next_at = BREAKTHROUGH_REPEAT_FAILS

        return (
            f"Floor={s['stuck_floor']} | "
            f"Aktiv={'JA' if s['is_active'] else 'NEIN'} | "
            f"Fails(aktiv)={s['active_fails_on_floor']} | "
            f"Fails(seit Anp.)={s['fails_since_adjustment']}/{next_at} | "
            f"Anpassungen={s['adjustments_made']} | "
            f"Durchbrueche={s['breakthroughs_given']} | "
            f"Total Fails={s['total_fails_on_floor']}"
        )


# =============================================
# Durchbruch-Item-Generator
# =============================================

class BreakthroughItemGenerator:
    """
    Generiert gezielte Durchbruch-Items basierend auf Spieler-Schwaeche.

    Analysiert die Stats des Spielers und erstellt ein Item das
    genau die Schwachstelle adressiert:
      - Niedrige DEF → Ruestung/Schild
      - Niedriger ATK → Waffe
      - Niedrige SPD → Handschuhe/Stiefel
      - Ausgeglichen → Bestes Item fuer aktuellen Floor

    Items sind IMMER hilfreich und nie redundant.
    """

    def __init__(self, seed: int = None):
        """
        Args:
            seed: Optionaler RNG-Seed fuer deterministische Tests
        """
        self._rng = random.Random(seed)

    def generate_breakthrough_item(
        self,
        breakthrough_info: Dict[str, Any],
        player_stats: Dict[str, int],
        player_luk: int = 10,
        current_equipment: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Gezieltes Durchbruch-Item generieren.

        Das Item adressiert die groesste Schwaeche des Spielers
        und hat garantierte Mindest-Stats die auf dem aktuellen
        Floor hilfreich sind.

        Args:
            breakthrough_info: Dict von BreakthroughTracker._check_breakthrough()
            player_stats: Dict mit "atk", "def", "spd", "luk"
            player_luk: LUK fuer Fragment-Raritaet
            current_equipment: Optionales Dict mit aktuell ausgeruesteten Items

        Returns:
            Item-Dict (kompatibel mit dem regulaeren Item-System)
        """
        btype = breakthrough_info["type"]
        rarity = breakthrough_info["rarity"]
        stage = breakthrough_info["stage"]

        if btype == "worldboss_fragment":
            return self._generate_breakthrough_fragment(player_stats, player_luk)

        return self._generate_targeted_item(
            rarity, player_stats, stage, current_equipment
        )

    def _analyze_weakness(
        self,
        player_stats: Dict[str, int],
        current_equipment: Optional[Dict] = None
    ) -> str:
        """
        Groesste Schwaeche des Spielers bestimmen.

        Vergleicht ATK vs DEF (die kampfrelevanten Haupt-Stats).
        Beruecksichtigt auch Equipment-Luecken wenn vorhanden.

        Args:
            player_stats: Spieler-Stats
            current_equipment: Aktuelles Equipment

        Returns:
            "atk" oder "def" (primaere Schwaeche)
        """
        total_atk = player_stats.get("atk", 25)
        total_def = player_stats.get("def", 25)

        # Equipment-Bonus beruecksichtigen (wenn verfuegbar)
        if current_equipment:
            equip_atk = sum(
                item.get("atk_mod", 0)
                for item in current_equipment.values()
                if item and item.get("equipped")
            )
            equip_def = sum(
                item.get("def_mod", 0)
                for item in current_equipment.values()
                if item and item.get("equipped")
            )
            total_atk += equip_atk
            total_def += equip_def

        # Die niedrigere Seite ist die Schwaeche
        # Bei Gleichstand → DEF bevorzugen (laengeres Ueberleben hilft mehr)
        if total_atk < total_def:
            return "atk"
        return "def"

    def _generate_targeted_item(
        self,
        rarity: str,
        player_stats: Dict[str, int],
        stage: int,
        current_equipment: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Gezieltes Item fuer die Spieler-Schwaeche generieren.

        Das Item hat:
          - Garantiert den richtigen Typ (Waffe fuer ATK, Ruestung fuer DEF)
          - Stats im oberen Bereich der Raritaetsstufe
          - Bonus-Stats in der Schwaeche-Richtung

        Args:
            rarity: "rare" oder "legendary"
            player_stats: Spieler-Stats
            stage: Durchbruch-Stufe (hoeher = besser)
            current_equipment: Aktuelles Equipment

        Returns:
            Item-Dict
        """
        weakness = self._analyze_weakness(player_stats, current_equipment)

        # Item-Typ basierend auf Schwaeche
        if weakness == "atk":
            item_type = "Waffe"
        else:
            item_type = "Ruestung"

        # Stats: oberes Drittel der Raritaetsstufe (gezielt gut)
        if rarity == "legendary":
            # Legendary: 15-25 → gezielt: 19-25
            primary_mod = self._rng.randint(19, 25)
            secondary_mod = self._rng.randint(15, 20)
        elif rarity == "rare":
            # Rare: 8-14 → gezielt: 11-14
            primary_mod = self._rng.randint(11, 14)
            secondary_mod = self._rng.randint(8, 12)
        else:
            primary_mod = self._rng.randint(5, 7)
            secondary_mod = self._rng.randint(2, 5)

        # ATK/DEF basierend auf Item-Typ zuweisen
        if item_type == "Waffe":
            atk_mod = primary_mod
            def_mod = secondary_mod // 2  # Sekundaer halbiert
        else:
            atk_mod = secondary_mod // 2
            def_mod = primary_mod

        # Wert berechnen
        total_stats = atk_mod + def_mod
        base_value = total_stats * 5
        if rarity == "legendary":
            base_value *= 3
        elif rarity == "rare":
            base_value *= 2

        # Name generieren (Durchbruch-spezifisch)
        name = self._generate_breakthrough_name(item_type, rarity, stage)

        return {
            "name": name,
            "type": item_type,
            "rarity": rarity,
            "atk_mod": atk_mod,
            "def_mod": def_mod,
            "value": base_value,
            "equipped": False,
            "upgrade_level": 0,
            "source": "breakthrough",
            "breakthrough_stage": stage
        }

    def _generate_breakthrough_fragment(
        self,
        player_stats: Dict[str, int],
        player_luk: int
    ) -> Dict[str, Any]:
        """
        Weltboss-Fragment als Durchbruch-Belohnung.

        Wie das Kompensations-Fragment, aber gezielt auf Schwaeche
        und mit leicht besseren Stats (80% statt 70%).

        Args:
            player_stats: Spieler-Stats
            player_luk: LUK-Attribut

        Returns:
            Schmuck-Item-Dict
        """
        weakness = self._analyze_weakness(player_stats)

        # Ring fuer ATK-Schwaeche, Halskette fuer DEF-Schwaeche
        if weakness == "atk":
            schmuck_type = "Ring"
        else:
            schmuck_type = "Halskette"

        # Immer legendary fuer Durchbruch-Fragmente
        rarity = "legendary"
        stat_min, stat_max = FRAGMENT_LEGENDARY_STATS

        # 80% statt 70% → leicht besser als Kompensations-Fragmente
        atk_mod = self._rng.randint(stat_min, stat_max) + 2
        def_mod = self._rng.randint(stat_min, stat_max) + 2

        # Schwaeche-Bonus
        if schmuck_type == "Ring":
            atk_mod += 3  # Staerkerer ATK-Bonus
        else:
            def_mod += 3  # Staerkerer DEF-Bonus

        # Wert
        total_stats = atk_mod + def_mod
        base_value = total_stats * 5 * 3  # Legendary-Multiplikator

        # Name
        prefix = self._rng.choice(["Erwachter", "Erhabener", "Triumphaler"])
        name = f"{prefix} {schmuck_type}"

        return {
            "name": name,
            "type": "Schmuck",
            "slot": schmuck_type.lower(),
            "rarity": rarity,
            "atk_mod": atk_mod,
            "def_mod": def_mod,
            "value": base_value,
            "equipped": False,
            "upgrade_level": 0,
            "is_fragment": True,
            "source": "breakthrough"
        }

    def _generate_breakthrough_name(
        self,
        item_type: str,
        rarity: str,
        stage: int
    ) -> str:
        """Durchbruch-spezifische Item-Namen generieren."""
        # Spezielle Praefixe die "Durchbruch" thematisch widerspiegeln
        prefixes_by_stage = {
            1: ["Beharrlich", "Standhaft", "Unbeirrt"],
            2: ["Unerschuetterlich", "Entschlossen", "Triumphierend"],
            3: ["Erwacht", "Transzendent", "Erhaben"],
        }
        # Ab Stage 4: zufaellig aus allen
        if stage <= 3:
            prefixes = prefixes_by_stage.get(stage, prefixes_by_stage[1])
        else:
            prefixes = ["Meisterhaft", "Perfektioniert", "Vollendet"]

        prefix = self._rng.choice(prefixes)

        weapons = ["Schwert", "Axt", "Dolch", "Stab", "Hammer"]
        armors = ["Schild", "Helm", "Ruestung", "Panzer", "Mantel"]

        if item_type == "Waffe":
            base = self._rng.choice(weapons)
        else:
            base = self._rng.choice(armors)

        # Grammatik: "er" fuer Konsonanten-Ende, "es" fuer 'h'-Ende
        if prefix[-1] == "h":
            return f"{prefix}es {base}"
        elif prefix[-1] == "t":
            return f"{prefix}es {base}"
        elif prefix[-1] == "d":
            return f"{prefix}es {base}"
        else:
            return f"{prefix}er {base}"


# =============================================
# Reward-Berechnung
# =============================================

class RewardCalculator:
    """
    Zentraler Belohnungs-Rechner fuer alle Kampftypen.

    Nutzt deterministische Berechnung wo moeglich,
    Random nur fuer Drop-Chance und Varianz.
    """

    def __init__(self, seed: int = None):
        """
        Args:
            seed: Optionaler RNG-Seed fuer deterministische Tests
        """
        self._rng = random.Random(seed)

    # -----------------------------------------
    # Turm-Belohnungen (PVE)
    # -----------------------------------------

    def calculate_tower_rewards(
        self,
        floor: int,
        result: str,
        player_luk: int = 10,
        player_level: int = 1,
        ascension: int = 1,
        is_boss_floor: bool = False,
        active_buffs: Optional[Dict] = None,
        player_atk_base: int = 25,
        player_def_base: int = 25,
        breakthrough_item: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Belohnungen nach einem Turm-Kampf berechnen.

        Args:
            floor: Aktuelles Stockwerk
            result: "WIN", "LOSS" oder "DRAW"
            player_luk: LUK-Attribut des Spielers
            player_level: Aktuelles Level
            ascension: Ascension-Stufe
            is_boss_floor: True wenn Boss-Stockwerk (alle 10 SF)
            active_buffs: Aktive Buffs (z.B. Trinkbuddy +10% Gold)
            player_atk_base: ATK-Basiswert (fuer Kompensation)
            player_def_base: DEF-Basiswert (fuer Kompensation)
            breakthrough_item: Optionales Durchbruch-Item (vom Tracker)

        Returns:
            Dict mit allen Belohnungen
        """
        rewards = {
            "type": "TOWER",
            "floor": floor,
            "result": result,
            "exp": 0,
            "gold": 0,
            "scrap": 0,
            "diamonds": 0,
            "soul_shards": 0,
            "item_drop": None,
            "is_shiny": False,
            "is_boss": is_boss_floor,
            "ascension_multiplier": 1.0,
            "buff_multiplier": 1.0,
            "compensation_applied": None,
            "breakthrough_applied": False
        }

        # Glass-Cannon-Factor berechnen (fuer Kompensation)
        glass_cannon_factor = max(0, player_atk_base - player_def_base)

        # Ascension-Multiplikator bestimmen
        asc_mult = self._get_ascension_multiplier(floor)
        rewards["ascension_multiplier"] = asc_mult

        # Buff-Multiplikator (z.B. Trinkbuddy +10% Gold)
        buff_mult = 1.0
        if active_buffs:
            buff_mult += active_buffs.get("gold_bonus", 0.0)
        rewards["buff_multiplier"] = buff_mult

        if result == "WIN":
            # EXP
            rewards["exp"] = int(EXP_WIN * asc_mult)

            # Gold: floor x 10 x Ascension
            base_gold = floor * GOLD_TOWER_MULTIPLIER
            if is_boss_floor:
                base_gold *= 2  # Bosse geben doppelt Gold

            # Shiny-Check (1:8192)
            is_shiny = self._rng.randint(1, SHINY_CHANCE) == 1
            rewards["is_shiny"] = is_shiny
            if is_shiny:
                base_gold *= SHINY_GOLD_MULTIPLIER
                rewards["item_drop"] = self._generate_drop(
                    player_luk, force_rarity="legendary"
                )

            rewards["gold"] = int(base_gold * asc_mult * buff_mult)

            # Seelen-Scherben (ab SF 100)
            if floor >= SOUL_SHARD_MIN_FLOOR:
                if self._rng.random() < SOUL_SHARD_CHANCE:
                    shards = SOUL_SHARD_BASE + (floor // 500)
                    rewards["soul_shards"] = int(shards * asc_mult)

            # Item-Drop (wenn kein Shiny-Drop)
            if rewards["item_drop"] is None:
                drop = self._try_item_drop(player_luk)
                if drop:
                    # ── Kompensations-System anwenden ──
                    if glass_cannon_factor > 0:
                        compensation = self._apply_compensation(
                            drop, glass_cannon_factor, player_luk
                        )
                        if compensation is not None:
                            drop = compensation["item"]
                            rewards["compensation_applied"] = compensation["type"]

                    rewards["item_drop"] = drop

                else:
                    # Kein normaler Drop → Weltboss-Fragment-Chance (Glaskanonen)
                    if glass_cannon_factor > 0:
                        fragment = self._try_worldboss_fragment(
                            glass_cannon_factor, player_luk
                        )
                        if fragment is not None:
                            rewards["item_drop"] = fragment
                            rewards["compensation_applied"] = "worldboss_fragment"

        elif result == "LOSS":
            # Niederlage: trotzdem etwas EXP + Scrap
            rewards["exp"] = EXP_LOSS
            rewards["scrap"] = self._rng.randint(SCRAP_LOSS_MIN, SCRAP_LOSS_MAX)

            # ── Durchbruch-System: Item bei Niederlage einfuegen ──
            # Das Durchbruch-Item wird vom Game-Loop via BreakthroughTracker
            # bestimmt und hier als Parameter uebergeben
            if breakthrough_item is not None:
                rewards["item_drop"] = breakthrough_item
                rewards["breakthrough_applied"] = True

        # DRAW: keine Belohnungen

        return rewards

    # -----------------------------------------
    # PVP-Belohnungen
    # -----------------------------------------

    def calculate_pvp_rewards(
        self,
        result: str,
        player_floor: int = 1,
        player_luk: int = 10,
        opponent_name: str = "Unbekannt",
        active_buffs: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Belohnungen nach einem PVP-Kampf berechnen.

        Args:
            result: "WIN", "LOSS" oder "DRAW"
            player_floor: Aktuelles Turm-Stockwerk (fuer PVP-Gold-Bonus)
            player_luk: LUK-Attribut
            opponent_name: Name des Gegners (fuer Log)
            active_buffs: Aktive Buffs

        Returns:
            Dict mit allen Belohnungen
        """
        rewards = {
            "type": "PVP",
            "result": result,
            "opponent": opponent_name,
            "exp": 0,
            "gold": 0,
            "diamonds": 0,
            "scrap": 0,
            "soul_shards": 0,
            "item_drop": None,
            "pvp_gold_bonus": 0.0
        }

        # PVP-Gold-Bonus: +1% pro 100 Stockwerke
        pvp_gold_bonus = (player_floor // 100) * PVP_GOLD_BONUS_PER_100_FLOORS
        rewards["pvp_gold_bonus"] = pvp_gold_bonus

        # Buff-Multiplikator
        buff_mult = 1.0
        if active_buffs:
            buff_mult += active_buffs.get("gold_bonus", 0.0)

        if result == "WIN":
            rewards["exp"] = EXP_WIN
            base_gold = self._rng.randint(GOLD_WIN_MIN, GOLD_WIN_MAX)
            rewards["gold"] = int(base_gold * (1.0 + pvp_gold_bonus) * buff_mult)
            rewards["diamonds"] = DIAMONDS_PVP_WIN

            drop = self._try_item_drop(player_luk)
            if drop:
                rewards["item_drop"] = drop

        elif result == "LOSS":
            rewards["exp"] = EXP_LOSS
            rewards["scrap"] = self._rng.randint(SCRAP_LOSS_MIN, SCRAP_LOSS_MAX)

        elif result == "DRAW":
            rewards["exp"] = EXP_WIN // 2

        return rewards

    # -----------------------------------------
    # Weltboss-Belohnungen
    # -----------------------------------------

    def calculate_worldboss_rewards(
        self,
        boss_tier: int = 1,
        player_luk: int = 10,
        damage_dealt: int = 0,
        total_damage: int = 1,
        player_count: int = 1
    ) -> Dict[str, Any]:
        """
        Belohnungen nach Weltboss-Kampf.

        Args:
            boss_tier: Boss-Tier (1-5)
            player_luk: LUK-Attribut
            damage_dealt: Eigener Schaden am Boss
            total_damage: Gesamtschaden aller Spieler
            player_count: Anzahl teilnehmender Spieler

        Returns:
            Dict mit Belohnungen
        """
        damage_share = damage_dealt / max(1, total_damage)

        base_diamonds = DIAMONDS_WORLDBOSS_BASE * boss_tier
        diamonds = int(base_diamonds * max(0.3, damage_share))

        raid_marks = max(1, int(boss_tier * damage_share * 5))
        exp = int(EXP_WIN * boss_tier * 2)

        item_drop = None
        if boss_tier >= 3:
            item_drop = self._generate_drop(player_luk, force_rarity="rare")
        else:
            item_drop = self._try_item_drop(player_luk, bonus_chance=0.30)

        return {
            "type": "WORLDBOSS",
            "boss_tier": boss_tier,
            "player_count": player_count,
            "damage_share": round(damage_share, 2),
            "exp": exp,
            "diamonds": diamonds,
            "raid_marks": raid_marks,
            "gold": 0,
            "soul_shards": 0,
            "scrap": 0,
            "item_drop": item_drop
        }

    # -----------------------------------------
    # PVP-Power-Skalierung
    # -----------------------------------------

    @staticmethod
    def calculate_pvp_power(base_stats: Dict[str, int], floor: int) -> Dict[str, int]:
        """
        PVP-Power berechnen (Spec Abschnitt 5C).

        PVP-Power = Base-Stats x (1 + log10(SF / 100))
        """
        if floor <= PVP_SCALING_DIVISOR:
            factor = 1.0
        else:
            factor = 1.0 + math.log10(floor / PVP_SCALING_DIVISOR)

        return {
            "atk": max(1, int(base_stats.get("atk", 10) * factor)),
            "def": max(1, int(base_stats.get("def", 10) * factor)),
            "spd": max(1, int(base_stats.get("spd", 10) * factor)),
            "luk": max(1, int(base_stats.get("luk", 10) * factor)),
            "pvp_factor": round(factor, 3),
            "floor_reference": floor
        }

    # -----------------------------------------
    # Level-Up Check
    # -----------------------------------------

    @staticmethod
    def check_level_up(current_exp: int, current_level: int) -> Dict[str, Any]:
        """
        Pruefen ob ein Level-Up faellig ist.

        Level-Up: Alle 500 EXP -> +5 Bonuspunkte
        """
        xp_needed = EXP_PER_LEVEL
        levels_gained = 0
        bonus_points = 0
        remaining_exp = current_exp

        while remaining_exp >= xp_needed:
            remaining_exp -= xp_needed
            levels_gained += 1
            bonus_points += LEVELUP_BONUS_POINTS

        return {
            "level_up": levels_gained > 0,
            "levels_gained": levels_gained,
            "new_level": current_level + levels_gained,
            "remaining_exp": remaining_exp,
            "bonus_points": bonus_points,
            "xp_per_level": xp_needed
        }

    # -----------------------------------------
    # Ascension-Check
    # -----------------------------------------

    @staticmethod
    def check_ascension(floor: int, current_ascension: int) -> Dict[str, Any]:
        """
        Pruefen ob eine neue Ascension-Stufe erreicht wurde.

        Ascension bei SF 1000/5000/10000.
        """
        new_ascension = current_ascension
        multiplier = 1.0

        for threshold, mult in sorted(ASCENSION_THRESHOLDS.items()):
            if floor >= threshold:
                new_ascension = max(new_ascension, threshold // 1000)
                multiplier = mult

        return {
            "ascended": new_ascension > current_ascension,
            "new_ascension": new_ascension,
            "multiplier": multiplier,
            "floor": floor
        }

    # -----------------------------------------
    # Kompensations-System
    # -----------------------------------------

    def _apply_compensation(
        self,
        item: Dict[str, Any],
        glass_cannon_factor: int,
        player_luk: int
    ) -> Optional[Dict[str, Any]]:
        """
        Kompensation auf ein gedroptes Item anwenden.

        Zwei moegliche Effekte (exklusiv, Prio: Weltboss > Raritaet):
          1. Weltboss-Fragment: Ring/Halskette mit 70% Stats
          2. Raritaets-Upgrade: common→rare, rare→legendary
        """
        worldboss_chance = glass_cannon_factor * COMPENSATION_WORLDBOSS_FACTOR
        if self._rng.random() < worldboss_chance:
            fragment = self._generate_worldboss_fragment(player_luk)
            return {"type": "worldboss_fragment", "item": fragment}

        rarity_chance = glass_cannon_factor * COMPENSATION_RARITY_FACTOR
        if self._rng.random() < rarity_chance:
            old_rarity = item["rarity"]
            new_rarity = RARITY_UPGRADE.get(old_rarity, old_rarity)
            if new_rarity != old_rarity:
                upgraded = self._generate_drop(player_luk, force_rarity=new_rarity)
                return {
                    "type": f"rarity_upgrade_{old_rarity}_to_{new_rarity}",
                    "item": upgraded
                }

        return None

    def _try_worldboss_fragment(
        self,
        glass_cannon_factor: int,
        player_luk: int
    ) -> Optional[Dict[str, Any]]:
        """Separater Weltboss-Fragment-Wurf (wenn kein normaler Drop)."""
        fragment_chance = glass_cannon_factor * COMPENSATION_WORLDBOSS_FACTOR * 0.5
        if self._rng.random() < fragment_chance:
            return self._generate_worldboss_fragment(player_luk)
        return None

    def _generate_worldboss_fragment(
        self,
        player_luk: int
    ) -> Dict[str, Any]:
        """
        Weltboss-Fragment generieren (Ring oder Halskette).

        Early-Access Schmuck-Items mit 70% der normalen Weltboss-Stats.
        """
        schmuck_types = ["Ring", "Halskette"]
        schmuck_type = self._rng.choice(schmuck_types)

        luk_legendary_bonus = (player_luk // 10) * 0.01
        legendary_chance = RARITY_LEGENDARY + luk_legendary_bonus

        if self._rng.random() < legendary_chance:
            rarity = "legendary"
            stat_min, stat_max = FRAGMENT_LEGENDARY_STATS
        else:
            rarity = "rare"
            stat_min, stat_max = FRAGMENT_RARE_STATS

        atk_mod = self._rng.randint(stat_min, stat_max)
        def_mod = self._rng.randint(stat_min, stat_max)

        if schmuck_type == "Ring":
            atk_mod = atk_mod + 2
        else:
            def_mod = def_mod + 2

        total_stats = atk_mod + def_mod
        base_value = total_stats * 5
        if rarity == "legendary":
            base_value = base_value * 3 * 80 // 100
        else:
            base_value = base_value * 2 * 80 // 100

        fragment_prefixes = {
            "rare": ["Zerbrochener", "Verblasster", "Alter"],
            "legendary": ["Strahlender", "Uralter", "Mystischer"]
        }
        prefix = self._rng.choice(fragment_prefixes.get(rarity, fragment_prefixes["rare"]))
        name = f"{prefix} {schmuck_type}"

        return {
            "name": name,
            "type": "Schmuck",
            "slot": schmuck_type.lower(),
            "rarity": rarity,
            "atk_mod": atk_mod,
            "def_mod": def_mod,
            "value": base_value,
            "equipped": False,
            "upgrade_level": 0,
            "is_fragment": True,
            "source": "compensation"
        }

    # -----------------------------------------
    # Interne Hilfsfunktionen
    # -----------------------------------------

    def _get_ascension_multiplier(self, floor: int) -> float:
        """Ascension-Multiplikator basierend auf Stockwerk."""
        mult = 1.0
        for threshold, m in sorted(ASCENSION_THRESHOLDS.items()):
            if floor >= threshold:
                mult = m
        return mult

    def _try_item_drop(
        self,
        player_luk: int,
        bonus_chance: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        """
        Wuerfeln ob ein Item droppt.

        Drop-Chance: 15% + (LUK x 0.5%) + Bonus
        """
        drop_chance = BASE_DROP_CHANCE + (player_luk * LUK_DROP_BONUS) + bonus_chance
        drop_chance = min(0.95, drop_chance)

        if self._rng.random() < drop_chance:
            return self._generate_drop(player_luk)
        return None

    def _generate_drop(
        self,
        player_luk: int,
        force_rarity: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Item generieren mit Seltenheitsstufe.

        Seltenheit (beeinflusst durch LUK):
          Gewoehnlich: 75% -> Stats 2-7
          Selten:      20% -> Stats 8-14
          Legendaer:    5% -> Stats 15-25
        """
        if force_rarity:
            rarity = force_rarity
        else:
            luk_legendary_bonus = (player_luk // 10) * 0.01
            luk_rare_bonus = (player_luk // 10) * 0.02

            legendary_chance = RARITY_LEGENDARY + luk_legendary_bonus
            rare_chance = RARITY_RARE + luk_rare_bonus
            common_chance = max(0.1, 1.0 - legendary_chance - rare_chance)

            roll = self._rng.random()
            if roll < legendary_chance:
                rarity = "legendary"
            elif roll < legendary_chance + rare_chance:
                rarity = "rare"
            else:
                rarity = "common"

        if rarity == "legendary":
            atk_mod = self._rng.randint(15, 25)
            def_mod = self._rng.randint(15, 25)
        elif rarity == "rare":
            atk_mod = self._rng.randint(8, 14)
            def_mod = self._rng.randint(8, 14)
        else:
            atk_mod = self._rng.randint(2, 7)
            def_mod = self._rng.randint(2, 7)

        item_types = [("Waffe", "atk"), ("Ruestung", "def")]
        item_type, primary_stat = self._rng.choice(item_types)

        total_stats = atk_mod + def_mod
        base_value = total_stats * 5
        if rarity == "legendary":
            base_value *= 3
        elif rarity == "rare":
            base_value *= 2

        name = self._generate_item_name(item_type, rarity)

        return {
            "name": name,
            "type": item_type,
            "rarity": rarity,
            "atk_mod": atk_mod if item_type == "Waffe" else atk_mod // 2,
            "def_mod": def_mod if item_type == "Ruestung" else def_mod // 2,
            "value": base_value,
            "equipped": False,
            "upgrade_level": 0
        }

    def _generate_item_name(self, item_type: str, rarity: str) -> str:
        """Prozeduralen Item-Namen generieren."""
        prefixes = {
            "common": ["Einfach", "Alt", "Rostig", "Schlicht"],
            "rare": ["Fein", "Stark", "Magisch", "Verzaubert"],
            "legendary": ["Episch", "Mythisch", "Goettlich", "Legendaer"]
        }
        weapons = ["Schwert", "Axt", "Dolch", "Stab", "Hammer", "Bogen"]
        armors = ["Schild", "Helm", "Ruestung", "Mantel", "Stiefel", "Handschuhe"]

        prefix = self._rng.choice(prefixes.get(rarity, prefixes["common"]))
        if item_type == "Waffe":
            base = self._rng.choice(weapons)
        else:
            base = self._rng.choice(armors)

        return f"{prefix}er {base}" if prefix[-1] != "h" else f"{prefix}es {base}"


# =============================================
# Reward-Anwendung auf Charakter
# =============================================

def apply_rewards(character: Dict[str, Any], rewards: Dict[str, Any]) -> Dict[str, Any]:
    """
    Belohnungen auf einen Charakter anwenden.

    Aktualisiert Gold, EXP, Diamanten, Seelen-Scherben, Scrap.
    Prueft auf Level-Up.
    Meldet Kompensations- und Durchbruch-Effekte.

    Args:
        character: Charakter-Dict (aus forge.py)
        rewards: Rewards-Dict (aus RewardCalculator)

    Returns:
        Dict mit updated_character, level_ups, messages
    """
    messages = []
    calc = RewardCalculator()

    # Waehrungen addieren
    character["gold"] = character.get("gold", 0) + rewards.get("gold", 0)
    character["diamonds"] = character.get("diamonds", 0) + rewards.get("diamonds", 0)
    character["soul_shards"] = character.get("soul_shards", 0) + rewards.get("soul_shards", 0)
    character["scrap"] = character.get("scrap", 0) + rewards.get("scrap", 0)

    if rewards.get("gold", 0) > 0:
        messages.append(f"+{rewards['gold']} Gold")
    if rewards.get("diamonds", 0) > 0:
        messages.append(f"+{rewards['diamonds']} Diamanten")
    if rewards.get("soul_shards", 0) > 0:
        messages.append(f"+{rewards['soul_shards']} Seelen-Scherben")

    # EXP addieren + Level-Up pruefen
    old_exp = character.get("exp", 0)
    new_exp = old_exp + rewards.get("exp", 0)
    character["exp"] = new_exp

    level_result = calc.check_level_up(new_exp, character.get("level", 1))
    if level_result["level_up"]:
        character["level"] = level_result["new_level"]
        character["exp"] = level_result["remaining_exp"]
        messages.append(
            f"LEVEL UP! Level {level_result['new_level']}! "
            f"+{level_result['bonus_points']} Bonuspunkte"
        )

    # Shiny-Meldung
    if rewards.get("is_shiny"):
        messages.append("SHINY GEFUNDEN! 10x Gold + Legendaerer Loot!")

    # Kompensations-Meldung
    compensation = rewards.get("compensation_applied")
    if compensation:
        if compensation == "worldboss_fragment":
            messages.append(
                "GLASKANONEN-BONUS: Weltboss-Fragment erhalten! "
                "Ein seltenes Schmuckstueck als Ausgleich!"
            )
        elif compensation.startswith("rarity_upgrade_"):
            parts = compensation.split("_")
            old_r = parts[2]
            new_r = parts[4]
            rarity_names = {
                "common": "Gewoehnlich",
                "rare": "Selten",
                "legendary": "Legendaer"
            }
            old_name = rarity_names.get(old_r, old_r)
            new_name = rarity_names.get(new_r, new_r)
            messages.append(
                f"GLASKANONEN-BONUS: Raritaets-Upgrade! "
                f"{old_name} → {new_name}!"
            )

    # Durchbruch-Meldung
    if rewards.get("breakthrough_applied"):
        messages.append(
            "DURCHBRUCH! Deine Beharrlichkeit wurde belohnt! "
            "Ein maechtiges Item erscheint!"
        )

    # Item-Drop-Meldung
    if rewards.get("item_drop"):
        item = rewards["item_drop"]
        item_msg = f"Item gefunden: {item['name']} ({item['rarity']})"
        if item.get("is_fragment"):
            item_msg += " [Weltboss-Fragment]"
        if item.get("source") == "breakthrough":
            item_msg += " [Durchbruch]"
        messages.append(item_msg)

    return {
        "character": character,
        "level_up": level_result,
        "messages": messages,
        "rewards_applied": rewards
    }


# =============================================
# Standalone-Test
# =============================================
if __name__ == "__main__":
    calc = RewardCalculator(seed=42)

    print("=== TOWER REWARDS TEST ===")
    tower_win = calc.calculate_tower_rewards(
        floor=50, result="WIN", player_luk=20, is_boss_floor=True
    )
    print(f"Turm SF 50 (Boss, Sieg): {tower_win['gold']}g, {tower_win['exp']}xp")
    if tower_win["item_drop"]:
        print(f"  Item: {tower_win['item_drop']['name']} ({tower_win['item_drop']['rarity']})")
    print(f"  Shiny: {tower_win['is_shiny']}")

    tower_loss = calc.calculate_tower_rewards(floor=50, result="LOSS")
    print(f"Turm SF 50 (Niederlage): {tower_loss['exp']}xp, {tower_loss['scrap']} Scrap")

    print("\n=== PVP REWARDS TEST ===")
    pvp_win = calc.calculate_pvp_rewards(
        result="WIN", player_floor=500, player_luk=25, opponent_name="NeonDrifter"
    )
    print(f"PVP Sieg vs NeonDrifter: {pvp_win['gold']}g, {pvp_win['diamonds']}d, {pvp_win['exp']}xp")

    print("\n=== WORLDBOSS REWARDS TEST ===")
    wb = calc.calculate_worldboss_rewards(
        boss_tier=3, player_luk=30, damage_dealt=5000, total_damage=15000, player_count=3
    )
    print(f"Weltboss Tier 3: {wb['diamonds']}d, {wb['raid_marks']} Marken, {wb['exp']}xp")
    if wb["item_drop"]:
        print(f"  Item: {wb['item_drop']['name']} ({wb['item_drop']['rarity']})")

    print("\n=== PVP POWER SCALING ===")
    base = {"atk": 25, "def": 40, "spd": 20, "luk": 15}
    for sf in [100, 500, 1000, 5000, 10000]:
        pvp = RewardCalculator.calculate_pvp_power(base, sf)
        print(f"  SF {sf:>5}: ATK={pvp['atk']:>3} DEF={pvp['def']:>3} "
              f"SPD={pvp['spd']:>3} LUK={pvp['luk']:>3} (x{pvp['pvp_factor']})")

    print("\n=== LEVEL-UP CHECK ===")
    for xp in [499, 500, 1200, 2500]:
        lu = RewardCalculator.check_level_up(xp, 1)
        print(f"  {xp:>5} XP: Level-Up={lu['level_up']}, "
              f"Neues Level={lu['new_level']}, +{lu['bonus_points']} Bonus")

    print("\n=== ASCENSION CHECK ===")
    for sf in [999, 1000, 5000, 10000]:
        asc = RewardCalculator.check_ascension(sf, 1)
        print(f"  SF {sf:>5}: Ascended={asc['ascended']}, Mult={asc['multiplier']}x")

    # =============================================
    # Kompensations-System Test
    # =============================================
    print("\n" + "=" * 60)
    print("=== KOMPENSATIONS-SYSTEM TEST ===")
    print("=" * 60)

    classes = {
        "Krieger": {"atk": 25, "def": 40, "luk": 15},
        "Schurke": {"atk": 25, "def": 15, "luk": 20},
        "Magier":  {"atk": 45, "def": 10, "luk": 25}
    }

    for class_name, stats in classes.items():
        gc = max(0, stats["atk"] - stats["def"])
        rarity_chance = gc * COMPENSATION_RARITY_FACTOR * 100
        wb_chance = gc * COMPENSATION_WORLDBOSS_FACTOR * 100
        print(f"\n--- {class_name} (ATK={stats['atk']}, DEF={stats['def']}) ---")
        print(f"  Glass-Cannon-Factor: {gc}")
        print(f"  Raritaets-Upgrade-Chance: {rarity_chance:.1f}%")
        print(f"  Weltboss-Fragment-Chance: {wb_chance:.1f}%")

    # =============================================
    # Durchbruch-System Test
    # =============================================
    print("\n" + "=" * 60)
    print("=== DURCHBRUCH-SYSTEM TEST ===")
    print("=" * 60)

    # Szenario: Magier haengt auf Floor 23 fest
    print("\n--- Szenario: Magier auf Floor 23 festgehangen ---")
    tracker = BreakthroughTracker()
    bt_gen = BreakthroughItemGenerator(seed=42)
    magier_stats = {"atk": 45, "def": 10, "spd": 20, "luk": 25}

    # Phase 1: Idle-Niederlagen (Spieler offline)
    print("\n  Phase 1: 20 Idle-Niederlagen (Spieler offline)...")
    tracker.mark_idle()
    for i in range(20):
        result = tracker.record_loss(23)
        assert result is None, "Idle darf keinen Durchbruch ausloesen!"
    print(f"  Status: {tracker.get_info()}")
    print(f"  → Kein Durchbruch (korrekt: Spieler war idle)")

    # Phase 2: Spieler loggt ein, keine Anpassung
    print("\n  Phase 2: Spieler loggt ein, kaempft ohne Anpassung...")
    tracker.mark_active()
    for i in range(5):
        result = tracker.record_loss(23)
        assert result is None, "Ohne Anpassung kein Durchbruch!"
    print(f"  Status: {tracker.get_info()}")
    print(f"  → Kein Durchbruch (korrekt: keine Anpassung gemacht)")

    # Phase 3: Spieler passt Build an
    print("\n  Phase 3: Spieler ruestet neues Item aus...")
    tracker.record_adjustment("equip")
    print(f"  Status: {tracker.get_info()}")

    # Phase 4: Aktive Niederlagen nach Anpassung → Stufe 1 Durchbruch
    print("\n  Phase 4: Aktive Niederlagen nach Anpassung...")
    for i in range(10):
        result = tracker.record_loss(23)
        if result is not None:
            print(f"  Fail #{i+1}: DURCHBRUCH ausgeloest!")
            print(f"    Stufe: {result['stage']}")
            print(f"    Raritaet: {result['rarity']}")
            print(f"    Typ: {result['type']}")
            print(f"    Floor: {result['floor']}")

            # Item generieren
            item = bt_gen.generate_breakthrough_item(
                result, magier_stats, player_luk=25
            )
            print(f"    Item: {item['name']} ({item['rarity']})")
            print(f"    ATK+{item['atk_mod']} DEF+{item['def_mod']}")
            print(f"    Typ: {item['type']}")
            if item.get("is_fragment"):
                print(f"    Slot: {item.get('slot', '-')}")
            break
        else:
            pass  # Noch kein Durchbruch
    print(f"  Status: {tracker.get_info()}")

    # Phase 5: Weitere Anpassung + Eskalation zu Stufe 2
    print("\n  Phase 5: Weitere Anpassung + Stufe 2 Eskalation...")
    tracker.record_adjustment("respec")
    for i in range(10):
        result = tracker.record_loss(23)
        if result is not None:
            print(f"  Fail #{i+1}: DURCHBRUCH Stufe {result['stage']}!")
            print(f"    Raritaet: {result['rarity']}, Typ: {result['type']}")
            item = bt_gen.generate_breakthrough_item(
                result, magier_stats, player_luk=25
            )
            print(f"    Item: {item['name']} ({item['rarity']})")
            print(f"    ATK+{item['atk_mod']} DEF+{item['def_mod']}")
            break
    print(f"  Status: {tracker.get_info()}")

    # Phase 6: Eskalation zu Stufe 3 (Weltboss-Fragment)
    print("\n  Phase 6: Eskalation zu Stufe 3 (Weltboss-Fragment)...")
    tracker.record_adjustment("upgrade")
    for i in range(15):
        result = tracker.record_loss(23)
        if result is not None:
            print(f"  Fail #{i+1}: DURCHBRUCH Stufe {result['stage']}!")
            print(f"    Raritaet: {result['rarity']}, Typ: {result['type']}")
            item = bt_gen.generate_breakthrough_item(
                result, magier_stats, player_luk=25
            )
            print(f"    Item: {item['name']} ({item['rarity']})")
            print(f"    ATK+{item['atk_mod']} DEF+{item['def_mod']}")
            if item.get("is_fragment"):
                print(f"    Slot: {item['slot']} [Weltboss-Fragment]")
            break
    print(f"  Status: {tracker.get_info()}")

    # Phase 7: Spieler gewinnt endlich!
    print("\n  Phase 7: SIEG auf Floor 23! Fortschritt!")
    tracker.record_progress(24)
    print(f"  Status: {tracker.get_info()}")
    print(f"  → Tracker zurueckgesetzt (Spieler macht Fortschritt)")

    # =============================================
    # Schwaeche-Erkennung Test
    # =============================================
    print("\n" + "=" * 60)
    print("=== SCHWAECHE-ERKENNUNG TEST ===")
    print("=" * 60)

    gen = BreakthroughItemGenerator(seed=123)
    test_classes = {
        "Krieger": {"atk": 25, "def": 40, "spd": 20, "luk": 15},
        "Schurke": {"atk": 25, "def": 15, "spd": 40, "luk": 20},
        "Magier":  {"atk": 45, "def": 10, "spd": 20, "luk": 25}
    }

    bt_info_rare = {"stage": 1, "rarity": "rare", "type": "targeted_item",
                    "floor": 25, "active_fails": 3, "adjustments": 1}
    bt_info_leg = {"stage": 2, "rarity": "legendary", "type": "targeted_item",
                   "floor": 25, "active_fails": 8, "adjustments": 2}

    for name, stats in test_classes.items():
        weakness = gen._analyze_weakness(stats)
        print(f"\n  {name} (ATK={stats['atk']}, DEF={stats['def']}):")
        print(f"    Schwaeche: {weakness.upper()}")

        item_r = gen.generate_breakthrough_item(bt_info_rare, stats)
        item_l = gen.generate_breakthrough_item(bt_info_leg, stats)
        print(f"    Stufe 1 (rare): {item_r['name']} → {item_r['type']} "
              f"ATK+{item_r['atk_mod']} DEF+{item_r['def_mod']}")
        print(f"    Stufe 2 (leg.): {item_l['name']} → {item_l['type']} "
              f"ATK+{item_l['atk_mod']} DEF+{item_l['def_mod']}")

    # =============================================
    # Integration: Durchbruch + Rewards
    # =============================================
    print("\n" + "=" * 60)
    print("=== INTEGRATION: Durchbruch + Reward-System ===")
    print("=" * 60)

    print("\n  Simuliere: Magier auf Floor 23, aktive Session mit Anpassung")
    int_tracker = BreakthroughTracker()
    int_gen = BreakthroughItemGenerator(seed=555)
    int_calc = RewardCalculator(seed=555)

    int_tracker.mark_active()
    int_tracker.record_adjustment("equip")

    test_char = {
        "name": "Magier_Durchbruch",
        "level": 5,
        "exp": 400,
        "gold": 500,
        "diamonds": 0,
        "soul_shards": 0,
        "scrap": 10
    }

    for i in range(10):
        bt_result = int_tracker.record_loss(23)
        bt_item = None
        if bt_result is not None:
            bt_item = int_gen.generate_breakthrough_item(
                bt_result,
                {"atk": 45, "def": 10, "spd": 20, "luk": 25},
                player_luk=25
            )

        rewards = int_calc.calculate_tower_rewards(
            floor=23,
            result="LOSS",
            player_luk=25,
            player_atk_base=45,
            player_def_base=10,
            breakthrough_item=bt_item
        )

        result = apply_rewards(test_char.copy(), rewards)

        if rewards["breakthrough_applied"]:
            print(f"\n  Kampf #{i+1}: DURCHBRUCH!")
            for msg in result["messages"]:
                print(f"    → {msg}")
            break
        else:
            print(f"  Kampf #{i+1}: Niederlage "
                  f"(+{rewards['exp']}xp, +{rewards['scrap']} Scrap)")

    print(f"\n  Tracker: {int_tracker.get_info()}")

    # =============================================
    # Persistenz-Test: State speichern/laden
    # =============================================
    print("\n" + "=" * 60)
    print("=== PERSISTENZ-TEST ===")
    print("=" * 60)

    tracker_a = BreakthroughTracker()
    tracker_a.mark_active()
    tracker_a.record_adjustment("equip")
    tracker_a.record_loss(15)
    tracker_a.record_loss(15)

    # State exportieren (wuerde im Charakter gespeichert)
    saved_state = tracker_a.get_state()
    print(f"  Gespeicherter State: stuck_floor={saved_state['stuck_floor']}, "
          f"fails_since_adj={saved_state['fails_since_adjustment']}, "
          f"adjustments={saved_state['adjustments_made']}")

    # State importieren (z.B. nach Server-Neustart)
    tracker_b = BreakthroughTracker(state=saved_state)
    print(f"  Geladener Tracker: {tracker_b.get_info()}")

    # Weitermachen wo aufgehoert
    bt_result = tracker_b.record_loss(15)
    if bt_result:
        print(f"  → Durchbruch nach Laden: Stufe {bt_result['stage']}!")
    else:
        print(f"  → Kein Durchbruch (noch {3 - saved_state['fails_since_adjustment'] - 1} Fails noetig)")
    print(f"  Tracker nach Loss: {tracker_b.get_info()}")
