#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - BLE Beacon Module
=============================================
BLE-basierte PVP-Erkennung und Gossip-Austausch.

Verwendet bleak (async BLE library) fuer:
  - BLE-Scan nach anderen ZTB-Pis (Manufacturer Data 0xFEAA)
  - BLE-Advertising des eigenen Beacons
  - Beacon-Parsing (31 Byte Payload)

Beacon-Format (31 Bytes):
  [0:2]   Magic: 0x5A54 ("ZT")
  [2:3]   Version: 0x01
  [3:4]   Flags: Bit0=PVP_Ready, Bit1=Gossip, Bit2=WorldBoss
  [4:20]  Player Name (UTF-8, zero-padded)
  [20:22] Player Level (uint16 LE)
  [22:24] Current Floor (uint16 LE)
  [24:26] PVP Wins (uint16 LE)
  [26:27] Class Type (0=Stein, 1=Schere, 2=Papier)
  [27:31] Checksum (CRC32 der Bytes 0-26)

WiFi-Direct Bridge:
  - wpa_cli P2P-Gruppe (GO-Negotiation)
  - TCP-Tunnel fuer Kampfdaten-Austausch (AES-256-GCM verschluesselt)
  - Simulation-Mode fuer 1-Pi-Tests (localhost Loopback)

