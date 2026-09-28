#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Language Module
==========================================
Zentrale Sprachverwaltung.
Delegiert an ui.options.language_config.
"""

from ui.options.language_config import LanguageSwitcher


class Language:
    """Zentrale Sprachverwaltung fuer alle UI-Komponenten."""

    def __init__(self, default_lang: str = "DE"):
        self._switcher = LanguageSwitcher()
        self._switcher.lang = default_lang
        self.current_lang = default_lang

    def get_text(self, key: str) -> str:
        """Hole uebersetzten Text fuer Key."""
        translations = self._switcher.load_language()
        return translations.get(key, key)

    def set_language(self, lang: str):
        """Sprache wechseln (DE/EN)."""
        self._switcher.change_language(lang)
        self.current_lang = lang

    def get_all_translations(self) -> dict:
        """Alle Uebersetzungen der aktuellen Sprache."""
        return self._switcher.load_language()
