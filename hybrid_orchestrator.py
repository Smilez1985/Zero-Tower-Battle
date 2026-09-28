#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Hybrid Orchestrator Master Loop
============================================================
Single-Process Architecture fuer Raspberry Pi Zero 2 WH.

State Machine:
  IDLE       -> PVE-Tower-Tick (Kampf, dann 90s Cooldown)
  BLE_SCAN   -> BLE-Scan NUR waehrend 90s PVE-Cooldown
  PVP_FOUND  -> PVP-Gegner erkannt, Handshake
  BATTLE     -> PVE oder PVP Kampf
  GOSSIP     -> Taverne-Austausch nach BLE-Fund
  CHECKPOINT -> Auto-Save (alle 5 Min)
  WORLDBOSS  -> Raid-Koordination (3+ Spieler)
  SLEEP      -> Erschoepfungs-Pause (max 1h bei 100%)
  SHUTDOWN   -> Gently Shutdown (Hot->Cold, Dienste stop)

Kritische Constraints:
  - BLE-Scan NUR im 90s PVE-Cooldown (BCM43436s Single-Radio-Chip)
  - SSH + PVP gleichzeitig via Split-Tunnel (wlan0 AP + tun0 WiFi-Direct)
  - RAM-Budget: ~20MB Idle, <45MB bei SSH-Session
  - OOM-Schutz: 90%-Schwelle -> Hot->Cold Migration