Referenz: Battle-Pi_Konsolidiert.txt Abschnitte 7, 8
"""

import asyncio
import json
import os
import struct
import subprocess
import time
import zlib
from typing import Dict, Any, Optional, List, Tuple


# =============================================
# Konstanten
# =============================================

ZTB_MAGIC = b"\x5A\x54"         # "ZT"
ZTB_BEACON_VERSION = 0x01
ZTB_MANUFACTURER_ID = 0xFEAA    # BLE Manufacturer Data Key
ZTB_BEACON_SIZE = 31

# Flags
FLAG_PVP_READY = 0x01
FLAG_GOSSIP = 0x02
FLAG_WORLDBOSS = 0x04

# Class-Type Mapping
CLASS_MAP = {"Stein": 0, "Schere": 1, "Papier": 2}
CLASS_MAP_REV = {0: "Stein", 1: "Schere", 2: "Papier"}

# Scan-Parameter
DEFAULT_SCAN_TIMEOUT = 5.0       # Sekunden
MIN_RSSI = -85                   # Minimale Signalstaerke

# WiFi-Direct Konstanten
P2P_INTERFACE = "p2p-wlan0-0"    # Typischer P2P-Interfacename
P2P_GO_INTENT = 7                # GO-Intent (0-15, 15=immer GO)
P2P_FIND_TIMEOUT = 10            # Sekunden fuer p2p_find
P2P_CONNECT_TIMEOUT = 15         # Sekunden fuer Verbindungsaufbau
P2P_DATA_PORT = 42042            # TCP-Port fuer Daten-Tunnel
P2P_IP_PREFIX = "192.168.49"     # Standard WiFi-Direct IP-Bereich
P2P_BUFFER_SIZE = 65536          # TCP-Buffer (64 KB)
P2P_EXCHANGE_TIMEOUT = 10        # Timeout fuer Datenaustausch

# Simulation
SIMULATION_MODE = False          # Wird per set_simulation_mode() gesetzt


def set_simulation_mode(enabled: bool) -> None:
    """Simulation-Mode fuer 1-Pi-Tests aktivieren/deaktivieren."""
    global SIMULATION_MODE
    SIMULATION_MODE = enabled


# =============================================
# Beacon Builder / Parser
# =============================================

class BLEBeaconBuilder:
    """Erstellt und parst ZTB BLE-Beacons."""

    @staticmethod
    def build_beacon(character: Dict[str, Any],
                     pvp_ready: bool = True,
                     gossip: bool = True,
                     worldboss: bool = False) -> bytes:
        """
        31-Byte Beacon aus Character-Dict erstellen.

        Args:
            character: Charakter-Dict
            pvp_ready: PVP bereit?
            gossip: Gossip-Modus aktiv?
            worldboss: Weltboss-Suche aktiv?

        Returns:
            31 Bytes Beacon-Payload
        """
        # Flags
        flags = 0x00
        if pvp_ready:
            flags |= FLAG_PVP_READY
        if gossip:
            flags |= FLAG_GOSSIP
        if worldboss:
            flags |= FLAG_WORLDBOSS

        # Name: 16 Bytes, zero-padded
        name = character.get("name", "Unknown")[:16]
        name_bytes = name.encode("utf-8").ljust(16, b"\x00")

        # Stats
        level = min(65535, character.get("level", 1))
        floor = min(65535, character.get("current_floor", 1))
        pvp_wins = min(65535, character.get("pvp_wins", 0))
        class_name = character.get("class_type", character.get("class_name", "Stein"))
        class_id = CLASS_MAP.get(class_name, 0)

        # Pack: magic(2) + version(1) + flags(1) + name(16) + level(2)
        #       + floor(2) + pvp(2) + class(1) = 27 Bytes
        payload = struct.pack(
            "<2sBB16sHHHB",
            ZTB_MAGIC,
            ZTB_BEACON_VERSION,
            flags,
            name_bytes,
            level,
            floor,
            pvp_wins,
            class_id
        )

        # CRC32 Checksum (4 Bytes)
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        beacon = payload + struct.pack("<I", crc)

        assert len(beacon) == ZTB_BEACON_SIZE
        return beacon

    @staticmethod
    def parse_beacon(data: bytes) -> Optional[Dict[str, Any]]:
        """
        31-Byte Beacon parsen.

        Args:
            data: 31 Bytes rohe Beacon-Daten

        Returns:
            Dict mit: name, level, floor, pvp_wins, class_type, flags
            oder None bei ungueltigem Beacon
        """
        if len(data) < ZTB_BEACON_SIZE:
            return None

        # Magic pruefen
        if data[0:2] != ZTB_MAGIC:
            return None

        # Version pruefen
        version = data[2]
        if version != ZTB_BEACON_VERSION:
            return None

        # CRC pruefen
        payload = data[:27]
        expected_crc = struct.unpack("<I", data[27:31])[0]
        actual_crc = zlib.crc32(payload) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            return None

        # Flags
        flags = data[3]

        # Name
        name_bytes = data[4:20]
        name = name_bytes.rstrip(b"\x00").decode("utf-8", errors="replace")

        # Stats
        level, floor, pvp_wins, class_id = struct.unpack("<HHHB", data[20:27])

        return {
            "name": name,
            "level": level,
            "floor": floor,
            "pvp_wins": pvp_wins,
            "class_type": CLASS_MAP_REV.get(class_id, "Stein"),
            "flags": {
                "pvp_ready": bool(flags & FLAG_PVP_READY),
                "gossip": bool(flags & FLAG_GOSSIP),
                "worldboss": bool(flags & FLAG_WORLDBOSS),
            },
            "version": version,
            "valid": True
        }


# =============================================
# BLE Scanner (async, bleak-basiert)
# =============================================

class BLEScanner:
    """
    Async BLE-Scanner fuer ZTB-Geraete.

    Nutzt bleak.BleakScanner um nach Manufacturer Data 0xFEAA
    zu suchen und ZTB-Beacons zu parsen.
    """

    def __init__(self):
        self._available = None    # None = nicht getestet
        self._last_scan_time = 0.0
        self._last_results: List[Dict[str, Any]] = []

    async def check_availability(self) -> bool:
        """
        Pruefen ob BLE-Adapter vorhanden und nutzbar ist.
        Ergebnis wird gecacht.
        """
        if self._available is not None:
            return self._available

        # Simulation: BLE immer verfuegbar
        if SIMULATION_MODE:
            self._available = True
            return True

        try:
            from bleak import BleakScanner
            # Kurzer Test-Scan (0.5s) um Adapter zu pruefen
            await BleakScanner.discover(timeout=0.5)
            self._available = True
        except ImportError:
            print("[BLE] bleak nicht installiert")
            self._available = False
        except Exception as e:
            # Kein Adapter, Permission-Problem, etc.
            print(f"[BLE] Adapter nicht verfuegbar: {e}")
            self._available = False

        return self._available

    async def scan_for_ztb_devices(
        self,
        timeout: float = DEFAULT_SCAN_TIMEOUT
    ) -> List[Dict[str, Any]]:
        """
        BLE-Scan nach ZTB-Geraeten durchfuehren.

        Sucht nach Manufacturer Data mit Key 0xFEAA,
        parst ZTB-Beacons und filtert nach Signalstaerke.

        Args:
            timeout: Scan-Dauer in Sekunden

        Returns:
            Liste von erkannten ZTB-Geraeten mit:
            - mac: BLE-Adresse
            - rssi: Signalstaerke
            - name: Spieler-Name (aus Beacon)
            - beacon: Geparstes Beacon-Dict
        """
        if not await self.check_availability():
            return []

        # Simulation: Fake-Device zurueckgeben
        if SIMULATION_MODE:
            return self._simulate_scan()

        found_devices = []
        self._last_scan_time = time.time()

        try:
            from bleak import BleakScanner

            devices = await BleakScanner.discover(
                timeout=timeout,
                return_adv=True
            )

            for device, adv_data in devices.values():
                # Manufacturer Data pruefen
                mfr_data = adv_data.manufacturer_data
                if ZTB_MANUFACTURER_ID not in mfr_data:
                    continue

                raw_beacon = bytes(mfr_data[ZTB_MANUFACTURER_ID])
                beacon = BLEBeaconBuilder.parse_beacon(raw_beacon)

                if beacon is None:
                    continue

                rssi = adv_data.rssi if hasattr(adv_data, "rssi") else -100

                # Signalstaerke-Filter
                if rssi < MIN_RSSI:
                    continue

                found_devices.append({
                    "mac": device.address,
                    "rssi": rssi,
                    "name": beacon["name"],
                    "level": beacon["level"],
                    "floor": beacon["floor"],
                    "pvp_wins": beacon["pvp_wins"],
                    "class_type": beacon["class_type"],
                    "flags": beacon["flags"],
                    "found": True,
                    "beacon_raw": raw_beacon,
                })

        except Exception as e:
            print(f"[BLE] Scan-Fehler: {e}")

        self._last_results = found_devices
        return found_devices

    async def scan_simple(self, timeout: float = DEFAULT_SCAN_TIMEOUT) -> Dict[str, Any]:
        """
        Vereinfachter Scan — gibt das erste gefundene ZTB-Geraet zurueck.
        Wird vom Orchestrator aufgerufen.

        Returns:
            Dict mit found=True/False und ggf. Geraete-Details
        """
        devices = await self.scan_for_ztb_devices(timeout)

        if not devices:
            return {
                "found": False,
                "scan_time": time.time(),
                "devices_count": 0
            }

        # Bestes Geraet (staerkstes Signal)
        best = max(devices, key=lambda d: d.get("rssi", -100))

        return {
            "found": True,
            "mac": best["mac"],
            "rssi": best["rssi"],
            "name": best["name"],
            "level": best["level"],
            "floor": best["floor"],
            "class_type": best["class_type"],
            "flags": best["flags"],
            "devices_count": len(devices),
            "all_devices": devices,
            "scan_time": time.time()
        }

    def _simulate_scan(self) -> List[Dict[str, Any]]:
        """Simulierten BLE-Scan-Ergebnis fuer 1-Pi-Tests erzeugen."""
        sim_char = {
            "name": "SimGegner",
            "level": 10,
            "current_floor": 50,
            "pvp_wins": 3,
            "class_type": "Schere"
        }
        sim_beacon = BLEBeaconBuilder.build_beacon(sim_char)
        parsed = BLEBeaconBuilder.parse_beacon(sim_beacon)

        self._last_scan_time = time.time()
        self._last_results = [{
            "mac": "SIM:00:00:00:00:01",
            "rssi": -45,
            "name": parsed["name"],
            "level": parsed["level"],
            "floor": parsed["floor"],
            "pvp_wins": parsed["pvp_wins"],
            "class_type": parsed["class_type"],
            "flags": parsed["flags"],
            "found": True,
            "beacon_raw": sim_beacon,
            "simulated": True,
        }]
        return self._last_results

    @property
    def last_results(self) -> List[Dict[str, Any]]:
        """Ergebnisse des letzten Scans."""
        return self._last_results

    @property
    def last_scan_time(self) -> float:
        """Zeitpunkt des letzten Scans (Unix-Timestamp)."""
        return self._last_scan_time


# =============================================
# WiFi-Direct Bridge (wpa_cli P2P)
# =============================================

class WiFiDirectBridge:
    """
    WiFi-Direct (P2P) Verbindung fuer PVP-Datentransfer.

    Nutzt wpa_cli fuer P2P Group Owner Negotiation auf dem
    BCM43436s Single-Radio-Chip des Pi Zero 2 WH.

    Ablauf:
      1. BLE-Scan findet Gegner (MAC-Adresse)
      2. p2p_find → p2p_connect → GO-Negotiation
      3. P2P-Gruppe gebildet → Interface p2p-wlan0-X aktiv
      4. TCP-Socket-Tunnel auf P2P-Interface
      5. AES-256-GCM verschluesselter Datenaustausch
      6. Tunnel schliessen → p2p_group_remove

    Simulation-Mode:
      Bei SIMULATION_MODE=True wird der TCP-Tunnel lokal
      ueber localhost aufgebaut (kein wpa_cli noetig).
    """

    def __init__(self):
        self.connected = False
        self._remote_mac: Optional[str] = None
        self._remote_name: Optional[str] = None
        self._p2p_interface: Optional[str] = None
        self._local_ip: Optional[str] = None
        self._remote_ip: Optional[str] = None
        self._is_group_owner: bool = False
        self._tcp_server: Optional[asyncio.Server] = None
        self._tcp_reader: Optional[asyncio.StreamReader] = None
        self._tcp_writer: Optional[asyncio.StreamWriter] = None
        self._wpa_cli_available: Optional[bool] = None

    # -----------------------------------------
    # wpa_cli Helper
    # -----------------------------------------

    def _run_wpa_cli(self, *args, timeout: int = 10) -> Tuple[bool, str]:
        """
        wpa_cli Befehl ausfuehren.

        Args:
            *args: wpa_cli Argumente (z.B. "p2p_find")
            timeout: Timeout in Sekunden

        Returns:
            Tuple (success, output)
        """
        cmd = ["wpa_cli", "-i", "wlan0"] + list(args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            output = result.stdout.strip()
            success = result.returncode == 0 and "FAIL" not in output
            return success, output
        except FileNotFoundError:
            return False, "wpa_cli nicht gefunden"
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)

    def _check_wpa_cli(self) -> bool:
        """Pruefen ob wpa_cli verfuegbar und funktional ist."""
        if self._wpa_cli_available is not None:
            return self._wpa_cli_available

        if SIMULATION_MODE:
            self._wpa_cli_available = False  # Nicht noetig im Sim-Mode
            return False

        success, output = self._run_wpa_cli("status")
        self._wpa_cli_available = success
        if not success:
            print(f"[WiFi-Direct] wpa_cli nicht verfuegbar: {output}")
        return success

    # -----------------------------------------
    # P2P Group Management
    # -----------------------------------------

    async def connect(self, remote_mac: str, remote_name: str = "",
                      session_key: bytes = None) -> Dict[str, Any]:
        """
        WiFi-Direct Verbindung herstellen.

        Args:
            remote_mac: BLE-MAC-Adresse des Gegners
            remote_name: Spieler-Name (fuer Logging)
            session_key: AES-256-GCM Key aus ECC-Handshake

        Returns:
            Dict mit: connected, reason, ip, interface, is_go
        """
        self._remote_mac = remote_mac
        self._remote_name = remote_name

        # --- Simulation-Mode: Localhost-Bridge ---
        if SIMULATION_MODE:
            return await self._connect_simulation()

        # --- Echte WiFi-Direct P2P-Verbindung ---
        if not self._check_wpa_cli():
            return {
                "connected": False,
                "reason": "wpa_cli nicht verfuegbar",
                "mac": remote_mac
            }

        print(f"[WiFi-Direct] Verbinde mit {remote_name} ({remote_mac})...")

        # 1. P2P-Suche starten
        success, output = self._run_wpa_cli("p2p_find", str(P2P_FIND_TIMEOUT))
        if not success:
            return {
                "connected": False,
                "reason": f"p2p_find fehlgeschlagen: {output}",
                "mac": remote_mac
            }

        # Warte kurz bis Peers gefunden werden
        await asyncio.sleep(min(3, P2P_FIND_TIMEOUT))

        # 2. P2P-Peers auflisten
        success, peers_output = self._run_wpa_cli("p2p_peers")
        if not success:
            self._run_wpa_cli("p2p_stop_find")
            return {
                "connected": False,
                "reason": "Keine P2P-Peers gefunden",
                "mac": remote_mac
            }

        # 3. p2p_find stoppen
        self._run_wpa_cli("p2p_stop_find")

        # 4. P2P-Verbindung zum Gegner herstellen
        # GO-Negotiation: go_intent bestimmt wer Group Owner wird
        connect_cmd = f"p2p_connect {remote_mac} pbc go_intent={P2P_GO_INTENT}"
        success, output = self._run_wpa_cli(
            "p2p_connect", remote_mac, "pbc",
            f"go_intent={P2P_GO_INTENT}",
            timeout=P2P_CONNECT_TIMEOUT
        )
        if not success:
            return {
                "connected": False,
                "reason": f"p2p_connect fehlgeschlagen: {output}",
                "mac": remote_mac
            }

        # 5. Warte auf Gruppenbildung
        p2p_interface = await self._wait_for_p2p_interface(timeout=P2P_CONNECT_TIMEOUT)
        if p2p_interface is None:
            await self._cleanup_p2p()
            return {
                "connected": False,
                "reason": "P2P-Interface nicht erstellt (Timeout)",
                "mac": remote_mac
            }

        self._p2p_interface = p2p_interface

        # 6. IP-Adresse ermitteln
        local_ip = await self._get_p2p_ip(p2p_interface)
        if local_ip is None:
            await self._cleanup_p2p()
            return {
                "connected": False,
                "reason": "Keine IP auf P2P-Interface",
                "mac": remote_mac
            }

        self._local_ip = local_ip
        self._is_group_owner = local_ip.endswith(".1")
        self.connected = True

        print(f"[WiFi-Direct] Verbunden! IF={p2p_interface} IP={local_ip} "
              f"GO={self._is_group_owner}")

        return {
            "connected": True,
            "reason": "OK",
            "mac": remote_mac,
            "interface": p2p_interface,
            "ip": local_ip,
            "is_go": self._is_group_owner,
        }

    async def _connect_simulation(self) -> Dict[str, Any]:
        """Simulierte Verbindung ueber localhost."""
        print(f"[WiFi-Direct-SIM] Simulierte Verbindung mit '{self._remote_name}'")
        self._p2p_interface = "lo"
        self._local_ip = "127.0.0.1"
        self._remote_ip = "127.0.0.1"
        self._is_group_owner = True
        self.connected = True

        return {
            "connected": True,
            "reason": "Simulation (localhost)",
            "mac": self._remote_mac,
            "interface": "lo",
            "ip": "127.0.0.1",
            "is_go": True,
            "simulated": True,
        }

    async def _wait_for_p2p_interface(self, timeout: int = 15) -> Optional[str]:
        """
        Warte bis P2P-Interface erstellt wird.

        Pollt /sys/class/net/ nach p2p-wlan0-* Interface.

        Returns:
            Interface-Name oder None bei Timeout
        """
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                interfaces = os.listdir("/sys/class/net/")
                for iface in interfaces:
                    if iface.startswith("p2p-"):
                        return iface
            except OSError:
                pass

            await asyncio.sleep(0.5)

        return None

    async def _get_p2p_ip(self, interface: str, timeout: int = 10) -> Optional[str]:
        """
        IP-Adresse des P2P-Interfaces ermitteln.

        Wartet auf DHCP-Zuweisung (Client) oder nutzt
        statische IP (Group Owner: 192.168.49.1).

        Args:
            interface: P2P-Interface-Name
            timeout: Warte-Timeout

        Returns:
            IP-Adresse oder None
        """
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                result = subprocess.run(
                    ["ip", "-4", "addr", "show", interface],
                    capture_output=True, text=True, timeout=5
                )
                output = result.stdout

                # IP aus "inet X.X.X.X/YY" extrahieren
                for line in output.split("\n"):
                    line = line.strip()
                    if line.startswith("inet "):
                        ip_cidr = line.split()[1]
                        ip_addr = ip_cidr.split("/")[0]
                        return ip_addr

            except Exception:
                pass

            await asyncio.sleep(1.0)

        return None

    async def _cleanup_p2p(self) -> None:
        """P2P-Gruppe aufloesen und aufraeumen."""
        if self._p2p_interface and self._p2p_interface not in ("lo",):
            self._run_wpa_cli("p2p_group_remove", self._p2p_interface)
        self._run_wpa_cli("p2p_stop_find")

    # -----------------------------------------
    # TCP-Tunnel (Datenaustausch)
    # -----------------------------------------

    async def exchange_data(self, local_data: Dict[str, Any],
                            session_key: bytes = None) -> Dict[str, Any]:
        """
        Bidirektionalen Datenaustausch ueber TCP-Tunnel durchfuehren.

        Der Group Owner (GO) startet den TCP-Server,
        der Client verbindet sich und tauscht Daten.

        Protokoll:
          1. GO: TCP-Server auf P2P_DATA_PORT
          2. Client: TCP-Connect zum GO
          3. Beide: JSON-Daten senden (Laenge-Prefix: 4 Bytes uint32 BE)
          4. Beide: JSON-Daten empfangen
          5. Verbindung schliessen

        Args:
            local_data: Zu sendende Daten (Dict, wird zu JSON serialisiert)
            session_key: AES-256-GCM Key (optional, fuer Verschluesselung)

        Returns:
            Dict mit: success, remote_data, bytes_sent, bytes_received
        """
        if not self.connected:
            return {"success": False, "reason": "Nicht verbunden"}

        # JSON serialisieren
        local_json = json.dumps(local_data, ensure_ascii=False).encode("utf-8")

        # Optional: AES-256-GCM verschluesseln
        if session_key:
            local_json = self._encrypt_payload(local_json, session_key)
            if local_json is None:
                return {"success": False, "reason": "Verschluesselung fehlgeschlagen"}

        if self._is_group_owner:
            return await self._exchange_as_server(local_json, session_key)
        else:
            return await self._exchange_as_client(local_json, session_key)

    async def _exchange_as_server(self, local_payload: bytes,
                                  session_key: bytes = None) -> Dict[str, Any]:
        """TCP-Server: Warte auf Client, tausche Daten."""
        remote_data = None
        bytes_received = 0

        async def handle_client(reader: asyncio.StreamReader,
                                writer: asyncio.StreamWriter):
            nonlocal remote_data, bytes_received
            try:
                # 1. Eigene Daten senden (4-Byte Laenge + Payload)
                length = len(local_payload)
                writer.write(struct.pack(">I", length))
                writer.write(local_payload)
                await writer.drain()

                # 2. Remote-Daten empfangen
                length_bytes = await asyncio.wait_for(
                    reader.readexactly(4),
                    timeout=P2P_EXCHANGE_TIMEOUT
                )
                remote_length = struct.unpack(">I", length_bytes)[0]

                if remote_length > P2P_BUFFER_SIZE:
                    print(f"[WiFi-Direct] Remote-Payload zu gross: {remote_length}")
                    writer.close()
                    return

                remote_payload = await asyncio.wait_for(
                    reader.readexactly(remote_length),
                    timeout=P2P_EXCHANGE_TIMEOUT
                )
                bytes_received = len(remote_payload)

                # Entschluesseln falls noetig
                if session_key:
                    remote_payload = self._decrypt_payload(remote_payload, session_key)
                    if remote_payload is None:
                        print("[WiFi-Direct] Entschluesselung fehlgeschlagen")
                        writer.close()
                        return

                remote_data = json.loads(remote_payload.decode("utf-8"))

            except (asyncio.TimeoutError, asyncio.IncompleteReadError) as e:
                print(f"[WiFi-Direct] Server-Exchange-Fehler: {e}")
            except json.JSONDecodeError as e:
                print(f"[WiFi-Direct] JSON-Parse-Fehler: {e}")
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

        # Server starten
        bind_ip = self._local_ip if self._local_ip else "0.0.0.0"
        try:
            server = await asyncio.start_server(
                handle_client, bind_ip, P2P_DATA_PORT
            )
            self._tcp_server = server

            print(f"[WiFi-Direct] TCP-Server auf {bind_ip}:{P2P_DATA_PORT}")

            # Warte auf einen Client (mit Timeout)
            async with server:
                try:
                    await asyncio.wait_for(
                        server.serve_forever(),
                        timeout=P2P_EXCHANGE_TIMEOUT + 5
                    )
                except asyncio.TimeoutError:
                    pass
                except asyncio.CancelledError:
                    pass

        except OSError as e:
            return {"success": False, "reason": f"Server-Start fehlgeschlagen: {e}"}
        finally:
            if self._tcp_server:
                self._tcp_server.close()
                self._tcp_server = None

        if remote_data is not None:
            return {
                "success": True,
                "remote_data": remote_data,
                "bytes_sent": len(local_payload),
                "bytes_received": bytes_received,
            }
        else:
            return {"success": False, "reason": "Kein Client verbunden (Timeout)"}

    async def _exchange_as_client(self, local_payload: bytes,
                                  session_key: bytes = None) -> Dict[str, Any]:
        """TCP-Client: Verbinde zum GO-Server, tausche Daten."""
        if not self._remote_ip:
            # GO-IP ist typischerweise .1 im P2P-Subnet
            self._remote_ip = f"{P2P_IP_PREFIX}.1"

        # Kurz warten damit Server bereit ist
        await asyncio.sleep(0.5)

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._remote_ip, P2P_DATA_PORT),
                timeout=P2P_EXCHANGE_TIMEOUT
            )

            # 1. Remote-Daten empfangen
            length_bytes = await asyncio.wait_for(
                reader.readexactly(4),
                timeout=P2P_EXCHANGE_TIMEOUT
            )
            remote_length = struct.unpack(">I", length_bytes)[0]

            if remote_length > P2P_BUFFER_SIZE:
                writer.close()
                return {"success": False, "reason": f"Remote-Payload zu gross: {remote_length}"}

            remote_payload = await asyncio.wait_for(
                reader.readexactly(remote_length),
                timeout=P2P_EXCHANGE_TIMEOUT
            )

            # 2. Eigene Daten senden
            length = len(local_payload)
            writer.write(struct.pack(">I", length))
            writer.write(local_payload)
            await writer.drain()

            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

            # Entschluesseln falls noetig
            if session_key:
                remote_payload = self._decrypt_payload(remote_payload, session_key)
                if remote_payload is None:
                    return {"success": False, "reason": "Entschluesselung fehlgeschlagen"}

            remote_data = json.loads(remote_payload.decode("utf-8"))

            return {
                "success": True,
                "remote_data": remote_data,
                "bytes_sent": len(local_payload),
                "bytes_received": len(remote_payload),
            }

        except asyncio.TimeoutError:
            return {"success": False, "reason": "Verbindungs-Timeout"}
        except ConnectionRefusedError:
            return {"success": False, "reason": "Server nicht erreichbar"}
        except json.JSONDecodeError as e:
            return {"success": False, "reason": f"JSON-Parse-Fehler: {e}"}
        except Exception as e:
            return {"success": False, "reason": f"Client-Fehler: {e}"}

    # -----------------------------------------
    # AES-256-GCM Payload-Verschluesselung
    # -----------------------------------------

    @staticmethod
    def _encrypt_payload(plaintext: bytes, session_key: bytes) -> Optional[bytes]:
        """
        Payload mit AES-256-GCM verschluesseln.

        Format: nonce(12) + ciphertext(N)

        Returns:
            Verschluesselter Payload oder None
        """
        try:
            from ecc_crypto import ECCKeyManager
            result = ECCKeyManager.encrypt(session_key, plaintext)
            if result is None:
                return None
            nonce, ciphertext = result
            return nonce + ciphertext
        except ImportError:
            # Fallback: Unverschluesselt (fuer Tests)
            print("[WiFi-Direct-WARN] ecc_crypto nicht verfuegbar, unverschluesselt!")
            return plaintext
        except Exception as e:
            print(f"[WiFi-Direct] Encrypt-Fehler: {e}")
            return None

    @staticmethod
    def _decrypt_payload(data: bytes, session_key: bytes) -> Optional[bytes]:
        """
        Payload mit AES-256-GCM entschluesseln.

        Erwartet: nonce(12) + ciphertext(N)

        Returns:
            Klartext oder None
        """
        try:
            from ecc_crypto import ECCKeyManager
            if len(data) < 13:  # Min: 12 nonce + 1 byte ct
                return None
            nonce = data[:12]
            ciphertext = data[12:]
            return ECCKeyManager.decrypt(session_key, nonce, ciphertext)
        except ImportError:
            # Fallback: Unverschluesselt
            return data
        except Exception as e:
            print(f"[WiFi-Direct] Decrypt-Fehler: {e}")
            return None

    # -----------------------------------------
    # Disconnect / Cleanup
    # -----------------------------------------

    async def disconnect(self) -> Dict[str, Any]:
        """WiFi-Direct Verbindung sauber trennen."""
        reason = "OK"

        # TCP-Server schliessen
        if self._tcp_server:
            self._tcp_server.close()
            self._tcp_server = None

        # TCP-Writer schliessen
        if self._tcp_writer:
            try:
                self._tcp_writer.close()
                await self._tcp_writer.wait_closed()
            except Exception:
                pass
            self._tcp_writer = None
            self._tcp_reader = None

        # P2P-Gruppe aufloesen (nur bei echter Verbindung)
        if not SIMULATION_MODE and self._p2p_interface:
            await self._cleanup_p2p()

        was_connected = self.connected
        self.connected = False
        self._remote_mac = None
        self._remote_name = None
        self._p2p_interface = None
        self._local_ip = None
        self._remote_ip = None

        return {
            "disconnected": True,
            "was_connected": was_connected,
            "reason": reason
        }

    # -----------------------------------------
    # Status / Info
    # -----------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Aktuellen Verbindungsstatus abrufen."""
        return {
            "connected": self.connected,
            "remote_mac": self._remote_mac,
            "remote_name": self._remote_name,
            "interface": self._p2p_interface,
            "local_ip": self._local_ip,
            "remote_ip": self._remote_ip,
            "is_group_owner": self._is_group_owner,
            "simulation": SIMULATION_MODE,
        }


