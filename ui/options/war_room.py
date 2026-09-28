#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - War Room Interface
==============================================
Bilinguales (DE/EN) SSH Terminal Menu mit Rich-UI.

Management = Gameplay. Tower = Idle.
Alle Texte ueber i18n/translator.py (de.json + en.json).

Rich-Farbcodierung (Spec 10C):
  Magenta: Header/Titel
  Gruen:   Spieler/Positiv
  Rot:     Gegner/Schaden
  Gold:    Waehrung/Loot
  Cyan:    Auswahl/Highlight
  Gelb:    Kritischer Treffer (blinkend)

Dynamische Aufloesung:
  - shutil.get_terminal_size() fuer Zeilen/Spalten
  - SIGWINCH Handler fuer Resize (Termux Rotate, Pinch-to-Zoom)
  - Keine hardcodierten Pixel-Aufloesungen (DPI-agnostisch)
  - Layout basiert auf Text-Zellen (Rows/Cols)

Navigation:
  - Zahlentasten (1-11, 0)
  - Pfeiltasten (optional, wo vorhanden)
  - Touch-freundlich durch grosse Menuepunkte

Menues:
  1. Level-Up         - Bonuspunkte manuell verteilen
  2. Dashboard        - Effektive Stats
  3. Inventar         - Items verwalten, verkaufen, zerlegen
  4. Shop             - Prozedurale Items kaufen
  5. Schmiede         - Items upgraden mit Scrap
  6. Runen            - Craften, fusionieren, einsetzen
  7. Codex            - Monster-Bestiary
  8. Taverne          - Social via BLE
  9. Psyche           - Erschoepfung/Moral
 10. Bestenliste      - P2P Leaderboard
 11. Optionen         - Sprache, Speichern, Shell, Reboot, Shutdown
  0. Zurueck
"""

import os
import sys
import json
import time
import shutil
import signal
import subprocess
from typing import Dict, Any, Optional, List


# =============================================
# Rich Import (Graceful Degradation)
# =============================================

_HAS_RICH = False
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.style import Style
    from rich.rule import Rule
    from rich.columns import Columns
    _HAS_RICH = True
except ImportError:
    pass


# =============================================
# Rich Console (Singleton, 80 Spalten Standard)
# =============================================

if _HAS_RICH:
    _console = Console(width=80, highlight=False)
else:
    _console = None


# =============================================
# Farb-Konstanten (Rich Markup + ANSI Fallback)
# =============================================

# Rich-Markup Farben (Spec 10C)
C_HEADER = "magenta"       # Header/Titel
C_PLAYER = "green"         # Spieler/Positiv
C_ENEMY = "red"            # Gegner/Schaden
C_GOLD = "gold1"           # Waehrung/Loot
C_SELECT = "cyan"          # Auswahl/Highlight
C_CRIT = "yellow blink"    # Kritischer Treffer

# ANSI Fallback Codes
_ANSI = {
    "magenta": "\033[35m",
    "green": "\033[32m",
    "red": "\033[31m",
    "gold": "\033[33m",
    "cyan": "\033[36m",
    "yellow": "\033[33;1m",
    "reset": "\033[0m",
    "bold": "\033[1m",
}


# =============================================
# ASCII-Art Splashscreen
# =============================================

SPLASH_ART = r"""
[magenta]
 _______ _______ ______   _______
|__   __|  _____|  ___ \ |  ___  |
   | |  | |___  | |___) || |   | |
   | |  |  ___| |  _  / | |   | |
   | |  | |___  | | \ \ | |___| |
   |_|  |_____| |_|  \_\|_______|

 _______ _______ _  _  _ _______ _______
|__   __|  ___  | || || ||  _____|  ___  |
   | |  | |   | | || || || |___  | |___| |
   | |  | |   | | || || ||  ___| |  _  _/
   | |  | |___| | \__/ / | |___  | | \ \
   |_|  |_______|______/  |_____| |_|  \_\

 ______   _______ _______ _______ _       _______
