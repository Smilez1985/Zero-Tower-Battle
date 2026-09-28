#!/usr/bin/env python3
"""Zero Tower Battle - Dashboard"""
import sys
from ui.language import Language

class Dashboard:
    def __init__(self):
        self.language = Language()
        
    def show_dashboard(self):
        print("=" * 40)
        print("🎮 DASHBOARD")
        print(f"   Sprache: {self.language.current_lang}")
        print("=" * 40)

