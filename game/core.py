#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Game Engine Core
============================================
Zentrale Engine mit Hot/Cold Storage und Modus-Switching.
Alle Subsysteme werden lazy geladen.
"""


class GameEngine:
    """Zentrale Game Engine mit Lazy-Loading."""

    def __init__(self):
        self._hot_storage = None
        self._cold_storage = None
        self._ble_beacon = None
        self.state = "PAUSED"

    def _get_hot_storage(self):
        """Lazy-Load Hot Storage."""
        if self._hot_storage is None:
            from game.hot_storage import HotStorageManager
            self._hot_storage = HotStorageManager()
        return self._hot_storage

    def _get_cold_storage(self):
        """Lazy-Load Cold Storage."""
        if self._cold_storage is None:
            from game.hot_storage import ColdStorageManager
            self._cold_storage = ColdStorageManager()
        return self._cold_storage

    def _get_ble_beacon(self):
        """Lazy-Load BLE Beacon."""
        if self._ble_beacon is None:
            from game.ble_beacon import BLEBeacon
            self._ble_beacon = BLEBeacon()
        return self._ble_beacon

    def start_pve(self):
        """Start PVE (Autonom)."""
        self.state = "PVE"
        print("[PVE-Start] Autonomer Kampf beginnt...")

    def find_pvp(self) -> bool:
        """Suche PvP-Spieler via BLE Beacon."""
        print("[BLE-SCAN] Suche PvP-Spieler...")
        try:
            beacon = self._get_ble_beacon()
            if beacon.scan():
                self.state = "PVP"
                print("[PVP-FOUND] PvP Spieler gefunden!")
                return True
        except Exception as e:
            print(f"[BLE-ERROR] {e}")
        return False

    def switch_mode(self) -> bool:
        """PVE zu PVP wechseln."""
        if self.state == "PVE":
            self.state = "PVP"
            print("[SWITCH] PVE -> PVP")
            return True
        return False

    def save_state(self):
        """Spielstand speichern (Hot -> Cold)."""
        try:
            hot = self._get_hot_storage()
            cold = self._get_cold_storage()
            data = hot.read()
            if data:
                cold.save_level(data)
                print("[SAVE] Hot -> Cold sync erfolgreich")
        except Exception as e:
            print(f"[SAVE-ERROR] {e}")
