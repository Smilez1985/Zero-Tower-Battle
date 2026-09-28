#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Zentrale Pfad-Konfiguration
=====================================================
Dynamische Pfade basierend auf Service-User und Umgebung.

Alle Module importieren Pfade von hier statt /home/pi hardcoded:
    from core.paths import GAME_DIR, COLD_DB_PATH, ...

Reihenfolge der Erkennung:
  1. Umgebungsvariable ZTB_HOME (fuer Entwicklung/Tests)
  2. config.json -> service.home (vom Installer gesetzt)
  3. Home-Dir des aktuellen Users (~)
  4. Fallback: /home/ZTB_Service

Der Installer (install.sh) erstellt den User ZTB_Service,
setzt Rechte, und schreibt service.home in config.json.
"""

import os
import json
from pathlib import Path


# ============================================================================
# SERVICE USER DEFAULTS
# ============================================================================

DEFAULT_SERVICE_USER = "ZTB_Service"
DEFAULT_SERVICE_HOME = f"/home/{DEFAULT_SERVICE_USER}"
DEFAULT_GAME_DIR_NAME = "battle_game"

# ============================================================================
# DYNAMIC BASE PATH DETECTION
# ============================================================================


def _detect_base_home() -> str:
    """
    Erkennt das Home-Verzeichnis des Service-Users.

    Prioritaet:
      1. ZTB_HOME Umgebungsvariable (Entwicklung/CI)
      2. config.json service.home (vom Installer gesetzt)
      3. Home des aktuellen Users
      4. Fallback /home/ZTB_Service
    """
    # 1. Umgebungsvariable
    env_home = os.environ.get("ZTB_HOME")
    if env_home and os.path.isdir(env_home):
        return env_home

    # 2. config.json neben dieser Datei (oder im Game-Dir)
    for rel in [
        os.path.join(os.path.dirname(__file__), "..", "config.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "config.json"),
    ]:
        abs_path = os.path.abspath(rel)
        if os.path.isfile(abs_path):
            try:
                with open(abs_path, "r") as f:
                    cfg = json.load(f)
                svc_home = cfg.get("service", {}).get("home")
                if svc_home and os.path.isdir(svc_home):
                    return svc_home
            except Exception:
                pass

    # 3. Home des aktuellen Users (wenn battle_game dort existiert)
    user_home = os.path.expanduser("~")
    if os.path.isdir(os.path.join(user_home, DEFAULT_GAME_DIR_NAME)):
        return user_home

    # 4. Fallback
    return DEFAULT_SERVICE_HOME


def _detect_game_dir() -> str:
    """Game-Verzeichnis erkennen."""
    # Pruefen ob wir bereits im Game-Dir laufen
    cwd = os.getcwd()
    if os.path.isfile(os.path.join(cwd, "hybrid_orchestrator.py")):
        return cwd

    # Sonst: base_home / battle_game
    base = _detect_base_home()
    return os.path.join(base, DEFAULT_GAME_DIR_NAME)


# ============================================================================
# EXPORTED PATHS (importierbar von allen Modulen)
# ============================================================================

# Basis
SERVICE_USER: str = os.environ.get("ZTB_USER", DEFAULT_SERVICE_USER)
SERVICE_HOME: str = _detect_base_home()
GAME_DIR: str = _detect_game_dir()

# Storage
COLD_DB_PATH: str = os.path.join(SERVICE_HOME, "cold_storage.db")
COLD_STORAGE_DIR: str = os.path.join(SERVICE_HOME, "ztb_cold_storage")
HOT_STORAGE_DIR: str = os.path.join(GAME_DIR, "hot_storage")

# Backups & Logs
BACKUP_DIR: str = os.path.join(GAME_DIR, "backups")
CHARACTER_BACKUP_DIR: str = os.path.join(BACKUP_DIR, "character")
LOG_DIR: str = os.path.join(GAME_DIR, "logs")
BATTLE_LOG: str = os.path.join(LOG_DIR, "battle_log.txt")

# Config
CONFIG_FILE: str = os.path.join(GAME_DIR, "config.json")

# i18n
I18N_DIR: str = os.path.join(GAME_DIR, "i18n")


# ============================================================================
# HELPER: Verzeichnisse sicherstellen
# ============================================================================

def ensure_directories():
    """
    Erstellt alle benoetigten Verzeichnisse falls nicht vorhanden.
    Wird beim Import NICHT automatisch aufgerufen — nur bei Bedarf.
    """
    for d in [
        GAME_DIR,
        os.path.join(GAME_DIR, "cold_storage"),
        HOT_STORAGE_DIR,
        COLD_STORAGE_DIR,
        BACKUP_DIR,
        CHARACTER_BACKUP_DIR,
        LOG_DIR,
    ]:
        os.makedirs(d, exist_ok=True)


def get_config() -> dict:
    """Liest config.json, gibt leeres Dict bei Fehler."""
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config: dict):
    """Schreibt config.json."""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass


# ============================================================================
# DEBUG: Wenn direkt ausgefuehrt, zeige alle Pfade
# ============================================================================

if __name__ == "__main__":
    print("=== ZTB Path Configuration ===")
    print(f"  SERVICE_USER:       {SERVICE_USER}")
    print(f"  SERVICE_HOME:       {SERVICE_HOME}")
    print(f"  GAME_DIR:           {GAME_DIR}")
    print(f"  COLD_DB_PATH:       {COLD_DB_PATH}")
    print(f"  COLD_STORAGE_DIR:   {COLD_STORAGE_DIR}")
    print(f"  HOT_STORAGE_DIR:    {HOT_STORAGE_DIR}")
    print(f"  BACKUP_DIR:         {BACKUP_DIR}")
    print(f"  LOG_DIR:            {LOG_DIR}")
    print(f"  CONFIG_FILE:        {CONFIG_FILE}")
    print(f"  I18N_DIR:           {I18N_DIR}")
    print()
    for d in [GAME_DIR, COLD_STORAGE_DIR, HOT_STORAGE_DIR, BACKUP_DIR, LOG_DIR]:
        exists = "EXISTS" if os.path.isdir(d) else "MISSING"
        print(f"  [{exists}] {d}")
