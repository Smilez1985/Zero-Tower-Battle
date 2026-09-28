#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Save Handler
========================================
Zentrales Save-System mit Hot/Cold Storage Integration.

Hot Storage (RAM): Schnelle Zwischenspeicherung, fluechtig
Cold Storage (SD): Persistente Speicherung, ueberlebt Neustarts

Strategien:
- Regulaer: Alle 20 Minuten Hot -> Cold Backup
- Emergency: Sofort bei PVP/WorldBoss
- Shutdown: Kompletter Hot -> Cold Flush
- Recovery: Cold -> Hot beim Systemstart

Pi Zero 2W: 512MB RAM + 50% ZRAM + 4GB Swap
"""

import json
import time
from typing import Dict, Any, Optional, List


class SaveHandler:
    """
    Save System mit Hot/Cold Storage Integration.

    Nutzt Lazy-Loading fuer alle Storage-Module um
    Speicher erst bei Bedarf zu belegen.
    """

    BACKUP_INTERVAL = 1200  # 20 Minuten in Sekunden

    def __init__(self):
        self._hot = None
        self._cold = None
        self._hot_cold = None
        self._last_backup = 0.0

    # ===========================
    # Lazy-Loading
    # ===========================

    def _get_hot(self):
        """Lazy-Load Hot Storage Manager."""
        if self._hot is None:
            from game.hot_storage import HotStorageManager
            self._hot = HotStorageManager()
        return self._hot

    def _get_cold(self):
        """Lazy-Load Cold Storage Manager."""
        if self._cold is None:
            from game.hot_storage import ColdStorageManager
            self._cold = ColdStorageManager()
        return self._cold

    def _get_hot_cold(self):
        """Lazy-Load Hot/Cold Koordinator."""
        if self._hot_cold is None:
            from game.hot_cold_storage import HotColdManager
            self._hot_cold = HotColdManager()
        return self._hot_cold

    # ===========================
    # Speichern
    # ===========================

    def save(self, data: Dict, force: bool = False) -> Dict[str, Any]:
        """
        Spielstand speichern.

        Normal: In Hot Storage (schnell)
        Force/Emergency: Direkt in Cold Storage (persistent)

        Args:
            data: Spieldaten (mode, score, level, hp, gold, etc.)
            force: True = sofort in Cold (PVP/WorldBoss/Shutdown)

        Returns:
            Dict mit result, storage_type, migrated
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        data["save_timestamp"] = timestamp

        if force:
            # Emergency Save: Direkt in Cold Storage
            cold = self._get_cold()
            key = f"save_{int(time.time())}"
            success = cold.save(key, data)

            # Auch den aktuellen Spielstand als game_state sichern
            cold.save("game_state", data)

            return {
                "result": "SUCCESS" if success else "ERROR",
                "storage_type": "COLD",
                "migrated": False,
                "timestamp": timestamp
            }
        else:
            # Normal Save: In Hot Storage (mit OOM-Schutz)
            hot = self._get_hot()
            result = hot.write(data, "current_data")

            return {
                "result": result.get("result", "ERROR"),
                "storage_type": "HOT",
                "migrated": result.get("migrated", False),
                "timestamp": timestamp
            }

    def save_emergency(self, data: Dict) -> Dict[str, Any]:
        """Emergency Save (PVP/WorldBoss) - sofort in Cold."""
        return self.save(data, force=True)

    # ===========================
    # Laden
    # ===========================

    def load(self) -> Optional[Dict]:
        """
        Neuesten Spielstand laden.
        Versucht zuerst Hot, dann Cold Storage.
        """
        # 1. Versuche Hot Storage (aktuellste Daten)
        hot = self._get_hot()
        data = hot.read("current_data")
        if data:
            return data

        # 2. Fallback: Cold Storage (letzter persistenter Stand)
        cold = self._get_cold()
        data = cold.load("game_state")
        if data:
            return data

        return None

    def load_from_cold(self) -> Optional[Dict]:
        """Explizit aus Cold Storage laden (fuer Recovery nach Crash)."""
        cold = self._get_cold()
        return cold.load("game_state")

    # ===========================
    # Backup-Zyklen
    # ===========================

    def check_backup_needed(self) -> bool:
        """Pruefe ob regulaeres 20-Min-Backup faellig ist."""
        now = time.time()
        return (now - self._last_backup) >= self.BACKUP_INTERVAL

    def run_backup_cycle(self) -> Dict[str, Any]:
        """
        Regulaeres Backup: Hot -> Cold alle 20 Minuten.
        Wird vom Orchestrator aufgerufen.
        """
        if not self.check_backup_needed():
            return {"result": "SKIPPED", "reason": "Intervall nicht erreicht"}

        hot = self._get_hot()
        cold = self._get_cold()

        # Aktuelle Hot-Daten lesen
        data = hot.read("current_data")
        if not data:
            return {"result": "SKIPPED", "reason": "Keine Hot-Daten vorhanden"}

        # In Cold speichern
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        data["backup_timestamp"] = timestamp
        success = cold.save("game_state", data)

        if success:
            self._last_backup = time.time()
            return {
                "result": "SUCCESS",
                "timestamp": timestamp,
                "hot_usage": hot.get_usage()
            }
        else:
            return {"result": "ERROR", "reason": "Cold Storage Schreibfehler"}

    # ===========================
    # Hot Storage Health
    # ===========================

    def check_hot_health(self) -> Dict[str, Any]:
        """Hot Storage Auslastung pruefen."""
        hot = self._get_hot()
        return hot.get_usage()

    def is_hot_critical(self) -> bool:
        """Pruefe ob Hot Storage >= 90% belegt."""
        hot = self._get_hot()
        return hot.is_critical()

    # ===========================
    # Shutdown & Recovery
    # ===========================

    def flush_for_shutdown(self) -> Dict[str, Any]:
        """
        Gently Shutdown: Alle Hot-Daten in Cold uebertragen.
        Wird vom War Room Shutdown aufgerufen.
        """
        hot = self._get_hot()
        return hot.flush_to_cold()

    def recover_from_cold(self) -> Optional[Dict]:
        """
        Recovery nach Crash/Neustart.
        Laedt Spielstand aus Cold Storage und schreibt
        ihn in den (leeren) Hot Storage.
        """
        cold = self._get_cold()
        hot = self._get_hot()

        # Spielstand aus Cold laden
        game_state = cold.load("game_state")
        if not game_state:
            return None

        # In Hot Storage wiederherstellen
        hot.write(game_state, "current_data")
        return game_state

    # ===========================
    # Player-Verwaltung
    # ===========================

    def get_players(self) -> List[Dict]:
        """Alle Spieler aus Cold Storage laden (Rangliste)."""
        hot_cold = self._get_hot_cold()
        try:
            import sqlite3
            conn = sqlite3.connect(hot_cold.cold_db)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT player_id, username, score, rank, level "
                "FROM players ORDER BY score DESC"
            )
            rows = cursor.fetchall()
            conn.close()
            return [
                {
                    "player_id": row[0],
                    "username": row[1],
                    "score": row[2],
                    "rank": row[3],
                    "level": row[4]
                }
                for row in rows
            ]
        except Exception as e:
            print(f"[SAVE] Player-Liste Fehler: {e}")
            return []


