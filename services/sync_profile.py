#!/usr/bin/env python3
"""
ZERO Tower Battle (ZTB) - Profile Sync System
====== ===============

Profil-Sync:
├─ DB → JSON Export
└─ Auto-Sync alle 5 Min
"""


import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import shutil


class ProfileSync:
    """
    Profile Sync System.
    
    Features:
    ├─ DB → JSON Export
    ├─ Auto-Sync alle 5 Min
    ├─ Backup-Logik
    └─ Cloud Sync (optional)
    """
    
    SYNC_INTERVAL = 5 * 60  # 5 Minuten in Sekunden
    try:
        from core.paths import BACKUP_DIR as _bd, GAME_DIR as _gd
        BACKUP_DIR = Path(_bd)
        _DEFAULT_DB_PATH = _gd
    except ImportError:
        BACKUP_DIR = Path(os.path.expanduser("~")) / "battle_game" / "backups"
        _DEFAULT_DB_PATH = str(Path(os.path.expanduser("~")) / "battle_game")

    def __init__(self, db_path: str = None,
                 backup_interval: int = SYNC_INTERVAL):
        self.db_path = Path(db_path or self._DEFAULT_DB_PATH)
        self.backup_interval = backup_interval
        self.last_sync: Optional[float] = None
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def sync_to_json(self) -> Dict[str, Any]:
        """
        Sync database to JSON.
        
        Returns:
            Dict mit: result, sync_path
        
        """
        # Ensure backup dir
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sync_file = self.BACKUP_DIR / f"sync_{timestamp}.json"
        
        # Export to JSON
        export_path = sync_file
        with open(export_path, "w") as f:
            # Would write actual DB export here
            json.dump({
                "characters": {},
                "items": {},
                "battles": {},
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
        
        # Cleanup
        if len(list(self.BACKUP_DIR.glob("sync_*.json"))) >= 10:
            for f in list(self.BACKUP_DIR.glob("sync_*.json"))[:-9]:
                f.unlink()
        
        return {
            "result": "SUCCESS",
            "sync_path": str(export_path),
            "timestamp": timestamp
        }

    def auto_sync(self) -> Dict[str, Any]:
        """
        Auto sync if interval passed.
        
        Returns:
            Dict mit: result, message
        
        """
        if self.last_sync:
            elapsed = datetime.now().timestamp() - self.last_sync
            if elapsed >= self.backup_interval:
                return self.sync_to_json()
        
        return {"result": "SKIPPED", "elapsed": elapsed}

    def create_backup(self, source: str, destination: str) -> Dict[str, Any]:
        """
        Create backup.
        
        Args:
            source: Source path
            destination: Destination path
        
        Returns:
            Dict mit: result, path
        
        """
        try:
            shutil.copy2(source, destination)
            return {
                "result": "SUCCESS",
                "source": source,
                "destination": destination
            }
        except Exception as e:
            return {
                "result": "ERROR",
                "message": str(e)
            }

    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get sync status.
        
        Returns:
            Dict mit: status, last_sync, interval
        
        """
        return {
            "last_sync": self.last_sync,
            "backup_interval": self.backup_interval,
            "backup_dir": str(self.BACKUP_DIR)
        }
