#!/usr/bin/env python3
"""
Zero Tower Battle - Language Support
Deutsch | English | Switch in War Room
"""

class LanguageSwitcher:
    """Language Switch for Game"""
    def __init__(self):
        self.lang = "DE"  # Default to DE
        self.translations = {
            "DE": self._get_de(),
            "EN": self._get_en()
        }
        
    def _get_de(self):
        """German Strings"""
        return {
            "title": "Zero Tower Battle",
            "menu_pve": "Kampfsimulation",
            "menu_pvp": "Team Battle",
            "menu_settings": "Einstellungen",
            "menu_quit": "Beenden",
            "score": "Ergebnis",
            "level": "Level",
            "health": "Gesundheit",
            "pve_start": "Kampfsimulation starten",
            "pvp_start": "Team Battle starten",
            "settings_saved": "Einstellungen gespeichert",
            "language_changed": "Sprache geändert",
            "option_pve": "PVE Kampfsimulation",
            "option_pvp": "PvP Battle",
            "option_settings": "Einstellungen",
            "option_quit": "Beenden",
            "world_boss": "Weltboss",
            "player_1": "Spieler 1",
            "player_2": "Spieler 2"
        }
        
    def _get_en(self):
        """English Strings"""
        return {
            "title": "Zero Tower Defense",
            "menu_pve": "Combat Simulation",
            "menu_pvp": "Team Battle",
            "menu_settings": "Settings",
            "menu_quit": "Quit",
            "score": "Score",
            "level": "Level",
            "health": "Health",
            "pve_start": "Start Combat Simulation",
            "pvp_start": "Start Team Battle",
            "settings_saved": "Settings saved",
            "language_changed": "Language changed",
            "option_pve": "PVE Combat",
            "option_pvp": "PvP Battle",
            "option_settings": "Settings",
            "option_quit": "Quit",
            "world_boss": "World Boss",
            "player_1": "Player 1",
            "player_2": "Player 2"
        }
        
    def load_language(self):
        """Load current language"""
        return self.translations.get(self.lang, self.translations["DE"])
        
    def change_language(self, new_lang):
        """Change language (DE ↔ EN)"""
        self.lang = new_lang
        print(f"✅ [LANG] Changed to {new_lang}")
        return True
        
    def get_current_language(self):
        """Get current language"""
        return self.lang

# Modul-Level Instanz nur wenn direkt ausgefuehrt
if __name__ == "__main__":
    switcher = LanguageSwitcher()
    print(f"[LANGUAGE] Ready! (Current: {switcher.get_current_language()})")
