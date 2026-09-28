#!/usr/bin/env python3
"""
Zero Tower Battle - SSH Access
Pi Zero 2W Headless Mode
"""

import argparse
import subprocess
import sys
import json

class SSHManager:
    def __init__(self):
        self.host = os.environ.get("ZTB_SSH_HOST", "127.0.0.1")  # Default IP
        self.port = 22
        self.user = "pi"
    
    def get_status(self, host=None):
        status = {
            "ssh_port": 22,
            "user": "pi",
            "mode": "headless",
            "wifi": "enabled"
        }
        return status
    
    def start_game(self):
        status = self.get_status()
        return status
    
    def access_ssh(self, host=None, port=22, user="pi"):
        """SSH access info"""
        if host:
            host = host
        info = {
            "ssh_command": f"ssh {user}@{host} -p {port}",
            "port": port,
            "user": user
        }
        return info

def main():
    manager = SSHManager()
    
    print("=" * 50)
    print("🎮 ZERO TOWER BATTLE - SSH ACCESS")
    print("==" * 25)
    
    status = manager.get_status()
    print("\n📊 System Status:")
    for k, v in status.items():
        print(f"    {k}: {v}")
    
    print("\n🔑 SSH Access:")
    info = manager.access_ssh()
    print(f"    Command: {info['ssh_command']}")
    print(f"    Port: {info['port']}")
    print(f"    User: {info['user']}")
    
    print("\n🎮 Game Commands (via SSH):")
    print("    ssh pi@<ip> -p 22 'start_game.sh'")
    print("    ssh pi@<ip> -p 22 'battle_main.py'")
    print("    ssh pi@<ip> -p 22 'status.sh'")
    
    print("\n✅ Headless SSH Ready!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
