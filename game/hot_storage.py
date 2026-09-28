#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Hot Storage (RAM/RAMDisk)
=====================================================
Pi Zero 2W: 512MB RAM + 50% ZRAM + 4GB Swap (SD)

Hot Storage = RAM / RAMDisk (schnell, fluechtig)
Cold Storage = SD / SQLite (langsam, persistent)

OOM-Schutz: Bei >= 90% Auslastung wird automatisch
in den Cold Storage ausgelagert.
"""

import os
import json
import shutil
from typing import Dict, Any, Optional
from pathlib import Path


class HotStorageManager:
    """
    Hot Storage (RAM) mit OOM-Schutz.

    - Max 100MB fuer aktive Spieldaten
    - Bei >= 90% Auslastung: Auto-Migration zu Cold
    - Daten sind nach Absturz/Neustart VERLOREN
    """

    MAX_SIZE_BYTES = 100 * 1024 * 1024  # 100MB Hard-Limit
    EVICTION_THRESHOLD = 0.90            # 90% -> Migration starten
    HOT_PATH = "/tmp/ztb_hot_storage"

    def __init__(self, hot_path: str = None):
        self.hot_path = hot_path or self.HOT_PATH
        self._cold_manager = None  # Lazy-Load
        self._usage_bytes = 0
        self._ensure_directory()

    def _ensure_directory(self):
        """Hot-Storage-Verzeichnis erstellen."""
        os.makedirs(self.hot_path, exist_ok=True)

    def _get_cold_manager(self):
        """Lazy-Load Cold Storage fuer Migration."""
        if self._cold_manager is None:
            self._cold_manager = ColdStorageManager()
        return self._cold_manager

    # ===========================
    # Speicher-Monitoring
    # ===========================

    def get_usage(self) -> Dict[str, Any]:
        """Aktuelle Hot-Storage-Auslastung."""
        self._update_usage()
        usage_pct = (self._usage_bytes / self.MAX_SIZE_BYTES) * 100
        return {
            "used_bytes": self._usage_bytes,
            "max_bytes": self.MAX_SIZE_BYTES,
            "usage_percent": round(usage_pct, 1),
            "is_critical": usage_pct >= (self.EVICTION_THRESHOLD * 100),
            "free_bytes": max(0, self.MAX_SIZE_BYTES - self._usage_bytes)
        }

    def _update_usage(self):
        """Berechne aktuelle Speicherbelegung."""
        total = 0
        try:
            for entry in os.scandir(self.hot_path):
                if entry.is_file():
                    total += entry.stat().st_size
        except OSError:
            pass
        self._usage_bytes = total

    def is_critical(self) -> bool:
        """Pruefe ob 90%-Schwelle erreicht."""
        self._update_usage()
        return self._usage_bytes >= (self.MAX_SIZE_BYTES * self.EVICTION_THRESHOLD)

    # ===========================
    # Lesen / Schreiben
    # ===========================

    def read(self, key: str = "current_data") -> Optional[Dict]:
        """Daten aus Hot Storage lesen."""
        filepath = os.path.join(self.hot_path, f"{key}.json")
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def write(self, data: Dict, key: str = "current_data") -> Dict[str, Any]:
        """
        Daten in Hot Storage schreiben.
        Bei >= 90% Auslastung: automatische Migration zu Cold Storage.

        Args:
            data: Zu speichernde Daten
            key: Schluessel/Dateiname

        Returns:
            Dict mit: result, migrated
        """
        migrated = False

        # Pruefe ob Migration noetig (OOM-Schutz!)
        if self.is_critical():
            print("[HOT] 90% Schwelle erreicht! Migration zu Cold Storage...")
            migrated = self._evict_to_cold()

        filepath = os.path.join(self.hot_path, f"{key}.json")
        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=None)  # Kompakt, spart Platz

            self._update_usage()
            return {
                "result": "SUCCESS",
                "migrated": migrated,
                "usage": self.get_usage()
            }
        except OSError as e:
            # Notfall: Direkt in Cold schreiben
            print(f"[HOT-ERROR] Schreibfehler: {e} -> Cold Storage Fallback")
            cold = self._get_cold_manager()
            cold.save(key, data)
            return {"result": "COLD_FALLBACK", "migrated": True}

    def _evict_to_cold(self) -> bool:
        """
        Aelteste/groesste Daten von Hot nach Cold migrieren.
        Ziel: Unter 90% kommen.
        """
        cold = self._get_cold_manager()
        evicted = False

        try:
            # Alle Dateien nach Aenderungszeit sortiert (aelteste zuerst)
            files = []
            for entry in os.scandir(self.hot_path):
                if entry.is_file() and entry.name.endswith(".json"):
                    files.append((entry.path, entry.name, entry.stat().st_mtime, entry.stat().st_size))

            files.sort(key=lambda x: x[2])  # Aelteste zuerst

            for filepath, filename, _, size in files:
                if not self.is_critical():
                    break  # Unter 90%, fertig

                key = filename.replace(".json", "")
                # In Cold speichern
                try:
                    with open(filepath, "r") as f:
                        data = json.load(f)
                    cold.save(key, data)
                    os.remove(filepath)
                    self._update_usage()
                    evicted = True
                    print(f"[HOT->COLD] '{key}' migriert ({size} bytes)")
                except Exception as e:
                    print(f"[EVICT-ERROR] {key}: {e}")

        except OSError as e:
            print(f"[EVICT-ERROR] Scan fehlgeschlagen: {e}")

        return evicted

    # ===========================
    # Cleanup
    # ===========================

    def clear(self):
        """Gesamten Hot Storage loeschen."""
        try:
            shutil.rmtree(self.hot_path, ignore_errors=True)
            os.makedirs(self.hot_path, exist_ok=True)
            self._usage_bytes = 0
            print("[HOT] Storage komplett geleert")
        except OSError as e:
            print(f"[HOT-ERROR] Clear fehlgeschlagen: {e}")

    def flush_to_cold(self) -> Dict[str, Any]:
        """
        ALLE Daten von Hot nach Cold uebertragen.
        Wird beim Gently Shutdown aufgerufen.

        Returns:
            Dict mit: result, flushed_count, flushed_bytes
        """
        cold = self._get_cold_manager()
        flushed_count = 0
        flushed_bytes = 0

        try:
            for entry in os.scandir(self.hot_path):
                if entry.is_file() and entry.name.endswith(".json"):
                    key = entry.name.replace(".json", "")
                    size = entry.stat().st_size
                    try:
                        with open(entry.path, "r") as f:
                            data = json.load(f)
                        cold.save(key, data)
                        flushed_count += 1
                        flushed_bytes += size
                    except Exception as e:
                        print(f"[FLUSH-ERROR] {key}: {e}")

            # Hot leeren nach Flush
            self.clear()

            print(f"[FLUSH] {flushed_count} Dateien ({flushed_bytes} bytes) -> Cold")
            return {
                "result": "SUCCESS",
                "flushed_count": flushed_count,
                "flushed_bytes": flushed_bytes
            }

        except OSError as e:
            print(f"[FLUSH-ERROR] {e}")
            return {"result": "ERROR", "error": str(e)}


class ColdStorageManager:
    """
    Cold Storage (SD-Karte / SQLite).

    - Persistent ueber Neustarts und Abstuerze
    - Laden beim Systemstart
    - Backup-Quelle fuer Hot Storage Recovery
    """

    try:
        from core.paths import COLD_STORAGE_DIR as _csd, COLD_DB_PATH as _cdb
        COLD_PATH = _csd
        COLD_DB = _cdb
    except ImportError:
        _home = os.path.expanduser("~")
        COLD_PATH = os.path.join(_home, "ztb_cold_storage")
        COLD_DB = os.path.join(_home, "cold_storage.db")

    def __init__(self, cold_path: str = None):
        self.cold_path = cold_path or self.COLD_PATH
        self.cold_db = self.COLD_DB
        os.makedirs(self.cold_path, exist_ok=True)

    def save(self, key: str, data: Dict) -> bool:
        """Daten persistent in Cold Storage speichern."""
        filepath = os.path.join(self.cold_path, f"{key}.json")
        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except OSError as e:
            print(f"[COLD-ERROR] Save '{key}': {e}")
            return False

    def load(self, key: str) -> Optional[Dict]:
        """Daten aus Cold Storage laden."""
        filepath = os.path.join(self.cold_path, f"{key}.json")
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def load_all(self) -> Dict[str, Dict]:
        """Alle Cold-Storage-Daten laden (fuer Recovery nach Neustart)."""
        data = {}
        try:
            for entry in os.scandir(self.cold_path):
                if entry.is_file() and entry.name.endswith(".json"):
                    key = entry.name.replace(".json", "")
                    try:
                        with open(entry.path, "r") as f:
                            data[key] = json.load(f)
                    except (json.JSONDecodeError, OSError):
                        pass
        except OSError:
            pass
        return data

    def list_keys(self):
        """Alle verfuegbaren Keys auflisten."""
        keys = []
        try:
            for entry in os.scandir(self.cold_path):
                if entry.is_file() and entry.name.endswith(".json"):
                    keys.append(entry.name.replace(".json", ""))
        except OSError:
            pass
        return keys

    def save_level(self, data: Dict) -> bool:
        """Level-Daten speichern (Alias fuer save)."""
        return self.save("level_data", data)

    def load_level(self) -> Optional[Dict]:
        """Level-Daten laden (Alias fuer load)."""
        return self.load("level_data")
