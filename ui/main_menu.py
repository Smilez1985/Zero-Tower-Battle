#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Main Menu
====================================
Delegiert an WarRoom fuer das Hauptmenue.
"""

from ui.options.war_room import WarRoom


class MainMenu:
    """Hauptmenue - Wrapper um WarRoom."""

    def __init__(self):
        self._war_room = None

    def _ensure_loaded(self):
        """Lazy-Load WarRoom."""
        if self._war_room is None:
            self._war_room = WarRoom()

    def show_menu(self):
        """Zeige Hauptmenue."""
        self._ensure_loaded()
        return self._war_room.show_menu()
