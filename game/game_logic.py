#!/usr/bin/env python3
"""
Zero Tower Battle - Core Game Logic
PVE/PVP Switch + Game Loop
"""
import time
import os
import signal

class GameLogic:
    """
    Core Game Logic:
    - PVE (Autonom): Pi gestartet mit Delay
    - PVP (Spieler): BLE/WiFi Direct
    - Switch bei PvP gefunden
    - 512MB RAM Hot/Cold Storage
    """
    def __init__(self, engine):
        self.engine = engine
        self.mode = "PAUSED"
        self.level = 0
        self.enemies = []
        self.player_health = 100
        
    def start_pve_loop(self):
        """Start PVE Game Loop (Autonom)"""
        self.mode = "PVE"
        print(f"🎮 [PVE] Autonomous Mode: Pi kämpft durch Turm...")
        
        while self.mode == "PVE":
            self.ai_move_forward()
            self.check_enemy_encounters()
            self.save_progress()
            
            # Check for PvP Beacon (PVP Suche)
            if self.engine.ble_beacon.detect_player():
                print(f"🔔 [BEEF!] PvP Spieler gefunden!")
                self.switch_to_pvp()
                break
                
            time.sleep(1)  # Game Loop
            
    def ai_move_forward(self):
        """AI: Pi geht vorwärts (PVE)"""
        return True
        
    def check_enemy_encounters(self):
        """Check for enemies (PVE)"""
        return True
        
    def switch_to_pvp(self):
        """Switch PVE → PVP"""
        self.mode = "PVP"
        print(f"🤖 [SWITCH] PVE → PVP")
        if self.mode == "PVP":
            print("🎮 [PVP] Player Battle Mode aktiviert")
            
    def save_progress(self):
        """Save to Cold Storage (SD)"""
        return True
        
    def pause_on_disconnect(self):
        """Pause game when PvP disconnected"""
        self.mode = "PAUSED"
        print(f"⏸️  [PAUSED] PvP disconnected")

# Game Config
GAME_CONFIG = {
    "pve_delay": 30,  # Delay before autonom start
    "pvp_timeout": 60,  # Timeout for PvP
    "hot_storage_limit": 100*1024*1024,  # 100MB
    "cold_storage_limit": 412*1024*1024,  # 412MB
}

print(f"✅ [GAME] Config: {GAME_CONFIG}")
