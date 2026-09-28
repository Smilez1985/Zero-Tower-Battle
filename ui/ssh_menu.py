#!/usr/bin/env python3
"""
ZERO Tower Battle (ZTB) - SSH Menu Dashboard
======== ===============

Main UI for Battle Management:
├─ Hauptmenü 1-9 Navigation
├─ HP-Balken Visualisierung
├─ Logs & UI
├─ Character Stats
├─ Inventory & Shop Integration
└─ Battle Logs & History

Features:
├─ Rich Console Output
├─ PIL Image Rendering (HP Bars, Icons)
└─ CLI Interface (Click)
"""


from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json
import os
import subprocess
# pylint: disable=import-error, unused-import

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.layout import Layout
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    from click import Command, option, argument, pass_context
    CLI_AVAILABLE = True
except ImportError:
    CLI_AVAILABLE = False


# Console für Rich
console = Console()
console = Console(width=80) if CLI_AVAILABLE else None

class SSHMenu:
    """
    SSH Menu für Battle Dashboard.
    
    Features:
    ├─ Hauptmenü 1-9
    ├─ Navigation
    ├─ HP-Balken
    ├─ Logs & UI
    └─ Stats & History
    """
    
    VERSION = "2.0.0"
    BATTLE_LOGS_MAX = 100
    
    def __init__(self, character_db=None, inventory=None, shop=None):
        self.db = character_db
        self.inventory = inventory
        self.shop = shop
        self.logs: list = []
        self._current_menu = None
        
    def display(self, menu_id: int = None, title: str = "Main Menu") -> Optional[Dict[str, Any]]:
        """
        Display SSH Menu UI with Rich Console + PIL Images.
        
        Features:
        ├─ Rich Console
        ├─ HP Bars (PIL Image)
        ├─ Battle Logs
        └─ Inventory Display
        
        Args:
            menu_id: Menu ID (1-9)
            title: Menu Title
        
        Returns:
            Dict mit: menu_id, title, ui_output
        
        """
        if not CLI_AVAILABLE or menu_id is None:
            return None
        
        # Get character data
        char = self.db.get_character() if self.db else None
        
        # Get inventory state
        inv_state = self.inventory.get_inventory_state() if self.inventory else None
        
        # Get shop state
        shop_state = self.shop.get_shop_state() if self.shop else None
        
        # Get battle logs
        battle_logs = []
        if hasattr(self.db, 'get_past_battles'):
            try:
                battles = self.db.get_past_battles(limit=5)
                battle_logs = [{"result": b.get("result", ""), "damage": b.get("damage", 0)} for b in battles]
            except:
                pass
        
        # Format UI with PIL + Rich
        ui_output = {
            "title": title,
            "version": self.VERSION,
            "menu_id": menu_id,
            "character": {
                "name": char.get("name", "Unbenannt") if char else "",
                "level": char.get("tier", 1) if char else 1,
                "class": char.get("class", "Krieger") if char else "Krieger",
                "hp": char.get("hp", 100) if char else 100,
                "max_hp": char.get("max_hp", 100) if char else 100,
                "atk": char.get("atk", 20) if char else 20,
                "def": char.get("def", 15) if char else 15
            },
            "inventory": {
                "slot_count": inv_state.get("slot_count", 0) if inv_state else 0,
                "equipped_count": inv_state.get("equipped_count", 0) if inv_state else 0
            },
            "shop": {
                "items_count": len(shop_state.get("items", [])) if shop_state else 0
            },
            "battle_history": battle_logs
        }
        
        # Render with Rich
        if CLI_AVAILABLE and menu_id:
            # HP-Balken (PIL Image)
            hp_progress = ui_output["character"]["hp"] / ui_output["character"]["max_hp"]
            hp_image = self._render_hp_bar(ui_output["character"]["hp"], ui_output["character"]["max_hp"])
            
            # Console output
            header = Text(ui_output["title"], style="bold white", justify="center")
            header_text = Text(f"Version: {ui_output['version']}\n", style="dim blue")
            
            # Character info
            char_info = f"[green]{ui_output['character']['name']}[/]"
            char_level = Text(f"Level {ui_output['character']['level']}", style="bold yellow")
            char_class = Text(f"[blue]{ui_output['character']['class']}[/]")
            
            # HP bar
            hp_bar = Text(f"{char_info} ({char_level}) [{char_class}]  ", style="white")
            hp_text = Text(str(hp_progress) + "%: ", style="black on magenta")
            hp_bar += hp_text
            hp_bar += Text(f"{ui_output['character']['hp']}/{ui_output['character']['max_hp']} HP", style="black on green")
            
            # Render with PIL
            if PIL_AVAILABLE:
                # HP Bar Image (optional - for display)
                hp_img = self._create_hp_image(char.get("hp", 100), char.get("max_hp", 100))
                
                # Store image
                ui_output["hp_bar_image"] = hp_img
            
            return ui_output
        
        return None

    def _create_hp_image(self, current_hp: int, max_hp: int) -> Optional[Image.Image]:
        """
        Create HP Bar Image with PIL.
        
        Args:
            current_hp: Current HP
            max_hp: Max HP
        
        Returns:
            PIL Image or None if PIL not installed
        """
        if not PIL_AVAILABLE:
            return None
        
        # Create background
        w, h = 200, 30
        
        # HP Progress
        progress = current_hp / max_hp
        
        # Create red bar
        img = Image.new("RGB", (w, h), "gray")
        draw = ImageDraw.Draw(img)
        
        # HP Green
        draw.rectangle([(2, 2), (w-5, h-2)], fill="green")
        draw.rectangle([(2, 2), (w-5 * progress, h-2)], fill="white")
        
        return img

    def _render_hp_bar(self, current_hp: int, max_hp: int) -> str:
        """
        Render HP bar to text representation.
        
        Args:
            current_hp: Current HP
            max_hp: Max HP
        
        Returns:
            HP bar string
        
        """
        if not RICH_AVAILABLE:
            return f"{current_hp}/{max_hp} HP"
        
        # HP Progress
        progress = current_hp / max_hp
        
        # Use Rich Panel
        return f"[green]{current_hp}[/] / [green]{max_hp}[/] HP ({progress:.0%})"

    def _get_last_battles(self, count: int = 10) -> list:
        """
        Get last battles from log.
        
        Args:
            count: Anzahl battles
        
        Returns:
            list of Battle-Entries
        
        """
        if not self.db:
            return []
        
        battles = self.db.get_past_battles(limit=count)
        return battles[:count] if battles else []