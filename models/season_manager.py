#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Season Manager
============ =============================

Biom-Rotation System:
├─ Saison-Logik (alle 3 Monate)
├─ Biome: Eis → Feuer → Blitz
├─ Monster-Sets pro Biome
└─ Event-Boni pro Biome
"""


from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import math


class Season(Enum):
    """Jahreszeiten/Biom."""
    EIS = "ice"
    FEUER = "fire"
    BLITZ = "lightning"
    BLUT = "blood"


class Biome:
    """
    Biom-Manager.

    Features:
    - Saison-Logik
    - Monster-Sets
    - Event-Boni
    - Rotation (alle 3 Monate)
    """
    
    SEASON_LENGTH_MONTHS = 3
    
    def __init__(self, 
                 start_date: datetime,
                 current_season: Season = None,
                 biomes: Dict[Season, Any] = None):
        
        self.start_date = start_date
        self.current_season = start_date.month // 3
        
        # Default Biomes
        self.biomes = {
            Season.EIS: {
                "name": "Tiefkalt",
                "theme": "ice_burst",
                "monster_sets": ["polar_bear", "snow_wolf", "frost_drake"],
                "bonus_multiplier": 1.2,
                "color": "#E0F7FA",
                "effects": ["frost_resist", "slow_build"]
            },
            Season.FEUER: {
                "name": "Vulkan",
                "theme": "fire_fury",
                "monster_sets": ["flame_drake", "lava_golem", "inferno_hound"],
                "bonus_multiplier": 1.5,
                "color": "#FF5722",
                "effects": ["fire_resist", "burn_debuff"]
            },
            Season.BLITZ: {
                "name": "Blitzgewitter",
                "theme": "storm_strike",
                "monster_sets": ["storm_elemental", "lightning_wolf", "thunder_chief"],
                "bonus_multiplier": 1.1,
                "color": "#2196F3",
                "effects": ["lightning_resist", "aoe_damage"]
            },
            Season.BLUT: {
                "name": "Verderb",
                "theme": "blood_curse",
                "monster_sets": ["blood_knight", "plague_monk", "necro_lord"],
                "bonus_multiplier": 2.0,
                "color": "#F44336",
                "effects": ["bleed_debuff", "dark_resist"]
            }
        }
    
    def get_current_biome(self) -> Dict[str, Any]:
        """Rückgib aktuellen Biome."""
        season_key = Season(["EIS", "FEUER", "BLITZ", "BLUT"][
            (self.start_date.month - 1) // 4 % 4
        ])
        return self.biomes.get(season_key, self.biomes[Season.EIS])
    
    def get_biome_for_month(self, month: int = None) -> Dict[str, Any]:
        """Rückgab Biome für spezifischen Monat."""
        if month is None:
            return self.get_current_biome()
        
        # Berechne Season basierend auf Monat
        seasons = ["EIS", "FEUER", "BLITZ", "BLUT"]
        season_index = (month - 1) // 3 % 4
        return self.biomes[Season(seasons[season_index])]
    
    def get_season_end(self) -> datetime:
        """Rückgab End-Datum der aktuellen Saison."""
        current_month = self.start_date.month
        last_day = [
            31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31
        ]
        
        # Nächster 3-Monats-Ende
        next_season_month = current_month + 3
        if next_season_month > 12:
            next_season_month -= 12
            year = self.start_date.year + 1
        else:
            year = self.start_date.year
        
        return datetime(year, next_season_month, last_day[next_season_month - 1])
    
    def get_remaining_days(self, current_date: datetime = None) -> int:
        """Rückgab verbleibende Tage bis Saisonende."""
        if current_date is None:
            current_date = datetime.now()
        
        end_date = self.get_season_end()
        delta = end_date - current_date
        return max(0, delta.days)
    
    def get_biome_rotation(self) -> List[Dict[str, Any]]:
        """Rückgab Rotation der Biomes (Jahreszyklus)."""
        return [
            {"season": Season.EIS, "months": [1, 2, 3], "color": "#E0F7FA"},
            {"season": Season.FEUER, "months": [4, 5, 6], "color": "#FF5722"},
            {"season": Season.BLITZ, "months": [7, 8, 9], "color": "#2196F3"},
            {"season": Season.BLUT, "months": [10, 11, 12], "color": "#F44336"},
        ]
