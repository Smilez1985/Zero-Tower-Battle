#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Hot/Cold Storage Manager
=====================================================
Koordiniert Hot Storage (RAM) und Cold Storage (SD/SQLite).

Hot: RAMDisk (Temp) - schnell, fluechtig
Cold: SQLite/JSON (SD) - langsam, persistent
Backup: 20min + Emergency (PVP/WorldBoss)
OOM-Schutz: 90% Schwelle -> Auto-Migration

Pi Zero 2W: 512MB RAM + 50% ZRAM + 4GB Swap
"""

import sqlite3
import time
import json
import os
from typing import Dict, Any, Optional


class HotColdManager:
    """
    Koordinator fuer Hot/Cold Storage.
    Nutzt game.hot_storage.HotStorageManager und ColdStorageManager.
    """

    def __init__(self, cold_db_path: str = None,
                 backup_interval: int = 1200):
        if cold_db_path is None:
            try:
                from core.paths import COLD_DB_PATH
                cold_db_path = COLD_DB_PATH
            except ImportError:
                cold_db_path = os.path.join(os.path.expanduser("~"), "cold_storage.db")
        self.cold_db = cold_db_path
        self.backup_interval = backup_interval  # 20min
        self._hot = None
        self._cold = None
        self._init_sqlite()

    def _get_hot(self):
        """Lazy-Load Hot Storage."""
        if self._hot is None:
            from game.hot_storage import HotStorageManager
            self._hot = HotStorageManager()
        return self._hot

    def _get_cold(self):
        """Lazy-Load Cold Storage."""
        if self._cold is None:
            from game.hot_storage import ColdStorageManager
            self._cold = ColdStorageManager()
        return self._cold

    def _init_sqlite(self):
        """SQLite-Tabellen fuer Cold Storage initialisieren."""
        try:
            conn = sqlite3.connect(self.cold_db)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS battles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    mode TEXT,
                    player_id TEXT,
                    score INTEGER,
                    level_data TEXT,
                    hot_backup DATETIME
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_backup
                ON battles(timestamp)
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id TEXT UNIQUE,
                    username TEXT,
                    score INTEGER,
                    rank INTEGER,
                    level INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SQLite] Init fehlgeschlagen: {e}")

    # ===========================
    # Hot Storage Operationen
    # ===========================

    def get_hot_data(self, key: str = "current_data") -> Optional[Dict]:
        """Daten aus Hot Storage lesen."""
        return self._get_hot().read(key)

    def save_hot(self, data: Dict, key: str = "current_data") -> Dict[str, Any]:
        """
        In Hot Storage speichern.
        Bei 90% Auslastung: automatische Migration.
        """
        return self._get_hot().write(data, key)

    def check_hot_storage_health(self) -> Dict[str, Any]:
        """Hot Storage Gesundheitscheck."""
        return self._get_hot().get_usage()

    # ===========================
    # Cold Storage Operationen
    # ===========================

    def save_to_cold(self, hot_data: Dict) -> bool:
        """Hot-Daten in SQLite Cold Storage speichern."""
        try:
            conn = sqlite3.connect(self.cold_db)
            cursor = conn.cursor()
            now = time.strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute('''
                INSERT INTO battles (mode, score, level_data, hot_backup)
                VALUES (?, ?, ?, ?)
            ''', (
                hot_data.get('mode'),
                hot_data.get('score'),
                json.dumps(hot_data.get('level', {})),
                now
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[COLD] Backup fehlgeschlagen: {e}")
            return False

    def load_from_cold(self) -> Optional[Dict]:
        """Neuesten Eintrag aus Cold Storage laden."""
        try:
            conn = sqlite3.connect(self.cold_db)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM battles ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    "id": row[0],
                    "timestamp": row[1],
                    "mode": row[2],
                    "player_id": row[3],
                    "score": row[4],
                    "level_data": json.loads(row[5]) if row[5] else {},
                    "hot_backup": row[6]
                }
            return None
        except Exception as e:
            print(f"[COLD] Load fehlgeschlagen: {e}")
            return None

    # ===========================
    # Backup & Emergency
    # ===========================

    def backup_20min(self) -> bool:
        """Regulaerer Backup-Zyklus (20min)."""
        try:
            hot_data = self.get_hot_data()
            if hot_data:
                return self.save_to_cold(hot_data)
            return False
        except Exception as e:
            print(f"[BACKUP] Error: {e}")
            return False

    def emergency_save(self, data: Dict) -> bool:
        """Sofortiges Emergency Save (PVP/WorldBoss)."""
        if self.save_to_cold(data):
            return True
        return False

    def flush_hot_to_cold(self) -> Dict[str, Any]:
        """Kompletter Hot->Cold Flush (fuer Shutdown)."""
        return self._get_hot().flush_to_cold()
