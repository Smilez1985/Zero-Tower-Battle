#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Game Initializer
===========================================
Erststart-Ablauf und System-Initialisierung.

Ablauf beim Erststart:
  1. Pruefe ob Cold Storage existiert (Crash-Recovery)
  2. Pruefe ob Charakter bereits vorhanden
  3. Falls nicht: Device-Name, Sprache waehlen, Charakter-Forge
  4. DB-Tabellen initialisieren (5 verbindliche Tabellen)
  5. Config schreiben / validieren
  6. Hot/Cold Storage Pfade anlegen
  7. Systemdienste starten (Backup-Timer, Shutdown-Hook)

Ablauf bei normalem Start:
  1. Cold Storage pruefen -> Hot Storage laden
  2. Charakter laden und validieren
  3. Psyche-System initialisieren
  4. State Machine auf IDLE setzen

Referenz: Battle-Pi_Konsolidiert.txt Abschnitte 3, 9, 11
"""

import json
import os
import sqlite3
import signal
import time
from typing import Dict, Any, Optional, Tuple
from pathlib import Path


# =============================================
# Pfad-Konstanten (verbindlich laut Spec)
# =============================================

# Dynamische Pfade (zentral ueber core.paths)
try:
    from core.paths import (
        COLD_DB_PATH, COLD_STORAGE_DIR, BACKUP_DIR, LOG_DIR,
        HOT_STORAGE_DIR, CONFIG_FILE as CONFIG_PATH_MAIN, GAME_DIR
    )
    CONFIG_PATH_APP = os.path.join(GAME_DIR, "config", "config.json")
except ImportError:
    # Fallback fuer Standalone-Ausfuehrung
    _home = os.path.expanduser("~")
    COLD_DB_PATH = os.path.join(_home, "cold_storage.db")
    COLD_STORAGE_DIR = os.path.join(_home, "ztb_cold_storage")
    BACKUP_DIR = os.path.join(_home, "battle_game", "backups")
    LOG_DIR = os.path.join(_home, "battle_game", "logs")
    CONFIG_PATH_MAIN = os.path.join(os.path.dirname(__file__), "config.json")
    CONFIG_PATH_APP = os.path.join(os.path.dirname(__file__), "config", "config.json")

# Hot Storage (RAM, fluechtig)
HOT_STORAGE_DIR = HOT_STORAGE_DIR if 'HOT_STORAGE_DIR' in dir() else "/tmp/ztb_hot_storage"
RAM_DB_PATH = "/dev/shm/ztb.db"

# Versionierung
GAME_VERSION = "1.0.0"
GAME_NAME = "Zero Tower Battle"
SERVICE_NAME = "zero-tower-battle"


# =============================================
# DB-Schema (5 verbindliche Tabellen laut Spec)
# =============================================

DB_SCHEMA = {
    "player": """
        CREATE TABLE IF NOT EXISTS player (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            klasse TEXT NOT NULL DEFAULT 'Krieger',
            typ TEXT NOT NULL DEFAULT 'Stein',
            level INTEGER NOT NULL DEFAULT 1,
            exp INTEGER NOT NULL DEFAULT 0,
            hp INTEGER NOT NULL DEFAULT 100,
            max_hp INTEGER NOT NULL DEFAULT 100,
            atk_base INTEGER NOT NULL DEFAULT 25,
            def_base INTEGER NOT NULL DEFAULT 40,
            spd_base INTEGER NOT NULL DEFAULT 20,
            luk_base INTEGER NOT NULL DEFAULT 15,
            atk_extra INTEGER NOT NULL DEFAULT 0,
            def_extra INTEGER NOT NULL DEFAULT 0,
            spd_extra INTEGER NOT NULL DEFAULT 0,
            luk_extra INTEGER NOT NULL DEFAULT 0,
            gold INTEGER NOT NULL DEFAULT 100,
            diamonds INTEGER NOT NULL DEFAULT 0,
            soul_shards INTEGER NOT NULL DEFAULT 0,
            scrap INTEGER NOT NULL DEFAULT 10,
            essence INTEGER NOT NULL DEFAULT 0,
            cores INTEGER NOT NULL DEFAULT 0,
            current_floor INTEGER NOT NULL DEFAULT 1,
            ascension INTEGER NOT NULL DEFAULT 1,
            pvp_wins INTEGER NOT NULL DEFAULT 0,
            pvp_losses INTEGER NOT NULL DEFAULT 0,
            exhaustion REAL NOT NULL DEFAULT 0.0,
            morale REAL NOT NULL DEFAULT 100.0,
            language TEXT NOT NULL DEFAULT 'de',
            total_playtime_seconds INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "inventory": """
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            item_type TEXT NOT NULL DEFAULT 'weapon',
            rarity TEXT NOT NULL DEFAULT 'common',
            atk_bonus INTEGER NOT NULL DEFAULT 0,
            def_bonus INTEGER NOT NULL DEFAULT 0,
            spd_bonus INTEGER NOT NULL DEFAULT 0,
            luk_bonus INTEGER NOT NULL DEFAULT 0,
            rune_slot TEXT DEFAULT NULL,
            upgrade_level INTEGER NOT NULL DEFAULT 0,
            is_equipped INTEGER NOT NULL DEFAULT 0,
            is_shiny INTEGER NOT NULL DEFAULT 0,
            shop_value INTEGER NOT NULL DEFAULT 0,
            salvage_value INTEGER NOT NULL DEFAULT 0,
            biome_origin TEXT DEFAULT NULL,
            floor_found INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES player(id)
        )
    """,
    "materials": """
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            material_type TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES player(id),
            UNIQUE(player_id, material_type)
        )
    """,
    "chronicle": """
        CREATE TABLE IF NOT EXISTS chronicle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT DEFAULT '{}',
            floor_at_event INTEGER NOT NULL DEFAULT 0,
            level_at_event INTEGER NOT NULL DEFAULT 1,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES player(id)
        )
    """,
    "codex": """
        CREATE TABLE IF NOT EXISTS codex (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            enemy_name TEXT NOT NULL,
            enemy_type TEXT NOT NULL DEFAULT 'normal',
            times_defeated INTEGER NOT NULL DEFAULT 0,
            times_lost INTEGER NOT NULL DEFAULT 0,
            first_encounter DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_encounter DATETIME DEFAULT CURRENT_TIMESTAMP,
            best_floor INTEGER NOT NULL DEFAULT 0,
            is_shiny_seen INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (player_id) REFERENCES player(id),
            UNIQUE(player_id, enemy_name)
        )
    """
}

