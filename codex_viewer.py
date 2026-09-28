#!/usr/bin/env python3
"""
ZERO Tower Battle (ZTB) - Codex Viewer
====== =========

Sammel-Album:
├─ Monster-Liste
├─ Sammel-Progress
├─ Shiny-Highlight
└─ UI-Integration
"""


from typing import Dict, Any, List
from collections import defaultdict


CODEN = {
    "Monster": {
        "Krieger": {"min": 10, "max": 30, "count": 500},
        "Schurke": {"min": 15, "max": 35, "count": 500},
        "Magier": {"min": 12, "max": 40, "count": 500}
    },
    "Items": {
        "Waffe": {"min": 5, "max": 25, "count": 300},
        "Rüstung": {"min": 4, "max": 20, "count": 250},
        "Rune": {"min": 8, "max": 30, "count": 150}
    }
}


class CodexViewer:
    """
    Codex Viewer für Sammel-Album.
    
    Features:
    ├─ Monster-Liste
    ├─ Sammel-Progress
    ├─ Shiny-Highlight
    └─ UI-Integration
    """
    
    SHINY_CHANCE = 1 << 13  # 8192

    def __init__(self):
        self.codex: Dict[str, Dict[str, Any]] = CODEN.copy()
        self.collected: Dict[str, int] = defaultdict(int)
        self.collected_shiny: Dict[str, int] = defaultdict(int)

    def get_codex_entry(self, codex_type: str, codex_value: str) -> Dict[str, Any]:
        """
        Get codex entry.
        
        Args:
            codex_type: Monster oder Item
            codex_value: Value (e.g., "Krieger", "Waffe")
        
        Returns:
            Dict mit: name, tier, rarity, count
        
        """
        codex = self.codex.get(codex_type, {}).get(codex_value, {})
        
        return {
            "name": codex_value,
            "tier": "Common",
            "rarity": "Common",
            "count": self.collected.get(codex_value, 0),
            "shiny": self.collected_shiny.get(codex_value, 0)
        }

    def add_codex_entry(self, codex_type: str, codex_value: str,
                        item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add codex entry (collect).
        
        Args:
            codex_type: Monster oder Item
            codex_value: Value (e.g., "Krieger", "Waffe")
            item: Item data
        
        Returns:
            Dict mit: result, collection_count
        
        """
        # Track collection
        self.collected[codex_value] = self.collected.get(codex_value, 0) + 1
        
        # Check Shiny
        is_shiny = item.get("is_shiny", False)
        if is_shiny:
            self.collected_shiny[codex_value] = self.collected_shiny.get(codex_value, 0) + 1
        
        return {
            "result": "SUCCESS",
            "collection_count": self.collected[codex_value],
            "shiny_count": self.collected_shiny.get(codex_value, 0)
        }

    def check_collection_complete(self, codex_type: str, codex_value: str) -> bool:
        """
        Check if collection is complete.
        
        Returns:
            bool (Collection complete)
        
        """
        codex = self.codex.get(codex_type, {}).get(codex_value, [])
        return self.collected.get(codex_value, 0) >= codex.get("count", 0)

    def get_collection_progress(self) -> Dict[str, Any]:
        """
        Get collection progress.
        
        Returns:
            Dict mit: progress, percentage, total
        
        """
        total = sum(self.collected.values())
        total_possible = len(self.collected)
        
        return {
            "collected": total,
            "total": total_possible,
            "percentage": (total / len(self.collected) * 100) if self.collected else 0,
            "shiny": sum(self.collected_shiny.values())
        }

    def get_codex_status(self) -> Dict[str, Any]:
        """
        Get codex status.
        
        Returns:
            Dict mit: codex, progress, progress
        
        """
        return {
            "codex": {
                codex_type: count
                for codex_type, count in self.collected.items()
            },
            "progress": self.get_collection_progress()
        }
