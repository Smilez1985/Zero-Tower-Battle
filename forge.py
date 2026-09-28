#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Charakter-Schmiede (Forge)
=====================================================
Modul fuer die initiale Charakter-Erstellung.

Ablauf:
  1. Klasse waehlen (Krieger/Schurke/Magier)
  2. 100 Punkte auf 4 Attribute verteilen (ATK/DEF/SPD/LUK)
  3. Max 50 pro Attribut
  4. Charakter-Name eingeben
  5. Charakter in DB speichern

Das 100-Punkte-Gesetz:
  - Jede Klasse hat feste Basiswerte (Summe = 100)
  - Spieler kann die 100 Punkte frei umverteilen
  - Pro Level-Up: +5 Bonuspunkte (in separatem "extra"-Feld)
  - Bonuspunkte sind NICHT Teil der 100

Klassen-Typen (Schere-Stein-Papier):
  Krieger (Stein)  > Schurke (Schere) > Magier (Papier) > Krieger
  Typ-Vorteil: x1.25 Schaden

Referenz: Battle-Pi_Konsolidiert.txt Abschnitt 4 + 12
"""

import json
import os
import time
from typing import Dict, Any, Optional, Tuple


# =============================================
# Klassen-Definitionen (verbindlich aus Spec)
# =============================================
# Abschnitt 4A: Klassen-Basiswerte
# Summe MUSS immer 100 ergeben!

CLASSES = {
    "Krieger": {
        "type": "Stein",
        "description_de": "Defensiver Kaempfer. Haelt viel aus, schlaegt solide zu.",
        "description_en": "Defensive fighter. Tanks well, hits solidly.",
        "focus": "Defensive",
        "base_stats": {
            "atk": 25,
            "def": 40,
            "spd": 20,
            "luk": 15
        }
        # Spec sagt Krieger=Defensive mit Summe=100
        # Original (20/35/15/10=80) korrigiert auf 100
    },
    "Schurke": {
        "type": "Schere",
        "description_de": "Schneller Angreifer. Hohe Geschwindigkeit und Glueck.",
        "description_en": "Fast attacker. High speed and luck.",
        "focus": "Tempo",
        "base_stats": {
            "atk": 25,
            "def": 15,
            "spd": 40,
            "luk": 20
        }
    },
    "Magier": {
        "type": "Papier",
        "description_de": "Glaskanone. Enormer Schaden, aber zerbrechlich.",
        "description_en": "Glass cannon. Enormous damage, but fragile.",
        "focus": "Glaskanone",
        "base_stats": {
            "atk": 45,
            "def": 10,
            "spd": 20,
            "luk": 25
        }
    }
}

# Constraints
STAT_SUM_TARGET = 100       # Summe aller Basis-Stats MUSS 100 sein
STAT_MAX_PER_ATTRIBUTE = 50  # Kein Attribut darf ueber 50 gehen
STAT_MIN_PER_ATTRIBUTE = 1   # Kein Attribut darf unter 1 fallen
LEVELUP_BONUS_POINTS = 5    # +5 Bonuspunkte pro Level-Up
START_GOLD = 100             # Startgold laut Spec (Abschnitt 9)
START_HP = 100               # Start-HP laut Spec (Abschnitt 5A)
START_FLOOR = 1              # Startstockwerk
START_ASCENSION = 1          # Start-Ascension
XP_PER_LEVEL = 500           # XP pro Level-Up (Abschnitt 6B)


# =============================================
# Validierung
# =============================================

def validate_stat_distribution(atk: int, def_: int, spd: int, luk: int) -> Tuple[bool, str]:
    """
    Validiere eine Stat-Verteilung gegen das 100-Punkte-Gesetz.

    Args:
        atk: Angriff
        def_: Verteidigung
        spd: Geschwindigkeit
        luk: Glueck

    Returns:
        Tuple (valid, error_message)
    """
    stats = {"ATK": atk, "DEF": def_, "SPD": spd, "LUK": luk}
    total = atk + def_ + spd + luk

    # Summe muss exakt 100 sein
    if total != STAT_SUM_TARGET:
        return False, f"Summe ist {total}, muss aber exakt {STAT_SUM_TARGET} sein."

    # Kein Attribut ueber Maximum
    for name, value in stats.items():
        if value > STAT_MAX_PER_ATTRIBUTE:
            return False, f"{name} ist {value}, Maximum ist {STAT_MAX_PER_ATTRIBUTE}."
        if value < STAT_MIN_PER_ATTRIBUTE:
            return False, f"{name} ist {value}, Minimum ist {STAT_MIN_PER_ATTRIBUTE}."

    return True, "OK"


def validate_class_name(class_name: str) -> bool:
    """Pruefe ob Klassenname gueltig ist."""
    return class_name in CLASSES


# =============================================
# Charakter-Erstellung
# =============================================

class CharacterForge:
    """
    Charakter-Schmiede fuer die initiale Erstellung.

    Zustaendigkeiten:
    - Klasse waehlen + Basiswerte anzeigen
    - 100 Punkte frei verteilen lassen
    - Validierung gegen 100-Punkte-Gesetz
    - Charakter-Daten als Dict erzeugen
    - In DB speichern (ueber Callback oder direkt)
    """

    def __init__(self):
        self._db = None

    def _get_db(self):
        """Lazy-Load CharacterDB."""
        if self._db is None:
            from models.character_db import CharacterDB
            self._db = CharacterDB()
        return self._db

    # -----------------------------------------
    # Klassen-Info
    # -----------------------------------------

    def get_available_classes(self) -> Dict[str, Dict]:
        """Alle verfuegbaren Klassen mit Beschreibung und Basiswerten."""
        result = {}
        for name, data in CLASSES.items():
            base = data["base_stats"]
            result[name] = {
                "type": data["type"],
                "focus": data["focus"],
                "description_de": data["description_de"],
                "description_en": data["description_en"],
                "base_stats": base.copy(),
                "stat_sum": sum(base.values())
            }
        return result

    def get_class_defaults(self, class_name: str) -> Optional[Dict[str, int]]:
        """Basiswerte einer Klasse als Startpunkt fuer Verteilung."""
        if class_name not in CLASSES:
            return None
        return CLASSES[class_name]["base_stats"].copy()

    # -----------------------------------------
    # Charakter erstellen
    # -----------------------------------------

    def create_character(
        self,
        name: str,
        class_name: str,
        atk: int,
        def_: int,
        spd: int,
        luk: int,
        language: str = "de"
    ) -> Dict[str, Any]:
        """
        Neuen Charakter erstellen.

        Args:
            name: Charakter-Name (1-20 Zeichen)
            class_name: Klasse (Krieger/Schurke/Magier)
            atk: Angriffswert (1-50, Summe aller = 100)
            def_: Verteidigungswert (1-50)
            spd: Geschwindigkeit (1-50)
            luk: Glueck (1-50)
            language: Sprache (de/en)

        Returns:
            Dict mit result, character (bei Erfolg) oder error (bei Fehler)
        """
        # Name validieren
        name = name.strip()
        if not name or len(name) > 20:
            return {
                "result": "ERROR",
                "error": "Name muss 1-20 Zeichen lang sein."
            }

        # Klasse validieren
        if not validate_class_name(class_name):
            valid_classes = ", ".join(CLASSES.keys())
            return {
                "result": "ERROR",
                "error": f"Unbekannte Klasse '{class_name}'. Gueltig: {valid_classes}"
            }

        # Stats validieren (100-Punkte-Gesetz)
        valid, error_msg = validate_stat_distribution(atk, def_, spd, luk)
        if not valid:
            return {
                "result": "ERROR",
                "error": f"Stat-Validierung fehlgeschlagen: {error_msg}"
            }

        # Klassen-Daten holen
        class_data = CLASSES[class_name]

        # Charakter-Dict aufbauen (DB-kompatibel, Spec Abschnitt 9)
        character = {
            "name": name,
            "klasse": class_name,
            "type": class_data["type"],
            "focus": class_data["focus"],
            "level": 1,
            "exp": 0,
            "xp_per_level": XP_PER_LEVEL,

            # Basis-Stats (100-Punkte-Gesetz, vom Spieler verteilt)
            "atk_base": atk,
            "def_base": def_,
            "spd_base": spd,
            "luk_base": luk,

            # Extra-Stats (durch Level-Ups, NICHT Teil der 100)
            "atk_extra": 0,
            "def_extra": 0,
            "spd_extra": 0,
            "luk_extra": 0,

            # Effektiv-Stats (Basis + Extra, berechnet)
            "atk_effective": atk,
            "def_effective": def_,
            "spd_effective": spd,
            "luk_effective": luk,

            # Kampf-Zustand
            "hp": START_HP,
            "max_hp": START_HP,

            # Psyche (champion_psyche.py verwaltet diese Werte)
            "exhaustion": 0.0,       # 0-100%, +2 pro Turm-Kampf
            "morale": 100.0,         # 0-100%, Login-Bonus
            "trauma": [],            # Liste aktiver Phobien

            # Progression
            "current_floor": START_FLOOR,
            "ascension": START_ASCENSION,
            "pvp_wins": 0,
            "pvp_losses": 0,

            # Wirtschaft
            "gold": START_GOLD,
            "diamonds": 0,
            "soul_shards": 0,        # Seelen-Scherben (ab SF 100)

            # Materialien (Spec Abschnitt 9: materials-Tabelle)
            "scrap": 10,             # Start: 10 Scrap
            "essence": 0,
            "cores": 0,

            # Einstellungen
            "language": language,

            # Meta
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_playtime_seconds": 0,
            "last_login": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        return {
            "result": "SUCCESS",
            "character": character
        }

    def create_with_defaults(
        self,
        name: str,
        class_name: str,
        language: str = "de"
    ) -> Dict[str, Any]:
        """
        Charakter mit Klassen-Standardwerten erstellen.
        Nutzt die Basiswerte der gewaehlten Klasse direkt.

        Args:
            name: Charakter-Name
            class_name: Klasse
            language: Sprache

        Returns:
            Dict mit result, character
        """
        defaults = self.get_class_defaults(class_name)
        if defaults is None:
            return {
                "result": "ERROR",
                "error": f"Unbekannte Klasse '{class_name}'."
            }

        return self.create_character(
            name=name,
            class_name=class_name,
            atk=defaults["atk"],
            def_=defaults["def"],
            spd=defaults["spd"],
            luk=defaults["luk"],
            language=language
        )

    # -----------------------------------------
    # Stats umverteilen (Reforge)
    # -----------------------------------------

    def reforge_stats(
        self,
        character: Dict[str, Any],
        new_atk: int,
        new_def: int,
        new_spd: int,
        new_luk: int
    ) -> Dict[str, Any]:
        """
        Basis-Stats eines bestehenden Charakters umverteilen.
        Nur die 100 Basis-Punkte werden neu verteilt.
        Extra-Punkte (Level-Up) bleiben unberuehrt.

        Args:
            character: Bestehendes Charakter-Dict
            new_atk: Neuer ATK-Basiswert
            new_def: Neuer DEF-Basiswert
            new_spd: Neuer SPD-Basiswert
            new_luk: Neuer LUK-Basiswert

        Returns:
            Dict mit result, character (aktualisiert)
        """
        valid, error_msg = validate_stat_distribution(
            new_atk, new_def, new_spd, new_luk
        )
        if not valid:
            return {
                "result": "ERROR",
                "error": f"Reforge fehlgeschlagen: {error_msg}"
            }

        # Basis-Stats aktualisieren
        character["atk_base"] = new_atk
        character["def_base"] = new_def
        character["spd_base"] = new_spd
        character["luk_base"] = new_luk

        # Effektiv-Stats neu berechnen (Basis + Extra)
        character["atk_effective"] = new_atk + character.get("atk_extra", 0)
        character["def_effective"] = new_def + character.get("def_extra", 0)
        character["spd_effective"] = new_spd + character.get("spd_extra", 0)
        character["luk_effective"] = new_luk + character.get("luk_extra", 0)

        return {
            "result": "SUCCESS",
            "character": character
        }

    # -----------------------------------------
    # Level-Up Bonuspunkte verteilen
    # -----------------------------------------

    def apply_levelup_points(
        self,
        character: Dict[str, Any],
        atk_bonus: int = 0,
        def_bonus: int = 0,
        spd_bonus: int = 0,
        luk_bonus: int = 0
    ) -> Dict[str, Any]:
        """
        Level-Up Bonuspunkte verteilen.
        Diese sind NICHT Teil der 100 Basis-Punkte.
        Pro Level-Up stehen 5 Punkte zur Verfuegung.

        Args:
            character: Charakter-Dict
            atk_bonus: Punkte auf ATK
            def_bonus: Punkte auf DEF
            spd_bonus: Punkte auf SPD
            luk_bonus: Punkte auf LUK

        Returns:
            Dict mit result, character, points_spent
        """
        total_bonus = atk_bonus + def_bonus + spd_bonus + luk_bonus

        if total_bonus != LEVELUP_BONUS_POINTS:
            return {
                "result": "ERROR",
                "error": f"Genau {LEVELUP_BONUS_POINTS} Punkte verteilen, nicht {total_bonus}."
            }

        # Extra-Stats erhoehen (kein Cap auf Extra-Punkte laut Spec)
        character["atk_extra"] = character.get("atk_extra", 0) + atk_bonus
        character["def_extra"] = character.get("def_extra", 0) + def_bonus
        character["spd_extra"] = character.get("spd_extra", 0) + spd_bonus
        character["luk_extra"] = character.get("luk_extra", 0) + luk_bonus

        # Effektiv-Stats neu berechnen
        character["atk_effective"] = character["atk_base"] + character["atk_extra"]
        character["def_effective"] = character["def_base"] + character["def_extra"]
        character["spd_effective"] = character["spd_base"] + character["spd_extra"]
        character["luk_effective"] = character["luk_base"] + character["luk_extra"]

        return {
            "result": "SUCCESS",
            "character": character,
            "points_spent": total_bonus
        }

    # -----------------------------------------
    # Effektiv-Stats berechnen (mit Erschoepfung)
    # -----------------------------------------

    @staticmethod
    def calculate_effective_stats(character: Dict[str, Any]) -> Dict[str, int]:
        """
        Berechne Effektiv-Stats nach dem Dreischichten-Modell.

        Effektiv-Stat = (Basis + Extra) x Erschoepfungs-Faktor

        Erschoepfungs-Faktoren (Spec Abschnitt 4B):
          - 0-49%:  Faktor 1.0 (kein Malus)
          - 50-79%: Faktor 0.9 (-10% auf alles)
          - 80-99%: Faktor 0.8 (-20% auf ATK, PVP kann auto-abgelehnt werden)
          - 100%:   Kampfverweigerung (Faktor 0.0)

        Args:
            character: Charakter-Dict

        Returns:
            Dict mit effective atk/def/spd/luk und exhaustion_factor
        """
        exhaustion = character.get("exhaustion", 0.0)

        # Erschoepfungs-Faktor bestimmen
        if exhaustion >= 100.0:
            factor = 0.0    # Kampfverweigerung!
        elif exhaustion >= 80.0:
            factor = 0.8    # -20% auf ATK
        elif exhaustion >= 50.0:
            factor = 0.9    # -10% auf alles
        else:
            factor = 1.0    # Kein Malus

        # Basis + Extra
        raw_atk = character.get("atk_base", 0) + character.get("atk_extra", 0)
        raw_def = character.get("def_base", 0) + character.get("def_extra", 0)
        raw_spd = character.get("spd_base", 0) + character.get("spd_extra", 0)
        raw_luk = character.get("luk_base", 0) + character.get("luk_extra", 0)

        # Faktor anwenden
        return {
            "atk": max(1, int(raw_atk * factor)),
            "def": max(1, int(raw_def * factor)),
            "spd": max(1, int(raw_spd * factor)),
            "luk": max(1, int(raw_luk * factor)),
            "exhaustion": exhaustion,
            "exhaustion_factor": factor,
            "can_fight": factor > 0.0
        }

    # -----------------------------------------
    # Speichern & Laden
    # -----------------------------------------

    def save_character_to_db(self, character: Dict[str, Any]) -> Dict[str, Any]:
        """Charakter in die CharacterDB speichern."""
        db = self._get_db()
        return db.create_character(
            name=character["name"],
            level=character.get("level", 1),
            class_name=character.get("klasse", "Krieger"),
            gold=character.get("gold", START_GOLD),
            hp=character.get("hp", START_HP)
        )

    def save_character_to_cold(self, character: Dict[str, Any]) -> bool:
        """Charakter persistent in Cold Storage speichern."""
        try:
            from game.hot_storage import ColdStorageManager
            cold = ColdStorageManager()
            return cold.save("character_data", character)
        except ImportError:
            return False

    def load_character_from_cold(self) -> Optional[Dict[str, Any]]:
        """Charakter aus Cold Storage laden (Recovery nach Crash)."""
        try:
            from game.hot_storage import ColdStorageManager
            cold = ColdStorageManager()
            return cold.load("character_data")
        except ImportError:
            return None

    # -----------------------------------------
    # Terminal-UI (SSH-Interaktion)
    # -----------------------------------------

    def interactive_create(self) -> Optional[Dict[str, Any]]:
        """
        Interaktive Charakter-Erstellung im Terminal.
        Wird beim Erststart aufgerufen.

        Returns:
            Charakter-Dict oder None bei Abbruch
        """
        try:
            print("\n" + "=" * 50)
            print("  ZERO TOWER BATTLE - Charakter-Schmiede")
            print("=" * 50)

            # 1. Name
            print("\nWaehle einen Namen fuer deinen Champion:")
            name = input("  Name (1-20 Zeichen): ").strip()
            if not name or len(name) > 20:
                print("[FORGE] Ungueltiger Name.")
                return None

            # 2. Klasse waehlen
            print("\nWaehle deine Klasse:")
            print("-" * 40)
            classes = self.get_available_classes()
            class_list = list(classes.keys())

            for i, (cls_name, cls_info) in enumerate(classes.items(), 1):
                base = cls_info["base_stats"]
                print(f"  [{i}] {cls_name} ({cls_info['type']}) - {cls_info['focus']}")
                print(f"      ATK:{base['atk']} DEF:{base['def']} "
                      f"SPD:{base['spd']} LUK:{base['luk']}")
                print(f"      {cls_info['description_de']}")
                print()

            choice = input("  Klasse (1-3): ").strip()
            try:
                class_idx = int(choice) - 1
                if class_idx < 0 or class_idx >= len(class_list):
                    print("[FORGE] Ungueltige Auswahl.")
                    return None
                class_name = class_list[class_idx]
            except ValueError:
                print("[FORGE] Ungueltige Eingabe.")
                return None

            # 3. Stats verteilen oder Defaults nutzen
            defaults = self.get_class_defaults(class_name)
            print(f"\nKlasse: {class_name}")
            print(f"Basiswerte: ATK:{defaults['atk']} DEF:{defaults['def']} "
                  f"SPD:{defaults['spd']} LUK:{defaults['luk']}")
            print(f"\nMoechtest du die Punkte selbst verteilen?")
            print(f"  [1] Basiswerte uebernehmen")
            print(f"  [2] Punkte selbst verteilen (Summe = {STAT_SUM_TARGET})")

            distribute = input("  Auswahl (1-2): ").strip()

            if distribute == "2":
                # Eigene Verteilung
                print(f"\nVerteile {STAT_SUM_TARGET} Punkte "
                      f"(max {STAT_MAX_PER_ATTRIBUTE} pro Attribut):")

                while True:
                    try:
                        atk = int(input(f"  ATK ({STAT_MIN_PER_ATTRIBUTE}-{STAT_MAX_PER_ATTRIBUTE}): "))
                        def_ = int(input(f"  DEF ({STAT_MIN_PER_ATTRIBUTE}-{STAT_MAX_PER_ATTRIBUTE}): "))
                        spd = int(input(f"  SPD ({STAT_MIN_PER_ATTRIBUTE}-{STAT_MAX_PER_ATTRIBUTE}): "))
                        luk = int(input(f"  LUK ({STAT_MIN_PER_ATTRIBUTE}-{STAT_MAX_PER_ATTRIBUTE}): "))
                    except ValueError:
                        print("  Bitte nur Zahlen eingeben.")
                        continue

                    valid, error_msg = validate_stat_distribution(atk, def_, spd, luk)
                    if valid:
                        break
                    else:
                        print(f"  Fehler: {error_msg}")
                        print("  Nochmal versuchen...\n")
            else:
                atk = defaults["atk"]
                def_ = defaults["def"]
                spd = defaults["spd"]
                luk = defaults["luk"]

            # 4. Charakter erstellen
            result = self.create_character(
                name=name,
                class_name=class_name,
                atk=atk,
                def_=def_,
                spd=spd,
                luk=luk
            )

            if result["result"] == "SUCCESS":
                char = result["character"]
                print("\n" + "=" * 50)
                print(f"  Champion '{char['name']}' geschmiedet!")
                print(f"  Klasse: {char['klasse']} ({char['type']})")
                print(f"  ATK:{char['atk_base']} DEF:{char['def_base']} "
                      f"SPD:{char['spd_base']} LUK:{char['luk_base']}")
                print(f"  Gold: {char['gold']} | HP: {char['hp']}")
                print("=" * 50)
                print("\a", end="", flush=True)  # Bell: Charakter erstellt!
                return char
            else:
                print(f"\n[FORGE-ERROR] {result['error']}")
                return None

        except (EOFError, KeyboardInterrupt):
            print("\n[FORGE] Abgebrochen.")
            return None


# =============================================
# Standalone-Test
# =============================================
if __name__ == "__main__":
    forge = CharacterForge()

    # Test: Klassen anzeigen
    print("Verfuegbare Klassen:")
    for name, info in forge.get_available_classes().items():
        print(f"  {name}: {info['base_stats']} (Summe: {info['stat_sum']})")

    # Test: Charakter mit Defaults erstellen
    result = forge.create_with_defaults("TestHeld", "Schurke")
    if result["result"] == "SUCCESS":
        char = result["character"]
        print(f"\nCharakter: {char['name']} ({char['klasse']})")
        print(f"  ATK:{char['atk_base']} DEF:{char['def_base']} "
              f"SPD:{char['spd_base']} LUK:{char['luk_base']}")
        print(f"  Gold:{char['gold']} Diamonds:{char['diamonds']} "
              f"Shards:{char['soul_shards']}")

        # Test: Effektiv-Stats
        effective = CharacterForge.calculate_effective_stats(char)
        print(f"  Effektiv: ATK:{effective['atk']} DEF:{effective['def']} "
              f"SPD:{effective['spd']} LUK:{effective['luk']}")
        print(f"  Kampffaehig: {effective['can_fight']}")

    # Test: Validierung
    print(f"\nValidierung (25/25/25/25): {validate_stat_distribution(25, 25, 25, 25)}")
    print(f"Validierung (60/20/10/10): {validate_stat_distribution(60, 20, 10, 10)}")
    print(f"Validierung (50/20/20/10): {validate_stat_distribution(50, 20, 20, 10)}")