# =============================================
# Standalone Test
# =============================================

if __name__ == "__main__":
    print("=== BLE Beacon + WiFi-Direct Test ===\n")

    # --- Beacon Build/Parse ---
    test_char = {
        "name": "TestRitter",
        "level": 42,
        "current_floor": 128,
        "pvp_wins": 7,
        "class_type": "Schere"
    }

    beacon = BLEBeaconBuilder.build_beacon(test_char)
    print(f"Beacon ({len(beacon)} bytes): {beacon.hex()}")

    parsed = BLEBeaconBuilder.parse_beacon(beacon)
    print(f"Parsed: {parsed}")

    # Korruptions-Test
    bad_beacon = bytearray(beacon)
    bad_beacon[10] = 0xFF
    bad_parsed = BLEBeaconBuilder.parse_beacon(bytes(bad_beacon))
    print(f"Corrupt beacon: {bad_parsed}")  # Sollte None sein

    # --- WiFi-Direct Simulation ---
    async def _test_wifi_direct():
        print("\n=== WiFi-Direct Simulation ===")
        set_simulation_mode(True)

        bridge = WiFiDirectBridge()

        # Verbinden
        result = await bridge.connect(
            "SIM:00:00:00:00:01",
            "SimGegner"
        )
        print(f"Connect: {result}")
        assert result["connected"], "Simulation-Connect fehlgeschlagen!"

        # Status
        status = bridge.get_status()
        print(f"Status: {status}")

        # Datenaustausch (Server-Seite simulieren)
        # In echt: GO=Server, Client=Gegner
        # Hier: Nur Server-Start testen (Client kommt vom 2. Pi)
        print(f"Status nach Connect: connected={bridge.connected}")

        # Disconnect
        disc = await bridge.disconnect()
        print(f"Disconnect: {disc}")
        assert not bridge.connected, "Disconnect fehlgeschlagen!"

        set_simulation_mode(False)
        print("WiFi-Direct Simulation OK!")

    # --- BLE Scan Test ---
    async def _test_ble():
        print("\n=== BLE Scan ===")

        # Erst Simulation testen
        set_simulation_mode(True)
        scanner = BLEScanner()
        avail = await scanner.check_availability()
        print(f"BLE (Sim) available: {avail}")

        if avail:
            result = await scanner.scan_simple(timeout=1.0)
            print(f"Scan (Sim): found={result.get('found')} "
                  f"name={result.get('name', 'N/A')}")

        set_simulation_mode(False)

        # Dann echten Scan versuchen
        scanner2 = BLEScanner()
        avail2 = await scanner2.check_availability()
        print(f"BLE (Real) available: {avail2}")
        if avail2:
            result2 = await scanner2.scan_simple(timeout=3.0)
            print(f"Scan (Real): {result2}")

    async def _run_all_tests():
        await _test_wifi_direct()
        await _test_ble()

    asyncio.run(_run_all_tests())
    print("\nAlle BLE/WiFi-Direct Tests bestanden!")
