#!/usr/bin/env python3
"""
ZERO Tower Battle (ZTB) - Rune Crafting System
======= ========================

Runen-Crafting:
├─ Runen-Typen (Feuer/Gift/Blitz)
├─ Runen-Fusion
├─ Runen-Slots pro Item
└─ UI-Integration
"""


import random
from typing import Dict, Any, List


class Runes:
    """
    Runen-Crafting System.
    
    Features:
    ├─ Runen-Typen (Feuer/Gift/Blitz)
    ├─ Runen-Fusion
    ├─ Runen-Slots
    └─ UI-Integration
    """
    
    TYPES = {
        "Feuer": {
            "multiplier": 1.15,
            "description": "+15% Schaden"
        },
        "Gift": {
            "multiplier": 1.12,
            "description": "+12% Schaden (DoT)"
        },
        "Blitz": {
            "multiplier": 1.18,
            "description": "+18% Schaden (Krit)"
        }
    }
    
    MAX_SLOTS = 3
    
    def __init__(self):
        self.runes: List[Dict[str, Any]] = []
        self._rune_id_counter = 1000

    def create_rune(self, rune_type: str, item_id: str, stats: float = 5.0) -> Dict[str, Any]:
        """
        Create rune for item.
        
        Args:
            rune_type: Feuer/Gift/Blitz
            item_id: Item ID
            stats: Rune Stats
        
        Returns:
            Dict mit: rune_id, rune
        
        """
        # Validate rune type
        if rune_type not in self.TYPES:
            return {
                "result": "ERROR",
                "message": f"Invalid rune type: {rune_type}. Use: {list(self.TYPES.keys())}"
            }
        
        # Create rune
        rune = {
            "id": self._rune_id_counter,
            "rune_id": f"RNE{self._rune_id_counter}",
            "type": rune_type,
            "item_id": item_id,
            "multiplier": self.TYPES[rune_type]["multiplier"],
            "stats": stats,
            "slots_used": 0,
            "slots_total": self.MAX_SLOTS,
            "description": self.TYPES[rune_type]["description"],
            "equipped": False
        }
        
        self.runes.append(rune)
        
        return {
            "result": "SUCCESS",
            "rune_id": rune["rune_id"],
            "rune": rune
        }

    def fuse_runes(self, rune_ids: List[str], item_id: str) -> Dict[str, Any]:
        """
        Fuse multiple runes into one.
        
        Args:
            rune_ids: List of rune IDs
            item_id: Item ID
        
        Returns:
            Dict mit: result, fused_rune
        
        """
        if len(rune_ids) < 2 or len(rune_ids) > 3:
            return {
                "result": "ERROR",
                "message": "Fuse 2-3 runes (max 3 slots)"
            }
        
        # Find runes
        fused_runes = []
        for rune_id in rune_ids:
            rune = next((r for r in self.runes if r["rune_id"] == rune_id), None)
            if not rune:
                return {"result": "ERROR", "message": f"Rune {rune_id} not found"}
            fused_runes.append(rune)
        
        # Calculate combined stats
        total_stats = sum(r["stats"] for r in fused_runes)
        avg_multiplier = sum(r["multiplier"] for r in fused_runes) / len(fused_runes)
        
        # Create new rune
        new_rune = {
            "id": len(self.runes) + 1,
            "rune_id": f"RNE{self._rune_id_counter + len(self.runes)}",
            "type": self._choose_rune_type(fused_runes, avg_multiplier),
            "item_id": item_id,
            "multiplier": avg_multiplier,
            "stats": total_stats * (1.0 + avg_multiplier * 0.1),  # Bonus
            "slots_used": 0,
            "slots_total": len(fused_runes),
            "description": f"Fused {sum(r['multiplier'] for r in fused_runes)} runes",
            "equipped": False
        }
        
        # Add to collection
        self.runes.append(new_rune)
        
        return {
            "result": "SUCCESS",
            "rune_id": new_rune["rune_id"],
            "rune": new_rune
        }

    def _choose_rune_type(self, runes: List[Dict[str, Any]], avg_multiplier: float) -> str:
        """
        Choose rune type based on multiplier.
        
        Args:
            runes: List of merged runes
            avg_multiplier: Average multiplier
        
        Returns:
            str: Rune type
        
        """
        if avg_multiplier >= 1.15:
            return "Blitz"
        elif avg_multiplier >= 1.12:
            return "Gift"
        else:
            return "Feuer"

    def equip_rune(self, rune_id: str) -> Dict[str, Any]:
        """
        Equip rune to item.
        
        Args:
            rune_id: Rune ID
        
        Returns:
            Dict mit: result, rune
        
        """
        rune = next((r for r in self.runes if r["rune_id"] == rune_id), None)
        
        if not rune:
            return {
                "result": "ERROR",
                "message": f"Rune {rune_id} not found"
            }
        
        rune["equipped"] = True
        
        return {
            "result": "SUCCESS",
            "rune": rune
        }

    def unequip_rune(self, rune_id: str) -> Dict[str, Any]:
        """
        Unequip rune from item.
        
        Args:
            rune_id: Rune ID
        
        Returns:
            Dict mit: result, rune
        
        """
        rune = next((r for r in self.runes if r["rune_id"] == rune_id), None)
        
        if not rune:
            return {
                "result": "ERROR",
                "message": f"Rune {rune_id} not found"
            }
        
        rune["equipped"] = False
        
        return {
            "result": "SUCCESS",
            "rune": rune
        }

    def get_rune_collection(self) -> List[Dict[str, Any]]:
        """
        Get all runes in collection.
        
        Returns:
            list of runes
        
        """
        return self.runes

    def calculate_total_multiplier(self) -> float:
        """
        Calculate total multiplier for all equipped runes.
        
        Returns:
            float: total multiplier
        
        """
        total = 1.0
        equipped = [r for r in self.runes if r["equipped"]]
        
        for r in equipped:
            total *= r["multiplier"]
        
        return total