|  ___ \ |  ___  |__   __|__   __|| |     |  _____|
| |___) || |   | |  | |     | |  | |     | |___
|  ___ < | |___| |  | |     | |  | |     |  ___|
| |___) ||  ___  |  | |     | |  | |___  | |___
|______/ |_|   |_|  |_|     |_|  |_____| |_____|
[/magenta]"""

SPLASH_ART_SIMPLE = """
 ╔══════════════════════════════════════════════╗
 ║                                              ║
 ║     ███████╗███████╗██████╗  ██████╗         ║
 ║        ███╔╝██╔════╝██╔══██╗██╔═══██╗        ║
 ║       ███╔╝ █████╗  ██████╔╝██║   ██║        ║
 ║      ███╔╝  ██╔══╝  ██╔══██╗██║   ██║        ║
 ║     ███████╗███████╗██║  ██║╚██████╔╝        ║
 ║     ╚══════╝╚══════╝╚═╝  ╚═╝ ╚═════╝         ║
 ║                                              ║
 ║     ████████╗ ██████╗ ██╗    ██╗███████╗██████╗  ║
 ║     ╚══██╔══╝██╔═══██╗██║    ██║██╔════╝██╔══██╗ ║
 ║        ██║   ██║   ██║██║ █╗ ██║█████╗  ██████╔╝ ║
 ║        ██║   ██║   ██║██║███╗██║██╔══╝  ██╔══██╗ ║
 ║        ██║   ╚██████╔╝╚███╔███╔╝███████╗██║  ██║ ║
 ║        ╚═╝    ╚═════╝  ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝ ║
 ║                                              ║
 ║     ██████╗  █████╗ ████████╗████████╗██╗     ███████╗ ║
 ║     ██╔══██╗██╔══██╗╚══██╔══╝╚══██╔══╝██║     ██╔════╝ ║
 ║     ██████╔╝███████║   ██║      ██║   ██║     █████╗  ║
 ║     ██╔══██╗██╔══██║   ██║      ██║   ██║     ██╔══╝  ║
 ║     ██████╔╝██║  ██║   ██║      ██║   ███████╗███████╗ ║
 ║     ╚═════╝ ╚═╝  ╚═╝   ╚═╝      ╚═╝   ╚══════╝╚══════╝ ║
 ║                                              ║
 ╚══════════════════════════════════════════════╝"""

# Kompakter Splashscreen fuer 80x24 Terminals
SPLASH_COMPACT = r"""
  ╔════════════════════════════════════════════════════════════════╗
  ║  ______ _____ ____   ___    _____ ___  _    _ _____ ____      ║
  ║ |__  / | ____|  _ \ / _ \  |_   _/ _ \| |  | | ____|  _ \    ║
  ║   / /  |  _| | |_) | | | |   | || | | | |  | |  _| | |_) |   ║
  ║  / /_  | |___|  _ <| |_| |   | || |_| | |/\| | |___|  _ <    ║
  ║ /____| |_____|_| \_\\___/    |_| \___/ \_/\_/|_____|_| \_\   ║
  ║                                                                ║
  ║  ____    _  _____ _____ _     _____                            ║
  ║ | __ )  / \|_   _|_   _| |   | ____|                          ║
  ║ |  _ \ / _ \ | |   | | | |   |  _|                            ║
  ║ | |_) / ___ \| |   | | | |___| |___                           ║
  ║ |____/_/   \_\_|   |_| |_____|_____|                           ║
  ║                                                                ║
  ║          Serverless P2P Auto-Battler + Idle Tower RPG          ║
  ╚════════════════════════════════════════════════════════════════╝"""


# =============================================
# Safe Import
# =============================================

def _safe_import(module_path: str):
    """Import module by dotted path, return None on failure."""
    try:
        parts = module_path.split(".")
        mod = __import__(module_path)
        for part in parts[1:]:
            mod = getattr(mod, part)
        return mod
    except Exception:
        return None


# =============================================
# War Room
# =============================================

class WarRoom:
    """
    War Room - Das spielbare Interface via SSH.
    Bilingual DE/EN, alle Texte ueber Translator.

    Rich-UI mit Farbcodierung gemaess Spec 10C:
      Magenta = Header, Gruen = Spieler, Rot = Gegner,
      Gold = Waehrung, Cyan = Auswahl, Gelb = Krit

    Dynamische Terminal-Groesse (Rows/Cols basiert, kein Pixel-Hardcoding).
    SIGWINCH Handler fuer Live-Resize (Termux Rotate, Pinch-to-Zoom).
    """

    def __init__(self):
        self._character = None
        self._translator = None
        self._levelup = None
        self._loot_factory = None
        self._forge = None
        self._codex = None
        self._psyche = None
        self._leaderboard = None
        self._trinkbuddy = None
        self._shop_items = []
        self._shop_floor = 0
        self.running = True
        self._needs_redraw = False
        self._show_system_status = False  # Toggle fuer System-Status im Hauptmenu
        self._splash_shown = False  # Splashscreen nur einmal zeigen

        # Rich Console
        self._console = _console

        # Dynamische Terminal-Groesse
        self._update_terminal_size()

        # SIGWINCH Handler: Terminal-Resize (Termux Rotate, Pinch-to-Zoom)
        try:
            signal.signal(signal.SIGWINCH, self._on_terminal_resize)
        except (OSError, AttributeError):
            pass  # Windows oder kein TTY

        # Sprache aus config.json laden
        self._init_language()

    # ------------------------------------------
    # Rich Output Helpers
    # ------------------------------------------

    def _rprint(self, text: str = "", style: str = None, **kwargs):
        """
        Rich-aware print. Nutzt Rich Console wenn verfuegbar,
        sonst normales print() mit ANSI-Fallback.

        Rich-Markup in text wird nur bei _HAS_RICH interpretiert.
        """
        if self._console and _HAS_RICH:
            self._console.print(text, style=style, **kwargs)
        else:
            # ANSI-Fallback: Rich-Markup Tags entfernen
            clean = text
            for tag in ["[magenta]", "[/magenta]", "[green]", "[/green]",
                        "[red]", "[/red]", "[gold1]", "[/gold1]",
                        "[cyan]", "[/cyan]", "[yellow blink]", "[/yellow blink]",
                        "[yellow]", "[/yellow]", "[bold]", "[/bold]",
                        "[dim]", "[/dim]", "[italic]", "[/italic]"]:
                clean = clean.replace(tag, "")
            # Einfacher ANSI-Farbcode fuer style
            prefix = ""
            suffix = ""
            if style:
                if "magenta" in style:
                    prefix = _ANSI["magenta"]
                    suffix = _ANSI["reset"]
                elif "green" in style:
                    prefix = _ANSI["green"]
                    suffix = _ANSI["reset"]
                elif "red" in style:
                    prefix = _ANSI["red"]
                    suffix = _ANSI["reset"]
                elif "gold" in style or "yellow" in style:
                    prefix = _ANSI["gold"]
                    suffix = _ANSI["reset"]
                elif "cyan" in style:
                    prefix = _ANSI["cyan"]
                    suffix = _ANSI["reset"]
            print(f"{prefix}{clean}{suffix}")

    def _rpanel(self, content: str, title: str = "", border_style: str = C_HEADER):
        """Rich Panel oder ASCII-Fallback."""
        if self._console and _HAS_RICH:
            self._console.print(Panel(content, title=title, border_style=border_style))
        else:
            w = self._width
            print("=" * w)
            if title:
                padding = max(0, (w - len(title)) // 2)
                print(f"{_ANSI['magenta']}{' ' * padding}{title}{_ANSI['reset']}")
            print(content)
            print("=" * w)

    def _rrule(self, title: str = "", style: str = C_HEADER):
        """Rich Rule (horizontale Linie mit optionalem Titel)."""
        if self._console and _HAS_RICH:
            if title:
                self._console.print(Rule(title=title, style=style))
            else:
                self._console.print(Rule(style=style))
        else:
            w = self._width
            if title:
                padding = max(0, (w - len(title) - 4) // 2)
                print(f"{_ANSI['magenta']}{'=' * padding} {title} {'=' * padding}{_ANSI['reset']}")
            else:
                print(f"{_ANSI['magenta']}{'=' * w}{_ANSI['reset']}")

    def _rtable(self, table) -> None:
        """Rich Table rendern."""
        if self._console and _HAS_RICH:
            self._console.print(table)
        # Fallback: Table-Objekte werden nur mit Rich angezeigt

    # ------------------------------------------
    # Terminal-Groesse (dynamisch, DPI-agnostisch)
    # ------------------------------------------

    def _update_terminal_size(self):
        """Terminal-Groesse aktualisieren (Cols x Rows)."""
        size = shutil.get_terminal_size(fallback=(80, 24))
        self._cols = size.columns
        self._rows = size.lines
        # Nutzbare Breite (mit etwas Padding)
        self._width = max(40, min(self._cols - 2, 120))
        # Rich Console Breite anpassen
        if self._console and _HAS_RICH:
            self._console.width = self._width

    def _on_terminal_resize(self, signum, frame):
        """SIGWINCH Handler — wird aufgerufen wenn Terminal-Groesse sich aendert."""
        self._update_terminal_size()
        self._needs_redraw = True

    # ------------------------------------------
    # i18n
    # ------------------------------------------

    def _init_language(self):
        """Sprache aus config.json lesen, Translator initialisieren."""
        lang = "de"
        try:
            from core.paths import CONFIG_FILE
            config_paths = [
                os.path.join(os.path.dirname(__file__), "..", "..", "config.json"),
                CONFIG_FILE,
            ]
        except ImportError:
            config_paths = [
                os.path.join(os.path.dirname(__file__), "..", "..", "config.json"),
            ]
        for path in config_paths:
            try:
                with open(path, "r") as f:
                    cfg = json.load(f)
                lang = cfg.get("character", {}).get("language", "de")
                break
            except Exception:
                continue

        try:
            from i18n.translator import Translator
            self._translator = Translator(lang)
        except Exception:
            self._translator = None

    def _t(self, key: str, **kwargs) -> str:
        """Translate key. Fallback: key name."""
        if self._translator:
            return self._translator.get(key, **kwargs)
        return key

    def _is_yes(self, text: str) -> bool:
        """Check if user input is affirmative (works DE + EN)."""
        yes_vals = self._t("wr_yes_values").split(",")
        return text.strip().lower() in yes_vals

    def _set_language(self, lang: str):
        """Sprache wechseln + in config.json persistieren."""
        if self._translator:
            self._translator.set_language(lang)

        # Auch im Character speichern
        if self._character:
            self._character["language"] = lang

        # In config.json schreiben
        try:
            from core.paths import CONFIG_FILE
            config_paths = [
                os.path.join(os.path.dirname(__file__), "..", "..", "config.json"),
                CONFIG_FILE,
            ]
        except ImportError:
            config_paths = [
                os.path.join(os.path.dirname(__file__), "..", "..", "config.json"),
            ]
        for path in config_paths:
            try:
                cfg = {}
                if os.path.exists(path):
                    with open(path, "r") as f:
                        cfg = json.load(f)
                cfg.setdefault("character", {})["language"] = lang
                with open(path, "w") as f:
                    json.dump(cfg, f, indent=2)
                break
            except Exception:
                continue

    # ------------------------------------------
    # Character
    # ------------------------------------------

    def set_character(self, character: Dict[str, Any]):
        """Charakter-Dict vom Orchestrator setzen."""
        self._character = character
        for key, default in [
            ("gold", 500), ("scrap", 0), ("diamonds", 0),
            ("soul_shards", 0), ("inventory_items", []),
            ("runes", []), ("pending_bonus_points", 0),
            ("level", 1), ("xp", 0), ("current_floor", 1),
        ]:
            self._character.setdefault(key, default)

        # Sprache aus Character uebernehmen falls vorhanden
        lang = character.get("language")
        if lang and self._translator:
            self._translator.set_language(lang)

    # ------------------------------------------
    # Splashscreen (ASCII-Art beim Login)
    # ------------------------------------------

    def _show_splash(self):
        """
        ASCII-Art Splashscreen beim ersten Login anzeigen.
        Zeigt 'ZERO TOWER BATTLE' als grosse ASCII-Art.
        """
        if self._splash_shown:
            return
        self._splash_shown = True

        self._clear_screen()

        if self._console and _HAS_RICH:
            # Rich-Version: Farbiger Splash mit Panel
            self._console.print()
            self._console.print(SPLASH_COMPACT, style=C_HEADER)
            self._console.print()
            subtitle = self._t("wr_splash_subtitle") if self._translator else (
                "Ein serverloser P2P Auto-Battler + Idle Tower RPG")
            self._console.print(f"  [cyan]{subtitle}[/cyan]")
            self._console.print()

            # Monster-Sprite als Willkommen (wenn Pillow verfuegbar)
            try:
                from monster_gen import generate_monster_ansi
                sprite = generate_monster_ansi(size_choice=2, seed=42, rarity="legendary",
                                               terminal_width=24)
                if sprite:
                    self._console.print(f"[gold1]{sprite}[/gold1]")
            except Exception:
                pass

            self._console.print()
            enter_text = self._t("wr_splash_press_enter") if self._translator else (
                "Druecke Enter um den War Room zu betreten...")
            self._console.print(f"  [cyan]{enter_text}[/cyan]")
        else:
            # ANSI-Fallback
            print(f"{_ANSI['magenta']}{SPLASH_COMPACT}{_ANSI['reset']}")
            print()
            subtitle = self._t("wr_splash_subtitle") if self._translator else (
                "Ein serverloser P2P Auto-Battler + Idle Tower RPG")
            print(f"  {_ANSI['cyan']}{subtitle}{_ANSI['reset']}")
            print()
            enter_text = self._t("wr_splash_press_enter") if self._translator else (
                "Druecke Enter um den War Room zu betreten...")
            print(f"  {_ANSI['cyan']}{enter_text}{_ANSI['reset']}")

        try:
            input()
        except EOFError:
            pass

    # ------------------------------------------
    # First-Start: Charakter-Erstellung im War Room
    # ------------------------------------------

    def _is_first_start(self) -> bool:
        """Pruefen ob Erststart aussteht (kein Charakter vorhanden)."""
        try:
            config_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                return cfg.get("state", {}).get("first_start_pending", True)
        except Exception:
            pass
        return self._character is None

    def _run_character_creation(self) -> bool:
        """
        Interaktive Charakter-Erstellung im War Room (erste SSH-Session).

        Returns:
            True wenn Charakter erstellt, False bei Abbruch
        """
        w = self._width

        self._clear_screen()
        self._rrule("ZERO TOWER BATTLE")
        welcome = (self._t("wr_first_start_welcome") if self._translator
                   else "Willkommen, Champion!")
        self._rprint(f"  [cyan]{welcome}[/cyan]")
        self._rrule()
        print()

        # Forge lazy laden
        try:
            from forge import CharacterForge
            forge = CharacterForge()
        except ImportError:
            self._rprint(f"  [red][ERROR] CharacterForge nicht gefunden![/red]")
            self._wait()
            return False

        # 1. Name
        name_prompt = (self._t('wr_first_start_name') if self._translator
                       else 'Waehle einen Namen fuer deinen Champion')
        self._rprint(f"  [cyan]{name_prompt}:[/cyan]")
        print()
        name = self._input("  Name (1-20): ")
        if not name or len(name) > 20:
            name = "Champion"

        # 2. Klasse waehlen
        print()
        class_prompt = (self._t('wr_first_start_class') if self._translator
                        else 'Waehle deine Klasse')
        self._rrule(class_prompt)

        classes = forge.get_available_classes()
        class_list = list(classes.keys())

        for i, (cls_name, cls_info) in enumerate(classes.items(), 1):
            base = cls_info["base_stats"]
            lang_key = "description_de" if (not self._translator or
                        self._translator.get_language() == "de") else "description_en"
            desc = cls_info.get(lang_key, cls_info.get("description_de", ""))
            print()
            self._rprint(f"  [cyan][{i}][/cyan] [bold]{cls_name}[/bold] "
                         f"({cls_info['type']}) - {cls_info['focus']}")
            self._rprint(f"      ATK:{base['atk']:>2} DEF:{base['def']:>2} "
                         f"SPD:{base['spd']:>2} LUK:{base['luk']:>2}",
                         style=C_PLAYER)
            self._rprint(f"      [dim]{desc}[/dim]")

        print()
        choice = self._input("  Klasse (1-3): ")
        try:
            class_idx = int(choice) - 1
            if class_idx < 0 or class_idx >= len(class_list):
                class_idx = 0
        except (ValueError, TypeError):
            class_idx = 0
        class_name = class_list[class_idx]

        # 3. Stats: Defaults oder custom
        defaults = forge.get_class_defaults(class_name)
        print()
        stats_q = (self._t('wr_first_start_stats_q') if self._translator
                   else 'Punkte verteilen?')
        self._rprint(f"  {stats_q}:")
        defaults_label = (self._t('wr_first_start_defaults') if self._translator
                          else 'Basiswerte uebernehmen')
        custom_label = (self._t('wr_first_start_custom') if self._translator
                        else 'Punkte selbst verteilen (Summe = 100)')
        self._rprint(f"  [cyan][1][/cyan] {defaults_label}")
        self._rprint(f"  [cyan][2][/cyan] {custom_label}")
        print()

        stat_choice = self._input("  (1-2): ")

        if stat_choice == "2":
            # Custom-Verteilung
            self._rprint(f"\n  [cyan]Verteile 100 Punkte (max 50 pro Attribut):[/cyan]")
            while True:
                try:
                    atk = int(self._input("  ATK (1-50): ") or "0")
                    def_ = int(self._input("  DEF (1-50): ") or "0")
                    spd = int(self._input("  SPD (1-50): ") or "0")
                    luk = int(self._input("  LUK (1-50): ") or "0")
                except (ValueError, TypeError):
                    self._rprint("  [red]Bitte nur Zahlen eingeben.[/red]")
                    continue

                from forge import validate_stat_distribution
                valid, error_msg = validate_stat_distribution(atk, def_, spd, luk)
                if valid:
                    break
                else:
                    self._rprint(f"  [red]Fehler: {error_msg}[/red]")
                    print("  Nochmal...\n")
        else:
            atk = defaults["atk"]
            def_ = defaults["def"]
            spd = defaults["spd"]
            luk = defaults["luk"]

        # 4. Charakter erstellen
        result = forge.create_character(
            name=name, class_name=class_name,
            atk=atk, def_=def_, spd=spd, luk=luk
        )

        if result["result"] != "SUCCESS":
            self._rprint(f"\n  [red][ERROR] {result.get('error', '?')}[/red]")
            self._wait()
            return False

        character = result["character"]

        # 5. Via GameInitializer in DB/Cold/Hot speichern
        try:
            from init_game import GameInitializer
            gi = GameInitializer()
            gi._ensure_directories()
            gi._init_database()
            save_result = gi.complete_first_start(character)

            if save_result["status"] == "SUCCESS":
                self.set_character(character)

                print()
                self._rrule()
                self._rprint(f"  [green]Champion '{character['name']}' geschmiedet![/green]")
                self._rprint(f"  Klasse: {character['klasse']} ({character['type']})",
                             style=C_PLAYER)
                self._rprint(f"  ATK:{character['atk_base']} DEF:{character['def_base']} "
                             f"SPD:{character['spd_base']} LUK:{character['luk_base']}",
                             style=C_PLAYER)
                self._rrule()
                print("\a", end="", flush=True)
                self._wait()
                return True
            else:
                self._rprint(f"\n  [red][ERROR] {save_result.get('message', '?')}[/red]")
                self._wait()
                return False

        except Exception as e:
            self._rprint(f"\n  [red][ERROR] Speichern fehlgeschlagen: {e}[/red]")
            self._wait()
            return False

    # ------------------------------------------
    # SSH-Key Auto-Setup (erste Verbindung)
    # ------------------------------------------

    def _setup_ssh_key(self):
        """
        Automatisches SSH-Key Setup bei erster War Room Verbindung.

        Generiert ein Ed25519-Keypair fuer den ZTB_Service User.
        Fuegt den Public Key zu authorized_keys hinzu.
        Zeigt dem User die Termux-Befehle zum Speichern des Private Keys.

        Wird NUR einmal ausgefuehrt (geprueft via config.json Flag).
        """
        # Pruefen ob bereits erledigt
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "config.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                if cfg.get("state", {}).get("ssh_key_setup_done", False):
                    return  # Bereits erledigt
        except Exception:
            pass

        # SSH-Verzeichnis des Service-Users
        home_dir = os.path.expanduser("~")
        ssh_dir = os.path.join(home_dir, ".ssh")
        key_path = os.path.join(ssh_dir, "id_ztb")
        pub_path = key_path + ".pub"
        auth_keys = os.path.join(ssh_dir, "authorized_keys")

        # Pruefen ob bereits authorized_keys mit Inhalt existiert
        if os.path.exists(auth_keys):
            try:
                with open(auth_keys, "r") as f:
                    content = f.read().strip()
                if content:
                    # Bereits Keys vorhanden -> Flag setzen und ueberspringen
                    self._mark_ssh_key_done(config_path)
                    return
            except Exception:
                pass

        w = self._width
        self._clear_screen()
        self._rrule("SSH-KEY AUTO-SETUP")
        print()

        try:
            # .ssh Verzeichnis erstellen falls noetig
            os.makedirs(ssh_dir, mode=0o700, exist_ok=True)

            # Ed25519 Key generieren (ohne Passwort)
            result = subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-f", key_path,
                 "-N", "", "-C", "ZTB_AutoKey"],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode != 0:
                self._rprint(f"  [red][ERROR] ssh-keygen fehlgeschlagen: "
                             f"{result.stderr}[/red]")
                self._wait()
                return

            # Public Key zu authorized_keys hinzufuegen
            if os.path.exists(pub_path):
                with open(pub_path, "r") as f:
                    pub_key = f.read().strip()

                # authorized_keys schreiben/anhaengen
                with open(auth_keys, "a") as f:
                    f.write(pub_key + "\n")

                # Berechtigungen setzen
                os.chmod(auth_keys, 0o600)
                os.chmod(key_path, 0o600)

                # Private Key anzeigen
                with open(key_path, "r") as f:
                    private_key = f.read()

                # Hostname und IP ermitteln
                hostname = "piwhore"
                ip_addr = "?"
                try:
                    hostname = subprocess.run(
                        ["hostname"], capture_output=True, text=True, timeout=5
                    ).stdout.strip() or hostname
                except Exception:
                    pass
                try:
                    result = subprocess.run(
                        ["hostname", "-I"], capture_output=True, text=True, timeout=5
                    )
                    ips = result.stdout.strip().split()
                    if ips:
                        ip_addr = ips[0]
                except Exception:
                    pass

                user = os.environ.get("USER", "ZTB_Service")

                # Anzeige fuer den User
                if self._translator and self._translator._language == "en":
                    self._rprint("  [green]SSH key generated! Copy this to your phone[/green]")
                    self._rprint("  [green]so you never need a password again.[/green]")
                else:
                    self._rprint("  [green]SSH-Key generiert! Kopiere diesen auf dein Handy,[/green]")
                    self._rprint("  [green]damit du nie wieder ein Passwort brauchst.[/green]")

                print()
                self._rrule("PRIVATE KEY (komplett kopieren!)")
                print()
                print(private_key)
                self._rrule()
                print()

                if self._translator and self._translator._language == "en":
                    self._rprint("  [cyan]Run these commands in Termux on your phone:[/cyan]")
                else:
                    self._rprint("  [cyan]Fuehre diese Befehle in Termux auf deinem Handy aus:[/cyan]")

                print()
                print("  mkdir -p ~/.ssh && chmod 700 ~/.ssh")
                print(f"  nano ~/.ssh/id_ztb")
                print("  # (Key oben einfuegen, CTRL+O speichern, CTRL+X beenden)")
                print(f"  chmod 600 ~/.ssh/id_ztb")
                print()

                if self._translator and self._translator._language == "en":
                    self._rprint("  [cyan]Then connect without password:[/cyan]")
                else:
                    self._rprint("  [cyan]Dann verbinden ohne Passwort:[/cyan]")

                self._rprint(f"  [green]ssh -i ~/.ssh/id_ztb {user}@{ip_addr}[/green]")
                print()

                if self._translator and self._translator._language == "en":
                    self._rprint("  [cyan]Or add to ~/.ssh/config for even easier access:[/cyan]")
                else:
                    self._rprint("  [cyan]Oder in ~/.ssh/config eintragen fuer noch "
                                 "einfacheren Zugang:[/cyan]")

                print()
                print(f"  Host ztb")
                print(f"    HostName {ip_addr}")
                print(f"    User {user}")
                print(f"    IdentityFile ~/.ssh/id_ztb")
                print()
                print("  # Danach nur noch: ssh ztb")
                print()

                self._rrule()

                # Flag setzen
                self._mark_ssh_key_done(config_path)

                self._wait()

        except Exception as e:
            self._rprint(f"  [red][ERROR] SSH-Key Setup: {e}[/red]")
            self._wait()

    def _mark_ssh_key_done(self, config_path: str):
        """Flag in config.json setzen dass SSH-Key Setup erledigt ist."""
        try:
            cfg = {}
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    cfg = json.load(f)
            cfg.setdefault("state", {})["ssh_key_setup_done"] = True
            with open(config_path, "w") as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    # ------------------------------------------
    # Service Loaders (Lazy)
    # ------------------------------------------

    def _get_levelup(self):
        if not self._levelup:
            cls = _safe_import("services.levelup.LevelUp")
            if cls:
                self._levelup = cls()
        return self._levelup

    def _get_loot_factory(self):
        if not self._loot_factory:
            cls = _safe_import("loot_factory.LootFactory")
            if cls:
                self._loot_factory = cls()
        return self._loot_factory

    def _get_forge(self):
        if not self._forge:
            cls = _safe_import("services.forge_upgrade.ForgeUpgrade")
            if cls:
                self._forge = cls()
        return self._forge

    def _get_codex(self):
        if not self._codex:
            cls = _safe_import("codex_manager.CodexManager")
            if cls:
                self._codex = cls()
        return self._codex

    def _get_psyche(self):
        if not self._psyche:
            cls = _safe_import("champion_psyche.ChampionPsyche")
            if cls:
                self._psyche = cls()
        return self._psyche

    def _get_leaderboard(self):
        if not self._leaderboard:
            cls = _safe_import("gossip_taverne.P2PLeaderboard")
            if cls:
                self._leaderboard = cls()
        return self._leaderboard

    def _get_trinkbuddy(self):
        if not self._trinkbuddy:
            cls = _safe_import("gossip_taverne.TrinkbuddyBuff")
            if cls:
                self._trinkbuddy = cls()
        return self._trinkbuddy

    # ------------------------------------------
    # Helpers (dynamische Breite)
    # ------------------------------------------

    def _clear_screen(self):
        """Terminal leeren."""
        if self._console and _HAS_RICH:
            self._console.clear()
        else:
            print("\033[2J\033[H", end="", flush=True)

    def _sep(self, w: int = 0):
        """Separator-Linie in dynamischer Breite (Rich-aware)."""
        self._rrule()

    def _center(self, text: str, w: int = 0):
        """Text zentriert ausgeben (Rich-aware)."""
        if w <= 0:
            w = self._width
        if self._console and _HAS_RICH:
            self._console.print(text, justify="center", style=C_HEADER)
        else:
            padding = max(0, (w - len(text)) // 2)
            print(f"{_ANSI['magenta']}{' ' * padding}{text}{_ANSI['reset']}")

    def _header(self, title: str):
        """Section Header mit Rich Panel oder ASCII-Rahmen."""
        if self._console and _HAS_RICH:
            self._console.print()
            self._console.print(Panel(title, style=C_HEADER, expand=True))
        else:
            w = self._width
            print(f"\n{_ANSI['magenta']}{'=' * w}{_ANSI['reset']}")
            padding = max(0, (w - len(title)) // 2)
            print(f"{_ANSI['magenta']}{' ' * padding}{title}{_ANSI['reset']}")
            print(f"{_ANSI['magenta']}{'=' * w}{_ANSI['reset']}")

    def _input(self, prompt: str = "") -> str:
        """Eingabe lesen — flexibel fuer Zahlen, Pfeiltasten, Touch."""
        if not prompt:
            prompt = f"  {self._t('wr_choice')} [0-11]? "
        try:
            return input(prompt).strip()
        except EOFError:
            return "0"

    def _wait(self):
        """Warte auf Eingabe (Enter oder beliebige Taste)."""
        try:
            input(f"\n  {self._t('wr_enter')}")
        except EOFError:
            pass

    def _equipped(self) -> Dict[str, Optional[Dict]]:
        """Weapon/Armor die gerade getragen werden."""
        w, a = None, None
        for item in self._character.get("inventory_items", []):
            if item.get("equipped"):
                slot = item.get("equip_slot", item.get("type", ""))
                if slot in ("weapon", "Waffe") and not w:
                    w = item
                elif slot in ("armor", "Ruestung") and not a:
                    a = item
        return {"weapon": w, "armor": a}

    def _eff_stats(self) -> Dict[str, int]:
        """Basis + Extra + Equipment = Effektive Stats."""
        c = self._character or {}
        eq = self._equipped()
        ea, ed = 0, 0
        for slot in ("weapon", "armor"):
            if eq[slot]:
                ea += eq[slot].get("atk_mod", 0)
                ed += eq[slot].get("def_mod", 0)
        return {
            "ATK": c.get("atk_base", 0) + c.get("atk_extra", 0) + ea,
            "DEF": c.get("def_base", 0) + c.get("def_extra", 0) + ed,
            "SPD": c.get("spd_base", 0) + c.get("spd_extra", 0),
            "LUK": c.get("luk_base", 0) + c.get("luk_extra", 0),
        }

    def _hp_bar(self, current: int, maximum: int, width: int = 20) -> str:
        """
        HP-Balken mit Farbe (Rich-Markup oder ANSI).
        Integriert visualizer.py hp_bar_rich Logik.
        Gruen >50%, Gelb 25-50%, Rot <25%.
        """
        if maximum <= 0:
            maximum = 1
        current = max(0, min(current, maximum))
        ratio = current / maximum

        filled = int(ratio * width)
        empty = width - filled

        bar_chars = "#" * filled + " " * empty

        if _HAS_RICH:
            if ratio > 0.5:
                color = "green"
            elif ratio > 0.25:
                color = "yellow"
            else:
                color = "red"
            return f"[[{color}]{bar_chars}[/{color}]] {current}/{maximum}"
        else:
            # ANSI Fallback
            if ratio > 0.5:
                color = _ANSI["green"]
            elif ratio > 0.25:
                color = _ANSI["yellow"]
            else:
                color = _ANSI["red"]
            return f"[{color}{bar_chars}{_ANSI['reset']}] {current}/{maximum}"

    def _item_line(self, idx: int, item: Dict, price: bool = False) -> str:
        """Item-Zeile mit dynamischer Breite und Farb-Coding."""
        eq_tag = "[E]" if item.get("equipped") else "   "
        max_name = max(10, self._width - 40)
        nm = item.get("name", "???")[:max_name]
        rar = item.get("rarity", "common")
        rar_short = item.get("rarity_de", rar)[:4]
        a = item.get("atk_mod", 0)
        d = item.get("def_mod", 0)
        up = item.get("upgrade_level", 0)
        r = "R" if item.get("rune_slot") else " "

        # Farbe nach Raritaet
        if _HAS_RICH:
            if rar == "legendary":
                color = "gold1"
            elif rar == "rare":
                color = "cyan"
            else:
                color = "white"
            line = (f" {idx:2d}. {eq_tag} [{color}]{nm:{max_name}s}[/{color}] "
                    f"[{rar_short:4s}] A:{a:>3} D:{d:>3} +{up} {r}")
        else:
            line = (f" {idx:2d}. {eq_tag} {nm:{max_name}s} "
                    f"[{rar_short:4s}] A:{a:>3} D:{d:>3} +{up} {r}")

        if price:
            p = item.get("buy_price", item.get("value", 0))
            if _HAS_RICH:
                line += f"  [gold1]{p}g[/gold1]"
            else:
                line += f"  {p}g"
        return line

    # =============================================
    # PVP BATTLE REPLAY (mit Skip/Abbruch)
    # =============================================

    def show_pvp_results(self, battles: List[Dict[str, Any]]):
        """
        PvP-Kampf-Echos anzeigen mit Skip/Abbruch.

        Bei vielen Kaempfen (>3) wird dem User sofort die Option gegeben,
        alle zu ueberspringen und nur die Zusammenfassung zu sehen.

        Args:
            battles: Liste von Kampf-Ergebnis-Dicts
        """
        if not battles:
            return

        n = len(battles)

        self._header(f"PVP {self._t('wr_pvp_results')} ({n})")

        if n > 3:
            print()
            self._rprint(f"  {n} {self._t('wr_pvp_battles_since_last')}")
            print()
            self._rprint(f"  [cyan][1][/cyan] {self._t('wr_pvp_show_all')}")
            self._rprint(f"  [cyan][2][/cyan] {self._t('wr_pvp_show_summary')}")
            print()
            choice = self._input(f"  {self._t('wr_choice')}? ")
            if choice != "1":
                self._show_pvp_summary(battles)
                return

        # Einzelne Kaempfe anzeigen (mit Skip pro Kampf)
        wins = 0
        losses = 0
        for i, battle in enumerate(battles):
            print()
            self._rrule()
            opponent = battle.get("opponent_name", "???")
            result = battle.get("result", "loss")
            self._rprint(f"  [{i+1}/{n}] vs. [red]{opponent}[/red]")

            if result in ("win", "victory"):
                wins += 1
                self._rprint(f"  >>> [green]{self._t('wr_pvp_win')}[/green] <<<")
                rewards = battle.get("rewards", {})
                if rewards:
                    parts = []
                    if rewards.get("gold", 0):
                        parts.append(f"+{rewards['gold']}g")
                    if rewards.get("xp", 0):
                        parts.append(f"+{rewards['xp']}xp")
                    if parts:
                        self._rprint(f"  [gold1]{' '.join(parts)}[/gold1]")
            else:
                losses += 1
                self._rprint(f"  --- [red]{self._t('wr_pvp_loss')}[/red] ---")

            # Skip-Option bei verbleibenden Kaempfen
            remaining = n - i - 1
            if remaining > 0:
                print()
                self._rprint(f"  [cyan][Enter][/cyan] {self._t('wr_pvp_next')} | "
                             f"[cyan][S][/cyan] {self._t('wr_pvp_skip_rest')} ({remaining})")
                skip = self._input("  ")
                if skip.lower() == "s":
                    for b in battles[i+1:]:
                        if b.get("result") in ("win", "victory"):
                            wins += 1
                        else:
                            losses += 1
                    break

        # Zusammenfassung am Ende
        print()
        self._rrule()
        self._rprint(f"  {self._t('wr_pvp_total')}: "
                     f"[green]{wins}W[/green] / [red]{losses}L[/red]")
        self._rrule()
        self._wait()

    def _show_pvp_summary(self, battles: List[Dict[str, Any]]):
        """Nur PvP-Zusammenfassung ohne einzelne Kampf-Details."""
        wins = sum(1 for b in battles if b.get("result") in ("win", "victory"))
        losses = len(battles) - wins

        total_gold = sum(b.get("rewards", {}).get("gold", 0) for b in battles)
        total_xp = sum(b.get("rewards", {}).get("xp", 0) for b in battles)

        print()
        self._rrule()
        self._rprint(f"  {self._t('wr_pvp_total')}: "
                     f"[green]{wins}W[/green] / [red]{losses}L[/red]")
        if total_gold > 0:
            self._rprint(f"  [gold1]+{total_gold} Gold[/gold1]")
        if total_xp > 0:
            self._rprint(f"  [green]+{total_xp} XP[/green]")
        self._rrule()

        # Top-Gegner
        if battles:
            opponents = {}
            for b in battles:
                bname = b.get("opponent_name", "???")
                if bname not in opponents:
                    opponents[bname] = {"w": 0, "l": 0}
                if b.get("result") in ("win", "victory"):
                    opponents[bname]["w"] += 1
                else:
                    opponents[bname]["l"] += 1

            self._rprint(f"\n  {self._t('wr_pvp_opponents')}:")
            for bname, stats in sorted(opponents.items(),
                                        key=lambda x: x[1]["w"], reverse=True):
                self._rprint(f"    [red]{bname}[/red]: "
                             f"[green]{stats['w']}W[/green] / "
                             f"[red]{stats['l']}L[/red]")

        self._wait()

    # =============================================
    # MAIN MENU
    # =============================================

    def show_menu(self):
        """Hauptmenue anzeigen (Rich-UI mit Farbcodierung)."""
        self._update_terminal_size()

        if not self._character:
            self._rprint(f"  [red][{self._t('wr_error')}] "
                         f"{self._t('wr_no_char')}[/red]")
            return

        c = self._character
        eff = self._eff_stats()
        eq = self._equipped()

        # Header
        self._header(self._t("wr_header"))

        # Charakter-Info
        self._rprint(f"  [green]{c.get('name', 'Champion')}[/green] "
                     f"({c.get('class_name', '?')}) "
                     f"Lv.[bold]{c.get('level', 1)}[/bold]  "
                     f"{self._t('wr_floor')} [cyan]{c.get('current_floor', 1)}[/cyan]")

        # Stats-Zeile mit Farben
        self._rprint(f"  [green]ATK:{eff['ATK']:>3}[/green]  "
                     f"[cyan]DEF:{eff['DEF']:>3}[/cyan]  "
                     f"SPD:{eff['SPD']:>3}  LUK:{eff['LUK']:>3}")

        # Ressourcen mit Gold-Farbe
        self._rprint(f"  [gold1]{self._t('wr_gold')}:{c.get('gold', 0):>6}[/gold1]  "
                     f"{self._t('wr_scrap')}:{c.get('scrap', 0):>4}  "
                     f"[cyan]{self._t('wr_diamonds')}:{c.get('diamonds', 0):>3}[/cyan]")

        # Equipment
        wn = eq["weapon"]["name"] if eq["weapon"] else "---"
        an = eq["armor"]["name"] if eq["armor"] else "---"
        self._rprint(f"  {self._t('wr_weapon')}: [bold]{wn}[/bold]  |  "
                     f"{self._t('wr_armor')}: [bold]{an}[/bold]")

        # System-Status Widget (bei Bedarf einblenden)
        if self._show_system_status:
            self._print_system_status()
        else:
            self._rrule()

        # Menuepunkte mit Cyan-Nummern
        pending = c.get("pending_bonus_points", 0)
        ph = (f" [yellow blink]<<< {pending} {self._t('wr_pending_points')} >>>[/yellow blink]"
              if pending > 0 else "")

        self._rprint(f"  [cyan] 1.[/cyan] {self._t('wr_menu_levelup')}{ph}")
        self._rprint(f"  [cyan] 2.[/cyan] {self._t('wr_menu_dashboard')}")
        n_items = len(c.get("inventory_items", []))
        self._rprint(f"  [cyan] 3.[/cyan] {self._t('wr_menu_inventory')} "
                     f"({n_items} {self._t('wr_inv_items')})")
        self._rprint(f"  [cyan] 4.[/cyan] {self._t('wr_menu_shop')}")
        self._rprint(f"  [cyan] 5.[/cyan] {self._t('wr_menu_forge')}")
        self._rprint(f"  [cyan] 6.[/cyan] {self._t('wr_menu_runes')}")
        self._rprint(f"  [cyan] 7.[/cyan] {self._t('wr_menu_codex')}")
        self._rprint(f"  [cyan] 8.[/cyan] {self._t('wr_menu_taverne')}")
        self._rprint(f"  [cyan] 9.[/cyan] {self._t('wr_menu_psyche')}")
        self._rprint(f"  [cyan]10.[/cyan] {self._t('wr_menu_leaderboard')}")
        self._rprint(f"  [cyan]11.[/cyan] {self._t('wr_menu_options')}")
        self._rprint(f"  [cyan] 0.[/cyan] {self._t('wr_back')}")
        print()

    def parse_menu(self) -> Optional[str]:
        """Menu-Eingabe parsen (Zahlen, Pfeiltasten tolerant)."""
        choice = self._input()
        return {
            "1": "LEVELUP", "2": "DASHBOARD", "3": "INVENTORY",
            "4": "SHOP", "5": "FORGE", "6": "RUNES",
            "7": "CODEX", "8": "TAVERNE", "9": "PSYCHE",
            "10": "LEADERBOARD", "11": "OPTIONS", "0": "BACK",
            "levelup": "LEVELUP", "level": "LEVELUP",
            "dash": "DASHBOARD", "dashboard": "DASHBOARD",
            "inv": "INVENTORY", "inventar": "INVENTORY",
            "shop": "SHOP", "forge": "FORGE", "schmiede": "FORGE",
            "rune": "RUNES", "runen": "RUNES",
            "codex": "CODEX", "taverne": "TAVERNE",
            "psyche": "PSYCHE", "board": "LEADERBOARD",
            "opt": "OPTIONS", "options": "OPTIONS",
            "quit": "BACK", "exit": "BACK", "q": "BACK",
        }.get(choice.lower() if choice else "")

    # =============================================
    # 1. LEVEL-UP
    # =============================================

    def menu_levelup(self):
        self._header(self._t("wr_levelup_title"))
        svc = self._get_levelup()
        c = self._character
        if not svc or not c:
            self._rprint(f"  [red][{self._t('wr_error')}][/red]")
            self._wait()
            return

        pending = c.get("pending_bonus_points", 0)
        self._rprint(f"  {self._t('wr_levelup_champion')}: "
                     f"[green]{c.get('name', '?')}[/green]")
        self._rprint(f"  {self._t('wr_levelup_level')}: "
                     f"[bold]{c.get('level', 1)}[/bold]")
        self._rprint(f"  EXP: [cyan]{c.get('xp', 0)} / {svc.XP_PER_LEVEL}[/cyan]")
        print()

        # Stat-Bars mit Rich Table (wenn verfuegbar)
        if self._console and _HAS_RICH:
            table = Table(title=self._t("wr_levelup_stats_header"),
                          title_style=C_HEADER, show_header=True, header_style="bold")
            table.add_column("Stat", style=C_SELECT, width=5)
            table.add_column("Base", justify="right", width=5)
            table.add_column("Extra", justify="right", width=6)
            table.add_column("Total", justify="right", style="bold", width=6)
            table.add_column("Bar", width=max(10, min(30, self._width - 40)))

            for s in svc.STAT_NAMES:
                b = c.get(f"base_{s.lower()}", 0)
                e = c.get(f"extra_{s.lower()}", 0)
                bar_max = max(10, min(30, self._width - 40))
                filled = min(bar_max, int(e / max(1, svc.MAX_BONUS_PER_STAT) * bar_max))
                empty = bar_max - filled
                bar = f"[green]{'#' * filled}[/green][dim]{'.' * empty}[/dim]"
                table.add_row(s, str(b), str(e), str(b + e), bar)

            self._rtable(table)
        else:
            bar_max = max(10, min(30, self._width - 25))
            print(f"  === {self._t('wr_levelup_stats_header')} ===")
            for s in svc.STAT_NAMES:
                b = c.get(f"base_{s.lower()}", 0)
                e = c.get(f"extra_{s.lower()}", 0)
                filled = min(bar_max, int(e / max(1, svc.MAX_BONUS_PER_STAT) * bar_max))
                empty = bar_max - filled
                bar = "#" * filled + "." * empty
                print(f"  {s:3s}: {b:2d} + {e:2d} = {b+e:3d}  [{bar}]")

        print()
        self._rrule()

        if pending <= 0:
            self._rprint(f"  {self._t('wr_levelup_no_points')}")
            self._rprint(f"  [dim]({self._t('wr_levelup_collected_idle')})[/dim]")
            self._wait()
            return

        self._rprint(f"  [yellow blink]>>> {pending} "
                     f"{self._t('wr_levelup_available')} <<<[/yellow blink]")
        print()
        self._rprint(f"  {self._t('wr_levelup_format_hint', n=pending)}")
        self._rprint(f"  [dim]{self._t('wr_levelup_partial_ok')}[/dim]")
        print()

        ui = self._input(f"  {self._t('wr_levelup_prompt')} ")
        if not ui:
            self._rprint(f"  {self._t('wr_cancelled')}")
            self._wait()
            return

        dist = {}
        try:
            for part in ui.upper().replace(" ", "").split(","):
                if "=" not in part:
                    self._rprint(f"  [red][{self._t('wr_error')}] "
                                 f"{self._t('wr_format_error')}[/red]")
                    self._wait()
                    return
                sn, vs = part.split("=", 1)
                if sn.strip() not in svc.STAT_NAMES:
                    self._rprint(f"  [red][{self._t('wr_error')}] {sn}[/red]")
                    self._wait()
                    return
                dist[sn.strip()] = int(vs.strip())
        except ValueError:
            self._rprint(f"  [red][{self._t('wr_error')}] "
                         f"{self._t('wr_format_error')}[/red]")
            self._wait()
            return

        total = sum(dist.values())
        if total <= 0 or total > pending:
            self._rprint(f"  [red][{self._t('wr_error')}] {total}/{pending}[/red]")
            self._wait()
            return

        ds = ", ".join(f"{k}+{v}" for k, v in dist.items() if v > 0)
        self._rprint(f"\n  {self._t('wr_levelup_distribute')}: "
                     f"[cyan]{ds}[/cyan] ({total}/{pending})")
        confirm = self._input(f"  {self._t('wr_confirm')} ")
        if not self._is_yes(confirm):
            self._rprint(f"  {self._t('wr_cancelled')}")
            self._wait()
            return

        result = svc.apply_pending_points(c, dist)
        if result["result"] == "SUCCESS":
            self._rprint(f"\n  [green]{result['message']}[/green]")
            print()
            self._rrule(self._t('wr_levelup_updated'))
            for s in svc.STAT_NAMES:
                b = c.get(f"base_{s.lower()}", 0)
                e = c.get(f"extra_{s.lower()}", 0)
                m = f" [green]<--[/green]" if s in result.get("applied", {}) else ""
                self._rprint(f"  {s:3s}: {b:2d} + {e:2d} = {b+e:3d}{m}")
            rem = result.get("remaining_pending", 0)
            if rem > 0:
                self._rprint(f"\n  [yellow]{self._t('wr_levelup_remaining', n=rem)}[/yellow]")
        else:
            self._rprint(f"  [red][{self._t('wr_error')}] "
                         f"{result['message']}[/red]")
        self._wait()

    # =============================================
    # 2. DASHBOARD (mit HP-Balken aus visualizer.py)
    # =============================================

    def menu_dashboard(self):
        self._header(self._t("wr_dash_title"))
        c = self._character
        if not c:
            self._wait()
            return

        eff = self._eff_stats()
        eq = self._equipped()

        # Charakter-Info mit Rich
        for k, lbl in [("name", "wr_dash_name"), ("class_name", "wr_dash_class"),
                        ("level", "wr_dash_level"), ("xp", "wr_dash_exp"),
                        ("current_floor", "wr_dash_floor")]:
            val = c.get(k, '?')
            if k == "name":
                self._rprint(f"  {self._t(lbl):12s}: [green]{val}[/green]")
            elif k == "current_floor":
                self._rprint(f"  {self._t(lbl):12s}: [cyan]{val}[/cyan]")
            elif k == "level":
                self._rprint(f"  {self._t(lbl):12s}: [bold]{val}[/bold]")
            else:
                self._rprint(f"  {self._t(lbl):12s}: {val}")

        # HP-Balken (integriert aus visualizer.py)
        level = c.get("level", 1)
        total_def = eff.get("DEF", 0)
        max_hp = 100 + (level - 1) * 17 + total_def * 3 // 2
        current_hp = c.get("current_hp", max_hp)
        print()
        self._rprint(f"  {'HP':12s}: {self._hp_bar(current_hp, max_hp)}")

        # Stats-Tabelle
        print()
        if self._console and _HAS_RICH:
            table = Table(title=self._t("wr_dash_stat_header"),
                          title_style=C_HEADER, show_header=True, header_style="bold")
            table.add_column("Stat", style=C_SELECT, width=5)
            table.add_column("Base", justify="right", width=6)
            table.add_column("Extra", justify="right", width=6)
            table.add_column("Equip", justify="right", width=6)
            table.add_column("= Eff", justify="right", style="bold green", width=7)

            for sn in ["ATK", "DEF", "SPD", "LUK"]:
                b = c.get(f"base_{sn.lower()}", 0)
                e = c.get(f"extra_{sn.lower()}", 0)
                eb = 0
                if sn == "ATK":
                    for sl in ("weapon", "armor"):
                        if eq[sl]:
                            eb += eq[sl].get("atk_mod", 0)
                elif sn == "DEF":
                    for sl in ("weapon", "armor"):
                        if eq[sl]:
                            eb += eq[sl].get("def_mod", 0)
                table.add_row(sn, str(b), str(e), str(eb), str(eff[sn]))
            self._rtable(table)
        else:
            self._rrule(self._t('wr_dash_stat_header'))
            for sn in ["ATK", "DEF", "SPD", "LUK"]:
                b = c.get(f"base_{sn.lower()}", 0)
                e = c.get(f"extra_{sn.lower()}", 0)
                eb = 0
                if sn == "ATK":
                    for sl in ("weapon", "armor"):
                        if eq[sl]:
                            eb += eq[sl].get("atk_mod", 0)
                elif sn == "DEF":
                    for sl in ("weapon", "armor"):
                        if eq[sl]:
                            eb += eq[sl].get("def_mod", 0)
                print(f"  {sn:3s}   {b:>5}  {e:>5}  {eb:>5}  = {eff[sn]:>5}")

        # Equipment
        print()
        self._rrule(self._t('wr_dash_equipment'))
        for sl, lbl in [("weapon", "wr_weapon"), ("armor", "wr_armor")]:
            it = eq[sl]
            if it:
                ri = ""
                if it.get("rune_slot"):
                    ri = f" [cyan][{it['rune_slot'].get('name', 'Rune')}][/cyan]"
                self._rprint(f"  {self._t(lbl):12s}: [bold]{it['name']}[/bold] "
                             f"(A:{it.get('atk_mod', 0)} D:{it.get('def_mod', 0)}){ri}")
            else:
                self._rprint(f"  {self._t(lbl):12s}: [dim]--- ({self._t('wr_none')})[/dim]")

        # Ressourcen
        print()
        self._rrule(self._t('wr_dash_resources'))
        for key, lbl in [("gold", "wr_gold"), ("scrap", "wr_scrap"),
                          ("diamonds", "wr_diamonds"), ("soul_shards", "wr_soul_shards")]:
            val = c.get(key, 0)
            if key == "gold":
                self._rprint(f"  {self._t(lbl):14s}: [gold1]{val:>6}[/gold1]")
            elif key == "diamonds":
                self._rprint(f"  {self._t(lbl):14s}: [cyan]{val:>6}[/cyan]")
            else:
                self._rprint(f"  {self._t(lbl):14s}: {val:>6}")

        p = c.get("pending_bonus_points", 0)
        if p > 0:
            self._rprint(f"\n  [yellow blink]!!! {p} "
                         f"{self._t('wr_dash_pending_hint')} !!![/yellow blink]")
        self._wait()

    # =============================================
    # 3. INVENTAR
    # =============================================

    def menu_inventory(self):
        self._header(self._t("wr_inv_title"))
        c = self._character
        if not c:
            self._wait()
            return

        items = c.get("inventory_items", [])
        self._rprint(f"  [gold1]{self._t('wr_gold')}: {c.get('gold', 0)}[/gold1]  |  "
                     f"{self._t('wr_scrap')}: {c.get('scrap', 0)}  |  "
                     f"{self._t('wr_inv_items')}: {len(items)}")
        self._rrule()

        if not items:
            self._rprint(f"  {self._t('wr_inv_empty')}")
            self._rprint(f"  [dim]({self._t('wr_inv_empty_hint')})[/dim]")
            self._wait()
            return

        for i, it in enumerate(items):
            self._rprint(self._item_line(i, it))
        print()
        self._rprint(f"  [cyan][E][/cyan]quip Nr | [cyan][U][/cyan]nequip Nr | "
                     f"[cyan][V][/cyan] {self._t('wr_inv_sell')} Nr")
        self._rprint(f"  [cyan][Z][/cyan] {self._t('wr_inv_salvage')} Nr | "
                     f"[cyan][0][/cyan] {self._t('wr_opt_back')}")
        print()

        ch = self._input(f"  {self._t('wr_choice')}? ").lower()
        if ch == "0" or not ch:
            return

        parts = ch.split()
        if len(parts) < 2:
            self._wait()
            return

        act, idx_s = parts[0], parts[1]
        try:
            idx = int(idx_s)
        except ValueError:
            self._rprint(f"  [red]{self._t('wr_invalid_index')}[/red]")
            self._wait()
            return

        if idx < 0 or idx >= len(items):
            self._rprint(f"  [red]{self._t('wr_invalid_index')}[/red]")
            self._wait()
            return

        item = items[idx]

        if act == "e":
            if item.get("equipped"):
                self._rprint(f"  '{item['name']}' {self._t('wr_inv_already_equipped')}")
            else:
                slot = item.get("equip_slot", item.get("type", ""))
                for o in items:
                    if (o.get("equipped") and
                            o.get("equip_slot", o.get("type", "")) == slot):
                        o["equipped"] = False
                item["equipped"] = True
                self._rprint(f"  [green]'{item['name']}' "
                             f"{self._t('wr_inv_equip')}![/green]")

        elif act == "u":
            if not item.get("equipped"):
                self._rprint(f"  '{item['name']}' {self._t('wr_inv_not_equipped')}")
            else:
                item["equipped"] = False
                self._rprint(f"  [green]'{item['name']}' "
                             f"{self._t('wr_inv_unequip')}![/green]")

        elif act == "v":
            if item.get("equipped"):
                self._rprint(f"  [red]{self._t('wr_inv_equipped_no_sell')}[/red]")
                self._wait()
                return
            sp = item.get("sell_price", item.get("value", 5))
            self._rprint(f"  '{item['name']}' "
                         f"{self._t('wr_inv_sell_confirm', n=sp)}")
            if self._is_yes(self._input(f"  {self._t('wr_confirm')} ")):
                c["gold"] = c.get("gold", 0) + sp
                items.pop(idx)
                self._rprint(f"  [gold1]{self._t('wr_inv_sold', n=sp, total=c['gold'])}[/gold1]")
            else:
                self._rprint(f"  {self._t('wr_cancelled')}")

        elif act == "z":
            if item.get("equipped"):
                self._rprint(f"  [red]{self._t('wr_inv_equipped_no_sell')}[/red]")
                self._wait()
                return
            lf = self._get_loot_factory()
            if lf:
                sv = lf.calculate_salvage_value(item)
                scr, gld = sv.get("scrap", 1), sv.get("gold", 1)
            else:
                r = item.get("rarity", "common")
                scr = {"rare": 3, "legendary": 10}.get(r, 1)
                gld = max(1, item.get("sell_price", 5) // 2)

            self._rprint(f"  '{item['name']}' {self._t('wr_inv_salvage_confirm')}")
            self._rprint(f"  {self._t('wr_inv_salvage_yield', scrap=scr, gold=gld)}")
            if self._is_yes(self._input(f"  {self._t('wr_confirm')} ")):
                c["scrap"] = c.get("scrap", 0) + scr
                c["gold"] = c.get("gold", 0) + gld
                items.pop(idx)
                self._rprint(f"  [gold1]{self._t('wr_inv_salvaged', scrap=scr, gold=gld)}[/gold1]")
            else:
                self._rprint(f"  {self._t('wr_cancelled')}")

        self._wait()

    # =============================================
    # 4. SHOP
    # =============================================

    def menu_shop(self):
        self._header(self._t("wr_shop_title"))
        c = self._character
        lf = self._get_loot_factory()
        if not c or not lf:
            self._wait()
            return

        floor = c.get("current_floor", 1)
        gold = c.get("gold", 0)

        if not self._shop_items or self._shop_floor != floor:
            self._shop_items = lf.generate_shop_inventory(
                player_level=c.get("level", 1),
                player_floor=floor,
                biome=c.get("current_biome", "Neutral"))
            self._shop_floor = floor

        self._rprint(f"  [gold1]{self._t('wr_shop_your_gold')}: {gold}[/gold1]")
        print()
        self._rrule(self._t('wr_shop_offer'))
        for i, it in enumerate(self._shop_items):
            self._rprint(self._item_line(i, it, price=True))
        print()
        self._rprint(f"  [cyan][K][/cyan] {self._t('wr_shop_buy')} Nr  |  "
                     f"[cyan][R][/cyan] {self._t('wr_shop_refresh')}  |  "
                     f"[cyan][0][/cyan] {self._t('wr_opt_back')}")
        print()

        ch = self._input(f"  {self._t('wr_choice')}? ").lower()
        if ch == "0" or not ch:
            return
        if ch == "r":
            self._shop_items = lf.generate_shop_inventory(
                player_level=c.get("level", 1), player_floor=floor,
                biome=c.get("current_biome", "Neutral"))
            self._rprint(f"  [green]{self._t('wr_shop_refreshed')}[/green]")
            self._wait()
            return

        parts = ch.split()
        if len(parts) < 2 or parts[0] != "k":
            self._wait()
            return
        try:
            idx = int(parts[1])
        except ValueError:
            self._wait()
            return
        if idx < 0 or idx >= len(self._shop_items):
            self._wait()
            return

        item = self._shop_items[idx]
        price = item.get("buy_price", item.get("value", 0))

        if gold < price:
            self._rprint(f"  [red]{self._t('wr_shop_not_enough', need=price, have=gold)}[/red]")
            self._wait()
            return

        self._rprint(f"\n  '{item['name']}' "
                     f"{self._t('wr_shop_buy_confirm', n=price)}")
        if not self._is_yes(self._input(f"  {self._t('wr_confirm')} ")):
            self._rprint(f"  {self._t('wr_cancelled')}")
            self._wait()
            return

        c["gold"] = gold - price
        bought = dict(item)
        bought["equipped"] = False
        c.setdefault("inventory_items", []).append(bought)
        self._shop_items.pop(idx)
        self._rprint(f"  [green]'{bought['name']}' "
                     f"{self._t('wr_shop_bought')}[/green]")
        self._rprint(f"  [gold1]-{price} {self._t('wr_gold')} "
                     f"({self._t('wr_gold')}: {c['gold']})[/gold1]")
        self._rprint(f"  [dim]{self._t('wr_shop_to_inventory')}[/dim]")
        self._wait()

    # =============================================
    # 5. SCHMIEDE
    # =============================================

    def menu_forge(self):
        self._header(self._t("wr_forge_title"))
        c = self._character
        forge = self._get_forge()
        if not c or not forge:
            self._wait()
            return

        scrap = c.get("scrap", 0)
        plvl = c.get("level", 1)
        self._rprint(f"  {self._t('wr_forge_your_scrap')}: [cyan]{scrap}[/cyan]")
        self._rprint(f"  [dim]({self._t('wr_forge_scrap_hint')})[/dim]")
        print()

        eq = self._equipped()
        has_items = False
        for slot, lbl in [("weapon", "wr_weapon"), ("armor", "wr_armor")]:
            it = eq[slot]
            if it:
                has_items = True
                pv = forge.get_upgrade_preview(it, plvl)
                cl = it.get("upgrade_level", 0)
                ml = it.get("upgrade_cap", 5)
                self._rprint(f"  [{self._t(lbl)}] [bold]{it['name']}[/bold]")
                self._rprint(f"     A:{it.get('atk_mod', 0):>3}  D:{it.get('def_mod', 0):>3}"
                             f"  {self._t('wr_forge_upgrade')}: [cyan]{cl}/{ml}[/cyan]")
                if pv.get("can_upgrade"):
                    self._rprint(f"     -> {self._t('wr_forge_next_cost')}: "
                                 f"[gold1]{pv['cost_scrap']} {self._t('wr_scrap')}[/gold1], "
                                 f"[green]+{forge.UPGRADE_STAT_BONUS}[/green]")
                else:
                    self._rprint(f"     -> [dim]{pv.get('message', self._t('wr_forge_max'))}[/dim]")
                print()

        if not has_items:
            self._rprint(f"  [red]{self._t('wr_forge_no_equipped')}[/red]")
            self._wait()
            return

        self._rprint(f"  [cyan][1][/cyan] {self._t('wr_forge_weapon_atk')}")
        self._rprint(f"  [cyan][2][/cyan] {self._t('wr_forge_weapon_def')}")
        self._rprint(f"  [cyan][3][/cyan] {self._t('wr_forge_armor_def')}")
        self._rprint(f"  [cyan][4][/cyan] {self._t('wr_forge_armor_atk')}")
        self._rprint(f"  [cyan][0][/cyan] {self._t('wr_opt_back')}")
        print()

        ch = self._input(f"  {self._t('wr_choice')}? ")
        cm = {"1": ("weapon", "atk"), "2": ("weapon", "def"),
              "3": ("armor", "def"), "4": ("armor", "atk")}
        if ch not in cm:
            return

        sk, mode = cm[ch]
        it = eq.get(sk)
        if not it:
            self._rprint(f"  [red]{self._t('wr_forge_no_equipped')}[/red]")
            self._wait()
            return

        res = forge.upgrade_weapon(it.get("name", "?"), it, scrap, plvl, mode)

        if res["result"] == "SUCCESS":
            c["scrap"] = scrap - res.get("cost_used", 0)
            self._rprint(f"\n  [green]{self._t('wr_forge_success')}[/green]")
            self._rprint(f"  [green]{res['message']}[/green]")
            self._rprint(f"  {self._t('wr_forge_new_name')}: [bold]{it['name']}[/bold]")
            self._rprint(f"  [gold1]-{res.get('cost_used', 0)} {self._t('wr_scrap')} "
                         f"({self._t('wr_scrap')}: {c['scrap']})[/gold1]")
            print("\a", end="", flush=True)
        elif res["result"] == "INSUFFICIENT_SCRAP":
            self._rprint(f"\n  [red]{self._t('wr_forge_no_scrap')}[/red]")
            self._rprint(f"  [red]{self._t('wr_forge_need_scrap', need=res.get('required', '?'), have=scrap)}[/red]")
            self._rprint(f"  [dim]{self._t('wr_forge_scrap_tip')}[/dim]")
        elif res["result"] == "COOLDOWN":
            self._rprint(f"\n  [yellow]{self._t('wr_forge_cooldown')}[/yellow]")
            self._rprint(f"  [yellow]{self._t('wr_forge_cooldown_wait', n=res.get('remaining_minutes', '?'))}[/yellow]")
        elif res["result"] == "MAX_LEVEL":
            self._rprint(f"\n  [cyan]{self._t('wr_forge_max')}[/cyan]")
        else:
            self._rprint(f"\n  [red][{self._t('wr_error')}] "
                         f"{res.get('message', '?')}[/red]")
        self._wait()

    # =============================================
    # 6. RUNEN
    # =============================================

    def menu_runes(self):
        self._header(self._t("wr_rune_title"))
        c = self._character
        lf = self._get_loot_factory()
        if not c:
            self._wait()
            return

        gold = c.get("gold", 0)
        runes = c.get("runes", [])
        rune_types = {
            "Feuer": {"bonus_atk": 5, "bonus_def": 0, "cost": 150,
                      "desc": "+5 ATK"},
            "Gift": {"bonus_atk": 3, "bonus_def": 2, "cost": 120,
                     "desc": "+3 ATK, +2 DEF"},
            "Blitz": {"bonus_atk": 4, "bonus_def": 1, "cost": 180,
                      "desc": "+4 ATK, +1 DEF"},
        }

        self._rprint(f"  [gold1]{self._t('wr_gold')}: {gold}[/gold1]  |  "
                     f"{self._t('wr_menu_runes')}: {len(runes)}")
        print()

        # Runen-Typen Tabelle
        if self._console and _HAS_RICH:
            table = Table(title=self._t("wr_rune_types"),
                          title_style=C_HEADER, show_header=True, header_style="bold")
            table.add_column("Typ", style=C_SELECT, width=8)
            table.add_column("Bonus", width=20)
            table.add_column("Kosten", style=C_GOLD, justify="right", width=8)
            for rt, info in rune_types.items():
                table.add_row(rt, info["desc"], f"{info['cost']}g")
            self._rtable(table)
        else:
            print(f"  === {self._t('wr_rune_types')} ===")
            for rt, info in rune_types.items():
                print(f"  - {rt:6s}: {info['desc']:20s}  "
                      f"{self._t('wr_rune_cost')}: {info['cost']}g")
        print()

        if runes:
            self._rrule(self._t('wr_rune_your_runes'))
            for i, r in enumerate(runes):
                att = r.get("attached_to", "---") or "---"
                self._rprint(f"  {i}. [bold]{r.get('name', '?'):20s}[/bold] "
                             f"[green]A:+{r.get('bonus_atk', 0)} "
                             f"D:+{r.get('bonus_def', 0)}[/green]  "
                             f"-> {att}")
            print()

        self._rprint(f"  [cyan][C][/cyan] {self._t('wr_rune_craft')} <Typ>  |  "
                     f"[cyan][E][/cyan] {self._t('wr_rune_attach')} <Nr>")
        self._rprint(f"  [cyan][R][/cyan] {self._t('wr_rune_remove')} <Nr>  |  "
                     f"[cyan][F][/cyan] {self._t('wr_rune_fuse')}")
        self._rprint(f"  [cyan][0][/cyan] {self._t('wr_opt_back')}")
        print()

        ch = self._input(f"  {self._t('wr_choice')}? ").strip()
        if not ch or ch == "0":
            return

        parts = ch.split(maxsplit=1)
        act = parts[0].lower()

        # CRAFT
        if act == "c":
            if len(parts) < 2:
                self._wait()
                return
            rt = parts[1].strip().capitalize()
            if rt not in rune_types:
                self._wait()
                return
            cost = rune_types[rt]["cost"]
            if gold < cost:
                self._rprint(f"  [red]{self._t('wr_rune_no_gold')}[/red]")
                self._wait()
                return
            rune = {"name": f"{rt}-Rune", "type": rt,
                    "bonus_atk": rune_types[rt]["bonus_atk"],
                    "bonus_def": rune_types[rt]["bonus_def"],
                    "attached_to": None}
            c["gold"] = gold - cost
            runes.append(rune)
            c["runes"] = runes
            self._rprint(f"\n  [green]{rt}-Rune {self._t('wr_rune_crafted')}[/green]")
            self._rprint(f"  [gold1]-{cost} {self._t('wr_gold')}[/gold1]")

        # ATTACH
        elif act == "e":
            if len(parts) < 2:
                self._wait()
                return
            try:
                ri = int(parts[1])
            except ValueError:
                self._wait()
                return
            if ri < 0 or ri >= len(runes):
                self._wait()
                return
            rune = runes[ri]
            if rune.get("attached_to"):
                self._rprint(f"  [red]{self._t('wr_rune_already_attached')}[/red]")
                self._wait()
                return
            eq = self._equipped()
            opts = [(s, eq[s]) for s in ("weapon", "armor") if eq[s]]
            if not opts:
                self._rprint(f"  [red]{self._t('wr_forge_no_equipped')}[/red]")
                self._wait()
                return
            self._rprint(f"\n  '{rune['name']}' {self._t('wr_rune_attach_to')}")
            for i, (_, it) in enumerate(opts):
                has = (self._t("wr_rune_slot_used")
                       if it.get("rune_slot") else self._t("wr_rune_slot_free"))
                self._rprint(f"  [cyan]{i+1}.[/cyan] {it['name']} ({has})")
            try:
                si = int(self._input(f"  {self._t('wr_choice')}? ")) - 1
            except ValueError:
                self._wait()
                return
            if si < 0 or si >= len(opts):
                self._wait()
                return
            _, target = opts[si]
            if target.get("rune_slot") is not None:
                self._rprint(f"  [red]{self._t('wr_rune_item_has_rune')}[/red]")
                self._wait()
                return
            if lf:
                lf.attach_rune(target, {"name": rune["name"],
                    "bonus_atk": rune.get("bonus_atk", 0),
                    "bonus_def": rune.get("bonus_def", 0)})
            else:
                target["rune_slot"] = {"name": rune["name"],
                    "bonus_atk": rune.get("bonus_atk", 0),
                    "bonus_def": rune.get("bonus_def", 0)}
                target["atk_mod"] = target.get("atk_mod", 0) + rune.get("bonus_atk", 0)
                target["def_mod"] = target.get("def_mod", 0) + rune.get("bonus_def", 0)
            rune["attached_to"] = target["name"]
            self._rprint(f"\n  [green]'{rune['name']}' "
                         f"{self._t('wr_rune_attached')} '{target['name']}'![/green]")

        # REMOVE
        elif act == "r":
            if len(parts) < 2:
                self._wait()
                return
            try:
                ri = int(parts[1])
            except ValueError:
                self._wait()
                return
            if ri < 0 or ri >= len(runes):
                self._wait()
                return
            rune = runes[ri]
            aname = rune.get("attached_to")
            if not aname:
                self._rprint(f"  [red]{self._t('wr_rune_not_attached')}[/red]")
                self._wait()
                return
            for it in c.get("inventory_items", []):
                if it.get("name") == aname and it.get("rune_slot"):
                    if lf:
                        lf.remove_rune(it)
                    else:
                        sl = it.get("rune_slot", {})
                        it["atk_mod"] = max(0, it.get("atk_mod", 0) - sl.get("bonus_atk", 0))
                        it["def_mod"] = max(0, it.get("def_mod", 0) - sl.get("bonus_def", 0))
                        it["rune_slot"] = None
                    break
            rune["attached_to"] = None
            self._rprint(f"  [green]'{rune['name']}' "
                         f"{self._t('wr_rune_removed')} '{aname}'.[/green]")

        # FUSE
        elif act == "f":
            free = [(i, r) for i, r in enumerate(runes) if not r.get("attached_to")]
            if len(free) < 2:
                self._rprint(f"  [red]{self._t('wr_rune_need_2')}[/red]")
                self._wait()
                return
            self._rprint(f"\n  {self._t('wr_rune_free_runes')}:")
            for oi, r in free:
                self._rprint(f"  [cyan]{oi}.[/cyan] {r['name']} "
                             f"[green]A:+{r.get('bonus_atk', 0)} "
                             f"D:+{r.get('bonus_def', 0)}[/green]")
            self._rprint(f"\n  {self._t('wr_rune_fuse_prompt')}")
            fi = self._input("  ")
            try:
                idxs = [int(x.strip()) for x in fi.split(",")]
            except ValueError:
                self._wait()
                return
            if len(idxs) < 2 or len(idxs) > 3:
                self._wait()
                return
            flist = []
            for ix in idxs:
                if ix < 0 or ix >= len(runes) or runes[ix].get("attached_to"):
                    self._wait()
                    return
                flist.append((ix, runes[ix]))
            ta = int(sum(r.get("bonus_atk", 0) for _, r in flist) * 1.25)
            td = int(sum(r.get("bonus_def", 0) for _, r in flist) * 1.25)
            types = [r.get("type", "Feuer") for _, r in flist]
            dt = max(set(types), key=types.count)
            self._rprint(f"\n  {self._t('wr_rune_fuse_result', n=len(flist))}")
            self._rprint(f"  [green]A:+{ta}  D:+{td}[/green]  ({dt})")
            if not self._is_yes(self._input(f"  {self._t('wr_rune_fuse_confirm')} ")):
                self._wait()
                return
            for ix, _ in sorted(flist, key=lambda x: x[0], reverse=True):
                runes.pop(ix)
            nr = {"name": f"{dt}-Fusionsrune", "type": dt,
                  "bonus_atk": ta, "bonus_def": td, "attached_to": None}
            runes.append(nr)
            c["runes"] = runes
            self._rprint(f"\n  [gold1]'{nr['name']}' "
                         f"{self._t('wr_rune_fused')}[/gold1]")
            print("\a", end="", flush=True)

        self._wait()

    # =============================================
    # 7-10. INFO MENUS
    # =============================================

    def menu_codex(self):
        self._header(self._t("wr_codex_title"))
        c = self._character
        codex = self._get_codex()
        if not c or not codex:
            self._rprint(f"  {self._t('wr_codex_info')}")
            self._rprint(f"  [dim]({self._t('wr_codex_idle_hint')})[/dim]")
            self._wait()
            return

        pid = c.get("player_id", 1)
        progress = codex.get_progress(pid)
        entries = codex.get_all_entries(pid)

        self._rprint(f"  {self._t('wr_codex_progress')}: "
                     f"[cyan]{progress['discovered']}/{progress['total']} "
                     f"({progress['percentage']}%)[/cyan]")
        self._rprint(f"  {self._t('wr_codex_shiny')}: "
                     f"[gold1]{progress['shiny_seen']}[/gold1]")
        self._rprint(f"  {self._t('wr_codex_total_wins')}: "
                     f"[green]{progress['total_defeats']}[/green]")
        self._rprint(f"  {self._t('wr_codex_total_loss')}: "
                     f"[red]{progress['total_losses']}[/red]")
        self._rrule()

        if not entries:
            self._rprint(f"\n  {self._t('wr_codex_empty')}")
            self._rprint(f"  [dim]({self._t('wr_codex_idle_hint')})[/dim]")

            # Monster-Sprite Demo anzeigen
            try:
                from monster_gen import generate_monster_ansi
                sprite = generate_monster_ansi(size_choice=1, seed=1234, rarity="rare",
                                               terminal_width=16)
                if sprite:
                    print()
                    self._rprint(f"  [cyan]{self._t('wr_codex_sprite')}:[/cyan]")
                    print(sprite)
            except Exception:
                pass

            self._wait()
            return

        # Codex-Tabelle
        if self._console and _HAS_RICH:
            table = Table(show_header=True, header_style="bold magenta")
            name_w = max(12, min(22, self._width - 30))
            table.add_column("Name", width=name_w)
            table.add_column("W", justify="right", style=C_PLAYER, width=4)
            table.add_column("L", justify="right", style=C_ENEMY, width=4)
            table.add_column("Floor", justify="right", style=C_SELECT, width=5)
            table.add_column("Shiny", justify="center", style=C_GOLD, width=5)

            for e in entries[:20]:
                nm = e.get("enemy_name", "?")[:name_w]
                w = str(e.get("times_defeated", 0))
                l = str(e.get("times_lost", 0))
                bf = str(e.get("best_floor", 0))
                sh = "*" if e.get("is_shiny_seen") else " "
                table.add_row(nm, w, l, bf, sh)
            self._rtable(table)
        else:
            name_w = max(12, min(22, self._width - 30))
            print(f"  {'Name':{name_w}s} {'W':>4} {'L':>4} {'Floor':>5} {'Shiny':>5}")
            self._rrule()
            for e in entries[:20]:
                nm = e.get("enemy_name", "?")[:name_w]
                w = e.get("times_defeated", 0)
                l = e.get("times_lost", 0)
                bf = e.get("best_floor", 0)
                sh = "*" if e.get("is_shiny_seen") else " "
                print(f"  {nm:{name_w}s} {w:>4} {l:>4} {bf:>5} {sh:>5}")

        if len(entries) > 20:
            self._rprint(f"\n  [dim]... +{len(entries) - 20} "
                         f"{self._t('wr_codex_more')}[/dim]")

        # Monster-Sprite fuer ersten Eintrag anzeigen (wenn Pillow da)
        if entries:
            try:
                from monster_gen import generate_monster_ansi
                first_entry = entries[0]
                seed = hash(first_entry.get("enemy_name", "?")) % 999999
                rarity = "legendary" if first_entry.get("is_shiny_seen") else "common"
                sprite = generate_monster_ansi(size_choice=1, seed=seed,
                                               rarity=rarity, terminal_width=16)
                if sprite:
                    print()
                    self._rprint(f"  [cyan]{first_entry.get('enemy_name', '?')}:[/cyan]")
                    print(sprite)
            except Exception:
                pass

        self._wait()

    def menu_taverne(self):
        self._header(self._t("wr_taverne_title"))
        self._rprint(f"  {self._t('wr_taverne_welcome')}")
        print()

        # Trinkbuddy Status
        tb = self._get_trinkbuddy()
        if tb and tb.is_active():
            buddies = tb.get_active_buddies()
            mult = tb.get_gold_multiplier()
            self._rprint(f"  [green]{self._t('wr_taverne_buff_active')}[/green] "
                         f"[gold1](Gold x{mult:.1f})[/gold1]")
            for b in buddies:
                self._rprint(f"    -> [cyan]{b['partner']}[/cyan] "
                             f"({b['remaining_minutes']}m)")
        else:
            self._rprint(f"  [dim]{self._t('wr_taverne_no_buff')}[/dim]")
        print()
        self._rrule()

        # Features
        self._rprint(f"  {self._t('wr_taverne_hint')}")
        print()
        features = [
            ("wr_taverne_f1", self._t("wr_taverne_f1_desc")),
            ("wr_taverne_f2", self._t("wr_taverne_f2_desc")),
            ("wr_taverne_f3", self._t("wr_taverne_f3_desc")),
            ("wr_taverne_f4", self._t("wr_taverne_f4_desc")),
            ("wr_taverne_f5", self._t("wr_taverne_f5_desc")),
            ("wr_taverne_f6", self._t("wr_taverne_f6_desc")),
        ]
        for i, (key, desc) in enumerate(features, 1):
            self._rprint(f"  [cyan]{i}.[/cyan] [bold]{self._t(key)}[/bold]")
            self._rprint(f"     [dim]{desc}[/dim]")
        print()

        # BLE Status
        c = self._character or {}
        ble = c.get("ble_last_scan", "---")
        nearby = c.get("ble_nearby_count", 0)
        self._rprint(f"  BLE: {self._t('wr_taverne_last_scan')}: {ble}")
        self._rprint(f"  BLE: {self._t('wr_taverne_nearby')}: "
                     f"[cyan]{nearby}[/cyan]")
        self._rprint(f"\n  [dim]({self._t('wr_taverne_auto_hint')})[/dim]")
        self._wait()

    def menu_psyche(self):
        self._header(self._t("wr_psyche_title"))
        c = self._character or {}
        psyche = self._get_psyche()

        # Falls Service verfuegbar: echte Daten
        if psyche:
            status = psyche.get_full_status(c)
            ex = status["exhaustion"]
            mo = status["morale"]
            mood = status.get("mood_de", "?")
            crit = status.get("crit_modifier", 0.0)
            tower_ok = status.get("tower_allowed", True)
            pause_rem = status.get("tower_pause_remaining", 0)
            traumas = status.get("traumas", [])
            debuffs = status.get("debuffs", {})
        else:
            ex = c.get("exhaustion", 0)
            mo = c.get("morale", 50)
            mood = "?"
            crit = 0.0
            tower_ok = True
            pause_rem = 0
            traumas = c.get("trauma", [])
            debuffs = {}

        # Stimmung
        self._rprint(f"  {self._t('wr_psyche_mood')}: [bold]{mood}[/bold]")
        print()

        # Erschoepfung mit farbigem Balken
        bar_w = max(10, min(30, self._width - 20))
        self._rrule(self._t('wr_psyche_exhaustion'))
        self._rprint(f"  {self._hp_bar(int(ex), 100, bar_w)}")

        if ex < 50:
            self._rprint(f"  [green]{self._t('wr_psyche_no_penalty')}[/green]")
        elif ex < 75:
            self._rprint(f"  [yellow]{self._t('wr_psyche_loot_10')}[/yellow]")
        elif ex < 90:
            self._rprint(f"  [red]{self._t('wr_psyche_loot_exp')}[/red]")
        elif ex < 100:
            self._rprint(f"  [red]{self._t('wr_psyche_all_debuff')}[/red]")
        else:
            self._rprint(f"  [red]{self._t('wr_psyche_paused')}[/red]")

        if not tower_ok and pause_rem > 0:
            pm = int(pause_rem // 60)
            self._rprint(f"  [red]>>> {self._t('wr_psyche_pause_timer', m=pm)} <<<[/red]")

        # Debuffs
        if debuffs.get("has_debuff"):
            self._rprint(f"\n  {self._t('wr_psyche_debuffs')}:")
            if debuffs.get("loot_multiplier", 1.0) < 1.0:
                self._rprint(f"    [red]Loot: x{debuffs['loot_multiplier']:.2f}[/red]")
            if debuffs.get("xp_multiplier", 1.0) < 1.0:
                self._rprint(f"    [red]XP:   x{debuffs['xp_multiplier']:.2f}[/red]")
            if debuffs.get("gold_multiplier", 1.0) < 1.0:
                self._rprint(f"    [red]Gold: x{debuffs['gold_multiplier']:.2f}[/red]")

        # Moral
        self._rrule(self._t('wr_psyche_morale'))
        # Moral-Balken invertiert (100 = gut)
        self._rprint(f"  {self._hp_bar(int(mo), 100, bar_w)}")

        if crit > 0:
            self._rprint(f"  [green]{self._t('wr_psyche_crit_plus')} (+{crit:.0%})[/green]")
        elif crit < 0:
            self._rprint(f"  [red]{self._t('wr_psyche_crit_minus')} ({crit:.0%})[/red]")
        else:
            self._rprint(f"  {self._t('wr_psyche_neutral')}")

        # Trauma
        self._rrule(self._t('wr_psyche_trauma'))
        if traumas:
            for t in traumas:
                etype = t.get("enemy_type", "?")
                vrem = t.get("victories_remaining", t.get("victories_to_heal", "?"))
                narr = t.get("narrative", "")
                self._rprint(f"  [red]- {etype}: -5% Loot "
                             f"({vrem} {self._t('wr_psyche_trauma_heal')})[/red]")
                if narr:
                    self._rprint(f"    [dim]\"{narr}\"[/dim]")
        else:
            self._rprint(f"  [green]{self._t('wr_psyche_no_trauma')}[/green]")

        # Login-Bonus
        self._rprint(f"\n  [dim]{self._t('wr_psyche_login_bonus')}[/dim]")
        self._wait()

    def menu_leaderboard(self):
        self._header(self._t("wr_leaderboard_title"))
        c = self._character
        lb = self._get_leaderboard()

        if not c:
            self._wait()
            return

        # Lokalen Spieler aktualisieren
        if lb:
            lb.update_local(c)
            top = lb.get_top(20)
            rank = lb.get_rank(c.get("name", ""))
        else:
            top = []
            rank = None

        # Eigener Rang
        self._rprint(f"  {self._t('wr_leaderboard_you')}:")
        name = c.get("name", "?")
        self._rprint(f"  [green]{name}[/green] | "
                     f"Lv.[bold]{c.get('level', 1)}[/bold] | "
                     f"{self._t('wr_floor')} [cyan]{c.get('current_floor', 1)}[/cyan] | "
                     f"PVP: [green]{c.get('pvp_wins', 0)}W[/green]")
        if rank:
            self._rprint(f"  {self._t('wr_leaderboard_rank')}: "
                         f"[gold1]#{rank}[/gold1]")
        print()
        self._rrule()

        # Top-Liste
        if top:
            if self._console and _HAS_RICH:
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("#", justify="right", style=C_GOLD, width=4)
                name_w = max(10, min(18, self._width - 35))
                table.add_column("Name", width=name_w)
                table.add_column("Lv", justify="right", width=4)
                table.add_column("Floor", justify="right", style=C_SELECT, width=5)
                table.add_column("PVP", justify="right", style=C_PLAYER, width=4)
                table.add_column("Score", justify="right", style=C_GOLD, width=6)

                for i, entry in enumerate(top, 1):
                    en = entry.get("name", "?")[:name_w]
                    is_me = " <-" if en == name else ""
                    style = "bold green" if en == name else None
                    table.add_row(
                        str(i), f"{en}{is_me}",
                        str(entry.get("level", 1)),
                        str(entry.get("floor", 1)),
                        str(entry.get("pvp_wins", 0)),
                        str(entry.get("score", 0)),
                        style=style
                    )
                self._rtable(table)
            else:
                name_w = max(10, min(18, self._width - 35))
                print(f"  {'#':>3} {'Name':{name_w}s} {'Lv':>4} {'Floor':>5} "
                      f"{'PVP':>4} {'Score':>6}")
                self._rrule()
                for i, entry in enumerate(top, 1):
                    en = entry.get("name", "?")[:name_w]
                    is_me = " <-" if en == name else ""
                    print(f"  {i:>3} {en:{name_w}s} {entry.get('level', 1):>4} "
                          f"{entry.get('floor', 1):>5} "
                          f"{entry.get('pvp_wins', 0):>4} "
                          f"{entry.get('score', 0):>6}{is_me}")
        else:
            self._rprint(f"\n  [dim]{self._t('wr_leaderboard_empty')}[/dim]")

        self._rprint(f"\n  [dim]({self._t('wr_leaderboard_hint')})[/dim]")
        self._wait()

    # =============================================
    # SYSTEM-STATUS (On-Demand Widget)
    # =============================================

    def _get_system_status(self) -> Dict[str, Any]:
        """
        System-Status auslesen: RAM, Swap, zRAM, CPU, Temperatur,
        Hostname, IP, Netzwerkauslastung.

        Liest direkt aus /proc und /sys (kein htop noetig).
        """
        status = {}

        # --- RAM ---
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = {}
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(":")
                        meminfo[key] = int(parts[1])

            total_mb = meminfo.get("MemTotal", 0) // 1024
            avail_mb = meminfo.get("MemAvailable", 0) // 1024
            used_mb = total_mb - avail_mb
            swap_total_mb = meminfo.get("SwapTotal", 0) // 1024
            swap_free_mb = meminfo.get("SwapFree", 0) // 1024
            swap_used_mb = swap_total_mb - swap_free_mb

            status["ram_total"] = total_mb
            status["ram_used"] = used_mb
            status["ram_avail"] = avail_mb
            status["ram_pct"] = round(used_mb / total_mb * 100, 1) if total_mb > 0 else 0
            status["swap_total"] = swap_total_mb
            status["swap_used"] = swap_used_mb
            status["swap_pct"] = (round(swap_used_mb / swap_total_mb * 100, 1)
                                  if swap_total_mb > 0 else 0)
        except Exception:
            status["ram_total"] = 0
            status["ram_used"] = 0

        # --- zRAM ---
        try:
            zram_used = 0
            zram_total = 0
            import glob as _glob
            for dev in _glob.glob("/sys/block/zram*/"):
                try:
                    with open(os.path.join(dev, "disksize"), "r") as f:
                        zram_total += int(f.read().strip()) // (1024 * 1024)
                    with open(os.path.join(dev, "mem_used_total"), "r") as f:
                        zram_used += int(f.read().strip()) // (1024 * 1024)
                except (OSError, ValueError):
                    pass
            status["zram_total"] = zram_total
            status["zram_used"] = zram_used
        except Exception:
            status["zram_total"] = 0
            status["zram_used"] = 0

        # --- CPU Load ---
        try:
            with open("/proc/loadavg", "r") as f:
                parts = f.read().strip().split()
            status["cpu_load_1"] = float(parts[0])
            status["cpu_load_5"] = float(parts[1])
            status["cpu_load_15"] = float(parts[2])
        except Exception:
            status["cpu_load_1"] = 0.0

        # --- CPU Temperatur ---
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                raw = int(f.read().strip())
            status["cpu_temp"] = raw / 1000.0
        except Exception:
            status["cpu_temp"] = 0.0

        # --- Hostname + IP ---
        try:
            import socket
            status["hostname"] = socket.gethostname()
        except Exception:
            status["hostname"] = "?"

        try:
            result = subprocess.run(
                ["hostname", "-I"], capture_output=True, text=True, timeout=3
            )
            ips = result.stdout.strip().split()
            status["ip"] = ips[0] if ips else "?"
        except Exception:
            status["ip"] = "?"

        # --- Netzwerk (RX/TX Bytes von wlan0) ---
        try:
            with open("/proc/net/dev", "r") as f:
                for line in f:
                    if "wlan0" in line:
                        parts = line.strip().split()
                        status["net_rx_mb"] = round(int(parts[1]) / (1024 * 1024), 1)
                        status["net_tx_mb"] = round(int(parts[9]) / (1024 * 1024), 1)
                        break
        except Exception:
            status["net_rx_mb"] = 0
            status["net_tx_mb"] = 0

        # --- ZTB Prozess ---
        try:
            result = subprocess.run(
                ["pgrep", "-f", "hybrid_orchestrator"],
                capture_output=True, text=True, timeout=3
            )
            pid = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""
            if pid:
                with open(f"/proc/{pid}/status", "r") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            parts = line.split()
                            status["ztb_rss_mb"] = int(parts[1]) // 1024
                            break
                status["ztb_pid"] = pid
                status["ztb_running"] = True
            else:
                status["ztb_running"] = False
        except Exception:
            status["ztb_running"] = False

        return status

    def _print_system_status(self):
        """System-Status kompakt im Terminal anzeigen (Rich-aware)."""
        s = self._get_system_status()

        ram_pct = s.get("ram_pct", 0)
        bar_len = 20
        filled = int(bar_len * ram_pct / 100)

        if _HAS_RICH:
            # Rich-Farbiger RAM-Balken
            if ram_pct > 85:
                ram_color = "red"
            elif ram_pct > 70:
                ram_color = "yellow"
            else:
                ram_color = "green"

            self._rrule("SYSTEM")
            self._rprint(f"  [bold]{s.get('hostname', '?')}[/bold] | "
                         f"[cyan]{s.get('ip', '?')}[/cyan] | "
                         f"{s.get('cpu_temp', 0):.1f}C")

            ram_bar = "#" * filled + "-" * (bar_len - filled)
            self._rprint(f"  RAM  [[{ram_color}]{ram_bar}[/{ram_color}]] "
                         f"{s.get('ram_used', 0)}/{s.get('ram_total', 0)}MB "
                         f"[{ram_color}]{ram_pct}%[/{ram_color}]")

            swap_used = s.get("swap_used", 0)
            swap_total = s.get("swap_total", 0)
            zram_used = s.get("zram_used", 0)
            zram_total = s.get("zram_total", 0)
            self._rprint(f"  Swap {swap_used}/{swap_total}MB | "
                         f"zRAM {zram_used}/{zram_total}MB")

            self._rprint(f"  CPU  {s.get('cpu_load_1', 0):.2f} "
                         f"{s.get('cpu_load_5', 0):.2f} "
                         f"{s.get('cpu_load_15', 0):.2f} (1/5/15m)")

            net_rx = s.get("net_rx_mb", 0)
            net_tx = s.get("net_tx_mb", 0)
            self._rprint(f"  Net  RX:{net_rx:.1f}MB TX:{net_tx:.1f}MB (wlan0)")

            if s.get("ztb_running"):
                self._rprint(f"  ZTB  [green]PID:{s.get('ztb_pid', '?')} "
                             f"RSS:{s.get('ztb_rss_mb', '?')}MB[/green]")
            else:
                self._rprint(f"  ZTB  [red][STOPPED][/red]")
            self._rrule()
        else:
            # Plain ANSI Fallback (wie bisher)
            ram_bar = "#" * filled + "-" * (bar_len - filled)
            if ram_pct > 85:
                ram_indicator = "(!)"
            elif ram_pct > 70:
                ram_indicator = "(?)"
            else:
                ram_indicator = ""

            self._rrule("SYSTEM")
            print(f"  {s.get('hostname', '?')} | "
                  f"{s.get('ip', '?')} | "
                  f"{s.get('cpu_temp', 0):.1f}C")
            print(f"  RAM  [{ram_bar}] "
                  f"{s.get('ram_used', 0)}/{s.get('ram_total', 0)}MB "
                  f"{ram_pct}% {ram_indicator}")
            print(f"  Swap {s.get('swap_used', 0)}/{s.get('swap_total', 0)}MB | "
                  f"zRAM {s.get('zram_used', 0)}/{s.get('zram_total', 0)}MB")
            print(f"  CPU  {s.get('cpu_load_1', 0):.2f} "
                  f"{s.get('cpu_load_5', 0):.2f} "
                  f"{s.get('cpu_load_15', 0):.2f} (1/5/15m)")
            print(f"  Net  RX:{s.get('net_rx_mb', 0):.1f}MB "
                  f"TX:{s.get('net_tx_mb', 0):.1f}MB (wlan0)")
            if s.get("ztb_running"):
                print(f"  ZTB  PID:{s.get('ztb_pid', '?')} "
                      f"RSS:{s.get('ztb_rss_mb', '?')}MB")
            else:
                print(f"  ZTB  [STOPPED]")
            self._rrule()

    # =============================================
    # 11. OPTIONEN (mit Reboot)
    # =============================================

    def menu_options(self):
        """Optionen-Untermenu: Sprache, Speichern, Shell, Reboot, Shutdown, Beenden."""
        self._header(self._t("wr_opt_title"))
        self._rprint(f"  [cyan]1.[/cyan] {self._t('wr_opt_language')}")
        self._rprint(f"  [cyan]2.[/cyan] {self._t('wr_opt_save')}")
        self._rprint(f"  [cyan]3.[/cyan] {self._t('wr_opt_shell')}")
        self._rprint(f"  [cyan]4.[/cyan] {self._t('wr_opt_reboot')}")
        self._rprint(f"  [cyan]5.[/cyan] {self._t('wr_opt_shutdown')}")
        self._rprint(f"  [cyan]6.[/cyan] {self._t('wr_opt_quit')}")

        # System-Status Toggle (i18n)
        if self._show_system_status:
            toggle_label = self._t("wr_opt_system_status") + " (OFF)"
        else:
            toggle_label = self._t("wr_opt_system_status") + " (ON)"
        self._rprint(f"  [cyan]7.[/cyan] {toggle_label}")
        self._rprint(f"  [cyan]0.[/cyan] {self._t('wr_opt_back')}")
        print()

        ch = self._input(f"  {self._t('wr_choice')}? ")

        if ch == "1":
            self._opt_language()
        elif ch == "2":
            self._opt_save()
        elif ch == "3":
            self._opt_shell()
        elif ch == "4":
            self._opt_reboot()
        elif ch == "5":
            self._opt_shutdown()
        elif ch == "6":
            self._opt_quit()
        elif ch == "7":
            self._show_system_status = not self._show_system_status
            if self._show_system_status:
                self._rprint(f"\n  [green]{self._t('wr_opt_system_status_on')}[/green]")
            else:
                self._rprint(f"\n  {self._t('wr_opt_system_status_off')}")
            time.sleep(0.5)

    def _opt_language(self):
        """Sprache wechseln DE <-> EN."""
        cur = self._translator.get_language() if self._translator else "de"
        self._rprint(f"\n  {self._t('wr_opt_lang_current')}: [bold]{cur.upper()}[/bold]")
        print()
        self._rprint("  [cyan][DE][/cyan] Deutsch")
        self._rprint("  [cyan][EN][/cyan] English")
        print()
        ch = self._input(f"  {self._t('wr_choice')}? ").upper()
        if ch in ("DE", "EN"):
            self._set_language(ch.lower())
            self._rprint(f"  [green]{self._t('wr_opt_lang_changed')} -> {ch}[/green]")
            time.sleep(0.5)

    def _opt_save(self):
        """Manuelles Speichern: Hot -> Cold Storage flush."""
        self._rprint(f"\n  {self._t('wr_opt_save_start')}")

        # 1. Hot -> Cold flush
        try:
            from game.hot_storage import HotStorageManager
            hot = HotStorageManager()
            result = hot.flush_to_cold()
            n = result.get("flushed_count", 0) if result else 0
            self._rprint(f"  [green]{self._t('wr_opt_save_flushed', n=n)}[/green]")
        except Exception as e:
            self._rprint(f"  [yellow][WARN] Hot->Cold: {e}[/yellow]")

        # 2. Game State to Cold
        try:
            from hybrid_orchestrator import save_game_state_to_cold
            save_game_state_to_cold()
        except Exception as e:
            self._rprint(f"  [yellow][WARN] Save: {e}[/yellow]")

        self._rprint(f"  [green]{self._t('wr_opt_save_done')}[/green]")
        print("\a", end="", flush=True)
        self._wait()

    def _opt_shell(self):
        """Interaktive bash-Shell oeffnen."""
        self._rprint(f"\n  [cyan]{self._t('wr_opt_shell_hint')}[/cyan]")
        print()
        try:
            from core.paths import GAME_DIR as _gd
            shell_cwd = _gd
        except ImportError:
            shell_cwd = os.path.join(os.path.dirname(__file__), "..", "..")
        try:
            subprocess.run(
                ["/bin/bash", "--login"],
                cwd=shell_cwd
            )
        except FileNotFoundError:
            try:
                subprocess.run(["/bin/sh"])
            except Exception as e:
                self._rprint(f"  [red][{self._t('wr_error')}] {e}[/red]")
        self._rprint(f"\n  {self._t('wr_opt_back')}.")

    def _opt_reboot(self):
        """
        Gently Reboot: Save, Flush, Close DBs, Stop Service, Reboot.
        Identisch zu Shutdown, aber mit 'sudo reboot' statt 'sudo shutdown -h now'.
        """
        print()
        confirm = self._input(f"  {self._t('wr_opt_reboot_confirm')} ")
        if not self._is_yes(confirm):
            self._rprint(f"  {self._t('wr_cancelled')}")
            return False

        print("\a", end="", flush=True)
        print()

        # Step 1: Hot -> Cold
        self._rprint(f"  [cyan][1/5][/cyan] {self._t('wr_opt_reboot_step1')}")
        try:
            from game.hot_storage import HotStorageManager
            HotStorageManager().flush_to_cold()
            self._rprint(f"         [green]OK[/green]")
        except Exception as e:
            self._rprint(f"         [yellow]WARN: {e}[/yellow]")

        # Step 2: Save
        self._rprint(f"  [cyan][2/5][/cyan] {self._t('wr_opt_reboot_step2')}")
        try:
            from hybrid_orchestrator import save_game_state_to_cold
            save_game_state_to_cold()
            self._rprint(f"         [green]OK[/green]")
        except Exception as e:
            self._rprint(f"         [yellow]WARN: {e}[/yellow]")

        # Step 3: Close databases
        self._rprint(f"  [cyan][3/5][/cyan] {self._t('wr_opt_reboot_step3')}")
        try:
            from db.database import Database
            db = Database()
            db.close()
            self._rprint(f"         [green]OK[/green]")
        except Exception as e:
            self._rprint(f"         [yellow]WARN: {e}[/yellow]")

        # Step 4: Stop service
        self._rprint(f"  [cyan][4/5][/cyan] {self._t('wr_opt_reboot_step4')}")
        try:
            subprocess.run(["sudo", "systemctl", "stop", "zero-tower-battle.service"],
                           timeout=15, check=False, capture_output=True)
            self._rprint(f"         [green]OK[/green]")
        except Exception:
            pass

        # Step 5: Reboot
        self._rprint(f"  [cyan][5/5][/cyan] {self._t('wr_opt_reboot_step5')}")
        try:
            subprocess.run(["sudo", "reboot"],
                           timeout=10, check=False)
        except Exception as e:
            self._rprint(f"  [red][{self._t('wr_error')}] {e}[/red]")
            self._rprint("  sudo reboot")

        self.running = False
        return True

    def _opt_shutdown(self):
        """Gently Shutdown: Save, Flush, Stop, Power Off."""
        print()
        confirm = self._input(f"  {self._t('wr_opt_shutdown_confirm')} ")
        if not self._is_yes(confirm):
            self._rprint(f"  {self._t('wr_cancelled')}")
            return False

        print("\a", end="", flush=True)
        print()

        # Step 1: Hot -> Cold
        self._rprint(f"  [cyan][1/4][/cyan] {self._t('wr_opt_shutdown_step1')}")
        try:
            from game.hot_storage import HotStorageManager
            HotStorageManager().flush_to_cold()
            self._rprint(f"         [green]OK[/green]")
        except Exception:
            pass

        # Step 2: Save
        self._rprint(f"  [cyan][2/4][/cyan] {self._t('wr_opt_shutdown_step2')}")
        try:
            from hybrid_orchestrator import save_game_state_to_cold
            save_game_state_to_cold()
            self._rprint(f"         [green]OK[/green]")
        except Exception:
            pass

        # Step 3: Stop service
        self._rprint(f"  [cyan][3/4][/cyan] {self._t('wr_opt_shutdown_step3')}")
        try:
            subprocess.run(["sudo", "systemctl", "stop", "zero-tower-battle.service"],
                           timeout=15, check=False, capture_output=True)
            self._rprint(f"         [green]OK[/green]")
        except Exception:
            pass

        # Step 4: Power off
        self._rprint(f"  [cyan][4/4][/cyan] {self._t('wr_opt_shutdown_step4')}")
        try:
            subprocess.run(["sudo", "shutdown", "-h", "now"],
                           timeout=10, check=False)
        except Exception as e:
            self._rprint(f"  [red][{self._t('wr_error')}] {e}[/red]")
            print("  sudo shutdown -h now")

        self.running = False
        return True

    def _opt_quit(self):
        """Spiel beenden (Service stoppen, nicht Pi herunterfahren)."""
        confirm = self._input(f"\n  {self._t('wr_opt_quit_confirm')} ")
        if not self._is_yes(confirm):
            self._rprint(f"  {self._t('wr_cancelled')}")
            return

        # Save first
        try:
            from hybrid_orchestrator import save_game_state_to_cold
            save_game_state_to_cold()
        except Exception:
            pass

        # Stop service
        try:
            subprocess.run(["sudo", "systemctl", "stop", "zero-tower-battle.service"],
                           timeout=15, check=False, capture_output=True)
        except Exception:
            pass

        self._rprint(f"  [green]{self._t('wr_opt_quit_done')}[/green]")
        self.running = False

    # =============================================
    # BATTLE REPLAY (Visualizer Integration)
    # =============================================

    def show_battle_replay(self, battle_result: Dict[str, Any],
                           player_name: str = "Spieler",
                           player_max_hp: int = 100,
                           enemy_name: str = "Gegner",
                           enemy_max_hp: int = 100):
        """
        Kampf-Replay mit Rich-HP-Balken im War Room anzeigen.
        Integriert visualizer.py Logik direkt.

        Args:
            battle_result: Ergebnis von BattleEngine
            player_name: Spielername
            player_max_hp: Max HP des Spielers
            enemy_name: Gegnername
            enemy_max_hp: Max HP des Gegners
        """
        log = battle_result.get("log", [])
        is_shiny = battle_result.get("is_shiny", False)

        # Header
        shiny_tag = " [gold1][SHINY!][/gold1]" if is_shiny else ""
        self._rrule("KAMPF")
        self._rprint(f"  [green]{player_name}[/green] "
                     f"({battle_result.get('player_type', '?')})")
        self._rprint(f"     vs  [red]{enemy_name}[/red] "
                     f"({battle_result.get('enemy_type', '?')}){shiny_tag}")
        self._rrule()

        if not log:
            self._rprint("  [dim](Kein Kampf-Log vorhanden)[/dim]")
            return

        # Runden durchgehen
        current_round = 0
        for entry in log:
            round_num = entry.get("round", 0)
            if round_num != current_round:
                current_round = round_num
                self._rprint(f"\n  [magenta]--- Runde {round_num} ---[/magenta]")
                time.sleep(0.15)

            attacker = entry.get("attacker", "?")
            damage = entry.get("damage", 0)
            is_crit = entry.get("is_crit", False)
            type_adv = entry.get("type_advantage", 0)

            atk_name = player_name if attacker == "player" else enemy_name
            atk_color = C_PLAYER if attacker == "player" else C_ENEMY

            extras = []
            if is_crit:
                extras.append("[yellow blink]!! KRIT[/yellow blink]")
            if type_adv == 1:
                extras.append("[green]>>> Typ-Vorteil[/green]")
            elif type_adv == -1:
                extras.append("[red]<<< Typ-Nachteil[/red]")

            extra_str = f" ({', '.join(extras)})" if extras else ""
            self._rprint(f"  [{atk_color}]{atk_name}[/{atk_color}] -> "
                         f"[red]{damage} Schaden[/red]{extra_str}")

            p_hp = entry.get("player_hp", 0)
            e_hp = entry.get("enemy_hp", 0)
            self._rprint(f"    {player_name:>12}: {self._hp_bar(p_hp, player_max_hp)}")
            self._rprint(f"    {enemy_name:>12}: {self._hp_bar(e_hp, enemy_max_hp)}")

        # Ergebnis
        result = battle_result.get("result", "DRAW")
        rounds = battle_result.get("rounds", 0)
        print()
        self._rrule()
        if result == "WIN":
            self._rprint(f"  [green]SIEG! {player_name} gewinnt in Runde {rounds}![/green]")
            if battle_result.get("survived_barely"):
                self._rprint(f"  [yellow]Knapp ueberlebt! (<10% HP)[/yellow]")
            print("\a", end="", flush=True)
        elif result == "LOSS":
            self._rprint(f"  [red]NIEDERLAGE. {enemy_name} gewinnt in Runde {rounds}.[/red]")
        elif result == "DRAW":
            self._rprint(f"  [yellow]UNENTSCHIEDEN nach {rounds} Runden.[/yellow]")
        elif result == "BLOCKED":
            self._rprint(f"  [red]KAMPF BLOCKIERT: "
                         f"{battle_result.get('message', 'Erschoepfung')}[/red]")
        self._rrule()

    # =============================================
    # MAIN LOOP
    # =============================================

    def run(self):
        """
        Hauptschleife.

        1. Splashscreen zeigen (ASCII-Art)
        2. Pruefen ob Erststart (kein Charakter) -> Charakter-Erstellung
        3. Charakter aus Storage laden
        4. Menu-Loop
        """
        self.running = True

        # ASCII-Art Splashscreen beim Login
        self._show_splash()

        # SSH-Key Auto-Setup (einmalig bei erster Verbindung)
        self._setup_ssh_key()

        # Erststart: Charakter erstellen falls keiner vorhanden
        if self._character is None and self._is_first_start():
            success = self._run_character_creation()
            if not success:
                self._rprint("\n  [red]Charakter-Erstellung abgebrochen.[/red]")
                self._rprint("  [dim]'warroom' -> Erneut versuchen[/dim]")
                self.running = False
                return

        # Falls kein Charakter gesetzt: Aus Storage laden
        if self._character is None:
            self._load_character_from_storage()

        while self.running:
            try:
                self._clear_screen()
                self.show_menu()
                action = self.parse_menu()

                handlers = {
                    "LEVELUP": self.menu_levelup,
                    "DASHBOARD": self.menu_dashboard,
                    "INVENTORY": self.menu_inventory,
                    "SHOP": self.menu_shop,
                    "FORGE": self.menu_forge,
                    "RUNES": self.menu_runes,
                    "CODEX": self.menu_codex,
                    "TAVERNE": self.menu_taverne,
                    "PSYCHE": self.menu_psyche,
                    "LEADERBOARD": self.menu_leaderboard,
                    "OPTIONS": self.menu_options,
                }

                if action == "BACK" or action is None:
                    self.running = False
                elif action in handlers:
                    handlers[action]()

            except KeyboardInterrupt:
                self._rprint(f"\n  [yellow][WAR ROOM] Ctrl+C[/yellow]")
                self.running = False
            except Exception as e:
                self._rprint(f"  [red][{self._t('wr_error')}] {e}[/red]")
                self._wait()

    def _load_character_from_storage(self):
        """Charakter aus Hot/Cold Storage laden."""
        try:
            from game.hot_storage import HotStorageManager
            hot = HotStorageManager()
            data = hot.read("character_data")
            if data and "name" in data:
                self.set_character(data)
                return
        except Exception:
            pass

        try:
            from game.hot_storage import ColdStorageManager
            cold = ColdStorageManager()
            data = cold.load("character_data")
            if data and "name" in data:
                self.set_character(data)
                return
        except Exception:
            pass


# =============================================
# Standalone
# =============================================

if __name__ == "__main__":
    # PYTHONPATH sicherstellen (noetig wenn direkt gestartet)
    import sys as _sys
    _game_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _game_dir not in _sys.path:
        _sys.path.insert(0, _game_dir)
    # Umgebungsvariable fuer Sub-Prozesse
    os.environ.setdefault("PYTHONPATH", _game_dir)

    wr = WarRoom()
    # Kein Demo-Charakter mehr — der War Room erkennt jetzt selbst
    # ob ein Charakter existiert oder erstellt werden muss.
    wr.run()
