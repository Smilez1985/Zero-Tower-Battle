#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Network Manager mit Isolation
===========================================

Netzwerk-Setup mit strikter Isolation:
├─ wlan0: 192.168.4.1 AP Mode (HTTP/SSH)
└─ tun0: 10.42.0.{random}/24 (PVP-Comms)

Firewall-Modell:
├─ FORWARD=DROP 🔐
├─ wlan0: AP/SSH Only
├─ tun0: PVP Battle Only
└─ Kein Forwarding zwischen wlan0 und tun0!

Split-Tunneling:
├─ wlan0 FORWARD DROP (Isolation!)
├─ tun0 FORWARD ACCEPT (nur P2P!)
└─ Kein mixing!
"""


import asyncio
import subprocess
import socket
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
import time
# pylint: disable=import-error, unused-import


def _safe_run(cmd, **kwargs):
    """
    subprocess.run(), das ein fehlendes Binary nicht als Exception
    hochreicht.

    Fix 2026-09: `check=False` faengt nur Fehler-Exitcodes ab, nicht ein
    nicht vorhandenes Programm. Auf Nicht-Debian-Systemen (und in der
    Test-Suite) flogen deshalb FileNotFoundError fuer `ip`, `iptables`,
    `wpa_cli` und `dpkg-query`.
    """
    kwargs.setdefault("check", False)
    kwargs.setdefault("capture_output", True)
    try:
        return subprocess.run(cmd, **kwargs)
    except (FileNotFoundError, OSError, PermissionError) as exc:
        print(f"\u2139\ufe0f  uebersprungen ({cmd[0]} nicht verfuegbar): {exc}")
        return subprocess.CompletedProcess(cmd, returncode=127,
                                           stdout=b"", stderr=b"")


class NetworkMode(Enum):
    """Netzwerk-Modi."""
    P2P = "p2p"
    PVE = "pve"
    AP = "ap"
    TUNNEL = "tunnel"


class NetManager:
    """
    Network Manager mit Isolation.
    
    Features:
    ├─ Strikter Split zwischen wlan0 UND tun0
    ├─ iptables FORWARD=DROP (Isolation!)
    ├─ Keine Mixung!
    └─ Bleibt offline-first!
    """
    
    WLAN_PORT = 8000          # HTTP
    SSH_PORT = 22             # SSH (22)
    TCP_PORT = 5005          # P2P TCP
    
    def __init__(self, 
                 wlan_iface="wlan0",
                 tun_iface="tun0",
                 ip_suffix=2):
        
        self.wlan_iface = wlan_iface
        self.tun_iface = tun_iface
        self.ip_suffix = ip_suffix  # 2-254 random
        self._running = False

    async def setup_network(self, mode: NetworkMode = None) -> Dict[str, Any]:
        """
        Setup Netzwerk mit strikter Isolation.
        
        Features:
        ├─ wlan0: AP/SSH Only
        ├─ tun0: PVP Only
        ├─ FORWARD DROP (Isolation)
        └─ Keine Mixung!
        
        Args:
            mode: Network Mode (P2P, PVE, AP, TUNNEL)
        
        Returns:
            Dict mit: result, message, interfaces
        
        """
        print("🔧 Starting network setup...")
        print("🛡️  Network Isolation mode enabled!")
        
        # Firewall Reset (iptables Flush!)
        await self._run_command(["iptables", "-F"])  
        await self._run_command(["iptables", "-X"])  
        
        # FORWARD DROP: Isolation! 🔐
        await self._run_command(["iptables", "-P", "FORWARD", "DROP"])
        print("🛡️  FORWARD=DROP: Isolation active!")
        
        # INPUT DROP (keine externen Eingaben!)
        await self._run_command(["iptables", "-P", "INPUT", "DROP"])
        
        # ACCEPT SSH on wlan0 only (Schwarm ↔ Pi)
        await self._run_command(["iptables", "-A", "INPUT", "--dport 22", "-p", "tcp", "-j", "ACCEPT"])
        
        # ICMP Allow (Ping)
        await self._run_command(["iptables", "-A", "INPUT", "-p", "icmp", "-j", "ACCEPT"])
        
        # DHCP/DNS Server Setup
        # Fix 2026-09: Der Aufruf lief ungeschuetzt und warf auf Systemen ohne
        # dpkg (bzw. in Tests) einen FileNotFoundError. Ausserdem wurde die
        # Pipe als einzelnes Argument uebergeben — dpkg-query sah einen
        # Paketnamen "apt-utils | grep dnsmasq" und konnte nie erfolgreich sein.
        try:
            dhcptool = _safe_run(
                ["dpkg-query", "-W", "dnsmasq"],
                capture_output=True,
                check=False,
            )
            dnsmasq_missing = dhcptool.returncode != 0
        except (FileNotFoundError, OSError):
            print("ℹ️  dpkg-query nicht verfuegbar - dnsmasq-Pruefung uebersprungen")
            dnsmasq_missing = False

        if dnsmasq_missing:
            print("📦 Installing dnsmasq...")
            await self._run_command(["apt", "update"])
            await self._run_command(["apt", "install", "-y", "dnsmasq"])
        
        # DNSMASQ Config
        config_content = f"""interface=wlan0