class WorldBossManager:
    """
    WorldBoss Save Manager.
    Emergency Save bei WorldBoss-Events.
    Nutzt SaveHandler fuer persistente Speicherung.
    """

    def __init__(self):
        self._save_handler = None

    def _get_save_handler(self):
        """Lazy-Load SaveHandler."""
        if self._save_handler is None:
            self._save_handler = SaveHandler()
        return self._save_handler

    def save_worldboss(self, boss_name: str, boss_data: Dict) -> Dict[str, Any]:
        """
        Emergency Save bei WorldBoss-Event.
        Speichert sofort in Cold Storage.

        Args:
            boss_name: Name des WorldBoss
            boss_data: Boss-Daten (kills, level, damage, etc.)

        Returns:
            Dict mit Save-Ergebnis
        """
        data = {
            "mode": "WORLDBOSS",
            "boss_name": boss_name,
            "kills": boss_data.get("kills", 0),
            "level": boss_data.get("level", 0),
            "damage_dealt": boss_data.get("damage_dealt", 0),
            "participants": boss_data.get("participants", []),
            "loot": boss_data.get("loot", []),
            "save_type": "EMERGENCY"
        }

        handler = self._get_save_handler()
        result = handler.save_emergency(data)

        if result.get("result") == "SUCCESS":
            print(f"[WORLDBOSS] '{boss_name}' gesichert (Cold Storage)")
        else:
            print(f"[WORLDBOSS-ERROR] '{boss_name}' Speichern fehlgeschlagen")

        return result

    def load_worldboss_history(self) -> List[Dict]:
        """WorldBoss-Historie aus Cold Storage laden."""
        handler = self._get_save_handler()
        cold = handler._get_cold()
        all_data = cold.load_all()
        return [
            v for k, v in all_data.items()
            if isinstance(v, dict) and v.get("mode") == "WORLDBOSS"
        ]
