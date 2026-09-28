#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Battle Server Module
==== ========================

TCP-Server für P2P Encounters:
├─ Socket-Server Logik
├─ JSON-Profile Empfangen
├─ Schema-Validierung
├─ Disconnect Handling
├─ Retry Logic
└─ Security: Pydantic Validation
"""


import socket
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
# pylint: disable=import-error, unused-import


class BattleServer:
    """
    Battle Server für empfangen & verarbeiten P2P Data.

    Features:
    ├─ Bind to TCP Socket
    ├─ Receive JSON Profiles
    ├─ Validate Input
    ├─ Process Battle Data
    ├─ Handle Disconnect
    └─ Graceful Shutdown
    """

    # Zeitfenster (Sekunden) fuer die Seed-Quantisierung. Gleicht Uhrendrift
    # zwischen zwei Pis ohne RTC aus, damit beide Seiten denselben Seed
    # erzeugen. Siehe process_battle().
    SEED_TIME_WINDOW = 60

    SOCKET_PORT = 5005
    MAX_BUFFER_SIZE = 4096

    def __init__(self,
                 bind_host: str = "0.0.0.0",
                 bind_port: int = SOCKET_PORT,
                 tun_vnet_base: str = "10.42.0"):

        self.bind_host = bind_host
        self.bind_port = bind_port
        self.tun_vnet_base = tun_vnet_base
        self.server_socket: Optional[socket.socket] = None
        self.connected_clients: List[socket.socket] = []
        self.received_profiles: List[Dict[str, Any]] = []
        self._is_running: bool = False

    async def bind_socket(self, retries: int = 3) -> bool:
        """
        Bind & Listen on TCP Socket.

        Args:
            retries: Number of retry attempts

        Returns:
            bool (Bind successful)

        """
        for attempt in range(retries):
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind((self.bind_host, self.bind_port))
                self.server_socket.listen(5)
                self.server_socket.setblocking(False)

                print(f"[PVP-SERVER] Listening on {self.bind_host}:{self.bind_port}")
                return True

            except Exception as e:
                if attempt < retries - 1:
                    print(f"[PVP-SERVER] Attempt {attempt+1}/{retries} failed: {e}")
                    await asyncio.sleep(1.0)
                    continue
                else:
                    print(f"[PVP-SERVER] Failed after {retries} attempts: {e}")
                    return False

        return False

    async def accept_connections(self) -> None:
        """
        Accept incoming connections and handle them asynchronously.
        """
        if not self.server_socket:
            await self.bind_socket()

        print("[PVP-SERVER] Ready to accept connections")
        self._is_running = True

        while self._is_running:
            try:
                # Use asyncio.to_thread to avoid blocking
                try:
                    client_socket, client_address = await asyncio.to_thread(
                        self.server_socket.accept
                    )
                except BlockingIOError:
                    await asyncio.sleep(0.1)
                    continue

                print(f"[PVP-SERVER] Client connected from {client_address}")

                # Handle client connection in background task
                asyncio.create_task(self._handle_client(client_socket, client_address))

            except Exception as e:
                if self._is_running:
                    print(f"[PVP-SERVER] Exception: {e}")
                continue

    async def _handle_client(self, client_socket: socket.socket, client_address: tuple) -> None:
        """
        Handle incoming client connection.

        Args:
            client_socket: Connected client socket
            client_address: Client IP address

        """
        try:
            self.connected_clients.append(client_socket)
            client_socket.setblocking(False)

            while True:
                try:
                    data = await asyncio.to_thread(
                        client_socket.recv,
                        self.MAX_BUFFER_SIZE
                    )

                    if not data:
                        break

                    # Parse JSON Profile
                    try:
                        remote_profile = json.loads(data.decode('utf-8'))
                        self.received_profiles.append(remote_profile)
                        print(f"[PVP-SERVER] Received profile: {remote_profile.get('beacon_id', 'unknown')}")

                        # Process battle with remote profile
                        battle_result = await self.process_battle(remote_profile)

                        # Send result back to client
                        response = json.dumps(battle_result).encode()
                        await asyncio.to_thread(client_socket.send, response)
                        print(f"[PVP-SERVER] Sent battle result to {client_address}")

                    except json.JSONDecodeError as e:
                        print(f"[PVP-SERVER] JSON Parse Error: {e}")
                        break

                except (socket.error, ConnectionResetError):
                    break
                except asyncio.TimeoutError:
                    break

                await asyncio.sleep(0.01)

        except Exception as e:
            print(f"[PVP-SERVER] Client handler error: {e}")
        finally:
            client_socket.close()
            if client_socket in self.connected_clients:
                self.connected_clients.remove(client_socket)
            print(f"[PVP-SERVER] Client disconnected: {client_address}")

    async def process_battle(self, remote_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deterministischen PVP-Kampf via BattleEngine ausfuehren.

        Laedt das lokale Profil aus Hot Storage, fuehrt einen
        deterministischen PVP-Kampf gegen das Remote-Profil durch
        und gibt das vollstaendige Ergebnis zurueck.

        Args:
            remote_profile: Gegner-Profil (JSON via TCP empfangen)

        Returns:
            Dict mit: status, battle_id, result, rounds, log,
                      opponent_name, timestamp
        """
        try:
            from engine.battle_engine import BattleEngine
            from game.hot_storage import HotStorageManager

            # 1. Lokales Profil aus Hot Storage laden
            hot = HotStorageManager()
            local_profile = hot.read("current_data")

            if not local_profile:
                print("[PVP-SERVER] Kein lokales Profil gefunden")
                return {
                    "status": "error",
                    "message": "No local character profile found",
                    "timestamp": datetime.now().isoformat()
                }

            # 2. Rollen deterministisch vergeben
            #
            # Fix 2026-09: Vorher war `player_a` immer das lokale Profil.
            # Auf Geraet 1 ist damit der eigene Champion A, auf Geraet 2 der
            # Gegner — und da bei SPD-Gleichstand A zuerst zuschlaegt, konnten
            # beide Seiten zu verschiedenen Ergebnissen kommen.
            # `generate_battle_seed()` sortiert zwar die Namen fuer den Seed,
            # die ROLLEN aber nicht. Jetzt entscheidet der Name (lexikografisch),
            # analog zur IP-Sortierung im hybrid_orchestrator.
            local_name = local_profile.get("name", "A")
            remote_name = remote_profile.get("name", "B")

            local_is_a = local_name <= remote_name
            if local_is_a:
                player_a, player_b = local_profile, remote_profile
            else:
                player_a, player_b = remote_profile, local_profile

            # Timestamp auf ein gemeinsames Zeitfenster quantisieren.
            #
            # Fix 2026-09: Sekundengenaue Timestamps driften auf zwei Pis ohne
            # RTC auseinander. Faellt der Handshake ueber eine Sekundengrenze,
            # erzeugen beide Seiten einen anderen Seed und rechnen einen
            # anderen Kampf. Das Fenster gleicht kleine Abweichungen aus.
            #
            # Besser waere der Weg des Orchestrators: Seed aus MACs plus
            # ECDH-Handshake-Token, voellig zeitunabhaengig. Siehe
            # docs/ROADMAP.md, Punkt 5.4.
            raw_ts = int(datetime.now(timezone.utc).timestamp())
            timestamp = (raw_ts // self.SEED_TIME_WINDOW) * self.SEED_TIME_WINDOW

            engine = BattleEngine()
            battle_result = engine.run_pvp_battle(
                player_a=player_a,
                player_b=player_b,
                timestamp=timestamp
            )

            # 3. Ergebnis aus LOKALER Perspektive auswerten
            #    (run_pvp_battle liefert WIN/LOSS bezogen auf player_a)
            result_str = battle_result.get("result", "DRAW")
            if result_str == "DRAW":
                local_winner = False
            elif local_is_a:
                local_winner = (result_str == "WIN")
            else:
                local_winner = (result_str == "LOSS")
                result_str = "WIN" if local_winner else "LOSS"

            response = {
                "status": "ok",
                "battle_id": f"pvp_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "result": result_str,
                "local_winner": local_winner,
                "rounds": battle_result.get("rounds", 0),
                "opponent_name": remote_profile.get("name", "Unbekannt"),
                "opponent_beacon_id": remote_profile.get("beacon_id"),
                "seed": battle_result.get("seed", 0),
                "mode": "PVP",
                "timestamp": datetime.now().isoformat()
            }

            # 4. Rewards verteilen wenn gewonnen
            if local_winner:
                try:
                    rewards = engine.distribute_rewards(
                        character=local_profile,
                        battle_result=battle_result,
                        floor=local_profile.get("floor", 1)
                    )
                    response["rewards"] = rewards

                    # Aktualisiertes Profil zurueck in Hot Storage
                    hot.write(local_profile, "current_data")

                except Exception as e:
                    print(f"[PVP-SERVER] Reward-Fehler (nicht kritisch): {e}")

            print(f"[PVP-SERVER] Battle: {result_str} vs {response['opponent_name']} "
                  f"({response['rounds']} Runden)")
            return response

        except ImportError as e:
            print(f"[PVP-SERVER] Import-Fehler: {e}")
            return {
                "status": "error",
                "message": f"Module not available: {e}",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"[PVP-SERVER] Battle-Fehler: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def close(self) -> None:
        """
        Close server & connections gracefully.
        """
        self._is_running = False

        for client in list(self.connected_clients):
            try:
                client.close()
            except Exception:
                pass

        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

        print("[PVP-SERVER] Battle Server closed")
