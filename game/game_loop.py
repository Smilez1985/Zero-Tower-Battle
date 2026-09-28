#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Game Loop
====================================
Haupt-Spielschleife mit Lazy-Loading aller Subsysteme.
"""

from typing import Optional


class GameLoop:
    """Haupt-Spielschleife mit Lazy-Loading."""

    def __init__(self):
        self.mode = "PVE"
        self.running = False
        self.floor = 1
        # Lazy-loaded Subsysteme
        self._pve_loop = None
        self._pvp_game = None
        self._levels = None

    def _get_pve_loop(self):
        """Lazy-Load PVE Loop."""
        if self._pve_loop is None:
            from game.pve_game_loop import PVEGameLoop
            self._pve_loop = PVEGameLoop()
        return self._pve_loop

    def _get_pvp_game(self):
        """Lazy-Load PVP Game."""
        if self._pvp_game is None:
            from game.pvp_game import PVPGame
            self._pvp_game = PVPGame()
        return self._pvp_game

    def _get_levels(self):
        """Lazy-Load Levels."""
        if self._levels is None:
            from game.levels.levels_data import Levels
            self._levels = Levels()
        return self._levels

    def loop(self):
        """Main Game Loop."""
        self.running = True
        print(f"[GAME] Loop gestartet (Modus: {self.mode})")

        while self.running:
            try:
                if self.mode == "PVE":
                    pve = self._get_pve_loop()
                    pve.state = "PVE"
                    pve.run()
                elif self.mode == "PVP":
                    pvp = self._get_pvp_game()
                    pvp.start_pvp()
                elif self.mode == "QUIT":
                    self.running = False
                    break
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                print(f"[ERROR] Game Loop: {e}")

        print("[GAME] Loop beendet.")

    def set_mode(self, game_mode: str):
        """Spielmodus setzen (PVE/PVP/QUIT)."""
        self.mode = game_mode
        print(f"[GAME] Modus gewechselt: {game_mode}")

    def get_current_floor(self) -> int:
        """Aktueller Floor."""
        return self.floor

    def stop(self):
        """Loop stoppen."""
        self.running = False

