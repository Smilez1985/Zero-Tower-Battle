#!/usr/bin/env python3
"""
Zero Tower Battle - Tower Model
Tower Defense Logic
"""

class Tower:
    def __init__(self, name, position, power):
        self.name = name
        self.position = position
        self.power = power
        self.enemies_defeated = 0
        
    def attack(self, enemy):
        """Attack enemy"""
        damage = self.power
        if self._hit(enemy):
            self.enemies_defeated += 1
            print(f"✅ [TOWER] {self.name} attacked! Damage: {damage}")
            return damage
        return 0
        
    def _hit(self, enemy):
        """Check if hit"""
        # Hit logic (simplified)
        return True

print("✅ [TOWER MODEL] Ready!")
