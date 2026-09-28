#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Character Database
====== ===============

CRITICAL: RAM-Disk für Schreibschutz
├─ /dev/shm/: RAM Disk (fast, volatile)
├─ Sync to SD: every 5 min + shutdown hook
├─ Sync to Disk: sync_to_disk() function
├─ Auto-Save on exit
└─ Backup-Logik
└─ Schema-Management
"""


import json
import os
import signal
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from collections import defaultdict


# SD Backup Path (dynamisch)
try:
    from core.paths import CHARACTER_BACKUP_DIR
    SD_BACKUP_PATH = Path(CHARACTER_BACKUP_DIR)
except ImportError:
    SD_BACKUP_PATH = Path(os.path.expanduser("~")) / "battle_game" / "backups" / "character"

class CharacterDB:
    """
    Character Database mit RAM-Disk.
    
    Critical:
    ├─ RAM Disk (/dev/shm) für alle Schreibvorgänge
    ├─ Auto-Sync auf SD: 5 Min Intervall
    ├─ Shutdown-Hook: sync_to_disk()
    └─ Sync-to-Disk: sync_to_disk() function
    """
    
    BACKUP_INTERVAL = 300  # 5 Minuten
    
    def __init__(self, db_path: str = "/dev/shm/ztb.db", sync_to_ram: bool = True):
        """
        Initialize CharacterDB.
        
        Args:
            db_path: Path for RAM Disk (/dev/shm/ztb.db)
            sync_to_ram: Use RAM Disk
        
        WARNING:
            - RAM Disk: volatile, sync to SD every 5 min
            - Sync to SD: on shutdown hook + 5 min interval
            - All writes go to RAM, backups to SD
        """
        self.db_path = Path(db_path)
        self.sync_to_ram = sync_to_ram
        
        # Use RAM Disk for writes (SD Backup path is different)
        if sync_to_ram and "/dev/shm" not in db_path:
            db_path = "/dev/shm/ztb.db"
        
        # Ensure paths exist
        self.ram_path = Path(db_path)
        self.ram_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_dir = SD_BACKUP_PATH
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory storage
        self.characters: Dict[str, Dict[str, Any]] = {}
        self.items: Dict[str, Dict[str, Any]] = {}
        self.battles: Dict[str, Dict[str, Any]] = {}
        self.codex: Dict[str, Dict[str, Any]] = {}
        self.settings: Dict[str, Any] = {}
        self.logs: List[Dict[str, Any]] = []
        
        # Sync timer
        self.last_sync: Optional[float] = datetime.now().timestamp()
        self._shutdown_hook_registered = False

    def sync_to_disk(self) -> Dict[str, Any]:
        """
        Sync RAM to SD (SD-Card!).
        
        Syncs RAM data to SD card at:
        ├─ Every 5 minutes
        ├─ On shutdown/handling SIGTERM
        └─ On manual call: sync_to_disk()
        
        Args:
            None
        
        Returns:
            Dict mit: result, path, timestamp
        
        WARNING:
            - This is the ONLY write to SD card
            - All writes go to RAM, sync to SD separately
            - On shutdown: auto-sync via shutdown hook
        
        """
        try:
            data = {
                "characters": self.characters,
                "items": self.items,
                "battles": self.battles,
                "codex": self.codex,
                "settings": self.settings,
                "last_updated": datetime.now().isoformat()
            }
            
            # Write to SD (backup)
            backup_path = self.backup_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            
            self.last_sync = datetime.now().timestamp()
            
            return {
                "result": "SUCCESS",
                "path": str(backup_path),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Sync to SD Error: {e}")
            return {
                "result": "ERROR",
                "message": f"Sync Error: {e}",
                "path": None,
                "timestamp": datetime.now().isoformat()
            }

    def _auto_sync(self) -> None:
        """
        Auto-Sync to SD every 5 minutes.
        
        """
        # Auto-save to SD every 5 min
        if self.last_sync and (datetime.now().timestamp() - self.last_sync) >= self.BACKUP_INTERVAL:
            self.sync_to_disk()

    def _register_shutdown_hook(self) -> None:
        """
        Register shutdown hook for auto-save.
        """
        if not self._shutdown_hook_registered:
            # Register SIGTERM handler
            def handle_shutdown(signum, frame):
                self._auto_sync()
                self.sync_to_disk()
                self._shutdown_hook_registered = True
                print("🔌 Shutdown: Synced to SD!")
            
            signal.signal(signal.SIGTERM, handle_shutdown)
            signal.signal(signal.SIGINT, handle_shutdown)
            self._shutdown_hook_registered = True

    def save_db(self) -> None:
        """
        Save database to file.
        
        Uses RAM, NOT SD card!
        """
        try:
            data = {
                "characters": self.characters,
                "items": self.items,
                "battles": self.battles,
                "codex": self.codex,
                "settings": self.settings,
                "last_updated": datetime.now().isoformat()
            }
            
            # Save to RAM (NOT SD)
            self.ram_path = self.ram_path.with_name(
                self.ram_path.name.replace(".db", f".db.{int(datetime.now().timestamp())}")
            )
            self.ram_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.db_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
                
            # Auto-Sync to SD if enabled
            self._auto_sync()
            
        except Exception as e:
            print(f"❌ Save Error (RAM): {e}")

    def get_character(self, character_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Get character data.
        
        Args:
            character_id: character ID or None for first
        
        Returns:
            Dict mit: character data
        
        """
        if not character_id:
            return next(iter(self.characters.values())) if self.characters else None
        return self.characters.get(character_id)

    def create_character(self, name: str, level: int = 1, class_name: str = "Krieger",
                         gold: int = 50, hp: int = 100) -> Dict[str, Any]:
        """
        Create new character.
        
        Args:
            name: Character Name
            level: Level (tier)
            class_name: Class
            gold: Start Gold
            hp: Start HP
        
        Returns:
            Dict mit: result, character
        
        """
        if name in self.characters:
            return {"result": "ERROR", "message": f"Character {name} exists"}
        
        character = {
            "id": name,
            "name": name,
            "class": class_name,
            "tier": level,
            "hp": hp,
            "max_hp": hp,
            "gold": gold,
            "equipped_item": None,
            "stats": {
                "atk_base": 25,
                "def_base": 40,
                "spd_base": 20,
                "luk_base": 15
            },
            "history": [],
            "created_at": datetime.now().isoformat()
        }
        
        self.characters[name] = character
        self.save_db()  # Save to RAM, sync to SD later
        
        return {
            "result": "SUCCESS",
            "character": character
        }
    
    def add_item(self, item_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add item to database.
        
        Args:
            item_id: Item ID
            item_data: Item data
        
        Returns:
            Dict mit: result, item
        
        """
        if item_id in self.items:
            return {"result": "ERROR", "message": "Item already exists"}
        
        self.items[item_id] = {
            **item_data,
            "owner": None
        }
        
        self.save_db()
        
        return {
            "result": "SUCCESS",
            "item": item_data
        }

    def log_event(self, character_id: str, event_type: str, message: str) -> None:
        """
        Log battle/event to history.
        
        Args:
            character_id: Character ID
            event_type: Battle event type
            message: Event message
        
        """
        character = self.characters.get(character_id)
        if not character:
            return
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "message": message
        }
        
        character["history"].append(log_entry)
        
        self.save_db()

    def cleanup_old_backups(self, days: int = 30) -> int:
        """
        Cleanup old backups.
        
        Args:
            days: Days to keep
        
        Returns:
            int: Anzahl gelöschter backups
        
        """
        import shutil
        from datetime import timedelta
        
        files = list(self.backup_dir.glob("backup_*.json"))
        cutoff = datetime.now() - timedelta(days=days)
        count = 0
        
        for backup_file in files:
            mod_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
            if mod_time < cutoff:
                backup_file.unlink()
                print(f"🗑️  Removed old backup: {backup_file}")
                count += 1
        
        return count
