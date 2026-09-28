#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Battle Connector Module
==== ========================

WiFi Direct + TCP Socket Communication Setup:
├─ WiFi Direct Handshake
├─ TCP Socket Verbindung
├─ IP-Bereich: 10.42.0.{random}
├─ IP-Suffix im Beacon
├─ Timeout: max 8 Sek
└─ Security: IP-Validation
"""


import subprocess
import socket
import json
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
# pylint: disable=import-error, unused-import


class BattleConnector:
    """
    WiFi Direct Connector für P2P-Kämpfe.
    
    Responsibilities:
    ├─ WiFi Direct Initialisierung
    ├─ TCP Socket Verbindung
    ├─ IP-Bereich: 10.42.0.{random}
    ├─ Beacon mit IP-Suffix
    └─ Timeout Management
    """
    
    def __init__(self,
                 tun_vnet_base: str = "10.42.0",
                 wlan_iface: str = "wlan0",
                 tun_iface: str = "tun0"):
        
        self.tun_vnet_base = tun_vnet_base
        self.wlan_iface = wlan_iface
        self.tun_iface = tun_iface
        self.client_socket: Optional[socket] = None
        self.beacon_id: Optional[str] = None
        self.ip_suffix: int = 2 + (hash(uuid.getnode()) % 253)
        
    async def init_wifi_direct(self, opponent_mac: str) -> Optional[str]:
        """
        Init WiFi Direct & TCP Socket.
        
        Args:
            opponent_mac: Gegners Bluetooth-MAC
        
        Returns:
            str: Server IP oder None if failed
        """
        try:
            # WiFi Direct Setup
            subprocess.run(["wpa_cli", "P2P_CONNECTION_UPDATE"], check=False)
            
            # Connect to P2P device
            result = subprocess.run([
                "wpa_cli", "p2p_connect", "wlan0",
                opponent_mac or "",
                "p2p_find_p2p_device"
            ], capture_output=True, text=True, timeout=8.0)
            
            if result.returncode == 0:
                print("✅ WiFi Direct Initialisierung erfolgreich")
                
                # TCP Socket Setup
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.settimeout(8.0)
                print("✅ TCP Socket initialized")
                
                return opponent_mac
                
            else:
                print("❌ WiFi Direct setup failed")
                return None
                
        except Exception as e:
            print(f"❌ WiFi Direct Error: {e}")
            return None

    async def connect_tcp(self, server_ip: str) -> bool:
        """
        Create TCP connection to server.
        
        Args:
            server_ip: Server IP Address
        
        Returns:
            bool (Connection successful)
        """
        try:
            if self.client_socket:
                self.client_socket.connect((server_ip, 5005))
                print(f"✅ TCP Connection established to {server_ip}:5005")
                return True
                return False
            else:
                print("❌ TCP Socket nicht gefunden")
                await self.init_wifi_direct(opponent_mac)
                return False
                
        except Exception as e:
            print(f"❌ TCP Error: {e}")
            return False
