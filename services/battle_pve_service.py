#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - PVE Battle Service
=============================================
Lazy-Loading Service fuer PVE-Kampfmodus.
Wird nur initialisiert wenn PVE gestartet wird.
"""


class ServicePve:
    """PVE Battle Service (Lazy-Loading)."""

    def __init__(self):
        self._game_loop = None
        self._is_running = False

    def _ensure_loaded(self):
        """Lazy-Load der PVE-Abhaengigkeiten."""
        if self._game_loop is None:
            from game.pve_game_loop import PVEGameLoop
            self._game_loop = PVEGameLoop()

    def start(self):
        """Starte PVE-Modus."""
        self._ensure_loaded()
        self._is_running = True
        print("[PVE] Kampfsimulation gestartet!")
        return {"status": "STARTED", "mode": "PVE"}

    def stop(self):
        """Stoppe PVE-Modus."""
        self._is_running = False
        print("[PVE] Kampfsimulation gestoppt!")
        return {"status": "STOPPED", "mode": "PVE"}

    def is_running(self):
        """Pruefe ob PVE aktiv."""
        return self._is_running

    def get_status(self):
        """Status des PVE-Service."""
        return {
            "mode": "PVE",
            "running": self._is_running,
            "loaded": self._game_loop is not None
        }
