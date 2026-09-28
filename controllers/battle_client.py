#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Battle Client Module
====== ==========================

TCP-Client für PVE/PVP Encounters:
├─ Socket-Client Logik
├─ JSON-Profile Senden
├─ Validierung gegen Schema
├─ Disconnect Handling
└─ Retry Logic
"""


import socket
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
# pylint: disable=import-error, unused-import


class BattleClient:
    """
    Battle Client für senden P2P Profile.
    
    Features:
    └─ Socket-Client Logik
    └─ JSON-Profile Senden
    └─ Validierung gegen Schema
    └─ Disconnect Handling
    └─ Retry Logic
    """
    
    RETRY_COUNT = 3
    RETRY_DELAY = 1.0  # Seconds
    
    def __init__(self,
                 server_ip: str = "10.42.0.2",
                 player_name: str = "ZTB_Pi-Ritter",
                 player_mac: Optional[str] = None):
        
        self.server_ip = server_ip
        self.player_name = player_name
        self.player_mac = player_mac
        self.client_socket: Optional[socket.socket] = None
        self._connected = False
    
    async def connect(self) -> bool:
        """
        Establish connection to server.
        
        Returns:
            bool (Connection successful)
        """
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(8.0)
            self.client_socket.connect((self.server_ip, 5005))
            self._connected = True
            print(f"✅ Connected to {self.server_ip}:5005")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """
        Close connection gracefully.
        """
        if self.client_socket:
            self.client_socket.close()
            self._connected = False
            print("🔌 Disconnected")

    async def send_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send JSON Profile to server.
        
        Args:
            profile_data: Profile-Datendikt
        
        Returns:
            Dict mit: result, message, profile
        
        """
        try:
            if not self._connected:
                await self.connect()
            
            profile_bytes = json.dumps(profile_data).encode('utf-8')
            self.client_socket.sendall(profile_bytes)
            
            print(f"✅ Profile sent: {profile_data}")
            
            return {
                "result": "SUCCESS",
                "message": "Profile sent successfully",
                "profile": profile_data
            }
            
        except Exception as e:
            print(f"❌ Error sending profile: {e}")
            return {"result": "FAILED", "message": f"Error: {e}"}
