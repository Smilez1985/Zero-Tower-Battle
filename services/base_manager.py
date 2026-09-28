#!/usr/bin/env python3
"""
ZERO Tower Battle (ZTB) - Base Builder
======== ======

Lager-System:
├─ Lager-Base
├─ Lager-Cap Erhöhung
└─ UI-Integration
"""


from typing import Dict, Any
import os


class BaseManager:
    """
    Base Manager für Lager.
    
    Features:
    ├─ Lager-Base
    ├─ Lager-Cap Erhöhung
    └─ UI-Integration
    """
    
    BASE_SIZE_MIN = 100
    BASE_SIZE_MAX = 1000
    INCREASE_COST_MULTIPLIER = 1.5  # Kosten steigen um 50%

    def __init__(self, base_size: int = BASE_SIZE_MIN):
        self.base_size = base_size
        self.base_capacity = self.base_size
        self.expansion_count = 0

    def build_base(self) -> Dict[str, Any]:
        """
        Build initial base.
        
        Returns:
            Dict mit: result, base
        
        """
        result = {
            "result": "SUCCESS",
            "base_size": self.base_size,
            "base_capacity": self.base_capacity,
            "expansion_count": self.expansion_count,
            "message": "Initial base built"
        }
        return result

    def expand_base(self, cost: int = None) -> Dict[str, Any]:
        """
        Expand base (increase capacity).
        
        Args:
            cost: Cost or auto-calculate
        
        Returns:
            Dict mit: result, base, cost
        
        """
        if cost is None:
            cost = self.base_size * self.INCREASE_COST_MULTIPLIER
        
        if cost:
            # Check if affordable
            base_capacity = self.base_capacity + cost // 3  # 3x capacity for cost
            
            return {
                "result": "SUCCESS",
                "base_capacity": base_capacity,
                "expansion_count": self.expansion_count + 1,
                "cost": cost,
                "message": f"Base expanded to {base_capacity} capacity"
            }
        
        return {"result": "INSUFFICIENT_FUNDS", "cost": cost}

    def get_base_status(self) -> Dict[str, Any]:
        """
        Get base status.
        
        Returns:
            Dict mit: size, capacity, expansions
        
        """
        return {
            "base_size": self.base_size,
            "base_capacity": self.base_capacity,
            "expansion_count": self.expansion_count,
            "next_expansion_cost": int(self.base_size * self.INCREASE_COST_MULTIPLIER)
        }

    def calculate_capacity(self, size: int) -> int:
        """
        Calculate capacity for base size.
        
        Args:
            size: Base size
        
        Returns:
            int: Capacity
        
        """
        # Capacity = base_size * multiplier
        return size * 3

    def upgrade_base(self, multiplier: float = 1.0) -> Dict[str, Any]:
        """
        Upgrade base (increase capacity multiplier).
        
        Args:
            multiplier: Multiplier for capacity
        
        Returns:
            Dict mit: result, size, capacity
        
        """
        upgrade_multiplier = 1.0 + multiplier
        
        base_capacity = self.base_size * upgrade_multiplier
        
        return {
            "result": "SUCCESS",
            "base_capacity": base_capacity,
            "message": f"Base upgraded to {upgrade_multiplier}x capacity"
        }