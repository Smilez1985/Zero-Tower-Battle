#!/usr/bin/env python3
"""
Zero Tower Battle - War Room Interface
Options + Language Switch + Game Start
"""

from ui.options.language_config import LanguageSwitcher

class WarRoom:
    """War Room (Game Menu Interface)"""
    def __init__(self):
        self.lang_switcher = LanguageSwitcher()
        self.translations = self.lang_switcher.load_language()
        
    def show_menu(self):
        """Show Main Menu (War Room)"""
        print(f"🏠 [WAR ROOM] {self.translations['title']}")
        print(f"   1. {self.translations['option_pve']}")
        print(f"   2. {self.translations['option_pvp']}")
        print(f"   3. {self.translations['option_settings']}")
        print(f"   4. {self.translations['option_quit']}")
        return self.parse_menu()
        
    def parse_menu(self):
        """Parse menu choice"""
        choice = input("Auswahl? ")
        if choice == "1":
            return "PVE"
        elif choice == "2":
            return "PVP"
        elif choice == "3":
            return "SETTINGS"
        elif choice == "4":
            return "Q"
        return None
        
    def change_language(self):
        """Change language (DE ↔ EN)"""
        print(f"🌐 [LANGUAGE] Sprache wechseln (DE ↔ EN)")
        lang = input("DE für Deutsch oder EN für English? ")
        if lang == "DE":
            self.lang_switcher.change_language("DE")
        elif lang == "EN":
            self.lang_switcher.change_language("EN")
        print(f"✅ [LANG] Changed to: {self.lang_switcher.get_current_language()}")

print("✅ [WAR ROOM] Ready!")
