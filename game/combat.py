#!/usr/bin/env python3
"""
Zero Tower Battle - Combat Logic
PvE/PvP/AI + WorldBoss
"""

class Combat:
    def __init__(self):
        self.score = 0
        
    def attack(self, damage):
        """Combat damage calculation"""
        self.score += damage