Referenz: Battle-Pi_Konsolidiert.txt, ECC Crypto.txt, Gossip-Taverne.txt
"""

import asyncio
import signal
import sys
import os
import json
import random
from datetime import datetime
from typing import Dict, Any, Optional

# ========================================
# LAZY IMPORTS (Pi Zero Speicher-Schutz)
# ========================================
_init_game = None
_battle_engine = None
_ble_scanner = None
_gossip = None
_pvp_cooldown = None
_codex = None
_visualizer = None
_hot_storage = None
_cold_storage = None
_psyche = None
_inventory = None
_loot_factory = None
_shop = None
_worldboss = None
_levelup = None
_monster_gen = None
_det_battle = None
_shutdown_requested = False
_ble_available = True
_enemies_cache = None


def _get_init_game():
    """Lazy-Load GameInitializer."""
    global _init_game
    if _init_game is None:
        from init_game import GameInitializer
        _init_game = GameInitializer()
    return _init_game


def _get_battle_engine():
    """Lazy-Load BattleEngine."""
    global _battle_engine
    if _battle_engine is None:
        from engine.battle_engine import BattleEngine
        _battle_engine = BattleEngine()
    return _battle_engine


def _get_hot_storage():
    """Lazy-Load HotStorageManager."""
    global _hot_storage
    if _hot_storage is None:
        from game.hot_storage import HotStorageManager
        _hot_storage = HotStorageManager()
    return _hot_storage


def _get_cold_storage():
    """Lazy-Load ColdStorageManager."""
    global _cold_storage
    if _cold_storage is None:
        from game.hot_storage import ColdStorageManager
        _cold_storage = ColdStorageManager()
    return _cold_storage


def _get_pvp_cooldown():
    """Lazy-Load PVPCooldownManager."""
    global _pvp_cooldown
    if _pvp_cooldown is None:
        from pvp_cooldown import PVPCooldownManager
        _pvp_cooldown = PVPCooldownManager()
    return _pvp_cooldown


def _get_codex():
    """Lazy-Load CodexManager."""
    global _codex
    if _codex is None:
        from codex_manager import CodexManager
        _codex = CodexManager()
    return _codex


def _get_gossip(local_name: str = ""):
    """Lazy-Load GossipTaverne mit DB-Restore."""
    global _gossip
    if _gossip is None:
        from gossip_taverne import GossipTaverne
        _gossip = GossipTaverne(local_name=local_name)
        try:
            loaded = _gossip.load_from_db()
            if any(v > 0 for v in loaded.values()):
                print(f"[GOSSIP] DB geladen: {loaded}")
        except Exception as e:
            print(f"[GOSSIP] DB-Load-Fehler: {e}")
    return _gossip


def _get_psyche():
    """Lazy-Load ChampionPsyche."""
    global _psyche
    if _psyche is None:
        from champion_psyche import ChampionPsyche
        _psyche = ChampionPsyche()
    return _psyche


def _get_visualizer():
    """Lazy-Load BattleVisualizer."""
    global _visualizer
    if _visualizer is None:
        from visualizer import BattleVisualizer
        _visualizer = BattleVisualizer(use_color=True, delay=0.0)
    return _visualizer


def _get_inventory():
    """Lazy-Load Inventory."""
    global _inventory
    if _inventory is None:
        from models.inventory import Inventory
        _inventory = Inventory()
    return _inventory


def _get_loot_factory():
    """Lazy-Load LootFactory."""
    global _loot_factory
    if _loot_factory is None:
        from loot_factory import LootFactory
        _loot_factory = LootFactory()
    return _loot_factory


def _get_shop():
    """Lazy-Load Shop."""
    global _shop
    if _shop is None:
        from services.shop import Shop
        _shop = Shop()
    return _shop


def _get_worldboss():
    """Lazy-Load WorldBoss."""
    global _worldboss
    if _worldboss is None:
        from services.worldboss import WorldBoss
        _worldboss = WorldBoss()
    return _worldboss


def _get_levelup():
    """Lazy-Load LevelUp service."""
    global _levelup
    if _levelup is None:
        from services.levelup import LevelUp
        _levelup = LevelUp()
    return _levelup


def _get_monster_gen():
    """Lazy-Load Monster-Generator Modul."""
    global _monster_gen
    if _monster_gen is None:
        import monster_generator
        _monster_gen = monster_generator
    return _monster_gen


def _get_det_battle():
    """Lazy-Load Deterministisches Battle-Modul."""
    global _det_battle
    if _det_battle is None:
        import deterministic_battle
        _det_battle = deterministic_battle
    return _det_battle


# ========================================
# STATE MACHINE
# ========================================

class OrchestratorState:
    """State-Konstanten fuer die Haupt-State-Machine."""
    IDLE = "IDLE"
    BLE_SCAN = "BLE_SCAN"
    PVP_FOUND = "PVP_FOUND"
    BATTLE = "BATTLE"
    GOSSIP = "GOSSIP"
    CHECKPOINT = "CHECKPOINT"
    WORLDBOSS = "WORLDBOSS"
    SLEEP = "SLEEP"
    SHUTDOWN = "SHUTDOWN"


# ========================================
# ORCHESTRATOR
# ========================================

class HybridOrchestrator:
    """
    Zentraler Orchestrator fuer den gesamten Spielablauf.

    Verwaltet:
      - Charakter-Daten (aus init_game.py)
      - State Machine (IDLE -> BLE_SCAN -> BATTLE -> ...)
      - PVE-Loop mit 90s Cooldown (BLE-Fenster)
      - PVP-Erkennung und Kampf
      - Gossip-Austausch
      - Checkpoint-Saves (alle 5 Min)
      - Erschoepfungs-Pause
      - Gently Shutdown
      - Loot-Integration
      - Weltboss-Koordination
      - Level-Up-System
    """

    # Timing-Konstanten
    PVE_COOLDOWN_SECONDS = 90       # 90s Cooldown zwischen PVE-Runs
    CHECKPOINT_INTERVAL = 300       # 5 Min Checkpoint
    BACKUP_INTERVAL = 1200          # 20 Min Full-Backup
    EXHAUSTION_PAUSE = 3600         # 1h Pause bei 100% Erschoepfung

    def __init__(self):
        self._state = OrchestratorState.IDLE
        self._character = None
        self._running = False
        self._last_checkpoint = 0.0
        self._last_backup = 0.0
        self._pve_cooldown_active = False
        self._ble_scan_result = None
        self._exhaustion_pause_start = 0.0
        self._ble_available = True

    @property
    def state(self) -> str:
        """Aktueller State."""
        return self._state

    # ========================================
    # INITIALISIERUNG
    # ========================================

    def initialize(self) -> Dict[str, Any]:
        """
        Spiel initialisieren (Erststart oder Recovery).

        Returns:
            Dict mit: status, character, first_start
        """
        init = _get_init_game()
        result = init.initialize()

        if result.get("status") == "SUCCESS":
            self._character = result.get("character")

            # Psyche laden
            if self._character:
                psyche = _get_psyche()
                psyche.load_from_character(self._character)

            # Gossip mit lokalem Namen initialisieren
            if self._character:
                _get_gossip(self._character.get("name", ""))

            # Inventory-Felder sicherstellen
            if self._character:
                self._character.setdefault("inventory_items", [])
                self._character.setdefault("gold", 500)
                self._character.setdefault("scrap", 0)
                self._character.setdefault("diamonds", 0)
                self._character.setdefault("soul_shards", 0)
                self._character.setdefault("runes", [])
                self._character.setdefault("pending_bonus_points", 0)
                # Migration: altes Inventory-Format -> inventory_items
                if ("inventory" in self._character
                        and "items" in self._character["inventory"]
                        and not self._character["inventory_items"]):
                    self._character["inventory_items"] = (
                        self._character["inventory"]["items"]
                    )
                    self._character["gold"] = self._character["inventory"].get(
                        "gold", self._character.get("gold", 500)
                    )

        return result

    # ========================================
    # SIGNAL HANDLER
    # ========================================

    def _signal_handler(self, signum, frame):
        """SIGTERM/SIGINT -> Gently Shutdown."""
        global _shutdown_requested
        signame = signal.Signals(signum).name
        print(f"\n[SIGNAL] {signame} -> Gently Shutdown...")
        _shutdown_requested = True
        self._state = OrchestratorState.SHUTDOWN

    # ========================================
    # MAIN LOOP
    # ========================================

    async def run(self) -> None:
        """
        Haupt-Event-Loop (asyncio).

        Ablauf:
          1. Init (Cold Recovery oder Erststart)
          2. PVE-Kampf -> 90s Cooldown (BLE-Fenster)
          3. BLE-Scan im Cooldown -> PVP oder Gossip
          4. Checkpoint alle 5 Min
          5. Loop bis Shutdown
        """
        global _shutdown_requested

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        print("=" * 60)
        print(f"  ZERO TOWER BATTLE - Hybrid Orchestrator")
        print(f"  Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # 1. Initialisierung (mit Warte-Loop fuer Erststart)
        init_result = self.initialize()

        # Bei FIRST_START_PENDING: Charakter wird ueber War Room erstellt
        # Orchestrator wartet bis config.json first_start_pending == False
        if init_result.get("status") == "FIRST_START_PENDING":
            print("[WAIT] Erststart: Warte auf Charakter-Erstellung via War Room (SSH)...")
            import json as _json
            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "config.json")
            while not _shutdown_requested:
                try:
                    await asyncio.sleep(10)  # Alle 10 Sekunden pruefen
                    if os.path.exists(config_path):
                        with open(config_path, "r") as _f:
                            _cfg = _json.load(_f)
                        if not _cfg.get("state", {}).get("first_start_pending", True):
                            print("[WAIT] Charakter erstellt! Initialisiere neu...")
                            init_result = self.initialize()
                            break
                except asyncio.CancelledError:
                    return
                except Exception:
                    await asyncio.sleep(10)

        if init_result.get("status") != "SUCCESS":
            print(f"[FATAL] Init fehlgeschlagen: {init_result.get('message')}")
            return

        char = self._character
        print(f"[BOOT] Champion: {char.get('name', '?')} "
              f"({char.get('klasse', '?')}) Lv.{char.get('level', 1)} "
              f"Floor {char.get('current_floor', 1)}")

        self._running = True
        self._last_checkpoint = asyncio.get_event_loop().time()
        self._last_backup = asyncio.get_event_loop().time()

        # 2. Main Loop
        while self._running and not _shutdown_requested:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ERROR] Tick: {e}")
                await asyncio.sleep(5)

        # 3. Gently Shutdown
        await self._gently_shutdown()

    # ========================================
    # TICK (ein Durchlauf der State Machine)
    # ========================================

    async def _tick(self) -> None:
        """Ein Tick der State Machine."""

        if self._state == OrchestratorState.IDLE:
            await self._tick_idle()

        elif self._state == OrchestratorState.BLE_SCAN:
            await self._tick_ble_scan()

        elif self._state == OrchestratorState.PVP_FOUND:
            await self._tick_pvp_found()

        elif self._state == OrchestratorState.BATTLE:
            await self._tick_battle()

        elif self._state == OrchestratorState.GOSSIP:
            await self._tick_gossip()

        elif self._state == OrchestratorState.CHECKPOINT:
            await self._tick_checkpoint()
            self._state = OrchestratorState.IDLE

        elif self._state == OrchestratorState.WORLDBOSS:
            await self._tick_worldboss()
            self._state = OrchestratorState.IDLE

        elif self._state == OrchestratorState.SLEEP:
            await self._tick_sleep()

        elif self._state == OrchestratorState.SHUTDOWN:
            self._running = False

        # Checkpoint-Check (zeit-basiert)
        now = asyncio.get_event_loop().time()
        if now - self._last_checkpoint >= self.CHECKPOINT_INTERVAL:
            self._save_checkpoint()
            self._last_checkpoint = now

    # ========================================
    # STATE: IDLE (PVE-Kampf starten)
    # ========================================

    async def _tick_idle(self) -> None:
        """
        IDLE: PVE-Tower-Kampf ausfuehren, dann 90s Cooldown.
        Im Cooldown: BLE-Scan (Single-Radio-Chip Constraint).
        """
        if not self._character:
            await asyncio.sleep(5)
            return

        # Hot Storage Monitoring (OOM-Schutz)
        hot = _get_hot_storage()
        if hot.is_critical():
            print("[HOT] 90%-Schwelle! Auto-Migration...")
            hot._evict_to_cold()

        # Erschoepfungs-Check
        engine = _get_battle_engine()
        exh_check = engine.check_exhaustion(self._character)
        if not exh_check["can_fight"]:
            print(f"[PSYCHE] {exh_check['message']}")
            self._exhaustion_pause_start = asyncio.get_event_loop().time()
            self._state = OrchestratorState.SLEEP
            return

        # PVE-Kampf mit prozeduralem Gegner
        floor = self._character.get("current_floor", 1)
        enemy = self._generate_pve_enemy(floor)

        battle_result = engine.run_pve_battle(self._character, enemy)

        # Visualisierung (kompakt im autonomen Modus)
        viz = _get_visualizer()
        viz.print_summary(
            battle_result,
            self._character.get("name", "Champion"),
            enemy.get("name", "Monster")
        )

        # Rewards verteilen
        if battle_result.get("rewards_eligible"):
            reward_result = engine.distribute_rewards(
                self._character, battle_result,
                floor=floor,
                ascension=self._character.get("ascension", 1)
            )
            viz.print_rewards(reward_result)

            # Level-Up Check nach Rewards
            levelup_svc = _get_levelup()
            level_up_data = levelup_svc.check_level_up(self._character)
            if level_up_data.get("can_level_up"):
                self.perform_level_up(level_up_data)

            # Loot Drop Integration
            loot = self._generate_and_store_loot(floor, battle_result)
            if loot:
                print(f"[LOOT] {loot}")

        # Floor-Progression bei Sieg
        if battle_result.get("result") == "WIN":
            self._character["current_floor"] = floor + 1

        # Codex-Eintrag
        try:
            codex = _get_codex()
            codex.register_encounter(
                player_id=1,
                enemy_name=enemy.get("name", "Unbekannt"),
                result=battle_result.get("result", "DRAW"),
                floor=floor,
                is_shiny=battle_result.get("is_shiny", False)
            )
        except Exception:
            pass

        # In Hot Storage sichern
        hot.write(self._character, "character_data")

        # -> 90s PVE-Cooldown mit BLE-Scan
        self._pve_cooldown_active = True
        self._state = OrchestratorState.BLE_SCAN

    # ========================================
    # STATE: BLE_SCAN (nur im 90s Cooldown!)
    # ========================================

    async def _tick_ble_scan(self) -> None:
        """
        BLE-Scan NUR waehrend des 90s PVE-Cooldowns.
        Constraint: BCM43436s = Single-Radio-Chip.
        WiFi-AP (SSH) + BLE-Scan NICHT gleichzeitig stabil.

        Timing: Scan-Duration = halber Intervall, da discover()
        blockiert und die Echtzeit den Cooldown verbraucht.
        Effektive Cooldown-Dauer ≈ PVE_COOLDOWN_SECONDS.
        """
        import time as _time
        cooldown_start = _time.time()
        cooldown_deadline = cooldown_start + self.PVE_COOLDOWN_SECONDS

        print(f"[COOLDOWN] {self.PVE_COOLDOWN_SECONDS}s PVE-Cooldown – "
              f"BLE-Scan aktiv...")

        scan_found = False
        scan_result = None

        while _time.time() < cooldown_deadline and not _shutdown_requested:
            remaining = cooldown_deadline - _time.time()
            if remaining <= 0:
                break

            # Scan-Duration: max 5s (Echtzeit-basiert, nicht Zähler-basiert)
            scan_duration = min(5.0, remaining)

            try:
                scan_result = await self._perform_ble_scan(scan_duration)
                if scan_result and scan_result.get("found"):
                    scan_found = True
                    break
            except Exception as e:
                print(f"[BLE-WARN] Scan-Fehler: {e}")

            # Sleep nur falls noch genug Cooldown uebrig
            remaining = cooldown_deadline - _time.time()
            if remaining > 2.0:
                await asyncio.sleep(min(5.0, remaining - 1.0))
            elif remaining > 0:
                await asyncio.sleep(remaining)

        self._pve_cooldown_active = False
        if scan_found:
            elapsed = _time.time() - cooldown_start
            print(f"[PVP] Gegner gefunden nach {int(elapsed)}s!")

        if scan_found and scan_result:
            # Gegner gefunden -> PVP oder Gossip
            self._ble_scan_result = scan_result
            opponent_mac = scan_result.get("mac", "")

            pvp_cd = _get_pvp_cooldown()
            cd_check = pvp_cd.can_fight(opponent_mac)

            if cd_check["allowed"]:
                self._state = OrchestratorState.PVP_FOUND
            else:
                # PVP-Cooldown aktiv -> nur Gossip
                print(f"[PVP] Cooldown: {cd_check['message']}")
                self._state = OrchestratorState.GOSSIP
        else:
            # Kein Gegner -> zurueck zu IDLE
            self._state = OrchestratorState.IDLE

    async def _perform_ble_scan(self, duration: float) -> Optional[Dict[str, Any]]:
        """
        BLE-Scan durchfuehren via game.ble_beacon.BLEScanner.

        Scannt nach ZTB-Geraeten (Manufacturer Data 0xFEAA),
        parst 31-Byte-Beacons, filtert nach RSSI >= -85.

        Args:
            duration: Scan-Dauer in Sekunden

        Returns:
            Dict mit: found, mac, name, level, floor, class_type, flags, ...
        """
        if not self._ble_available:
            return {"found": False}

        try:
            from game.ble_beacon import BLEScanner

            scanner = BLEScanner()

            # Verfuegbarkeit pruefen (Ergebnis wird gecacht)
            if not await scanner.check_availability():
                print("[BLE] Kein BLE-Adapter - PVP/Gossip deaktiviert")
                self._ble_available = False
                return {"found": False}

            # Scan durchfuehren
            result = await scanner.scan_simple(timeout=duration)
            return result

        except ImportError:
            print("[BLE] game.ble_beacon nicht verfuegbar")
            self._ble_available = False
            return {"found": False}
        except Exception as e:
            print(f"[BLE] Scan-Fehler: {e}")
            return {"found": False}

    # ========================================
    # STATE: PVP_FOUND
    # ========================================

    async def _tick_pvp_found(self) -> None:
        """
        PVP-Gegner erkannt: ECC-Handshake + WiFi-Direct + Datenaustausch.

        Ablauf:
          1. ECC-Schluessel laden/generieren
          2. GATT-Handshake simulieren (BLE-Beacon-Daten als Basis)
          3. WiFi-Direct Tunnel oeffnen (wpa_cli P2P)
          4. Gossip-Payload + Charakter-Daten austauschen
          5. Tunnel schliessen
          6. -> BATTLE State mit opponent_data
        """
        if not self._ble_scan_result:
            self._state = OrchestratorState.IDLE
            return

        scan = self._ble_scan_result
        remote_mac = scan.get("mac", "")
        remote_name = scan.get("name", "Unbekannt")

        print(f"[PVP] Gegner erkannt: '{remote_name}' ({remote_mac})")
        print(f"[PVP] Level {scan.get('level', '?')} | "
              f"Floor {scan.get('floor', '?')} | "
              f"Klasse {scan.get('class_type', '?')}")

        # --- 1. ECC-Handshake ---
        session_key = None
        handshake_token = b"fallback_pvp_token"

        try:
            from ecc_crypto import ECCKeyManager, GATTHandshakeManager

            ecc = ECCKeyManager()

            # Keys aus Cold Storage laden oder neu generieren
            ecc_loaded = False
            try:
                cold = _get_cold_storage()
                key_data = cold.load_ecc_keys() if hasattr(cold, 'load_ecc_keys') else None
                if key_data:
                    ecc_loaded = ecc.import_keys(key_data)
            except Exception:
                pass

            if not ecc_loaded:
                print("[PVP] Generiere neue ECC-Keys...")
                ecc.generate_keys()
                # Keys in Cold Storage speichern
                try:
                    exported = ecc.export_keys()
                    if exported and hasattr(cold, 'save_ecc_keys'):
                        cold.save_ecc_keys(exported)
                except Exception:
                    pass

            # GATT-Handshake vorbereiten
            gatt = GATTHandshakeManager(ecc)
            local_payload = gatt.prepare_handshake_payload()

            if local_payload:
                print(f"[PVP] ECC-Handshake bereit ({len(local_payload)} Bytes)")
                # Remote-Payload: In echter Impl via GATT-Characteristic
                # Hier: Aus BLE-Scan-Ergebnis oder Simulation
                remote_ecc_fragment = bytes.fromhex(
                    scan.get("ecc_fragment", "00" * 12)
                ) if scan.get("ecc_fragment") else None

                # Handshake-Token fuer Seed-Generierung
                handshake_token = local_payload[:16]
            else:
                print("[PVP] ECC nicht verfuegbar, Fallback-Modus")

        except ImportError:
            print("[PVP] ecc_crypto nicht verfuegbar, Fallback-Modus")
        except Exception as e:
            print(f"[PVP] ECC-Fehler: {e}, Fallback-Modus")

        # --- 2. WiFi-Direct Tunnel ---
        wifi_bridge = None
        exchange_result = None

        try:
            from game.ble_beacon import WiFiDirectBridge

            wifi_bridge = WiFiDirectBridge()
            connect_result = await wifi_bridge.connect(
                remote_mac, remote_name, session_key
            )

            if connect_result.get("connected"):
                print(f"[PVP] WiFi-Direct verbunden! "
                      f"IF={connect_result.get('interface', '?')} "
                      f"IP={connect_result.get('ip', '?')}")

                # --- 3. Datenaustausch ---
                gossip = _get_gossip(self._character.get("name", ""))
                gossip_payload = gossip.prepare_gossip_payload(self._character)

                # Lokale Daten zusammenstellen
                local_exchange_data = {
                    "type": "pvp_exchange",
                    "version": 1,
                    "character": {
                        "name": self._character.get("name", ""),
                        "level": self._character.get("level", 1),
                        "class_type": self._character.get("class_type",
                                      self._character.get("class_name", "Stein")),
                        "atk_base": self._character.get("atk_base", 20),
                        "def_base": self._character.get("def_base", 20),
                        "spd_base": self._character.get("spd_base", 20),
                        "luk_base": self._character.get("luk_base", 20),
                        "hp": self._character.get("hp",
                              self._character.get("max_hp", 100)),
                        "current_floor": self._character.get("current_floor", 1),
                        "pvp_wins": self._character.get("pvp_wins", 0),
                        "ascension": self._character.get("ascension", 1),
                        "mac": self._character.get("mac", "00:00:00:00:00:01"),
                        "ip_suffix": self._character.get("ip_suffix", 1),
                    },
                    "gossip": gossip_payload,
                    "handshake_token": handshake_token.hex()
                    if isinstance(handshake_token, bytes) else handshake_token,
                }

                exchange_result = await wifi_bridge.exchange_data(
                    local_exchange_data, session_key
                )

                if exchange_result.get("success"):
                    remote_data = exchange_result.get("remote_data", {})
                    print(f"[PVP] Datenaustausch OK! "
                          f"({exchange_result.get('bytes_received', 0)} Bytes empfangen)")

                    # Remote-Character-Daten in Scan-Result integrieren
                    remote_char = remote_data.get("character", {})
                    if remote_char:
                        scan["opponent_data"] = remote_char
                        scan["ip_suffix"] = remote_char.get("ip_suffix", 2)

                    # Remote-Gossip-Daten integrieren
                    remote_gossip = remote_data.get("gossip", {})
                    if remote_gossip:
                        scan["gossip_data"] = remote_gossip

                    # Handshake-Token vom Remote
                    remote_token = remote_data.get("handshake_token", "")
                    if remote_token:
                        try:
                            scan["handshake_token"] = bytes.fromhex(remote_token)
                        except (ValueError, TypeError):
                            scan["handshake_token"] = handshake_token

                else:
                    print(f"[PVP] Datenaustausch fehlgeschlagen: "
                          f"{exchange_result.get('reason', '?')}")

            else:
                print(f"[PVP] WiFi-Direct fehlgeschlagen: "
                      f"{connect_result.get('reason', '?')}")

        except ImportError:
            print("[PVP] WiFi-Direct nicht verfuegbar")
        except Exception as e:
            print(f"[PVP] WiFi-Direct-Fehler: {e}")
        finally:
            # Tunnel immer schliessen
            if wifi_bridge and wifi_bridge.connected:
                try:
                    await wifi_bridge.disconnect()
                    print("[PVP] WiFi-Direct getrennt")
                except Exception:
                    pass

        # --- 4. Opponent-Daten aus BLE-Beacon als Fallback ---
        if not scan.get("opponent_data"):
            # Kein WiFi-Direct-Austausch: Beacon-Daten als Basis
            print("[PVP] Verwende BLE-Beacon-Daten als Gegner-Grundlage")
            scan["opponent_data"] = {
                "name": scan.get("name", "Unbekannt"),
                "level": scan.get("level", 1),
                "class_type": scan.get("class_type", "Stein"),
                "current_floor": scan.get("floor", 1),
                "pvp_wins": scan.get("pvp_wins", 0),
                "atk_base": 20 + scan.get("level", 1),
                "def_base": 20 + scan.get("level", 1),
                "spd_base": 20,
                "luk_base": 15,
                "hp": 80 + scan.get("level", 1) * 10,
                "ascension": 1,
                "mac": remote_mac,
                "ip_suffix": 2,
            }
            scan["handshake_token"] = handshake_token

        # Scan-Result aktualisieren
        self._ble_scan_result = scan

        # -> BATTLE State
        print(f"[PVP] -> Kampf gegen '{scan['opponent_data'].get('name', '?')}'!")
        self._state = OrchestratorState.BATTLE

    # ========================================
    # STATE: BATTLE
    # ========================================

    async def _tick_battle(self) -> None:
        """
        PVP-Kampf mit deterministischem Seed.

        Seed = SHA256(sorted_macs_by_ip_suffix + handshake_token)
        Ergebnis ist auf beiden Geraeten identisch.
        """
        if not self._character or not self._ble_scan_result:
            self._state = OrchestratorState.GOSSIP
            return

        scan = self._ble_scan_result
        opponent = scan.get("opponent_data", {})

        if opponent:
            det = _get_det_battle()

            # Deterministischen Seed aus BLE-Handshake generieren
            local_mac = self._character.get("mac", "00:00:00:00:00:01")
            remote_mac = scan.get("mac", "00:00:00:00:00:02")
            local_ip = self._character.get("ip_suffix", 1)
            remote_ip = scan.get("ip_suffix", 2)
            handshake_token = scan.get("handshake_token", b"fallback_pvp_token")
            if isinstance(handshake_token, str):
                handshake_token = handshake_token.encode()

            # IP-Kollision pruefen
            collision = det.check_ip_collision(local_ip, remote_ip)
            if collision["collision"]:
                print(f"[PVP] {collision['message']}")
                # Deterministisch aufloesen
                local_ip, remote_ip = det.resolve_ip_collision_deterministic(
                    local_mac, remote_mac, local_ip, remote_ip
                )
                self._character["ip_suffix"] = local_ip
                print(f"[PVP] Neue IPs: Lokal=.{local_ip}, Remote=.{remote_ip}")

            # Gemeinsamen Seed generieren (identisch auf beiden Geraeten)
            pvp_seed = det.generate_pvp_seed(
                [local_mac, remote_mac],
                [local_ip, remote_ip],
                handshake_token
            )

            print(f"[PVP] Deterministischer Kampf (Seed: {pvp_seed & 0xFFFF:04X}...)")

            # Spieler nach IP sortieren (kleinere IP = Player A)
            if local_ip < remote_ip:
                player_a, player_b = self._character, opponent
                local_is_a = True
            else:
                player_a, player_b = opponent, self._character
                local_is_a = False

            # Kampf ausfuehren
            battle = det.DeterministicBattle(pvp_seed)
            battle_result = battle.run_pvp(player_a, player_b)

            # Ergebnis aus lokaler Perspektive
            if local_is_a:
                local_won = battle_result["winner"] == "A"
            else:
                local_won = battle_result["winner"] == "B"

            battle_result["result"] = "WIN" if local_won else ("LOSS" if not local_won and battle_result["winner"] != "DRAW" else "DRAW")
            battle_result["rewards_eligible"] = local_won

            viz = _get_visualizer()
            viz.print_summary(
                battle_result,
                self._character.get("name", "Champion"),
                opponent.get("name", "Gegner")
            )

            # PVP-Cooldown registrieren
            mac = scan.get("mac", "")
            if mac:
                pvp_cd = _get_pvp_cooldown()
                pvp_cd.register_fight(mac)

            # Rewards bei Sieg
            if battle_result.get("rewards_eligible"):
                engine = _get_battle_engine()
                reward_result = engine.distribute_rewards(
                    self._character, battle_result,
                    floor=self._character.get("current_floor", 1),
                    ascension=self._character.get("ascension", 1)
                )
                viz.print_rewards(reward_result)

                # Level-Up Check
                levelup_svc = _get_levelup()
                level_up_data = levelup_svc.check_level_up(self._character)
                if level_up_data.get("can_level_up"):
                    self.perform_level_up(level_up_data)

                # Loot
                loot = self._generate_and_store_loot(
                    self._character.get("current_floor", 1),
                    battle_result
                )
                if loot:
                    print(f"[LOOT] {loot}")

        # Nach PVP -> Gossip-Austausch
        self._state = OrchestratorState.GOSSIP

    # ========================================
    # STATE: GOSSIP
    # ========================================

    async def _tick_gossip(self) -> None:
        """
        Gossip-Taverne-Austausch nach Begegnung.

        Nutzt die Remote-Gossip-Daten die im PVP_FOUND-State
        via WiFi-Direct empfangen wurden.
        Persistiert Ergebnisse in SQLite Cold Storage.
        """
        if not self._character or not self._ble_scan_result:
            self._state = OrchestratorState.IDLE
            return

        remote_name = self._ble_scan_result.get("name", "Unbekannt")

        try:
            gossip = _get_gossip(self._character.get("name", ""))

            # Gossip-Daten aus WiFi-Direct-Austausch (PVP_FOUND hat sie befuellt)
            remote_data = self._ble_scan_result.get("gossip_data", {})

            if remote_data:
                results = gossip.perform_full_exchange(remote_name, remote_data)
                gossip.print_taverne_summary(results, remote_name)

                # Weltboss-Check
                if results.get("worldboss", {}).get("triggered", False):
                    self._state = OrchestratorState.WORLDBOSS
                    return
            else:
                # Kein Gossip-Daten empfangen (WiFi-Direct fehlgeschlagen)
                # Minimalen Gossip-Austausch nur mit BLE-Beacon-Infos
                print(f"[GOSSIP] Nur BLE-Beacon-Daten verfuegbar, "
                      f"minimaler Austausch mit '{remote_name}'")

                # Trinkbuddy aktivieren (braucht nur den Namen)
                buddy_result = gossip.trinkbuddy.activate(remote_name)
                print(f"[GOSSIP] {buddy_result.get('message', '')}")

                # Leaderboard: Remote aus Beacon-Daten
                beacon_entry = {
                    "name": remote_name,
                    "level": self._ble_scan_result.get("level", 1),
                    "floor": self._ble_scan_result.get("floor", 1),
                    "pvp_wins": self._ble_scan_result.get("pvp_wins", 0),
                    "ascension": 1,
                }
                gossip.leaderboard.merge([{
                    **beacon_entry,
                    "score": gossip.leaderboard._calculate_score(beacon_entry),
                    "last_seen": __import__("time").time(),
                }])

                # Weltboss-Ping registrieren
                gossip.worldboss_trigger.register_ping(remote_name)

                # Speichern
                gossip.save_to_db()

        except Exception as e:
            print(f"[GOSSIP-ERROR] {e}")

        self._ble_scan_result = None
        self._state = OrchestratorState.IDLE

    # ========================================
    # STATE: WORLDBOSS
    # ========================================

    async def _tick_worldboss(self) -> None:
        """
        Weltboss-Raid koordinieren.

        Boss skaliert auf:
          - Anzahl der teilnehmenden Spieler
          - Quersumme der addierten Stats
          - Deterministischer Seed aus BLE-Handshake + MACs
        """
        if not self._character:
            self._state = OrchestratorState.IDLE
            return

        print("[WORLDBOSS] Raid-Koordination gestartet!")

        try:
            gen = _get_monster_gen()
            det = _get_det_battle()

            # Teilnehmer sammeln (aus Gossip-Daten)
            participants = [self._character]
            gossip_data = {}
            if self._ble_scan_result:
                gossip_data = self._ble_scan_result.get("gossip_data", {})
                # Remote-Spielerdaten aus Gossip
                remote_players = gossip_data.get("raid_participants", [])
                participants.extend(remote_players)

            num_players = len(participants)
            print(f"[WORLDBOSS] {num_players} Spieler im Raid")

            # Weltboss generieren (skaliert auf Spieler + Stats)
            floor = self._character.get("current_floor", 1)
            boss = gen.generate_worldboss(participants, trigger_floor=floor)

            print(f"[WORLDBOSS] {boss['name']}")
            print(f"[WORLDBOSS] HP={boss['hp']} ATK={boss['total_atk']} "
                  f"DEF={boss['total_def']} (Quersumme={boss['cross_sum']})")

            # Deterministischen Raid-Seed generieren
            scan = self._ble_scan_result or {}
            macs = scan.get("raid_macs", [self._character.get("mac", "00:00:00:00:00:01")])
            ips = scan.get("raid_ips", [self._character.get("ip_suffix", 1)])
            token = scan.get("handshake_token", b"fallback_token_raid")
            if isinstance(token, str):
                token = token.encode()

            # Sicherstellen dass Listen gleich lang sind
            while len(macs) < num_players:
                macs.append(f"00:00:00:00:00:{len(macs)+1:02d}")
            while len(ips) < num_players:
                ips.append(len(ips) + 1)

            raid_seed = det.generate_raid_seed(
                macs[:num_players], ips[:num_players],
                token, boss_id=f"wb_{floor}_{num_players}"
            )

            # Deterministischen Raid-Kampf ausfuehren
            battle = det.DeterministicBattle(raid_seed)
            raid_result = battle.run_raid(participants, boss)

            # Ergebnis anzeigen
            if raid_result["boss_defeated"]:
                print(f"\a[WORLDBOSS] BESIEGT in {raid_result['rounds']} Runden!")
                print(f"[WORLDBOSS] Ueberlebende: "
                      f"{raid_result['survivors']}/{raid_result['total_players']}")

                # Schadensranking
                for entry in raid_result["damage_ranking"][:5]:
                    alive = "[OK]" if entry["alive"] else "[KO]"
                    print(f"  {entry['name']:15s}: {entry['damage']:6d} DMG {alive}")

                # Rewards verteilen
                self._character["gold"] = self._character.get("gold", 0) + raid_result["gold_reward"]
                self._character["diamonds"] = self._character.get("diamonds", 0) + raid_result["diamond_reward"]
                self._character["xp"] = self._character.get("xp", 0) + raid_result["xp_reward"]

                print(f"[WORLDBOSS] Belohnung: {raid_result['gold_reward']} Gold, "
                      f"{raid_result['diamond_reward']} Diamanten, "
                      f"{raid_result['xp_reward']} XP")
            else:
                print(f"[WORLDBOSS] NIEDERLAGE nach {raid_result['rounds']} Runden")
                print(f"[WORLDBOSS] Boss-HP verbleibend: "
                      f"{raid_result['boss_hp_remaining']}/{raid_result['boss_max_hp']}")

        except Exception as e:
            print(f"[WORLDBOSS-ERROR] {e}")

        self._ble_scan_result = None
        self._state = OrchestratorState.IDLE

    # ========================================
    # STATE: SLEEP (Erschoepfungs-Pause)
    # ========================================

    async def _tick_sleep(self) -> None:
        """
        Erschoepfungs-Pause: Max 1h, dann Reset auf 80%.
        Waehrend der Pause: BLE-Scan + Gossip weiterhin moeglich.
        """
        now = asyncio.get_event_loop().time()
        elapsed = now - self._exhaustion_pause_start

        if elapsed >= self.EXHAUSTION_PAUSE:
            # 1h um -> Reset auf 80%
            self._character["exhaustion"] = 80.0
            print("[PSYCHE] Erschoepfungs-Pause beendet. Reset auf 80%.")
            self._state = OrchestratorState.IDLE
            return

        remaining = int(self.EXHAUSTION_PAUSE - elapsed)
        minutes = remaining // 60
        if remaining % 300 == 0 and remaining > 0:
            print(f"[SLEEP] Erschoepfungs-Pause: noch {minutes} Min...")

        await asyncio.sleep(30)

    # ========================================
    # STATE: CHECKPOINT
    # ========================================

    async def _tick_checkpoint(self) -> None:
        """Checkpoint: Spielstand sichern."""
        self._save_checkpoint()

    def _save_checkpoint(self) -> None:
        """Spielstand in Hot + Cold Storage sichern."""
        if not self._character:
            return

        try:
            hot = _get_hot_storage()
            hot.write(self._character, "character_data")

            cold = _get_cold_storage()
            cold.save("character_data", self._character)

            floor = self._character.get("current_floor", 1)
            level = self._character.get("level", 1)
            gold = self._character.get("gold", 0)
            print(f"[CHECKPOINT] Floor {floor} | Lv.{level} | Gold {gold}")

        except Exception as e:
            print(f"[CHECKPOINT-ERROR] {e}")

    # ========================================
    # GENTLY SHUTDOWN
    # ========================================

    async def _gently_shutdown(self) -> None:
        """
        Sauberes Herunterfahren:
          1. Spielstand sichern (Hot + Cold + DB)
          2. Hot -> Cold komplett flushen
          3. Gossip-DB schliessen
          4. Async Tasks beenden
        """
        print("\a", end="", flush=True)  # Bell: Shutdown
        print("=" * 60)
        print("[SHUTDOWN] Gently Shutdown gestartet...")
        print("=" * 60)

        # 1. Spielstand sichern
        try:
            init = _get_init_game()
            init._character = self._character
            init.save_current_state()
            print("[SHUTDOWN] Spielstand gesichert")
        except Exception as e:
            print(f"[SHUTDOWN-WARN] Spielstand: {e}")

        # 2. Hot -> Cold Flush
        try:
            hot = _get_hot_storage()
            result = hot.flush_to_cold()
            print(f"[SHUTDOWN] Hot->Cold: {result.get('flushed_count', 0)} Dateien")
        except Exception as e:
            print(f"[SHUTDOWN-WARN] Flush: {e}")

        # 3. Gossip-DB
        try:
            if _gossip:
                _gossip.close()
        except Exception:
            pass

        # 4. Codex-DB
        try:
            if _codex:
                _codex.close()
        except Exception:
            pass

        # 5. Async Tasks
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        print("=" * 60)
        print("[SHUTDOWN] Gently Shutdown abgeschlossen.")
        print("=" * 60)

    # ========================================
    # HILFSMETHODEN
    # ========================================

    def _generate_pve_enemy(self, floor: int) -> Dict[str, Any]:
        """
        Prozeduralen PVE-Gegner generieren via Monster-Generator.

        - Unendlich viele verschiedene Monster
        - Skaliert an Spieler-Level UND Klasse
        - Typ-System mit strategischer Verteilung
        - Boss alle 25 Floors
        - Biome-Modifier nach Floor-Bereich
        - Spezialfaehigkeiten ab Floor 10
        """
        try:
            gen = _get_monster_gen()
            return gen.generate_pve_monster(floor, self._character or {})
        except Exception as e:
            print(f"[MONSTER-WARN] Generator-Fehler: {e}")
            return self._generate_pve_enemy_fallback(floor)

    def _generate_pve_enemy_fallback(self, floor: int) -> Dict[str, Any]:
        """Minimaler Fallback falls Monster-Generator nicht verfuegbar."""
        types = ["Stein", "Schere", "Papier"]
        rng = random.Random(floor * 7919)
        enemy_type = types[floor % 3]
        base = 20 + floor // 5
        hp = 50 + floor * 3
        is_boss = (floor % 25 == 0) and (floor > 0)
        if is_boss:
            base = base * 150 // 100
            hp = hp * 2
        return {
            "name": f"Monster-F{floor}",
            "type": enemy_type,
            "level": max(1, floor // 10),
            "total_atk": min(50, base + rng.randint(0, 5)),
            "total_def": min(50, max(5, base - 5 + rng.randint(0, 5))),
            "total_spd": min(50, max(5, base - 3 + rng.randint(0, 5))),
            "total_luk": min(50, max(3, 10 + rng.randint(0, floor // 10))),
            "hp": hp, "max_hp": hp, "is_boss": is_boss,
        }

    def _generate_and_store_loot(self, floor: int, battle_result: Dict[str, Any]) -> str:
        """
        Generate loot via LootFactory.roll_drop() und direkt
        in character["inventory_items"] speichern.

        Returns: Beschreibung des Loots (oder leerer String wenn nichts)
        """
        try:
            lf = _get_loot_factory()
            player_luk = (self._character.get("base_luk", 10)
                          + self._character.get("extra_luk", 0))
            is_boss = battle_result.get("enemy_is_boss", False)
            biome = self._character.get("current_biome", "Neutral")

            drop = lf.roll_drop(
                player_luk=player_luk,
                floor=floor,
                biome=biome,
                is_boss=is_boss
            )

            if drop.get("dropped") and drop.get("item"):
                item = drop["item"]
                item["equipped"] = False
                self._character.setdefault("inventory_items", []).append(item)

                name = item.get("name", "Item")
                rarity = item.get("rarity_de", item.get("rarity", "?"))
                shiny = " SHINY!" if drop.get("is_shiny") else ""

                return f"{name} ({rarity}){shiny}"
        except Exception as e:
            print(f"[LOOT-ERROR] {e}")

        return ""

    def perform_level_up(self, level_up_data: Dict[str, Any]) -> None:
        """
        Perform level-up: Level erhoehen, EXP abziehen,
        Bonuspunkte als pending_bonus_points speichern.

        Die Verteilung der Punkte erfolgt MANUELL durch den
        Spieler im War Room (SSH-Menue).

        Args:
            level_up_data: Dict von check_level_up()
        """
        if not self._character:
            return

        try:
            levelup_svc = _get_levelup()

            # EXP abziehen und Level erhoehen
            old_level = self._character.get("level", 1)
            self._character["xp"] = self._character.get("xp", 0) - levelup_svc.XP_PER_LEVEL
            self._character["level"] = old_level + 1
            new_level = self._character["level"]

            # Bonuspunkte als pending speichern (kumulativ)
            bonus = levelup_svc.BONUS_PER_LEVEL
            pending = self._character.get("pending_bonus_points", 0)
            self._character["pending_bonus_points"] = pending + bonus

            # Bell-Audio als Hinweis
            print("\a", end="", flush=True)
            print(f"[LEVELUP] Level {old_level} -> {new_level}! "
                  f"+{bonus} Bonuspunkte verfuegbar "
                  f"(gesamt wartend: {pending + bonus}) "
                  f"-> Im War Room verteilen!")

        except Exception as e:
            print(f"[LEVELUP-ERROR] {e}")

    def get_state_info(self) -> Dict[str, Any]:
        """Aktueller Orchestrator-Status fuer Dashboard."""
        return {
            "state": self._state,
            "character": self._character.get("name") if self._character else None,
            "floor": self._character.get("current_floor") if self._character else 0,
            "level": self._character.get("level") if self._character else 0,
            "exhaustion": self._character.get("exhaustion") if self._character else 0,
            "gold": self._character.get("gold") if self._character else 0,
            "pve_cooldown_active": self._pve_cooldown_active,
            "running": self._running
        }


# ========================================
# EXPORT: save_game_state_to_cold
# ========================================

def save_game_state_to_cold():
    """
    Kompatibilitaets-Export fuer war_room.py und andere Module.
    Speichert aktuellen Spielstand in Cold Storage.
    """
    try:
        cold = _get_cold_storage()
        init = _get_init_game()
        char = init.get_character()
        if char:
            cold.save("character_data", char)
    except Exception as e:
        print(f"[SAVE-ERROR] {e}")


# ========================================
# ENTRY POINT
# ========================================

if __name__ == "__main__":
    orchestrator = HybridOrchestrator()

    try:
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        print("\n[EXIT] Orchestrator beendet.")
    except Exception as e:
        print(f"[FATAL] {e}")
        sys.exit(1)
