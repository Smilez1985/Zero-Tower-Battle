#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - PVP Battle Service
=============================================
Lazy-Loading Service fuer PVP-Kampfmodus.
Wird nur initialisiert wenn PVP gestartet wird.
"""


class ServicePvp:
    """PVP Battle Service (Lazy-Loading)."""

    def __init__(self):
        self._pvp_game = None
        self._is_running = False

    def _ensure_loaded(self):
        """Lazy-Load der PVP-Abhaengigkeiten."""
        if self._pvp_game is None:
            from game.pvp_game import PVPGame
            self._pvp_game = PVPGame()

    def start(self):
        """Starte PVP-Modus."""
        self._ensure_loaded()
        self._is_running = True
        print("[PVP] Team Battle gestartet!")
        return {"status": "STARTED", "mode": "PVP"}

    def stop(self):
        """Stoppe PVP-Modus."""
        self._is_running = False
        print("[PVP] Team Battle gestoppt!")
        return {"status": "STOPPED", "mode": "PVP"}

    def is_running(self):
        """Pruefe ob PVP aktiv."""
        return self._is_running

    def get_status(self):
        """Status des PVP-Service."""
        return {
            "mode": "PVP",
            "running": self._is_running,
            "loaded": self._pvp_game is not None
        }
