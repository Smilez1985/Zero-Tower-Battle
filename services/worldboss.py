#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - World Boss System
====================================== ======

Weltboss-System:
- Boss Spawn Management
- Boss Stats & HP
- Loot Drops
- Event Timer
- Encounters Handling
"""

import random
from datetime import datetime, timedelta
from typing import Dict, List, Any


class WorldBoss:
    """World Boss Management System."""
    
    BOSS_STATS = {
        "Tier1": {"hp": 1000, "damage": 200, "loot_multiplier": 1.0, "name": "Slime King"},
        "Tier2": {"hp": 5000, "damage": 1000, "loot_multiplier": 2.0, "name": "Golem"},
        "Tier3": {"hp": 15000, "damage": 3000, "loot_multiplier": 5.0, "name": "Dragon"},
        "Tier4": {"hp": 50000, "damage": 10000, "loot_multiplier": 10.0, "name": "Dark Lord"},
        "Tier5": {"hp": 200000, "damage": 50000, "loot_multiplier": 25.0, "name": "Ancient Guardian"}
    }
    
    def __init__(self):
        self.boss_active = False
        self.boss_tier = 1
        self.boss_remaining_hp = 0
        self.boss_max_hp = 0
        self.encounters = []
        self.loot_drops = []
        self.next_spawn_time = datetime.now() + timedelta(hours=1)
        self.is_spawning = False
        self.spawn_timer = 0
        
    def spawn_boss(self, tier: int = 1):
        """Spawn world boss at specified tier."""
        if tier not in self.BOSS_STATS:
            tier = min(tier, max(self.BOSS_STATS.keys(), key=int))
        
        boss_data = self.BOSS_STATS[tier]
        self.boss_max_hp = boss_data["hp"]
        self.boss_remaining_hp = boss_data["hp"]
        self.boss_active = True
        self.boss_tier = tier
        
        self.encounters.append({
            "tier": tier,
            "name": boss_data["name"],
            "max_hp": boss_data["hp"],
            "damage": boss_data["damage"],
            "loot_multiplier": boss_data["loot_multiplier"],
            "spawn_time": datetime.now().isoformat(),
            "active": True
        })
        
        return {
            "status": "BOSS_spawned",
            "tier": tier,
            "name": boss_data["name"],
            "hp": boss_data["hp"]
        }
    
    def take_damage(self, damage: int) -> Dict:
        """Deal damage to boss."""
        if not self.boss_active:
            return {"status": "NO_BOSS", "message": "No active boss"}
        
        self.boss_remaining_hp -= damage
        self.boss_remaining_hp = max(0, self.boss_remaining_hp)
        
        return {
            "status": "DAMAGE_TAKEN",
            "damage": damage,
            "remaining_hp": self.boss_remaining_hp,
            "percent": (self.boss_remaining_hp / self.boss_max_hp) * 100
        }
    
    def deal_critical_hit(self, chance: float = 0.2) -> Dict:
        """Deal critical hit (simulation)."""
        if not self.boss_active:
            return {"status": "NO_BOSS"}
        
        if self._roll_chance(chance):
            base_damage = self.encounters[-1]["damage"]
            critical_damage = int(base_damage * 0.5)  # Boss counter dmg
            self.boss_remaining_hp -= critical_damage
            
            return {
                "status": "CRITICAL_HIT",
                "damage": critical_damage,
                "message": f"Critical hit! Boss takes {critical_damage}"
            }
        
        return {"status": "NORMAL_HIT"}
    
    def drop_loot(self, loot_type: str = "common") -> Dict:
        """Drop loot from boss."""
        loot_data = {
            "type": loot_type,
            "multiplier": self.encounters[-1]["loot_multiplier"] if self.encounters else 1.0,
            "items": [
                {"name": "XP Shard", "tier": 1, "multiplier": 1.0, "amount": 1},
                {"name": "Gold", "tier": 2, "multiplier": 1.0, "amount": 50},
                {"name": "Rare Gem", "tier": 3, "multiplier": 1.0, "amount": 1}
            ]
        }
        
        self.loot_drops.append(loot_data)
        return {
            "status": "LOOT_DROPPED",
            "loot_type": loot_type,
            "items": loot_data["items"]
        }
    
    def get_boss_state(self) -> Dict:
        """Get current boss state."""
        if not self.boss_active:
            return {
                "status": "NO_BOSS",
                "message": "No active boss",
                "next_spawn": self.next_spawn_time.isoformat()
            }
        
        current_encounter = self.encounters[-1]
        return {
            "status": "ACTIVE",
            "tier": current_encounter["tier"],
            "name": current_encounter["name"],
            "hp": current_encounter["max_hp"],
            "remaining_hp": self.boss_remaining_hp,
            "percent": (self.boss_remaining_hp / current_encounter["max_hp"]) * 100,
            "max_hp": current_encounter["max_hp"],
            "damage": current_encounter["damage"]
        }
    
    def _roll_chance(self, chance: float) -> bool:
        """Roll for chance."""
        return random.random() < chance
    
    def reset(self):
        """Reset boss system."""
        self.boss_active = False
        self.encounters = []
        self.loot_drops = []
        return {"status": "RESET"}


if __name__ == "__main__":
    # Test worldboss.py
    boss = WorldBoss()
    print("Weltboss System initialized!")
    print("Spawn Boss:")
    result = boss.spawn_boss(tier=1)
    print(f"  Tier {result['tier']}: {result['name']}")
    print(f"  HP: {result['hp']}")
