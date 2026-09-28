#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - PVP Cooldown Manager
================================================
Verwaltet den 30-Minuten-Cooldown pro gegnerischer MAC-Adresse.

Regeln (laut Spec):
  - Nach einem PVP-Kampf gegen eine MAC: 30 Min Sperre
  - Verschiedene MACs koennen parallel bekaempft werden
  - Cooldown wird in Hot Storage gehalten (fluechtig)
  - Bei Neustart: alle Cooldowns reset (kein Exploit moeglich)

Referenz: Battle-Pi_Konsolidiert.txt Abschnitt 8
"""

import time
from typing import Dict, Any, Optional, List


# =============================================
# Konstanten
# =============================================

PVP_COOLDOWN_SECONDS = 30 * 60  # 30 Minuten = 1800 Sekunden
MAX_TRACKED_MACS = 100          # Speicher-Limit (Pi Zero Schutz)


# =============================================
# PVP Cooldown Manager
# =============================================

class PVPCooldownManager:
    """
    Verwaltet PVP-Cooldowns pro gegnerischer MAC-Adresse.

    In-Memory (Hot Storage): Geht bei Neustart verloren.
    Das ist gewollt: Kein Exploit durch Neustart moeglich,
    da der Gegner ebenfalls den Cooldown hat.
    """

    def __init__(self, cooldown_seconds: int = PVP_COOLDOWN_SECONDS):
        """
        Args:
            cooldown_seconds: Cooldown-Dauer in Sekunden (Standard: 1800 = 30 Min)
        """
        self._cooldown_seconds = cooldown_seconds
        self._last_fight: Dict[str, float] = {}  # MAC -> Timestamp

    # -----------------------------------------
    # Cooldown pruefen
    # -----------------------------------------

    def can_fight(self, mac_address: str) -> Dict[str, Any]:
        """
        Pruefe ob PVP gegen diese MAC erlaubt ist.

        Args:
            mac_address: BLE-MAC des Gegners (uppercase, z.B. "AA:BB:CC:DD:EE:FF")

        Returns:
            Dict mit: allowed, remaining_seconds, message
        """
        mac = mac_address.upper().strip()
        now = time.time()

        last = self._last_fight.get(mac)
        if last is None:
            return {
                "allowed": True,
                "remaining_seconds": 0,
                "message": "Kein Cooldown aktiv."
            }

        elapsed = now - last
        remaining = self._cooldown_seconds - elapsed

        if remaining <= 0:
            # Cooldown abgelaufen -> bereinigen
            del self._last_fight[mac]
            return {
                "allowed": True,
                "remaining_seconds": 0,
                "message": "Cooldown abgelaufen."
            }

        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        return {
            "allowed": False,
            "remaining_seconds": int(remaining),
            "message": f"PVP-Cooldown: noch {minutes}m {seconds}s gegen diese MAC."
        }

    # -----------------------------------------
    # Cooldown registrieren
    # -----------------------------------------

    def register_fight(self, mac_address: str) -> None:
        """
        PVP-Kampf registrieren (Cooldown starten).

        Args:
            mac_address: BLE-MAC des Gegners
        """
        mac = mac_address.upper().strip()

        # Speicher-Limit: Aelteste entfernen
        if len(self._last_fight) >= MAX_TRACKED_MACS:
            self._cleanup_expired()

        self._last_fight[mac] = time.time()

    # -----------------------------------------
    # Cleanup
    # -----------------------------------------

    def _cleanup_expired(self) -> int:
        """Abgelaufene Cooldowns entfernen."""
        now = time.time()
        expired = [
            mac for mac, ts in self._last_fight.items()
            if (now - ts) >= self._cooldown_seconds
        ]
        for mac in expired:
            del self._last_fight[mac]
        return len(expired)

    def get_active_cooldowns(self) -> List[Dict[str, Any]]:
        """Alle aktiven Cooldowns auflisten."""
        now = time.time()
        active = []
        for mac, ts in self._last_fight.items():
            remaining = self._cooldown_seconds - (now - ts)
            if remaining > 0:
                active.append({
                    "mac": mac,
                    "remaining_seconds": int(remaining),
                    "started_at": ts
                })
        return active

    def reset_all(self) -> int:
        """Alle Cooldowns zuruecksetzen (z.B. bei Admin-Reset)."""
        count = len(self._last_fight)
        self._last_fight.clear()
        return count


# =============================================
# Standalone-Test
# =============================================

if __name__ == "__main__":
    mgr = PVPCooldownManager(cooldown_seconds=5)  # 5s fuer Test

    mac1 = "AA:BB:CC:DD:EE:01"
    mac2 = "AA:BB:CC:DD:EE:02"

    # Erster Kampf: erlaubt
    print(f"Vor Kampf: {mgr.can_fight(mac1)}")

    # Kampf registrieren
    mgr.register_fight(mac1)
    print(f"Nach Kampf: {mgr.can_fight(mac1)}")

    # Andere MAC: erlaubt
    print(f"Andere MAC: {mgr.can_fight(mac2)}")

    # Aktive Cooldowns
    print(f"Aktive Cooldowns: {mgr.get_active_cooldowns()}")

    # Warten und nochmal pruefen
    print("Warte 6s...")
    time.sleep(6)
    print(f"Nach 6s: {mgr.can_fight(mac1)}")
    print("Test abgeschlossen.")
