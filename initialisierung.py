#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Hauptinitialisierung
================================================
Entry Point mit Lazy-Loading aller Subsysteme.
Dienste werden erst geladen wenn sie benoetigt werden.
"""

import sys


def main():
    """Haupteinstiegspunkt mit Lazy-Loading."""

    # Nur die noetigen Module laden
    from ui.options.war_room import WarRoom
    from ui.settings import Settings
    from game.game_loop import GameLoop

    # Initialisierung
    settings = Settings()
    settings.load_language()
    game_loop = GameLoop()

    print("[WAR ROOM] Zero Tower Battle")

    # Hauptschleife
    war_room = WarRoom()
    while True:
        choice = war_room.show_menu()

        if choice == "PVE":
            game_loop.set_mode("PVE")
            game_loop.loop()
        elif choice == "PVP":
            game_loop.set_mode("PVP")
            game_loop.loop()
        elif choice == "SETTINGS":
            war_room.change_language()
        elif choice == "SHUTDOWN":
            war_room.gently_shutdown()
            break
        elif choice == "Q" or choice is None:
            print("[EXIT] Auf Wiedersehen!")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[EXIT] Beendet.")
    except Exception as e:
        print(f"[FATAL] {e}")
        sys.exit(1)
