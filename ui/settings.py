#!/usr/bin/env python3
"""
Zero Tower Battle - Settings Interface
Language Switch + Options
"""

class Settings:
    def __init__(self):
        self.language = "DE"
        
    def load_language(self):
        """Load DE or EN"""
        return self.language
        
    def change_language(self, new_lang):
        """Switch DE ↔ EN"""
        self.language = new_lang
        return True

