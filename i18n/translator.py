#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - JSON-basiertes i18n-System
=====================================================
Laedt Uebersetzungen aus JSON-Dateien (de.json, en.json).
Ersetzt das hardcodierte Dict-System in language_config.py.

Verwendung:
    from i18n.translator import Translator
    t = Translator("de")
    print(t.get("battle_win"))  # "SIEG!"
    t.set_language("en")
    print(t.get("battle_win"))  # "VICTORY!"
"""

import json
import os
from typing import Dict, Any, Optional


# Pfad zu den JSON-Dateien (relativ zum Modul)
I18N_DIR = os.path.dirname(os.path.abspath(__file__))
SUPPORTED_LANGUAGES = ["de", "en"]
DEFAULT_LANGUAGE = "de"


class Translator:
    """
    JSON-basiertes Uebersetzungssystem.

    - Laedt Sprachdateien aus i18n/de.json, i18n/en.json
    - Fallback auf Deutsch wenn Key nicht gefunden
    - Fallback auf Key-Name wenn nichts gefunden
    - Thread-safe (kein Shared State)
    """

    def __init__(self, language: str = DEFAULT_LANGUAGE):
        """
        Args:
            language: Sprachcode ("de" oder "en")
        """
        self._language = language.lower() if language else DEFAULT_LANGUAGE
        self._translations: Dict[str, Dict[str, str]] = {}
        self._load_all_languages()

    def _load_all_languages(self) -> None:
        """Alle verfuegbaren Sprachdateien laden."""
        for lang in SUPPORTED_LANGUAGES:
            filepath = os.path.join(I18N_DIR, f"{lang}.json")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    self._translations[lang] = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"[i18n-WARN] {lang}.json nicht geladen: {e}")
                self._translations[lang] = {}

    def get(self, key: str, **kwargs) -> str:
        """
        Uebersetzen Text fuer Key holen.

        Fallback-Reihenfolge:
          1. Aktuelle Sprache
          2. Deutsch (Fallback)
          3. Key-Name (letzter Fallback)

        Args:
            key: Uebersetzungs-Key (z.B. "battle_win")
            **kwargs: Platzhalter-Ersetzungen (z.B. name="TestHeld")

        Returns:
            Uebersetzter Text
        """
        # 1. Aktuelle Sprache
        text = self._translations.get(self._language, {}).get(key)

        # 2. Fallback: Deutsch
        if text is None and self._language != "de":
            text = self._translations.get("de", {}).get(key)

        # 3. Fallback: Key-Name
        if text is None:
            text = key

        # Platzhalter ersetzen (z.B. "{name}" -> "TestHeld")
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError):
                pass

        return text

    def set_language(self, language: str) -> bool:
        """
        Sprache wechseln.

        Args:
            language: "de" oder "en"

        Returns:
            True wenn erfolgreich
        """
        lang = language.lower()
        if lang in SUPPORTED_LANGUAGES:
            self._language = lang
            return True
        return False

    def get_language(self) -> str:
        """Aktuelle Sprache zurueckgeben."""
        return self._language

    def get_all(self) -> Dict[str, str]:
        """Alle Uebersetzungen der aktuellen Sprache."""
        return self._translations.get(self._language, {}).copy()

    def reload(self) -> None:
        """Sprachdateien neu laden (z.B. nach Aenderung)."""
        self._load_all_languages()


# =============================================
# Globale Instanz (optional, fuer einfachen Zugriff)
# =============================================

_global_translator: Optional[Translator] = None


def get_translator(language: str = None) -> Translator:
    """
    Globale Translator-Instanz holen oder erstellen.

    Args:
        language: Sprache (nur beim ersten Aufruf relevant)

    Returns:
        Translator-Instanz
    """
    global _global_translator
    if _global_translator is None:
        _global_translator = Translator(language or DEFAULT_LANGUAGE)
    elif language:
        _global_translator.set_language(language)
    return _global_translator


# =============================================
# Standalone-Test
# =============================================

if __name__ == "__main__":
    t = Translator("de")
    print(f"Sprache: {t.get_language()}")
    print(f"Titel: {t.get('title')}")
    print(f"Sieg: {t.get('battle_win')}")
    print(f"Krieger: {t.get('class_krieger_desc')}")
    print(f"Unbekannt: {t.get('nonexistent_key')}")
    print()

    t.set_language("en")
    print(f"Sprache: {t.get_language()}")
    print(f"Title: {t.get('title')}")
    print(f"Victory: {t.get('battle_win')}")
    print(f"Warrior: {t.get('class_krieger_desc')}")
    print()

    # Globale Instanz
    gt = get_translator("de")
    print(f"Global: {gt.get('forge_title')}")

    print("\ni18n-Test abgeschlossen.")