# Indizes fuer Performance
DB_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_inventory_player ON inventory(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_equipped ON inventory(is_equipped)",
    "CREATE INDEX IF NOT EXISTS idx_materials_player ON materials(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_chronicle_player ON chronicle(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_chronicle_type ON chronicle(event_type)",
    "CREATE INDEX IF NOT EXISTS idx_codex_player ON codex(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_codex_enemy ON codex(enemy_name)",
]


# =============================================
# Game Initializer
# =============================================

class GameInitializer:
    """
    Zentraler Initialisierungs-Manager fuer ZTB.

    Zustaendigkeiten:
    - Erststart-Erkennung (kein Charakter vorhanden)
    - DB-Schema anlegen (5 Tabellen + Indizes)
    - Verzeichnisse erstellen (Hot/Cold/Backup/Log)
    - Config validieren und zusammenfuehren
    - Charakter via Forge erstellen lassen
    - Crash-Recovery aus Cold Storage
    - Shutdown-Hooks registrieren
    """

    def __init__(self):
        self._forge = None
        self._hot_manager = None
        self._cold_manager = None
        self._psyche = None
        self._db_conn = None
        self._character = None
        self._is_first_start = False

    # -----------------------------------------
    # Lazy-Loader
    # -----------------------------------------

    def _get_forge(self):
        """Lazy-Load CharacterForge."""
        if self._forge is None:
            from forge import CharacterForge
            self._forge = CharacterForge()
        return self._forge

    def _get_hot_manager(self):
        """Lazy-Load Hot Storage."""
        if self._hot_manager is None:
            from game.hot_storage import HotStorageManager
            self._hot_manager = HotStorageManager()
        return self._hot_manager

    def _get_cold_manager(self):
        """Lazy-Load Cold Storage."""
        if self._cold_manager is None:
            from game.hot_storage import ColdStorageManager
            self._cold_manager = ColdStorageManager()
        return self._cold_manager

    def _get_psyche(self):
        """Lazy-Load ChampionPsyche."""
        if self._psyche is None:
            from champion_psyche import ChampionPsyche
            self._psyche = ChampionPsyche()
        return self._psyche

    def _get_db(self) -> sqlite3.Connection:
        """Lazy-Load SQLite-Verbindung."""
        if self._db_conn is None:
            os.makedirs(os.path.dirname(COLD_DB_PATH), exist_ok=True)
            self._db_conn = sqlite3.connect(COLD_DB_PATH)
            self._db_conn.execute("PRAGMA journal_mode=WAL")
            self._db_conn.execute("PRAGMA synchronous=NORMAL")
        return self._db_conn

    # -----------------------------------------
    # Hauptablauf
    # -----------------------------------------

    def initialize(self) -> Dict[str, Any]:
        """
        Kompletter Initialisierungs-Ablauf.

        Returns:
            Dict mit:
                status: 'SUCCESS' | 'ERROR'
                first_start: bool
                character: Dict (Charakter-Daten)
                message: str
        """
        try:
            # 1. Verzeichnisse anlegen
            self._ensure_directories()

            # 2. DB-Schema anlegen
            schema_result = self._init_database()
            if schema_result["status"] != "SUCCESS":
                return schema_result

            # 3. Config validieren
            config_result = self._validate_config()

            # 4. Pruefen: Erststart oder Recovery?
            existing_char = self._try_load_character()

            if existing_char is not None:
                # Normaler Start: Charakter gefunden
                self._character = existing_char
                self._is_first_start = False

                # Psyche-System initialisieren
                psyche = self._get_psyche()
                psyche.load_from_character(existing_char)

                # Login-Bonus (Moral +25% mit 1h Cooldown)
                login_result = psyche.on_login(existing_char)

                # Charakter in Hot Storage laden
                hot = self._get_hot_manager()
                hot.write(existing_char, "character_data")

                return {
                    "status": "SUCCESS",
                    "first_start": False,
                    "character": existing_char,
                    "login_bonus": login_result,
                    "message": f"Willkommen zurueck, {existing_char.get('name', 'Champion')}!"
                }

            else:
                # Erststart: Kein Charakter vorhanden
                # NICHT interaktiv! Charakter wird im War Room erstellt.
                # Der Orchestrator laeuft headless via systemd (kein TTY).
                self._is_first_start = True
                return {
                    "status": "FIRST_START_PENDING",
                    "first_start": True,
                    "character": None,
                    "message": "Kein Charakter vorhanden. Erststart wartet auf War Room."
                }

        except Exception as e:
            return {
                "status": "ERROR",
                "first_start": self._is_first_start,
                "character": None,
                "message": f"Initialisierung fehlgeschlagen: {e}"
            }

    # -----------------------------------------
    # Erststart-Ablauf
    # -----------------------------------------

    def complete_first_start(self, character: Dict[str, Any]) -> Dict[str, Any]:
        """
        Erststart abschliessen NACHDEM der War Room den Charakter erstellt hat.

        Wird vom War Room aufgerufen, NICHT vom Orchestrator/systemd.
        Sprache und Geraetename kommen aus config.json (vom Installer gesetzt).

        Args:
            character: Fertiges Charakter-Dict aus der Forge

        Returns:
            Dict mit status, character, message
        """
        try:
            # Sprache + Device aus Config lesen (vom Installer gesetzt)
            language = "de"
            device_name = "Pi-Ritter-X"
            try:
                if os.path.exists(CONFIG_PATH_MAIN):
                    with open(CONFIG_PATH_MAIN, "r") as f:
                        cfg = json.load(f)
                    language = cfg.get("character", {}).get("language", "de")
                    device_name = cfg.get("device", {}).get("name", "Pi-Ritter-X")
            except Exception:
                pass

            # Sprache in Charakter setzen
            character["language"] = language

            # 1. In Cold Storage speichern
            cold = self._get_cold_manager()
            cold.save("character_data", character)

            # 2. In DB speichern
            self._save_character_to_db(character)

            # 3. In Hot Storage laden
            hot = self._get_hot_manager()
            hot.write(character, "character_data")

            # 4. Initiale Materialien anlegen
            self._init_materials(character)

            # 5. Chronik-Eintrag: Erster Start
            self._log_chronicle_event(
                character["name"],
                "FIRST_START",
                {"version": GAME_VERSION, "device": device_name}
            )

            # 6. first_start_pending Flag in Config loeschen
            try:
                if os.path.exists(CONFIG_PATH_MAIN):
                    with open(CONFIG_PATH_MAIN, "r") as f:
                        cfg = json.load(f)
                    cfg.setdefault("state", {})["first_start_pending"] = False
                    cfg["character"]["name"] = character.get("name", "Champion")
                    with open(CONFIG_PATH_MAIN, "w") as f:
                        json.dump(cfg, f, indent=2)
            except Exception:
                pass

            self._character = character
            self._is_first_start = False

            return {
                "status": "SUCCESS",
                "first_start": True,
                "character": character,
                "device_name": device_name,
                "language": language,
                "message": f"Champion '{character['name']}' erstellt und bereit!"
            }

        except Exception as e:
            return {
                "status": "ERROR",
                "first_start": True,
                "character": None,
                "message": f"Erststart fehlgeschlagen: {e}"
            }

    # -----------------------------------------
    # Config-Leser (Sprache + Device aus Installer)
    # -----------------------------------------

    def get_language_from_config(self) -> str:
        """Sprache aus config.json lesen (vom Installer gesetzt)."""
        try:
            if os.path.exists(CONFIG_PATH_MAIN):
                with open(CONFIG_PATH_MAIN, "r") as f:
                    cfg = json.load(f)
                return cfg.get("character", {}).get("language", "de")
        except Exception:
            pass
        return "de"

    def get_device_name_from_config(self) -> str:
        """Geraetename aus config.json lesen (vom Installer gesetzt)."""
        try:
            if os.path.exists(CONFIG_PATH_MAIN):
                with open(CONFIG_PATH_MAIN, "r") as f:
                    cfg = json.load(f)
                return cfg.get("device", {}).get("name", "Pi-Ritter-X")
        except Exception:
            pass
        return "Pi-Ritter-X"

    def is_first_start_pending(self) -> bool:
        """Pruefen ob Erststart noch aussteht (kein Charakter erstellt)."""
        try:
            if os.path.exists(CONFIG_PATH_MAIN):
                with open(CONFIG_PATH_MAIN, "r") as f:
                    cfg = json.load(f)
                return cfg.get("state", {}).get("first_start_pending", True)
        except Exception:
            pass
        # Fallback: Pruefen ob Charakter existiert
        return self._try_load_character() is None

    # -----------------------------------------
    # Verzeichnis-Setup
    # -----------------------------------------

    def _ensure_directories(self) -> None:
        """Alle benoetigten Verzeichnisse anlegen."""
        directories = [
            COLD_STORAGE_DIR,
            BACKUP_DIR,
            os.path.join(BACKUP_DIR, "character"),
            os.path.join(BACKUP_DIR, "inventory"),
            LOG_DIR,
            HOT_STORAGE_DIR,
        ]

        for dir_path in directories:
            try:
                os.makedirs(dir_path, exist_ok=True)
            except PermissionError:
                # Auf dem Pi evtl. sudo noetig - ignorieren wenn lokal
                pass

    # -----------------------------------------
    # Datenbank-Initialisierung
    # -----------------------------------------

    def _init_database(self) -> Dict[str, Any]:
        """
        SQLite-Datenbank mit 5 verbindlichen Tabellen initialisieren.

        Tabellen (laut Spec Abschnitt 9):
          1. player    - Charakter-Stammdaten
          2. inventory - Items und Ausruestung
          3. materials - Crafting-Materialien (Scrap, Essenz, Kerne)
          4. chronicle - Spielverlauf / Event-Log
          5. codex     - Besiegte Monster und Begegnungen

        Returns:
            Dict mit: status, tables_created, indices_created
        """
        try:
            conn = self._get_db()
            cursor = conn.cursor()

            tables_created = []
            for table_name, create_sql in DB_SCHEMA.items():
                cursor.execute(create_sql)
                tables_created.append(table_name)

            # Indizes anlegen
            indices_created = 0
            for index_sql in DB_INDICES:
                cursor.execute(index_sql)
                indices_created += 1

            conn.commit()

            return {
                "status": "SUCCESS",
                "tables_created": tables_created,
                "indices_created": indices_created
            }

        except sqlite3.Error as e:
            return {
                "status": "ERROR",
                "message": f"DB-Init fehlgeschlagen: {e}",
                "tables_created": [],
                "indices_created": 0
            }

    # -----------------------------------------
    # Charakter laden / speichern
    # -----------------------------------------

    def _try_load_character(self) -> Optional[Dict[str, Any]]:
        """
        Versuche Charakter zu laden.

        Reihenfolge:
          1. Hot Storage (RAM) - schnellster Zugriff
          2. Cold Storage (JSON) - persistent nach normalem Shutdown
          3. DB (SQLite) - Fallback nach Crash
          4. None - Erststart
        """
        # 1. Hot Storage pruefen
        try:
            hot = self._get_hot_manager()
            hot_data = hot.read("character_data")
            if hot_data and "name" in hot_data:
                return hot_data
        except Exception:
            pass

        # 2. Cold Storage pruefen (JSON)
        try:
            cold = self._get_cold_manager()
            cold_data = cold.load("character_data")
            if cold_data and "name" in cold_data:
                return cold_data
        except Exception:
            pass

        # 3. SQLite-Fallback
        try:
            conn = self._get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM player ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                # Row zu Dict konvertieren
                columns = [desc[0] for desc in cursor.description]
                player_dict = dict(zip(columns, row))

                # In Charakter-Format konvertieren
                character = self._db_row_to_character(player_dict)
                return character
        except Exception:
            pass

        # 4. Kein Charakter gefunden -> Erststart
        return None

    def _save_character_to_db(self, character: Dict[str, Any]) -> bool:
        """Charakter in SQLite speichern."""
        try:
            conn = self._get_db()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO player (
                    name, klasse, typ, level, exp, hp, max_hp,
                    atk_base, def_base, spd_base, luk_base,
                    atk_extra, def_extra, spd_extra, luk_extra,
                    gold, diamonds, soul_shards,
                    scrap, essence, cores,
                    current_floor, ascension, pvp_wins, pvp_losses,
                    exhaustion, morale, language,
                    total_playtime_seconds
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?
                )
            """, (
                character.get("name", "Unbekannt"),
                character.get("klasse", "Krieger"),
                character.get("type", "Stein"),
                character.get("level", 1),
                character.get("exp", 0),
                character.get("hp", 100),
                character.get("max_hp", 100),
                character.get("atk_base", 25),
                character.get("def_base", 40),
                character.get("spd_base", 20),
                character.get("luk_base", 15),
                character.get("atk_extra", 0),
                character.get("def_extra", 0),
                character.get("spd_extra", 0),
                character.get("luk_extra", 0),
                character.get("gold", 100),
                character.get("diamonds", 0),
                character.get("soul_shards", 0),
                character.get("scrap", 10),
                character.get("essence", 0),
                character.get("cores", 0),
                character.get("current_floor", 1),
                character.get("ascension", 1),
                character.get("pvp_wins", 0),
                character.get("pvp_losses", 0),
                character.get("exhaustion", 0.0),
                character.get("morale", 100.0),
                character.get("language", "de"),
                character.get("total_playtime_seconds", 0),
            ))

            conn.commit()
            return True

        except sqlite3.Error as e:
            print(f"[DB-ERROR] Charakter speichern: {e}")
            return False

    def _db_row_to_character(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """SQLite-Row in Charakter-Dict konvertieren."""
        # Klassen-Typ-Mapping
        type_map = {
            "Krieger": "Stein",
            "Schurke": "Schere",
            "Magier": "Papier"
        }

        klasse = row.get("klasse", "Krieger")

        return {
            "name": row.get("name", "Unbekannt"),
            "klasse": klasse,
            "type": type_map.get(klasse, "Stein"),
            "focus": {
                "Krieger": "Defensive",
                "Schurke": "Tempo",
                "Magier": "Glaskanone"
            }.get(klasse, "Defensive"),
            "level": row.get("level", 1),
            "exp": row.get("exp", 0),
            "xp_per_level": 500,
            "atk_base": row.get("atk_base", 25),
            "def_base": row.get("def_base", 40),
            "spd_base": row.get("spd_base", 20),
            "luk_base": row.get("luk_base", 15),
            "atk_extra": row.get("atk_extra", 0),
            "def_extra": row.get("def_extra", 0),
            "spd_extra": row.get("spd_extra", 0),
            "luk_extra": row.get("luk_extra", 0),
            "atk_effective": row.get("atk_base", 25) + row.get("atk_extra", 0),
            "def_effective": row.get("def_base", 40) + row.get("def_extra", 0),
            "spd_effective": row.get("spd_base", 20) + row.get("spd_extra", 0),
            "luk_effective": row.get("luk_base", 15) + row.get("luk_extra", 0),
            "hp": row.get("hp", 100),
            "max_hp": row.get("max_hp", 100),
            "exhaustion": row.get("exhaustion", 0.0),
            "morale": row.get("morale", 100.0),
            "trauma": [],
            "current_floor": row.get("current_floor", 1),
            "ascension": row.get("ascension", 1),
            "pvp_wins": row.get("pvp_wins", 0),
            "pvp_losses": row.get("pvp_losses", 0),
            "gold": row.get("gold", 100),
            "diamonds": row.get("diamonds", 0),
            "soul_shards": row.get("soul_shards", 0),
            "scrap": row.get("scrap", 10),
            "essence": row.get("essence", 0),
            "cores": row.get("cores", 0),
            "language": row.get("language", "de"),
            "created_at": row.get("created_at", ""),
            "last_login": row.get("last_login", ""),
            "total_playtime_seconds": row.get("total_playtime_seconds", 0),
        }

    # -----------------------------------------
    # Materialien initialisieren
    # -----------------------------------------

    def _init_materials(self, character: Dict[str, Any]) -> None:
        """Initiale Materialien in DB anlegen."""
        try:
            conn = self._get_db()
            cursor = conn.cursor()

            # Player-ID holen
            cursor.execute(
                "SELECT id FROM player WHERE name = ?",
                (character["name"],)
            )
            row = cursor.fetchone()
            if not row:
                return

            player_id = row[0]

            # 3 Material-Typen laut Spec
            materials = [
                ("scrap", character.get("scrap", 10)),
                ("essence", character.get("essence", 0)),
                ("cores", character.get("cores", 0)),
            ]

            for mat_type, amount in materials:
                cursor.execute("""
                    INSERT OR REPLACE INTO materials (player_id, material_type, amount)
                    VALUES (?, ?, ?)
                """, (player_id, mat_type, amount))

            conn.commit()

        except sqlite3.Error as e:
            print(f"[DB-ERROR] Materialien init: {e}")

    # -----------------------------------------
    # Chronik (Event-Log)
    # -----------------------------------------

    def _log_chronicle_event(self, player_name: str, event_type: str,
                             event_data: Dict[str, Any] = None) -> None:
        """Ereignis in die Chronik-Tabelle schreiben."""
        try:
            conn = self._get_db()
            cursor = conn.cursor()

            # Player-ID holen
            cursor.execute(
                "SELECT id, current_floor, level FROM player WHERE name = ?",
                (player_name,)
            )
            row = cursor.fetchone()
            if not row:
                return

            player_id, floor_at, level_at = row

            cursor.execute("""
                INSERT INTO chronicle (player_id, event_type, event_data,
                                       floor_at_event, level_at_event)
                VALUES (?, ?, ?, ?, ?)
            """, (
                player_id,
                event_type,
                json.dumps(event_data or {}),
                floor_at,
                level_at
            ))

            conn.commit()

        except sqlite3.Error as e:
            print(f"[CHRONIK-ERROR] {e}")

    # -----------------------------------------
    # Config-Verwaltung
    # -----------------------------------------

    def _validate_config(self) -> Dict[str, Any]:
        """
        Config-Dateien pruefen und ggf. reparieren.

        Zwei Config-Dateien:
          1. config.json       - Hardware/Netzwerk (Hauptconfig)
          2. config/config.json - App-Einstellungen (Sprache, Debug)
        """
        result = {"main_config": False, "app_config": False}

        # Hauptconfig pruefen
        if os.path.exists(CONFIG_PATH_MAIN):
            try:
                with open(CONFIG_PATH_MAIN, "r") as f:
                    json.load(f)
                result["main_config"] = True
            except (json.JSONDecodeError, OSError):
                self._create_default_main_config()
                result["main_config"] = True
        else:
            self._create_default_main_config()
            result["main_config"] = True

        # App-Config pruefen
        if os.path.exists(CONFIG_PATH_APP):
            try:
                with open(CONFIG_PATH_APP, "r") as f:
                    json.load(f)
                result["app_config"] = True
            except (json.JSONDecodeError, OSError):
                self._create_default_app_config()
                result["app_config"] = True
        else:
            self._create_default_app_config()
            result["app_config"] = True

        return {"status": "SUCCESS", **result}

    def _create_default_main_config(self) -> None:
        """Standard-Hauptconfig anlegen."""
        config = {
            "device": {
                "name": "Pi-Ritter-X",
                "hostname": SERVICE_NAME,
                "cpu_info": "Raspberry Pi Zero 2 WH 1GHz",
                "ram_mb": 512,
                "storage_gb": 8
            },
            "character": {
                "name": "",
                "class": "Krieger",
                "level": 1,
                "language": "de",
                "ui_language": ["de", "en"]
            },
            "hardware": {
                "wlan0": {
                    "iface": "wlan0",
                    "mode": "ap",
                    "channel": 6,
                    "wpa2_passphrase": "ZeroBattle2026!",
                    "ip": "192.168.4.1",
                    "subnet": "255.255.255.0",
                    "max_clients": 50,
                    "country_code": "DE"
                },
                "tun0": {
                    "iface": "tun0",
                    "vnet_base": "10.42.0",
                    "method": "ifupdown",
                    "ipv6": False,
                    "max_connections": 2
                }
            },
            "network": {
                "sshd_port": 2222,
                "tcp_port": 5005,
                "backup_interval_minutes": 20,
                "retry_seconds": 10,
                "timeout_seconds": 8
            },
            "battle": {
                "max_rounds": 30,
                "world_boss_enabled": True,
                "world_boss_floor_divisor": 25,
                "pve_cooldown_seconds": 90,
                "pvp_cooldown_per_mac_minutes": 30
            },
            "inventory": {
                "slot_count": -1,
                "equipped_item_limit": 1,
                "auto_salvage_threshold": 5
            },
            "shop": {
                "refresh_interval_hours": 24,
                "items_per_shop": 3
            },
            "backup": {
                "path": BACKUP_DIR,
                "interval_minutes": 20,
                "max_backups": 100
            },
            "logging": {
                "level": "INFO",
                "file": os.path.join(LOG_DIR, "battle_log.txt"),
                "rotate": True,
                "rotate_on": 1000000,
                "rotate_days": 30
            },
            "version": GAME_VERSION
        }

        try:
            with open(CONFIG_PATH_MAIN, "w") as f:
                json.dump(config, f, indent=2)
        except OSError as e:
            print(f"[CONFIG-ERROR] Hauptconfig: {e}")

    def _create_default_app_config(self) -> None:
        """Standard-App-Config anlegen."""
        config = {
            "language": "DE",
            "debug": False,
            "autosave": True,
            "backup_interval_minutes": 20,
            "_note": "Hauptkonfiguration: siehe ../config.json"
        }

        try:
            config_dir = os.path.dirname(CONFIG_PATH_APP)
            os.makedirs(config_dir, exist_ok=True)
            with open(CONFIG_PATH_APP, "w") as f:
                json.dump(config, f, indent=4)
        except OSError as e:
            print(f"[CONFIG-ERROR] App-Config: {e}")

    def _update_device_config(self, device_name: str, language: str) -> None:
        """Config mit Erststart-Daten aktualisieren."""
        try:
            if os.path.exists(CONFIG_PATH_MAIN):
                with open(CONFIG_PATH_MAIN, "r") as f:
                    config = json.load(f)
            else:
                config = {}

            # Device-Name setzen
            if "device" not in config:
                config["device"] = {}
            config["device"]["name"] = device_name
            config["device"]["hostname"] = SERVICE_NAME

            # Charakter-Daten
            if "character" not in config:
                config["character"] = {}
            config["character"]["language"] = language

            with open(CONFIG_PATH_MAIN, "w") as f:
                json.dump(config, f, indent=2)

            # App-Config Sprache setzen
            if os.path.exists(CONFIG_PATH_APP):
                with open(CONFIG_PATH_APP, "r") as f:
                    app_config = json.load(f)
                app_config["language"] = language.upper()
                with open(CONFIG_PATH_APP, "w") as f:
                    json.dump(app_config, f, indent=4)

        except (json.JSONDecodeError, OSError) as e:
            print(f"[CONFIG-ERROR] Update: {e}")

    # -----------------------------------------
    # Shutdown & Cleanup
    # -----------------------------------------

    def register_shutdown_hooks(self) -> None:
        """Shutdown-Hooks fuer sauberes Beenden registrieren."""
        def _handle_shutdown(signum, frame):
            self.shutdown()

        signal.signal(signal.SIGTERM, _handle_shutdown)
        signal.signal(signal.SIGINT, _handle_shutdown)

    def shutdown(self) -> Dict[str, Any]:
        """
        Sauberes Herunterfahren.

        1. Charakter in Cold Storage sichern
        2. Hot -> Cold flushen
        3. DB-Verbindung schliessen
        4. Chronik-Eintrag: Shutdown
        """
        result = {"flushed": False, "saved": False, "closed": False}

        try:
            # Charakter sichern
            if self._character:
                cold = self._get_cold_manager()
                cold.save("character_data", self._character)
                self._save_character_to_db(self._character)
                result["saved"] = True

            # Hot -> Cold flush
            try:
                hot = self._get_hot_manager()
                hot.flush_to_cold()
                result["flushed"] = True
            except Exception:
                pass

            # Chronik
            if self._character:
                self._log_chronicle_event(
                    self._character.get("name", ""),
                    "SHUTDOWN",
                    {"playtime": self._character.get("total_playtime_seconds", 0)}
                )

            # DB schliessen
            if self._db_conn:
                self._db_conn.close()
                self._db_conn = None
                result["closed"] = True

        except Exception as e:
            print(f"[SHUTDOWN-ERROR] {e}")

        return result

    # -----------------------------------------
    # Hilfsmethoden
    # -----------------------------------------

    def get_character(self) -> Optional[Dict[str, Any]]:
        """Aktuellen Charakter zurueckgeben."""
        return self._character

    def is_first_start(self) -> bool:
        """War dies ein Erststart?"""
        return self._is_first_start

    def get_system_info(self) -> Dict[str, Any]:
        """System-Status fuer Dashboard."""
        hot_usage = {}
        try:
            hot = self._get_hot_manager()
            hot_usage = hot.get_usage()
        except Exception:
            hot_usage = {"usage_percent": 0, "is_critical": False}

        return {
            "game": GAME_NAME,
            "version": GAME_VERSION,
            "service": SERVICE_NAME,
            "character": self._character.get("name") if self._character else None,
            "first_start": self._is_first_start,
            "hot_storage": hot_usage,
            "cold_db": COLD_DB_PATH,
            "paths": {
                "hot": HOT_STORAGE_DIR,
                "cold": COLD_STORAGE_DIR,
                "backup": BACKUP_DIR,
                "logs": LOG_DIR
            }
        }

    def save_current_state(self) -> bool:
        """Aktuellen Spielstand komplett sichern (manueller Save)."""
        if not self._character:
            return False

        try:
            # Hot Storage
            hot = self._get_hot_manager()
            hot.write(self._character, "character_data")

            # Cold Storage
            cold = self._get_cold_manager()
            cold.save("character_data", self._character)

            # DB
            self._save_character_to_db(self._character)

            return True

        except Exception as e:
            print(f"[SAVE-ERROR] {e}")
            return False


# =============================================
# Standalone-Test
# =============================================

if __name__ == "__main__":
    print(f"=== {GAME_NAME} v{GAME_VERSION} ===")
    print(f"Service: {SERVICE_NAME}")
    print()

    init = GameInitializer()

    # Nur DB-Schema testen (ohne interaktive Eingabe)
    print("DB-Schema initialisieren...")
    init._ensure_directories()
    schema = init._init_database()
    print(f"  Status: {schema['status']}")
    if schema["status"] == "SUCCESS":
        print(f"  Tabellen: {', '.join(schema['tables_created'])}")
        print(f"  Indizes: {schema['indices_created']}")

    # Config validieren
    print("\nConfig validieren...")
    config = init._validate_config()
    print(f"  Main Config: {config['main_config']}")
    print(f"  App Config: {config['app_config']}")

    # System-Info
    print("\nSystem-Info:")
    info = init.get_system_info()
    for key, val in info.items():
        if isinstance(val, dict):
            print(f"  {key}:")
            for k, v in val.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {val}")

    print("\nInit-Test abgeschlossen.")
