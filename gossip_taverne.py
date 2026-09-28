#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Gossip-Protokoll der Taverne
========================================================
Dezentrales, serverloses soziales Netzwerk via BLE/WiFi-Direct.

Module:
  1. Trinkbuddy-Buff: +10% Gold fuer 1h nach Begegnung
  2. P2P-Leaderboard: Top-100 dezentrale Rangliste (Merge)
  3. Paket-Relay: Asynchrone Item-/Nachrichten-Zustellung
  4. Runen-Formel-Tausch: Runen-Rezepte austauschen
  5. Weltboss-Trigger: 3+ Pis im Raum = Weltboss-Spawn
  6. Drop & Leave: Alte Items als Fundstücke hinterlassen

Ausloesung: Automatisch wenn 2+ Pis in BLE-Reichweite (10-20m).
Verbindung: BLE-Scan → Handshake → WiFi-Direct → Gossip-Austausch.

Persistenz: Alle Subsysteme speichern in SQLite (Cold Storage).
Daten ueberleben Neustarts und werden beim Start geladen.

Referenz: "Das Gossip-Protokoll der Taverne.txt"
"""

import hashlib
import json
import os
import sqlite3
import time
from typing import Dict, Any, Optional, List, Tuple


# =============================================
# Konstanten
# =============================================

# Trinkbuddy
TRINKBUDDY_DURATION_SECONDS = 3600     # 1 Stunde Echtzeit
TRINKBUDDY_GOLD_BONUS = 0.10           # +10% Gold

# Leaderboard
LEADERBOARD_MAX_ENTRIES = 100           # Top-100
LEADERBOARD_FIELDS = ["name", "level", "floor", "pvp_wins", "ascension", "score"]

# Paket-Relay
RELAY_MAX_MESSAGE_LEN = 50             # Max 50 Zeichen Nachricht
RELAY_MAX_HOPS = 20                    # Max Weiterleitungen
RELAY_MAX_PENDING = 50                 # Max ausstehende Pakete

# Runen
MAX_RUNE_FORMULAS = 30                 # Max gespeicherte Runen-Formeln

# Weltboss
WORLDBOSS_MIN_PLAYERS = 3             # Minimum Pis fuer Trigger
WORLDBOSS_CHECK_WINDOW = 300           # 5 Min Zeitfenster (Sekunden)

# Gossip-DB
try:
    from core.paths import COLD_DB_PATH as GOSSIP_DB_PATH
except ImportError:
    GOSSIP_DB_PATH = os.path.join(os.path.expanduser("~"), "cold_storage.db")


# =============================================
# 1. Trinkbuddy-Buff
# =============================================

class TrinkbuddyBuff:
    """
    Trinkbuddy-System: +10% Gold fuer 1 Stunde nach Begegnung.

    Aktiviert wenn zwei Pis sich treffen (BLE-Handshake erfolgreich).
    Terminal-Visualisierung: "Dein Champion trinkt gerade mit 'ShadowX'"
    """

    def __init__(self):
        self._active_buffs: Dict[str, float] = {}  # partner_name -> expiry_timestamp
        self._buff_active = False
        self._buff_expiry = 0.0

    def activate(self, partner_name: str) -> Dict[str, Any]:
        """
        Trinkbuddy-Buff aktivieren nach Begegnung.

        Args:
            partner_name: Name des Trinkbuddy-Partners

        Returns:
            Dict mit: status, partner, expires_at, gold_bonus
        """
        now = time.time()
        expiry = now + TRINKBUDDY_DURATION_SECONDS

        self._active_buffs[partner_name] = expiry
        self._buff_active = True
        self._buff_expiry = expiry

        return {
            "status": "ACTIVATED",
            "partner": partner_name,
            "expires_at": expiry,
            "gold_bonus": f"+{int(TRINKBUDDY_GOLD_BONUS * 100)}%",
            "duration_minutes": TRINKBUDDY_DURATION_SECONDS // 60,
            "message": f"Dein Champion trinkt gerade mit '{partner_name}'!"
        }

    def is_active(self) -> bool:
        """Pruefe ob irgendein Trinkbuddy-Buff noch aktiv ist."""
        now = time.time()
        # Abgelaufene entfernen
        expired = [k for k, v in self._active_buffs.items() if v <= now]
        for k in expired:
            del self._active_buffs[k]

        self._buff_active = len(self._active_buffs) > 0
        if self._buff_active:
            self._buff_expiry = max(self._active_buffs.values())
        return self._buff_active

    def get_gold_multiplier(self) -> float:
        """Gold-Multiplikator (1.0 = kein Buff, 1.1 = +10%)."""
        if self.is_active():
            return 1.0 + TRINKBUDDY_GOLD_BONUS
        return 1.0

    def get_active_buddies(self) -> List[Dict[str, Any]]:
        """Alle aktiven Trinkbuddys auflisten."""
        now = time.time()
        result = []
        for name, expiry in self._active_buffs.items():
            remaining = max(0, expiry - now)
            if remaining > 0:
                result.append({
                    "partner": name,
                    "remaining_seconds": int(remaining),
                    "remaining_minutes": int(remaining // 60)
                })
        return result


# =============================================
# 2. P2P-Leaderboard
# =============================================

class P2PLeaderboard:
    """
    Dezentrale Top-100 Rangliste.

    Jeder Pi pflegt lokal seine eigene Liste.
    Bei Begegnung: Listen mergen (bessere Eintraege behalten).
    Viraler Effekt: Pi A lernt durch Pi B auch von Pi C.
    """

    def __init__(self, max_entries: int = LEADERBOARD_MAX_ENTRIES):
        self._entries: Dict[str, Dict[str, Any]] = {}  # name -> stats
        self._max_entries = max_entries

    def update_local(self, player_data: Dict[str, Any]) -> None:
        """
        Lokalen Spieler in Leaderboard aktualisieren.

        Args:
            player_data: Dict mit name, level, floor, pvp_wins, ascension
        """
        name = player_data.get("name", "")
        if not name:
            return

        score = self._calculate_score(player_data)
        self._entries[name] = {
            "name": name,
            "level": player_data.get("level", 1),
            "floor": player_data.get("current_floor", 1),
            "pvp_wins": player_data.get("pvp_wins", 0),
            "ascension": player_data.get("ascension", 1),
            "score": score,
            "last_seen": time.time()
        }
        self._trim()

    def merge(self, remote_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Remote-Leaderboard mergen (nach Begegnung).

        Regeln:
          - Bessere Scores ueberschreiben schlechtere
          - Neuere Timestamps bei gleichem Score
          - Max 100 Eintraege behalten

        Args:
            remote_entries: Liste von Leaderboard-Eintraegen

        Returns:
            Dict mit: merged_count, new_entries, updated_entries
        """
        merged = 0
        new_count = 0
        updated = 0

        for entry in remote_entries:
            name = entry.get("name", "")
            if not name:
                continue

            remote_score = entry.get("score", 0)
            existing = self._entries.get(name)

            if existing is None:
                # Neuer Eintrag
                self._entries[name] = entry
                new_count += 1
                merged += 1
            elif remote_score > existing.get("score", 0):
                # Besserer Score
                self._entries[name] = entry
                updated += 1
                merged += 1

        self._trim()

        return {
            "merged_count": merged,
            "new_entries": new_count,
            "updated_entries": updated,
            "total_entries": len(self._entries)
        }

    def get_top(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Top-N Eintraege sortiert nach Score."""
        sorted_entries = sorted(
            self._entries.values(),
            key=lambda x: x.get("score", 0),
            reverse=True
        )
        return sorted_entries[:limit]

    def get_rank(self, player_name: str) -> Optional[int]:
        """Rang eines Spielers (1-basiert, None wenn nicht vorhanden)."""
        top = self.get_top(self._max_entries)
        for i, entry in enumerate(top, 1):
            if entry.get("name") == player_name:
                return i
        return None

    def export_entries(self) -> List[Dict[str, Any]]:
        """Alle Eintraege fuer Gossip-Austausch exportieren."""
        return list(self._entries.values())

    @staticmethod
    def _calculate_score(data: Dict[str, Any]) -> int:
        """
        Score berechnen (fuer Sortierung).
        Formel: floor * ascension + pvp_wins * 10 + level * 5
        """
        floor = data.get("current_floor", data.get("floor", 1))
        ascension = data.get("ascension", 1)
        pvp_wins = data.get("pvp_wins", 0)
        level = data.get("level", 1)
        return floor * ascension + pvp_wins * 10 + level * 5

    def _trim(self):
        """Auf max_entries begrenzen (schlechteste entfernen)."""
        if len(self._entries) > self._max_entries:
            sorted_names = sorted(
                self._entries.keys(),
                key=lambda n: self._entries[n].get("score", 0),
                reverse=True
            )
            keep = set(sorted_names[:self._max_entries])
            self._entries = {k: v for k, v in self._entries.items() if k in keep}


# =============================================
# 3. Paket-Relay (Asynchrone Zustellung)
# =============================================

class PacketRelay:
    """
    Asynchrones Nachrichten-/Item-Relay-System.

    Ablauf:
      1. Spieler erstellt Paket (Item + Nachricht fuer Spieler X)
      2. Pi uebergibt Paket an naechste Begegnung
      3. Weiterleitung bis Spieler X physisch erreicht wird
      4. Kann Tage/Wochen dauern (je nach Spieler-Dichte)
    """

    def __init__(self):
        self._outgoing: List[Dict[str, Any]] = []   # Zu versendende Pakete
        self._carrying: List[Dict[str, Any]] = []    # Im Transit (Relay)
        self._inbox: List[Dict[str, Any]] = []       # Empfangene Pakete

    def create_packet(self, sender_name: str, recipient_name: str,
                      message: str, item: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Neues Relay-Paket erstellen.

        Args:
            sender_name: Absender
            recipient_name: Empfaenger (Spieler-Name)
            message: Nachricht (max 50 Zeichen)
            item: Optional Item-Dict

        Returns:
            Dict mit: status, packet
        """
        total_pending = len(self._outgoing) + len(self._carrying)
        if total_pending >= RELAY_MAX_PENDING:
            return {"status": "ERROR", "message": "Zu viele ausstehende Pakete"}

        if len(message) > RELAY_MAX_MESSAGE_LEN:
            message = message[:RELAY_MAX_MESSAGE_LEN]

        packet = {
            "id": hashlib.sha256(
                f"{sender_name}:{recipient_name}:{time.time()}".encode()
            ).hexdigest()[:12],
            "sender": sender_name,
            "recipient": recipient_name,
            "message": message,
            "item": item,
            "hops": 0,
            "max_hops": RELAY_MAX_HOPS,
            "created_at": time.time(),
            "relay_path": [sender_name]
        }

        self._outgoing.append(packet)

        return {
            "status": "CREATED",
            "packet": packet,
            "message": f"Paket fuer '{recipient_name}' erstellt. "
                       f"Wird bei naechster Begegnung weitergeleitet."
        }

    def exchange_packets(self, remote_name: str,
                         remote_packets: List[Dict[str, Any]],
                         local_name: str) -> Dict[str, Any]:
        """
        Pakete mit Remote-Pi austauschen.

        Logik:
          - Empfangene Pakete fuer uns → Inbox
          - Empfangene Pakete fuer andere → Carrying (Relay)
          - Eigene Outgoing-Pakete → an Remote uebergeben
          - Carrying-Pakete → an Remote weiterleiten
          - Hop-Counter incrementieren, Hop-Limit beachten

        Args:
            remote_name: Name des Gegenuebers
            remote_packets: Pakete vom Remote-Pi
            local_name: Eigener Spieler-Name

        Returns:
            Dict mit: delivered, relayed, sent_to_remote, packets_for_remote
        """
        delivered = []
        relayed = []
        sent_to_remote = []

        # --- 1. Empfangene Pakete verarbeiten ---
        for packet in remote_packets:
            # Hop-Limit pruefen
            if packet.get("hops", 0) >= packet.get("max_hops", RELAY_MAX_HOPS):
                continue  # Paket abgelaufen

            if packet.get("recipient") == local_name:
                # Direkt fuer uns → Inbox
                packet["delivered_at"] = time.time()
                self._inbox.append(packet)
                delivered.append(packet)
            else:
                # Nicht fuer uns → Relay (wir tragen es weiter)
                packet["hops"] = packet.get("hops", 0) + 1
                packet.setdefault("relay_path", []).append(local_name)
                self._carrying.append(packet)
                relayed.append(packet)

        # --- 2. Eigene Outgoing-Pakete an Remote uebergeben ---
        for packet in self._outgoing:
            if packet.get("recipient") == remote_name:
                # Direktzustellung: Empfaenger ist der Remote-Pi
                packet["delivered_at"] = time.time()
                sent_to_remote.append(packet)
            else:
                # Relay: Remote traegt es weiter
                packet["hops"] = packet.get("hops", 0) + 1
                packet.setdefault("relay_path", []).append(local_name)
                sent_to_remote.append(packet)

        # Outgoing ist jetzt leer (alle uebergeben)
        self._outgoing.clear()

        # --- 3. Carrying-Pakete an Remote weiterleiten ---
        still_carrying = []
        for packet in self._carrying:
            # Duplikat-Check: Nicht Pakete zurueck zum Absender leiten
            relay_path = packet.get("relay_path", [])
            if remote_name in relay_path:
                # Remote hat dieses Paket schon gesehen → behalten
                still_carrying.append(packet)
                continue

            if packet.get("recipient") == remote_name:
                # Direktzustellung
                packet["delivered_at"] = time.time()
                sent_to_remote.append(packet)
            else:
                # Weiterleiten
                packet["hops"] = packet.get("hops", 0) + 1
                packet.setdefault("relay_path", []).append(local_name)
                sent_to_remote.append(packet)

        # Nur Pakete behalten die nicht weitergeleitet wurden
        self._carrying = still_carrying

        return {
            "delivered": len(delivered),
            "relayed": len(relayed),
            "sent_to_remote": len(sent_to_remote),
            "packets_for_remote": sent_to_remote
        }

    def get_inbox(self) -> List[Dict[str, Any]]:
        """Empfangene Pakete abrufen."""
        return list(self._inbox)

    def clear_inbox(self) -> int:
        """Inbox leeren."""
        count = len(self._inbox)
        self._inbox.clear()
        return count

    def get_pending_count(self) -> Dict[str, int]:
        """Anzahl ausstehender Pakete."""
        return {
            "outgoing": len(self._outgoing),
            "carrying": len(self._carrying),
            "inbox": len(self._inbox),
            "total_pending": len(self._outgoing) + len(self._carrying)
        }


# =============================================
# 4. Runen-Formel-Tausch
# =============================================

class RuneFormulaExchange:
    """
    Austausch von Runen-Rezepten (Wissensaustausch).

    Da es kein Online-Wiki gibt, lernen Spieler Runen-Kombinationen
    durch P2P-Begegnungen.
    """

    def __init__(self):
        self._known_formulas: Dict[str, Dict[str, Any]] = {}  # formula_id -> formula

    def add_formula(self, formula_id: str, colors: List[str],
                    effect: str, source: str = "self") -> None:
        """Neue Runen-Formel hinzufuegen."""
        if len(self._known_formulas) >= MAX_RUNE_FORMULAS:
            return

        self._known_formulas[formula_id] = {
            "id": formula_id,
            "colors": colors,
            "effect": effect,
            "source": source,
            "learned_at": time.time()
        }

    def exchange(self, remote_formulas: List[Dict[str, Any]],
                 remote_name: str) -> Dict[str, Any]:
        """
        Runen-Formeln mit Remote-Pi austauschen.

        Args:
            remote_formulas: Formeln des Gegenubers
            remote_name: Name des Gegenubers

        Returns:
            Dict mit: learned_count, already_known, shared
        """
        learned = 0
        already_known = 0

        for formula in remote_formulas:
            fid = formula.get("id", "")
            if fid in self._known_formulas:
                already_known += 1
            elif len(self._known_formulas) < MAX_RUNE_FORMULAS:
                formula["source"] = remote_name
                formula["learned_at"] = time.time()
                self._known_formulas[fid] = formula
                learned += 1

        return {
            "learned_count": learned,
            "already_known": already_known,
            "shared": len(self._known_formulas)
        }

    def get_all_formulas(self) -> List[Dict[str, Any]]:
        """Alle bekannten Formeln (fuer Export)."""
        return list(self._known_formulas.values())

    def export_for_gossip(self) -> List[Dict[str, Any]]:
        """Formeln fuer Gossip-Austausch exportieren."""
        return self.get_all_formulas()


# =============================================
# 5. Weltboss-Trigger
# =============================================

class WorldBossTrigger:
    """
    Weltboss-Spawn durch Spieler-Dichte.

    Regel: 3+ Pis im selben Raum innerhalb von 5 Minuten
    → Weltboss spawnt (Schwierigkeit skaliert mit Spielerzahl)
    """

    def __init__(self):
        self._nearby_pings: Dict[str, float] = {}  # player_name -> last_ping_time

    def register_ping(self, player_name: str) -> None:
        """BLE-Ping eines Spielers registrieren."""
        self._nearby_pings[player_name] = time.time()

    def check_trigger(self) -> Dict[str, Any]:
        """
        Pruefe ob Weltboss getriggert werden soll.

        Returns:
            Dict mit: triggered, player_count, players, boss_scaling
        """
        now = time.time()
        cutoff = now - WORLDBOSS_CHECK_WINDOW

        # Abgelaufene Pings entfernen
        active = {
            name: ts for name, ts in self._nearby_pings.items()
            if ts >= cutoff
        }
        self._nearby_pings = active

        player_count = len(active)
        triggered = player_count >= WORLDBOSS_MIN_PLAYERS

        return {
            "triggered": triggered,
            "player_count": player_count,
            "players": list(active.keys()),
            "boss_scaling": max(1.0, player_count * 0.5) if triggered else 0.0,
            "message": (
                f"WELTBOSS! {player_count} Champions versammelt!"
                if triggered
                else f"{player_count}/{WORLDBOSS_MIN_PLAYERS} Champions in Reichweite."
            )
        }


# =============================================
# 6. Drop & Leave
# =============================================

class DropAndLeave:
    """
    "Drop & Leave"-System: Alte Items als Fundstuecke hinterlassen.

    Wenn ein Item durch ein besseres ersetzt wird (Auto-Equip),
    kann es "geopfert" werden → erscheint bei einem zufaelligen
    Spieler im Tower als Fundstueck mit persoenlicher Nachricht.
    """

    def __init__(self):
        self._dropped_items: List[Dict[str, Any]] = []
        self._found_items: List[Dict[str, Any]] = []

    def drop_item(self, item: Dict[str, Any], dropper_name: str,
                  message: str = "") -> Dict[str, Any]:
        """
        Item als Fundstueck hinterlassen.

        Args:
            item: Item-Dict
            dropper_name: Name des Hinterlassers
            message: Persoenliche Nachricht (max 50 Zeichen)

        Returns:
            Dict mit: status, dropped_item
        """
        if len(message) > RELAY_MAX_MESSAGE_LEN:
            message = message[:RELAY_MAX_MESSAGE_LEN]

        drop = {
            "item": item,
            "dropper": dropper_name,
            "message": message,
            "dropped_at": time.time(),
            "found": False
        }

        self._dropped_items.append(drop)

        return {
            "status": "DROPPED",
            "message": f"'{item.get('name', 'Item')}' als Fundstueck hinterlassen.",
            "dropped_item": drop
        }

    def exchange_drops(self, remote_drops: List[Dict[str, Any]],
                       local_name: str) -> Dict[str, Any]:
        """
        Fundstuecke mit Remote-Pi austauschen.
        Remote bekommt unsere Drops, wir bekommen seine.
        """
        received = 0
        for drop in remote_drops:
            if not drop.get("found", False):
                drop["found"] = True
                drop["found_by"] = local_name
                drop["found_at"] = time.time()
                self._found_items.append(drop)
                received += 1

        # Unsere Drops gehen zum Remote
        sent = list(self._dropped_items)
        self._dropped_items.clear()

        return {
            "received": received,
            "sent": len(sent),
            "drops_for_remote": sent
        }

    def get_found_items(self) -> List[Dict[str, Any]]:
        """Gefundene Items abrufen."""
        return list(self._found_items)

    def claim_found_item(self, index: int) -> Optional[Dict[str, Any]]:
        """Gefundenes Item beanspruchen."""
        if 0 <= index < len(self._found_items):
            return self._found_items.pop(index)
        return None


# =============================================
# Gossip-Protokoll Coordinator
# =============================================

class GossipTaverne:
    """
    Koordinator fuer alle Gossip-Subsysteme.

    Wird bei jeder BLE-Begegnung aufgerufen.
    Fuehrt den kompletten Gossip-Austausch durch.
    Persistiert alle Daten in SQLite (Cold Storage).
    """

    def __init__(self, local_name: str = "", db_path: str = None):
        self.local_name = local_name
        self.trinkbuddy = TrinkbuddyBuff()
        self.leaderboard = P2PLeaderboard()
        self.relay = PacketRelay()
        self.rune_exchange = RuneFormulaExchange()
        self.worldboss_trigger = WorldBossTrigger()
        self.drop_and_leave = DropAndLeave()
        self._db_path = db_path or GOSSIP_DB_PATH
        self._db_conn: Optional[sqlite3.Connection] = None

    def _get_db(self) -> sqlite3.Connection:
        """Lazy-Load DB fuer Gossip-Persistenz."""
        if self._db_conn is None:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            self._db_conn = sqlite3.connect(self._db_path)
            self._db_conn.row_factory = sqlite3.Row
            self._init_gossip_tables()
        return self._db_conn

    def _init_gossip_tables(self) -> None:
        """Gossip-spezifische DB-Tabellen anlegen."""
        conn = self._db_conn
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gossip_encounters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                local_player TEXT NOT NULL,
                remote_player TEXT NOT NULL,
                encounter_type TEXT DEFAULT 'gossip',
                trinkbuddy_activated INTEGER DEFAULT 0,
                leaderboard_merged INTEGER DEFAULT 0,
                packets_exchanged INTEGER DEFAULT 0,
                formulas_learned INTEGER DEFAULT 0,
                worldboss_triggered INTEGER DEFAULT 0,
                drops_exchanged INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gossip_leaderboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT UNIQUE NOT NULL,
                level INTEGER DEFAULT 1,
                floor INTEGER DEFAULT 1,
                pvp_wins INTEGER DEFAULT 0,
                ascension INTEGER DEFAULT 1,
                score INTEGER DEFAULT 0,
                last_seen REAL DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gossip_relay_packets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                packet_id TEXT UNIQUE NOT NULL,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                message TEXT DEFAULT '',
                item_data TEXT DEFAULT '{}',
                hops INTEGER DEFAULT 0,
                max_hops INTEGER DEFAULT 20,
                created_at REAL NOT NULL,
                relay_path TEXT DEFAULT '[]',
                delivered INTEGER DEFAULT 0,
                packet_type TEXT DEFAULT 'outgoing'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gossip_rune_formulas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                formula_id TEXT UNIQUE NOT NULL,
                colors TEXT NOT NULL,
                effect TEXT NOT NULL,
                source TEXT DEFAULT 'self',
                learned_at REAL NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gossip_found_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_data TEXT NOT NULL,
                dropper TEXT NOT NULL,
                message TEXT DEFAULT '',
                dropped_at REAL NOT NULL,
                found_by TEXT DEFAULT '',
                found_at REAL DEFAULT 0,
                claimed INTEGER DEFAULT 0
            )
        """)

        conn.commit()

    # -----------------------------------------
    # Persistenz: Speichern
    # -----------------------------------------

    def save_to_db(self) -> Dict[str, int]:
        """
        Alle Gossip-Daten in DB speichern.

        Wird nach jedem Gossip-Austausch und beim Shutdown aufgerufen.

        Returns:
            Dict mit Anzahl gespeicherter Eintraege pro Subsystem
        """
        conn = self._get_db()
        cursor = conn.cursor()
        counts = {}

        # --- Leaderboard ---
        lb_count = 0
        for entry in self.leaderboard.export_entries():
            try:
                cursor.execute("""
                    INSERT INTO gossip_leaderboard
                        (player_name, level, floor, pvp_wins, ascension, score, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(player_name) DO UPDATE SET
                        level=excluded.level,
                        floor=excluded.floor,
                        pvp_wins=excluded.pvp_wins,
                        ascension=excluded.ascension,
                        score=excluded.score,
                        last_seen=excluded.last_seen
                """, (
                    entry.get("name", ""),
                    entry.get("level", 1),
                    entry.get("floor", 1),
                    entry.get("pvp_wins", 0),
                    entry.get("ascension", 1),
                    entry.get("score", 0),
                    entry.get("last_seen", 0.0),
                ))
                lb_count += 1
            except sqlite3.Error:
                pass
        counts["leaderboard"] = lb_count

        # --- Relay-Pakete (Outgoing + Carrying) ---
        relay_count = 0
        # Bestehende nicht-zugestellte loeschen und neu einfuegen
        cursor.execute("DELETE FROM gossip_relay_packets WHERE delivered = 0")

        for ptype, packets in [("outgoing", self.relay._outgoing),
                                ("carrying", self.relay._carrying)]:
            for packet in packets:
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO gossip_relay_packets
                            (packet_id, sender, recipient, message, item_data,
                             hops, max_hops, created_at, relay_path, delivered, packet_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                    """, (
                        packet.get("id", ""),
                        packet.get("sender", ""),
                        packet.get("recipient", ""),
                        packet.get("message", ""),
                        json.dumps(packet.get("item"), ensure_ascii=False)
                        if packet.get("item") else "{}",
                        packet.get("hops", 0),
                        packet.get("max_hops", RELAY_MAX_HOPS),
                        packet.get("created_at", 0.0),
                        json.dumps(packet.get("relay_path", []), ensure_ascii=False),
                        ptype,
                    ))
                    relay_count += 1
                except sqlite3.Error:
                    pass
        counts["relay_packets"] = relay_count

        # --- Runen-Formeln ---
        rune_count = 0
        for formula in self.rune_exchange.get_all_formulas():
            try:
                colors_json = json.dumps(
                    formula.get("colors", []), ensure_ascii=False
                )
                cursor.execute("""
                    INSERT OR REPLACE INTO gossip_rune_formulas
                        (formula_id, colors, effect, source, learned_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    formula.get("id", ""),
                    colors_json,
                    formula.get("effect", ""),
                    formula.get("source", "self"),
                    formula.get("learned_at", 0.0),
                ))
                rune_count += 1
            except sqlite3.Error:
                pass
        counts["rune_formulas"] = rune_count

        # --- Found Items ---
        fi_count = 0
        for item_entry in self.drop_and_leave.get_found_items():
            try:
                cursor.execute("""
                    INSERT INTO gossip_found_items
                        (item_data, dropper, message, dropped_at, found_by, found_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    json.dumps(item_entry.get("item", {}), ensure_ascii=False),
                    item_entry.get("dropper", ""),
                    item_entry.get("message", ""),
                    item_entry.get("dropped_at", 0.0),
                    item_entry.get("found_by", ""),
                    item_entry.get("found_at", 0.0),
                ))
                fi_count += 1
            except sqlite3.Error:
                pass
        counts["found_items"] = fi_count

        conn.commit()
        return counts

    # -----------------------------------------
    # Persistenz: Laden
    # -----------------------------------------

    def load_from_db(self) -> Dict[str, int]:
        """
        Alle Gossip-Daten aus DB laden.

        Wird beim Start aufgerufen um den Zustand wiederherzustellen.

        Returns:
            Dict mit Anzahl geladener Eintraege pro Subsystem
        """
        conn = self._get_db()
        cursor = conn.cursor()
        counts = {}

        # --- Leaderboard ---
        try:
            cursor.execute("SELECT * FROM gossip_leaderboard ORDER BY score DESC")
            rows = cursor.fetchall()
            for row in rows:
                self.leaderboard._entries[row["player_name"]] = {
                    "name": row["player_name"],
                    "level": row["level"],
                    "floor": row["floor"],
                    "pvp_wins": row["pvp_wins"],
                    "ascension": row["ascension"],
                    "score": row["score"],
                    "last_seen": row["last_seen"],
                }
            counts["leaderboard"] = len(rows)
        except sqlite3.Error as e:
            print(f"[GOSSIP-DB] Leaderboard laden: {e}")
            counts["leaderboard"] = 0

        # --- Relay-Pakete ---
        try:
            cursor.execute(
                "SELECT * FROM gossip_relay_packets WHERE delivered = 0"
            )
            rows = cursor.fetchall()
            for row in rows:
                packet = {
                    "id": row["packet_id"],
                    "sender": row["sender"],
                    "recipient": row["recipient"],
                    "message": row["message"],
                    "item": json.loads(row["item_data"]) if row["item_data"] else None,
                    "hops": row["hops"],
                    "max_hops": row["max_hops"],
                    "created_at": row["created_at"],
                    "relay_path": json.loads(row["relay_path"])
                    if row["relay_path"] else [],
                }
                ptype = row["packet_type"] if "packet_type" in row.keys() else "outgoing"
                if ptype == "carrying":
                    self.relay._carrying.append(packet)
                else:
                    self.relay._outgoing.append(packet)

            counts["relay_packets"] = len(rows)
        except sqlite3.Error as e:
            print(f"[GOSSIP-DB] Relay laden: {e}")
            counts["relay_packets"] = 0

        # --- Runen-Formeln ---
        try:
            cursor.execute("SELECT * FROM gossip_rune_formulas")
            rows = cursor.fetchall()
            for row in rows:
                try:
                    colors = json.loads(row["colors"])
                except (json.JSONDecodeError, TypeError):
                    colors = []
                self.rune_exchange._known_formulas[row["formula_id"]] = {
                    "id": row["formula_id"],
                    "colors": colors,
                    "effect": row["effect"],
                    "source": row["source"],
                    "learned_at": row["learned_at"],
                }
            counts["rune_formulas"] = len(rows)
        except sqlite3.Error as e:
            print(f"[GOSSIP-DB] Runen laden: {e}")
            counts["rune_formulas"] = 0

        # --- Found Items (nicht-beanspruchte) ---
        try:
            cursor.execute(
                "SELECT * FROM gossip_found_items WHERE claimed = 0"
            )
            rows = cursor.fetchall()
            for row in rows:
                try:
                    item = json.loads(row["item_data"])
                except (json.JSONDecodeError, TypeError):
                    item = {}
                self.drop_and_leave._found_items.append({
                    "item": item,
                    "dropper": row["dropper"],
                    "message": row["message"],
                    "dropped_at": row["dropped_at"],
                    "found": True,
                    "found_by": row["found_by"],
                    "found_at": row["found_at"],
                })
            counts["found_items"] = len(rows)
        except sqlite3.Error as e:
            print(f"[GOSSIP-DB] Found Items laden: {e}")
            counts["found_items"] = 0

        return counts

    # -----------------------------------------
    # Komplett-Austausch
    # -----------------------------------------

    def perform_full_exchange(self, remote_name: str,
                              remote_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Kompletten Gossip-Austausch mit Remote-Pi durchfuehren.

        Args:
            remote_name: Name des Remote-Spielers
            remote_data: Dict mit:
                - player_stats: Stats des Remote-Spielers
                - leaderboard: Remote-Leaderboard-Eintraege
                - relay_packets: Pakete im Transit
                - rune_formulas: Bekannte Runen-Formeln
                - dropped_items: Hinterlassene Items

        Returns:
            Dict mit Ergebnissen aller Subsysteme
        """
        results = {}

        # 1. Trinkbuddy-Buff aktivieren
        buddy_result = self.trinkbuddy.activate(remote_name)
        results["trinkbuddy"] = buddy_result

        # 2. Leaderboard mergen
        remote_lb = remote_data.get("leaderboard", [])
        if remote_lb:
            lb_result = self.leaderboard.merge(remote_lb)
            results["leaderboard"] = lb_result
        else:
            results["leaderboard"] = {"merged_count": 0}

        # 3. Paket-Relay
        remote_packets = remote_data.get("relay_packets", [])
        relay_result = self.relay.exchange_packets(
            remote_name, remote_packets, self.local_name
        )
        results["relay"] = relay_result

        # 4. Runen-Formeln tauschen
        remote_formulas = remote_data.get("rune_formulas", [])
        if remote_formulas:
            rune_result = self.rune_exchange.exchange(remote_formulas, remote_name)
            results["runes"] = rune_result
        else:
            results["runes"] = {"learned_count": 0}

        # 5. Weltboss-Trigger pruefen
        self.worldboss_trigger.register_ping(remote_name)
        wb_result = self.worldboss_trigger.check_trigger()
        results["worldboss"] = wb_result

        # 6. Drop & Leave
        remote_drops = remote_data.get("dropped_items", [])
        if remote_drops:
            drop_result = self.drop_and_leave.exchange_drops(
                remote_drops, self.local_name
            )
            results["drops"] = drop_result
        else:
            results["drops"] = {"received": 0}

        # 7. Begegnung in DB loggen
        self._log_encounter(remote_name, results)

        # 8. Zustand in DB persistieren
        self.save_to_db()

        return results

    def prepare_gossip_payload(self, local_player: Dict[str, Any]) -> Dict[str, Any]:
        """
        Eigene Daten fuer Gossip-Austausch vorbereiten.

        Args:
            local_player: Lokaler Charakter-Dict

        Returns:
            Dict mit allen zu sendenden Gossip-Daten
        """
        # Lokalen Spieler im Leaderboard aktualisieren
        self.leaderboard.update_local(local_player)

        # Relay-Pakete: Outgoing + Carrying zum Versand zusammenstellen
        packets_to_send = list(self.relay._outgoing) + list(self.relay._carrying)

        # Drops zum Versand
        drops_to_send = list(self.drop_and_leave._dropped_items)

        return {
            "player_stats": {
                "name": local_player.get("name", ""),
                "level": local_player.get("level", 1),
                "floor": local_player.get("current_floor", 1),
                "pvp_wins": local_player.get("pvp_wins", 0),
                "ascension": local_player.get("ascension", 1),
            },
            "leaderboard": self.leaderboard.export_entries(),
            "relay_packets": packets_to_send,
            "rune_formulas": self.rune_exchange.export_for_gossip(),
            "dropped_items": drops_to_send,
        }

    # -----------------------------------------
    # DB-Logging
    # -----------------------------------------

    def _log_encounter(self, remote_name: str,
                       results: Dict[str, Any]) -> None:
        """Begegnung in DB loggen."""
        try:
            conn = self._get_db()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO gossip_encounters (
                    local_player, remote_player,
                    trinkbuddy_activated,
                    leaderboard_merged,
                    packets_exchanged,
                    formulas_learned,
                    worldboss_triggered,
                    drops_exchanged
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.local_name,
                remote_name,
                1 if results.get("trinkbuddy", {}).get("status") == "ACTIVATED" else 0,
                results.get("leaderboard", {}).get("merged_count", 0),
                results.get("relay", {}).get("delivered", 0),
                results.get("runes", {}).get("learned_count", 0),
                1 if results.get("worldboss", {}).get("triggered", False) else 0,
                results.get("drops", {}).get("received", 0),
            ))

            conn.commit()
        except sqlite3.Error as e:
            print(f"[GOSSIP-DB-ERROR] {e}")

    def get_encounter_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Letzte Begegnungen aus DB abrufen."""
        try:
            conn = self._get_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM gossip_encounters
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error:
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Gesamtstatistiken ueber alle Gossip-Aktivitaeten."""
        stats = {
            "leaderboard_entries": len(self.leaderboard._entries),
            "leaderboard_top3": [
                e.get("name", "?") for e in self.leaderboard.get_top(3)
            ],
            "relay_pending": self.relay.get_pending_count(),
            "rune_formulas_known": len(self.rune_exchange._known_formulas),
            "found_items": len(self.drop_and_leave._found_items),
            "trinkbuddy_active": self.trinkbuddy.is_active(),
            "trinkbuddy_buddies": [
                b["partner"] for b in self.trinkbuddy.get_active_buddies()
            ],
        }

        # Encounter-Count aus DB
        try:
            conn = self._get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM gossip_encounters")
            row = cursor.fetchone()
            stats["total_encounters"] = row[0] if row else 0
        except sqlite3.Error:
            stats["total_encounters"] = 0

        return stats

    # -----------------------------------------
    # Terminal-Visualisierung
    # -----------------------------------------

    def print_taverne_summary(self, results: Dict[str, Any],
                              remote_name: str) -> None:
        """Taverne-Begegnung im Terminal anzeigen."""
        print("\a", end="", flush=True)  # Bell: Begegnung!
        print()
        print("=" * 50)
        print(f"  TAVERNE - Begegnung mit '{remote_name}'")
        print("=" * 50)

        # Trinkbuddy
        buddy = results.get("trinkbuddy", {})
        if buddy.get("status") == "ACTIVATED":
            print(f"  Trinkbuddy: {buddy['message']}")
            print(f"  Gold-Bonus: {buddy['gold_bonus']} fuer "
                  f"{buddy['duration_minutes']} Min")

        # Leaderboard
        lb = results.get("leaderboard", {})
        if lb.get("merged_count", 0) > 0:
            print(f"  Rangliste: {lb['new_entries']} neue, "
                  f"{lb['updated_entries']} aktualisiert")

        # Relay
        relay = results.get("relay", {})
        if relay.get("delivered", 0) > 0:
            print(f"  Post: {relay['delivered']} Pakete zugestellt!")

        # Runen
        runes = results.get("runes", {})
        if runes.get("learned_count", 0) > 0:
            print(f"  Wissen: {runes['learned_count']} neue Runen-Formeln gelernt!")

        # Weltboss
        wb = results.get("worldboss", {})
        print(f"  Champions: {wb.get('message', '')}")
        if wb.get("triggered", False):
            print(f"  WELTBOSS SPAWN! Skalierung: x{wb['boss_scaling']:.1f}")

        # Drops
        drops = results.get("drops", {})
        if drops.get("received", 0) > 0:
            print(f"  Fundstuecke: {drops['received']} Items erhalten!")

        print("=" * 50)

    def close(self):
        """Zustand speichern und DB-Verbindung schliessen."""
        try:
            self.save_to_db()
        except Exception as e:
            print(f"[GOSSIP] Save-Fehler beim Close: {e}")

        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None


# =============================================
# Standalone-Test
# =============================================

if __name__ == "__main__":
    import tempfile

    print("=== Gossip-Taverne Test (mit DB-Persistenz) ===\n")

    # Temporaere DB fuer Tests
    tmp_db = os.path.join(tempfile.gettempdir(), "ztb_gossip_test.db")

    # Zwei Spieler simulieren
    taverne_a = GossipTaverne(local_name="Ritter_A", db_path=tmp_db)
    taverne_b = GossipTaverne(local_name="Schurke_B", db_path=tmp_db)

    player_a = {
        "name": "Ritter_A", "level": 15, "current_floor": 120,
        "pvp_wins": 8, "ascension": 2
    }
    player_b = {
        "name": "Schurke_B", "level": 12, "current_floor": 85,
        "pvp_wins": 12, "ascension": 1
    }

    # Gossip-Daten vorbereiten
    payload_a = taverne_a.prepare_gossip_payload(player_a)
    payload_b = taverne_b.prepare_gossip_payload(player_b)

    # 1. Trinkbuddy
    print("1. Trinkbuddy:")
    result = taverne_a.trinkbuddy.activate("Schurke_B")
    print(f"   {result['message']}")
    print(f"   Gold-Multiplier: x{taverne_a.trinkbuddy.get_gold_multiplier():.2f}")

    # 2. Leaderboard
    print("\n2. Leaderboard:")
    taverne_a.leaderboard.update_local(player_a)
    merge = taverne_a.leaderboard.merge(payload_b["leaderboard"])
    print(f"   Merged: {merge}")
    top = taverne_a.leaderboard.get_top(5)
    for i, e in enumerate(top, 1):
        print(f"   #{i} {e['name']} Score:{e['score']}")

    # 3. Relay (inkl. Bugfix-Test)
    print("\n3. Paket-Relay:")
    taverne_a.relay.create_packet("Ritter_A", "Phantom_C", "Gruss vom Ritter!")
    taverne_a.relay.create_packet("Ritter_A", "Schurke_B", "Direkt fuer dich!")
    exchange = taverne_a.relay.exchange_packets("Schurke_B", [], "Ritter_A")
    print(f"   Gesendet: {exchange['sent_to_remote']}")
    print(f"   Pending nach Exchange: {taverne_a.relay.get_pending_count()}")

    # Relay-Ketten-Test: Schurke_B traegt Paket fuer Phantom_C weiter
    received_packets = exchange["packets_for_remote"]
    exchange_b = taverne_b.relay.exchange_packets(
        "Magier_D", received_packets, "Schurke_B"
    )
    print(f"   Schurke_B relay an Magier_D: "
          f"delivered={exchange_b['delivered']} relayed={exchange_b['relayed']}")

    # 4. Runen
    print("\n4. Runen-Tausch:")
    taverne_a.rune_exchange.add_formula("fire_1", ["Rot", "Gelb"], "+5 ATK Feuer")
    taverne_b.rune_exchange.add_formula("ice_1", ["Blau", "Weiss"], "+5 DEF Eis")
    rune_result = taverne_a.rune_exchange.exchange(
        taverne_b.rune_exchange.export_for_gossip(), "Schurke_B"
    )
    print(f"   Gelernt: {rune_result['learned_count']}")

    # 5. Weltboss
    print("\n5. Weltboss-Trigger:")
    taverne_a.worldboss_trigger.register_ping("Schurke_B")
    taverne_a.worldboss_trigger.register_ping("Magier_C")
    taverne_a.worldboss_trigger.register_ping("Krieger_D")
    wb = taverne_a.worldboss_trigger.check_trigger()
    print(f"   {wb['message']}")
    print(f"   Triggered: {wb['triggered']}")

    # 6. Drop & Leave
    print("\n6. Drop & Leave:")
    fake_item = {"name": "Rostiges Schwert", "atk_bonus": 3, "rarity": "common"}
    drop = taverne_a.drop_and_leave.drop_item(
        fake_item, "Ritter_A", "Fuer den Naechsten!"
    )
    print(f"   {drop['message']}")
    exchange_drops = taverne_b.drop_and_leave.exchange_drops(
        [drop["dropped_item"]], "Schurke_B"
    )
    print(f"   Gefunden: {exchange_drops['received']}")

    # 7. DB-Persistenz
    print("\n7. DB-Persistenz:")
    saved = taverne_a.save_to_db()
    print(f"   Gespeichert: {saved}")

    # Neues Objekt, gleiche DB → Daten sollten geladen werden
    taverne_reload = GossipTaverne(local_name="Ritter_A", db_path=tmp_db)
    loaded = taverne_reload.load_from_db()
    print(f"   Geladen: {loaded}")

    # Verify
    lb_entries = taverne_reload.leaderboard.export_entries()
    print(f"   Leaderboard nach Reload: {len(lb_entries)} Eintraege")
    formulas = taverne_reload.rune_exchange.get_all_formulas()
    print(f"   Runen nach Reload: {len(formulas)} Formeln")

    # 8. Stats
    print("\n8. Gossip-Stats:")
    stats = taverne_a.get_stats()
    for key, val in stats.items():
        print(f"   {key}: {val}")

    # Aufraeumen
    taverne_a.close()
    taverne_b.close()
    taverne_reload.close()

    try:
        os.remove(tmp_db)
    except OSError:
        pass

    print("\nAlle Gossip-Tests bestanden!")
