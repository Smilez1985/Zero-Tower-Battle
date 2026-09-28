#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Codex Manager
=========================================
Verwaltet den Monster-Codex (Bestiarium).

Features:
  - Besiegte Monster registrieren
  - Begegnungs-Statistiken (Siege/Niederlagen)
  - Shiny-Sichtungen tracken
  - Bester Floor pro Monster
  - Codex-Fortschritt berechnen

Daten werden in der codex-Tabelle (SQLite) gespeichert.

Referenz: Battle-Pi_Konsolidiert.txt Abschnitt 10
"""

import sqlite3
import json
import time
from typing import Dict, Any, Optional, List


# =============================================
# Codex Manager
# =============================================

class CodexManager:
    """
    Monster-Codex (Bestiarium) Verwaltung.

    Speichert jede Begegnung in der codex-Tabelle:
      - enemy_name: Name des Monsters
      - enemy_type: Typ (normal/boss/worldboss/shiny)
      - times_defeated: Wie oft besiegt
      - times_lost: Wie oft verloren
      - first/last_encounter: Zeitstempel
      - best_floor: Hoechster Floor bei Begegnung
      - is_shiny_seen: Mindestens einmal Shiny gesehen?
    """

    def __init__(self, db_path: str = None):
        """
        Args:
            db_path: Pfad zur SQLite-Datenbank
        """
        if db_path is None:
            try:
                from core.paths import COLD_DB_PATH
                db_path = COLD_DB_PATH
            except ImportError:
                import os
                db_path = os.path.join(os.path.expanduser("~"), "cold_storage.db")
        self._db_path = db_path
        self._conn = None

    def _get_conn(self) -> sqlite3.Connection:
        """Lazy-Load DB-Verbindung."""
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    # -----------------------------------------
    # Begegnung registrieren
    # -----------------------------------------

    def register_encounter(self, player_id: int, enemy_name: str,
                           result: str, floor: int = 0,
                           enemy_type: str = "normal",
                           is_shiny: bool = False) -> Dict[str, Any]:
        """
        Monster-Begegnung im Codex registrieren.

        Args:
            player_id: Spieler-ID in der DB
            enemy_name: Name des Monsters
            result: "WIN", "LOSS", "DRAW"
            floor: Aktueller Tower-Floor
            enemy_type: "normal", "boss", "worldboss"
            is_shiny: War es ein Shiny?

        Returns:
            Dict mit: status, entry (aktualisierter Codex-Eintrag)
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            now = time.strftime("%Y-%m-%d %H:%M:%S")

            # Bestehenden Eintrag pruefen
            cursor.execute(
                "SELECT * FROM codex WHERE player_id = ? AND enemy_name = ?",
                (player_id, enemy_name)
            )
            existing = cursor.fetchone()

            if existing:
                # Update
                new_defeated = existing["times_defeated"] + (1 if result == "WIN" else 0)
                new_lost = existing["times_lost"] + (1 if result == "LOSS" else 0)
                new_best = max(existing["best_floor"], floor)
                new_shiny = 1 if (existing["is_shiny_seen"] or is_shiny) else 0

                cursor.execute("""
                    UPDATE codex SET
                        times_defeated = ?,
                        times_lost = ?,
                        last_encounter = ?,
                        best_floor = ?,
                        is_shiny_seen = ?
                    WHERE player_id = ? AND enemy_name = ?
                """, (new_defeated, new_lost, now, new_best, new_shiny,
                      player_id, enemy_name))

                conn.commit()

                return {
                    "status": "UPDATED",
                    "entry": {
                        "enemy_name": enemy_name,
                        "times_defeated": new_defeated,
                        "times_lost": new_lost,
                        "best_floor": new_best,
                        "is_shiny_seen": bool(new_shiny),
                        "is_new": False
                    }
                }
            else:
                # Neuer Eintrag
                cursor.execute("""
                    INSERT INTO codex (
                        player_id, enemy_name, enemy_type,
                        times_defeated, times_lost,
                        first_encounter, last_encounter,
                        best_floor, is_shiny_seen
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id, enemy_name, enemy_type,
                    1 if result == "WIN" else 0,
                    1 if result == "LOSS" else 0,
                    now, now, floor,
                    1 if is_shiny else 0
                ))

                conn.commit()

                return {
                    "status": "NEW",
                    "entry": {
                        "enemy_name": enemy_name,
                        "times_defeated": 1 if result == "WIN" else 0,
                        "times_lost": 1 if result == "LOSS" else 0,
                        "best_floor": floor,
                        "is_shiny_seen": is_shiny,
                        "is_new": True
                    }
                }

        except sqlite3.Error as e:
            return {"status": "ERROR", "message": str(e)}

    # -----------------------------------------
    # Codex abfragen
    # -----------------------------------------

    def get_entry(self, player_id: int, enemy_name: str) -> Optional[Dict[str, Any]]:
        """Einzelnen Codex-Eintrag holen."""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM codex WHERE player_id = ? AND enemy_name = ?",
                (player_id, enemy_name)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        except sqlite3.Error:
            return None

    def get_all_entries(self, player_id: int) -> List[Dict[str, Any]]:
        """Alle Codex-Eintraege eines Spielers."""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM codex WHERE player_id = ? ORDER BY enemy_name",
                (player_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error:
            return []

    def get_progress(self, player_id: int, total_monsters: int = 50) -> Dict[str, Any]:
        """
        Codex-Fortschritt berechnen.

        Args:
            player_id: Spieler-ID
            total_monsters: Gesamtzahl moeglicher Monster

        Returns:
            Dict mit: discovered, total, percentage, shiny_seen
        """
        entries = self.get_all_entries(player_id)
        discovered = len(entries)
        shiny_seen = sum(1 for e in entries if e.get("is_shiny_seen"))
        total_defeats = sum(e.get("times_defeated", 0) for e in entries)
        total_losses = sum(e.get("times_lost", 0) for e in entries)

        return {
            "discovered": discovered,
            "total": total_monsters,
            "percentage": round((discovered / max(1, total_monsters)) * 100, 1),
            "shiny_seen": shiny_seen,
            "total_defeats": total_defeats,
            "total_losses": total_losses
        }

    # -----------------------------------------
    # Cleanup
    # -----------------------------------------

    def close(self) -> None:
        """DB-Verbindung schliessen."""
        if self._conn:
            self._conn.close()
            self._conn = None


# =============================================
# Standalone-Test
# =============================================

if __name__ == "__main__":
    import tempfile
    import os

    # Temp-DB fuer Test
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    try:
        # Schema anlegen
        conn = sqlite3.connect(tmp.name)
        conn.execute("""
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
                UNIQUE(player_id, enemy_name)
            )
        """)
        conn.commit()
        conn.close()

        mgr = CodexManager(db_path=tmp.name)

        # Test: Neue Begegnung
        r1 = mgr.register_encounter(1, "Goblin", "WIN", floor=5)
        print(f"Erste Begegnung: {r1['status']} - {r1['entry']}")

        # Test: Nochmal (Update)
        r2 = mgr.register_encounter(1, "Goblin", "WIN", floor=10)
        print(f"Zweite Begegnung: {r2['status']} - {r2['entry']}")

        # Test: Niederlage
        r3 = mgr.register_encounter(1, "Goblin", "LOSS", floor=15)
        print(f"Niederlage: {r3['status']} - {r3['entry']}")

        # Test: Shiny
        r4 = mgr.register_encounter(1, "Dragon", "WIN", floor=50, is_shiny=True)
        print(f"Shiny Dragon: {r4['status']} - {r4['entry']}")

        # Test: Fortschritt
        progress = mgr.get_progress(1, total_monsters=50)
        print(f"Fortschritt: {progress}")

        # Alle Eintraege
        all_entries = mgr.get_all_entries(1)
        print(f"Alle Eintraege ({len(all_entries)}):")
        for e in all_entries:
            print(f"  {e['enemy_name']}: {e['times_defeated']}W/{e['times_lost']}L "
                  f"(Shiny: {bool(e['is_shiny_seen'])})")

        mgr.close()
        print("\nCodex-Test abgeschlossen.")

    finally:
        os.unlink(tmp.name)
