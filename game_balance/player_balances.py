#!/usr/bin/env python3
"""Player Balance Tuning"""

PLAYER_TITLES = {
    "Level 1-5": "Novice Adventurer",
    "Level 6-10": "Veteran Warrior",
    "Level 11-20": "Elite Champion",
    "Level 21-30": "Legendary Hero",
    "Level 30+": "Mythic Legend"
}

PLAYER_BONUSES = {
    "Novice Adventurer": 1.0,
    "Veteran Warrior": 1.15,
    "Elite Champion": 1.3,
    "Legendary Hero": 1.6,
    "Mythic Legend": 2.0
}

def calculate_player_stats(level):
    """Calculate player stats based on level"""
    title = PLAYER_TITLES.get(f"Level {level // 5}-{(level // 5) + 1}", "Novice Adventurer")
    multiplier = PLAYER_BONUSES.get(title, 1.0)
    
    base_hp = level * 10
    base_attack = level * 2
    base_xp_reward = level * 5
    
    return {
        "title": title,
        "multiplier": multiplier,
        "hp": int(base_hp * multiplier),
        "attack": int(base_attack * multiplier),
        "xp_reward": int(base_xp_reward * multiplier)
    }

# Export
__all__ = ['calculate_player_stats', 'PLAYER_TITLES', 'PLAYER_BONUSES']
