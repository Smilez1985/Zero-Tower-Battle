#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Backup System
=========================================
Rotations-Backup fuer Character-Daten und Cold Storage.

Features:
  - Automatische Backups mit konfigurierbarem Intervall
  - Rotations-System: Behaelt N Backups, loescht aelteste
  - Cold-DB Backup (sqlite3 .backup() fuer konsistente Kopien)
  - Character-JSON Backup (Spielstand-Snapshots)
  - Restore: Letztes oder benanntes Backup wiederherstellen

Wird vom Orchestrator im CHECKPOINT-State aufgerufen (alle 5 Min).

Referenz: Battle-Pi_Konsolidiert.txt Abschnitt 3
"""

import os
import json
import shutil
import sqlite3
import time
from datetime import datetime
from typing import Optional, Dict, Any, List


# =============================================
# Default-Pfade
# =============================================

def _default_cold_db() -> str:
    """Cold-Storage DB-Pfad via core.paths."""
    try:
        from core.paths import COLD_DB_PATH
        return COLD_DB_PATH
    except ImportError:
        return os.path.join(os.path.expanduser("~"), "cold_storage.db")


def _default_backup_dir() -> str:
    """Backup-Verzeichnis via core.paths."""
    try:
        from core.paths import BACKUP_DIR
        return BACKUP_DIR
    except ImportError:
        return os.path.join(os.path.expanduser("~"), "battle_game", "backups")


def _default_character_backup_dir() -> str:
    """Character-Backup-Verzeichnis via core.paths."""
    try:
        from core.paths import CHARACTER_BACKUP_DIR
        return CHARACTER_BACKUP_DIR
    except ImportError:
        return os.path.join(_default_backup_dir(), "character")


# =============================================
# Backup System
# =============================================

class BackupSystem:
    """
    Rotations-Backup fuer ZTB-Spielstand.

    Erstellt timestamped Backups und rotiert automatisch.
    Unterstuetzt sowohl Cold-DB als auch Character-JSON Backups.
    """

    MAX_BACKUPS = 10            # Maximale Anzahl Backups (aelteste werden geloescht)
    MIN_INTERVAL_SEC = 300      # Mindestens 5 Minuten zwischen Backups

    def __init__(
        self,
        cold_db_path: Optional[str] = None,
        backup_dir: Optional[str] = None,
        character_backup_dir: Optional[str] = None,
        max_backups: int = MAX_BACKUPS
    ):
        self._cold_db_path = cold_db_path or _default_cold_db()
        self._backup_dir = backup_dir or _default_backup_dir()
        self._character_backup_dir = character_backup_dir or _default_character_backup_dir()
        self._max_backups = max_backups
        self._last_backup_time = 0.0

        # Verzeichnisse sicherstellen
        os.makedirs(self._backup_dir, exist_ok=True)
        os.makedirs(self._character_backup_dir, exist_ok=True)

    # ========================================
    # Cold-DB Backup
    # ========================================

    def backup_cold_db(self, label: str = "") -> Optional[str]:
        """
        Erstellt ein konsistentes Backup der Cold-Storage-DB.

        Nutzt sqlite3 .backup() fuer eine konsistente Kopie
        ohne die laufende DB zu beeinflussen.

        Args:
            label: Optionales Label (z.B. "pre-pvp", "checkpoint")

        Returns:
            Pfad zum Backup oder None bei Fehler
        """
        if not os.path.exists(self._cold_db_path):
            print("[BACKUP] Cold-DB nicht gefunden, ueberspringe.")
            return None

        # Intervall-Check
        now = time.time()
        if now - self._last_backup_time < self.MIN_INTERVAL_SEC:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{label}" if label else ""
        backup_name = f"cold_storage_{timestamp}{suffix}.db"
        backup_path = os.path.join(self._backup_dir, backup_name)

        try:
            # sqlite3 .backup() fuer konsistente Kopie
            source = sqlite3.connect(self._cold_db_path)
            dest = sqlite3.connect(backup_path)
            source.backup(dest)
            dest.close()
            source.close()

            self._last_backup_time = now
            self._rotate_backups(self._backup_dir, "cold_storage_", ".db")

            size_kb = os.path.getsize(backup_path) / 1024
            print(f"[BACKUP] Cold-DB gesichert: {backup_name} ({size_kb:.1f} KB)")
            return backup_path

        except Exception as e:
            print(f"[BACKUP] Cold-DB Fehler: {e}")
            # Fehlgeschlagenes Backup aufraemen
            if os.path.exists(backup_path):
                try:
                    os.unlink(backup_path)
                except OSError:
                    pass
            return None

    # ========================================
    # Character-JSON Backup
    # ========================================

    def backup_character(self, character: Dict[str, Any], label: str = "") -> Optional[str]:
        """
        Character-Dict als JSON-Snapshot sichern.

        Args:
            character: Character-Dict
            label: Optionales Label

        Returns:
            Pfad zum Backup oder None bei Fehler
        """
        if not character:
            return None

        name = character.get("name", "unknown")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{label}" if label else ""
        backup_name = f"{name}_{timestamp}{suffix}.json"
        backup_path = os.path.join(self._character_backup_dir, backup_name)

        try:
            # Backup-Metadaten hinzufuegen
            backup_data = {
                "backup_timestamp": timestamp,
                "backup_label": label,
                "character": character
            }

            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)

            self._rotate_backups(self._character_backup_dir, f"{name}_", ".json")

            print(f"[BACKUP] Character gesichert: {backup_name}")
            return backup_path

        except Exception as e:
            print(f"[BACKUP] Character-Backup Fehler: {e}")
            return None

    # ========================================
    # Checkpoint (beide gleichzeitig)
    # ========================================

    def create_checkpoint(self, character: Optional[Dict[str, Any]] = None,
                          label: str = "checkpoint") -> Dict[str, Any]:
        """
        Vollstaendiger Checkpoint: Cold-DB + Character.

        Wird vom Orchestrator im CHECKPOINT-State aufgerufen.

        Args:
            character: Character-Dict (optional)
            label: Checkpoint-Label

        Returns:
            Dict mit Ergebnis-Info
        """
        result = {
            "timestamp": time.time(),
            "cold_db_backup": None,
            "character_backup": None,
            "success": False
        }

        # Cold-DB Backup
        db_path = self.backup_cold_db(label=label)
        result["cold_db_backup"] = db_path

        # Character Backup
        if character:
            char_path = self.backup_character(character, label=label)
            result["character_backup"] = char_path

        result["success"] = (db_path is not None) or (character is None)
        return result

    # ========================================
    # Restore
    # ========================================

    def list_db_backups(self) -> List[Dict[str, Any]]:
        """Verfuegbare Cold-DB Backups auflisten."""
        return self._list_backups(self._backup_dir, "cold_storage_", ".db")

    def list_character_backups(self, name: str = "") -> List[Dict[str, Any]]:
        """Verfuegbare Character-Backups auflisten."""
        prefix = f"{name}_" if name else ""
        return self._list_backups(self._character_backup_dir, prefix, ".json")

    def restore_cold_db(self, backup_path: str) -> bool:
        """
        Cold-DB aus einem Backup wiederherstellen.

        ACHTUNG: Ueberschreibt die aktuelle Cold-DB!

        Args:
            backup_path: Pfad zum Backup

        Returns:
            True bei Erfolg
        """
        if not os.path.exists(backup_path):
            print(f"[BACKUP] Backup nicht gefunden: {backup_path}")
            return False

        try:
            # Aktuelles als .bak sichern
            if os.path.exists(self._cold_db_path):
                shutil.copy2(self._cold_db_path, self._cold_db_path + ".bak")

            shutil.copy2(backup_path, self._cold_db_path)
            print(f"[BACKUP] Cold-DB wiederhergestellt aus: {os.path.basename(backup_path)}")
            return True

        except Exception as e:
            print(f"[BACKUP] Restore-Fehler: {e}")
            # .bak zurueck
            bak = self._cold_db_path + ".bak"
            if os.path.exists(bak):
                shutil.copy2(bak, self._cold_db_path)
            return False

    def restore_character(self, backup_path: str) -> Optional[Dict[str, Any]]:
        """
        Character aus einem Backup laden.

        Args:
            backup_path: Pfad zum Backup

        Returns:
            Character-Dict oder None bei Fehler
        """
        if not os.path.exists(backup_path):
            print(f"[BACKUP] Backup nicht gefunden: {backup_path}")
            return None

        try:
            with open(backup_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            character = data.get("character", data)
            print(f"[BACKUP] Character geladen: {character.get('name', '?')}")
            return character

        except Exception as e:
            print(f"[BACKUP] Character-Restore Fehler: {e}")
            return None

    # ========================================
    # Rotation (interne Hilfsmethode)
    # ========================================

    def _rotate_backups(self, directory: str, prefix: str, suffix: str) -> int:
        """
        Aelteste Backups loeschen wenn max_backups ueberschritten.

        Returns:
            Anzahl geloeschter Backups
        """
        backups = self._list_backups(directory, prefix, suffix)

        deleted = 0
        while len(backups) > self._max_backups:
            oldest = backups.pop()  # Liste ist nach Datum absteigend sortiert
            try:
                os.unlink(oldest["path"])
                deleted += 1
            except OSError as e:
                print(f"[BACKUP] Rotation-Fehler: {e}")

        return deleted

    def _list_backups(self, directory: str, prefix: str, suffix: str) -> List[Dict[str, Any]]:
        """
        Backups in einem Verzeichnis auflisten.

        Returns:
            Liste sortiert nach mtime (neueste zuerst)
        """
        if not os.path.isdir(directory):
            return []

        backups = []
        for fname in os.listdir(directory):
            if fname.startswith(prefix) and fname.endswith(suffix):
                fpath = os.path.join(directory, fname)
                try:
                    stat = os.stat(fpath)
                    backups.append({
                        "path": fpath,
                        "name": fname,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    })
                except OSError:
                    continue

        # Neueste zuerst
        backups.sort(key=lambda b: b["mtime"], reverse=True)
        return backups


# =============================================
# Standalone Test
# =============================================

if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_cold.db")
        backup_dir = os.path.join(tmpdir, "backups")
        char_dir = os.path.join(tmpdir, "backups", "character")

        # Test-DB erstellen
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE players (name TEXT, level INTEGER)")
        conn.execute("INSERT INTO players VALUES ('TestRitter', 42)")
        conn.commit()
        conn.close()

        # Backup-System
        bs = BackupSystem(
            cold_db_path=db_path,
            backup_dir=backup_dir,
            character_backup_dir=char_dir,
            max_backups=3
        )
        # Intervall fuer Test deaktivieren
        bs.MIN_INTERVAL_SEC = 0

        # Cold-DB Backup
        path1 = bs.backup_cold_db(label="test1")
        print(f"Backup 1: {path1}")

        # Character Backup
        test_char = {"name": "TestRitter", "level": 42, "class_type": "Schere"}
        path2 = bs.backup_character(test_char, label="test")
        print(f"Char Backup: {path2}")

        # Checkpoint
        result = bs.create_checkpoint(character=test_char, label="auto")
        print(f"Checkpoint: success={result['success']}")

        # List
        db_backups = bs.list_db_backups()
        print(f"\nDB Backups: {len(db_backups)}")
        for b in db_backups:
            print(f"  {b['name']} ({b['size']} bytes, {b['date']})")

        char_backups = bs.list_character_backups("TestRitter")
        print(f"\nChar Backups: {len(char_backups)}")
        for b in char_backups:
            print(f"  {b['name']} ({b['size']} bytes, {b['date']})")

        # Restore
        if db_backups:
            ok = bs.restore_cold_db(db_backups[0]["path"])
            print(f"\nRestore Cold-DB: {ok}")

        if char_backups:
            char = bs.restore_character(char_backups[0]["path"])
            print(f"Restore Char: {char}")

        print("\nAlle Tests bestanden!")
