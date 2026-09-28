#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Zentrales Database-Utility
=====================================================
Stellt eine einheitliche SQLite-Zugriffs-Schicht bereit.

Wird von allen Modulen genutzt die Cold-Storage-Zugriff brauchen:
  - game/hot_storage.py (ColdStorageManager)
  - codex_manager.py (CodexManager)
  - gossip_taverne.py (GossipTaverne, P2PLeaderboard)
  - champion_psyche.py (ChampionPsyche)
  - services/sync_profile.py
  - models/character_db.py

Features:
  - Thread-Safe via check_same_thread=False
  - WAL-Modus fuer bessere Concurrent-Reads
  - Auto-Retry bei "database is locked" (3 Versuche)
  - Kontextmanager fuer sichere Transaktionen
  - Zentraler DB-Pfad via core.paths

Referenz: Battle-Pi_Konsolidiert.txt Abschnitt 3 (Hot/Cold Storage)
"""

import os
import sqlite3
import time
from typing import Optional, Any, List, Tuple
from contextlib import contextmanager


# =============================================
# Default-Pfad
# =============================================

def _default_db_path() -> str:
    """Zentraler DB-Pfad via core.paths oder Fallback."""
    try:
        from core.paths import COLD_DB_PATH
        return COLD_DB_PATH
    except ImportError:
        return os.path.join(os.path.expanduser("~"), "cold_storage.db")


# =============================================
# Database Klasse
# =============================================

class Database:
    """
    Zentrales SQLite-Interface fuer ZTB Cold Storage.

    Usage:
        db = Database()
        with db.transaction() as cur:
            cur.execute("INSERT INTO ...", (...))

        rows = db.fetch_all("SELECT * FROM players")
        row = db.fetch_one("SELECT * FROM players WHERE name=?", ("Test",))
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 0.1  # Sekunden

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or _default_db_path()

        # Verzeichnis sicherstellen
        db_dir = os.path.dirname(self._db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._connection = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            timeout=10.0
        )
        self._connection.row_factory = sqlite3.Row

        # WAL-Modus fuer bessere Performance bei gleichzeitigen Lesezugriffen
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")

    @property
    def connection(self) -> sqlite3.Connection:
        """Direkte Verbindung fuer bestehenden Code."""
        return self._connection

    @property
    def path(self) -> str:
        """Pfad zur Datenbank-Datei."""
        return self._db_path

    # ========================================
    # Kontext-Manager
    # ========================================

    @contextmanager
    def transaction(self):
        """
        Kontextmanager fuer sichere Transaktionen.

        Usage:
            with db.transaction() as cur:
                cur.execute("INSERT INTO ...", (...))
                cur.execute("UPDATE ...", (...))
            # Auto-Commit bei Erfolg, Rollback bei Exception
        """
        cur = self._connection.cursor()
        try:
            yield cur
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        finally:
            cur.close()

    # ========================================
    # Query-Methoden mit Auto-Retry
    # ========================================

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        SQL-Statement ausfuehren mit Auto-Retry bei Lock.

        Args:
            sql: SQL-Statement
            params: Parameter-Tuple

        Returns:
            sqlite3.Cursor
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                cur = self._connection.execute(sql, params)
                self._connection.commit()
                return cur
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                raise

    def fetch_all(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        """
        Alle Zeilen einer Query zurueckgeben.

        Args:
            sql: SELECT-Statement
            params: Parameter-Tuple

        Returns:
            Liste von sqlite3.Row Objekten
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                cur = self._connection.execute(sql, params)
                return cur.fetchall()
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                raise

    def fetch_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """
        Eine Zeile einer Query zurueckgeben.

        Args:
            sql: SELECT-Statement
            params: Parameter-Tuple

        Returns:
            sqlite3.Row oder None
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                cur = self._connection.execute(sql, params)
                return cur.fetchone()
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                raise

    def table_exists(self, table_name: str) -> bool:
        """Pruefen ob eine Tabelle existiert."""
        row = self.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return row is not None

    # ========================================
    # Schema-Helpers
    # ========================================

    def create_table_if_not_exists(self, table_name: str, schema: str) -> None:
        """
        Tabelle erstellen falls nicht vorhanden.

        Args:
            table_name: Tabellenname
            schema: CREATE TABLE Schema (ohne "CREATE TABLE IF NOT EXISTS name")

        Beispiel:
            db.create_table_if_not_exists("players",
                "(name TEXT PRIMARY KEY, level INTEGER, class TEXT)")
        """
        self.execute(
            f"CREATE TABLE IF NOT EXISTS {table_name} {schema}"
        )

    # ========================================
    # Lifecycle
    # ========================================

    def close(self) -> None:
        """Verbindung schliessen."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# =============================================
# Standalone Test
# =============================================

if __name__ == "__main__":
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_path = f.name

    try:
        db = Database(db_path=test_path)

        # Tabelle erstellen
        db.create_table_if_not_exists("test_players",
            "(name TEXT PRIMARY KEY, level INTEGER DEFAULT 1)")
        print(f"Table exists: {db.table_exists('test_players')}")

        # Insert mit Transaction
        with db.transaction() as cur:
            cur.execute("INSERT INTO test_players (name, level) VALUES (?, ?)",
                        ("TestRitter", 42))
            cur.execute("INSERT INTO test_players (name, level) VALUES (?, ?)",
                        ("TestMagier", 17))

        # Fetch
        all_rows = db.fetch_all("SELECT * FROM test_players ORDER BY level DESC")
        for row in all_rows:
            print(f"  {row['name']}: Level {row['level']}")

        one = db.fetch_one("SELECT * FROM test_players WHERE name=?", ("TestRitter",))
        print(f"Single: {one['name']} Level {one['level']}")

        print(f"\nDB path: {db.path}")
        print("All tests passed!")

        db.close()
    finally:
        os.unlink(test_path)
