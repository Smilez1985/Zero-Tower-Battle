#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - SSH Menu System
====== ==============

SSH-Menü:
├─ SSH-Login Logik
├─ Menü-Optionen
├─ User Selection
├─ Password Management
└─ UI Integration
"""

import os
import subprocess
from typing import Dict, List, Any
from datetime import datetime


class SSHMenu:
    """SSH Menü für Battle-Pi."""
    
    def __init__(self, users_file="/etc/hosts"):
        self.users_file = users_file
        self.selected_user = None
        self.password = None
        self.menu_options = [
            {"id": "login", "title": "🔐 SSH Login", "action": self.login_option},
            {"id": "user_select", "title": "👤 User Select", "action": self.user_select},
            {"id": "restart", "title": "🔄 System Restart", "action": self.restart},
            {"id": "shutdown", "title": "⏻ System Shutdown", "action": self.shut_down},
            {"id": "status", "title": "📊 System Status", "action": self.status},
            {"id": "exit", "title": "❌ Exit", "action": self.exit}
        ]
        self.is_connected = False
        self.session_id = f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
    def get_menu_options(self) -> List[Dict]:
        """Get available menu options."""
        return self.menu_options
        
    def login_option(self) -> Dict:
        """Handle SSH login option."""
        if not self.is_connected:
            return {
                "status": "NOT_CONNECTED",
                "message": "Bitte user_select zuerst",
                "action_required": "user_select"
            }
        
        return {
            "status": "LOGIN_REQUEST",
            "message": f"Login fuer {self.selected_user}",
            "session_id": self.session_id
        }
    
    def user_select(self, user: str = None) -> Dict:
        """Handle user selection."""
        self.selected_user = user or self._get_default_user()
        self.password = self._generate_password()
        
        return {
            "status": "USER_SELECTED",
            "user": self.selected_user,
            "password_set": self.password is not None,
            "session_id": self.session_id
        }
    
    def _get_default_user(self) -> str:
        """Get default user (smilez)."""
        try:
            with open(self.users_file, 'r') as f:
                for line in f:
                    if 'pi' in line or 'smilez' in line:
                        return line.split()[0].split(':')[0]
            return "smilez"
        except:
            return "smilez"
    
    def _generate_password(self) -> str:
        """Generate random password (simulation)."""
        return f"bt_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    def restart(self) -> Dict:
        """Restart system."""
        try:
            subprocess.run("/sbin/reboot &", shell=True)
            return {
                "status": "RESTARTING",
                "message": "System wird neustartiert",
                "session_id": self.session_id
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e)
            }
    
    def shut_down(self) -> Dict:
        """Shut down system."""
        try:
            subprocess.run("/sbin/hwclock --halt -f /proc/uptime &", shell=True)
            return {
                "status": "SHUTTING_DOWN",
                "message": "System wird heruntergefahren",
                "session_id": self.session_id
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e)
            }
    
    def status(self) -> Dict:
        """Get system status."""
        return {
            "status": "CONNECTED" if self.is_connected else "NOT_CONNECTED",
            "user": self.selected_user if self.selected_user else "not selected",
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat()
        }
    
    def exit(self) -> Dict:
        """Exit menu."""
        self.is_connected = False
        return {
            "status": "EXITED",
            "message": "Exit",
            "session_id": self.session_id
        }


if __name__ == "__main__":
    # Test ssh_menu.py
    ssh_menu = SSHMenu()
    print("SSH Menu initialized!")
    print("Options:")
    for option in ssh_menu.get_menu_options():
        print(f"  [{option['title']}] - {option['id']}")