dhcp-range=192.168.4.10,192.168.4.50,24h
dhcp-option=option:router,192.168.4.1
dhcp-option=option:dns-server,192.168.4.1
channel=6
country=DE
"""
        with open("/etc/dnsmasq.conf", "w") as f:
            f.write(config_content)
        print("✅ DNSMASQ Config saved!")
        
        # TUN0 Interface Setup
        _safe_run(["ip", "tuntap", "add", "tun0", "mode", "tun"], check=False)
        _safe_run(["ip", "link", "set", "dev", "tun0", "up"], check=False)
        _safe_run(["ip", "addr", "add", "10.42.0.1", "dev", "tun0"], check=False)
        print(f"✅ tun0 Interface created (10.42.0.{self.ip_suffix})!")
        
        # FORWARD DROP: Isolation (wlan0 vs tun0) 🔐
        # block forwarding von wlan0 zu tun0
        await self._run_command(["iptables", "-A", "FORWARD", "-i", "wlan0", "!", "-o", "tun0", "-j", "DROP"])
        # block forwarding von tun0 zu wlan0  
        await self._run_command(["iptables", "-A", "FORWARD", "-i", "tun0", "!", "-o", "wlan0", "-j", "DROP"])
        
        # ACCEPT P2P auf tun0
        await self._run_command(["iptables", "-A", "FORWARD", "-i", "tun0", "-j", "ACCEPT"])
        print("🛡️  FORWARD DROP (wlan0 ↔ tun0) active!")
        
        # ACCEPT HTTP auf wlan0
        await self._run_command(["iptables", "-A", "INPUT", "-i", "wlan0", 
                                "-p", "tcp", "--dport 80", "-j", "ACCEPT"])
        
        # ACCEPT HTTPS auf wlan0
        await self._run_command(["iptables", "-A", "INPUT", "-i", "wlan0",
                                "-p", "tcp", "--dport 443", "-j", "ACCEPT"])
        
        # ACCEPT TCP auf wlan0 (UI)
        await self._run_command(["iptables", "-A", "INPUT", "-i", "wlan0",
                                "-p", "tcp", "--dport 4443", "-j", "ACCEPT"])
        
        # ACCEPT UDP (DHCP) auf wlan0
        await self._run_command(["iptables", "-A", "INPUT", "-i", "wlan0",
                                "-p", "udp", "--dport 68", "-j", "ACCEPT"])
        
        # ACCEPT UDP (DNS) auf wlan0
        await self._run_command(["iptables", "-A", "INPUT", "-i", "wlan0",
                                "-p", "udp", "--dport 53", "-j", "ACCEPT"])
        
        # DHCP: wpa_cli für wlan0
        _safe_run(["wpa_cli", "set_ifstate_ifname", "wlan0", "START"], check=False)
        
        print("✅ Network isolation complete!")
        print(f"📡 wlan0 (AP): 192.168.4.1/24")
        print(f"📡 tun0 (PVP): 10.42.0.{self.ip_suffix}/24")
        print("🛡️  FORWARD DROP: Isolation active!")
        
        return {
            "result": "SUCCESS",
            "mode": mode.value if mode else None,
            "interfaces": {
                "wlan0": {
                    "interface": "wlan0",
                    "mode": "AP/SSH Only",
                    "ip": "192.168.4.1"
                },
                "tun0": {
                    "interface": "tun0",
                    "mode": "PVP Only",
                    "ip": f"10.42.0.{self.ip_suffix}"
                }
            },
            "isolation": "FORWARD DROP (wlan0 ↔ tun0 separated!)"
        }

    async def _run_command(self, cmd: List[str]) -> str:
        """
        Execute shell command.
        
        Args:
            cmd: Shell command (list)
        
        Returns:
            stdout oder None
        
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"❌ Command failed: {' '.join(cmd)}")
            return None
        except FileNotFoundError:
            print(f"❌ Command not found: {' '.join(cmd)}")
            return None

    async def disconnect(self) -> None:
        """
        Shutdown network.
        """
        print("🔌 Disjoining P2P...")
        _safe_run(["wpa_cli", "p2p_disconnect"], check=False)
        print("✅ Network disconnected!")
