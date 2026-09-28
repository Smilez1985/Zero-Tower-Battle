# Zero Tower Battle (ZTB) - Abhaengigkeiten & Architektur

## Uebersicht

Dieses Dokument beschreibt die Modulstruktur, Abhaengigkeiten und
das Zusammenspiel aller Komponenten im Zero Tower Battle Projekt.

Zielplattform: Raspberry Pi Zero 2 WH (512MB RAM, DietPi)
Python-Version: >= 3.9


## Externe Abhaengigkeiten (requirements.txt)

| Paket          | Version  | Pflicht? | Verwendet von              |
|----------------|----------|----------|----------------------------|
| rich           | >= 13.0  | Optional | ui/ssh_menu.py             |
| Pillow         | >= 9.0   | Optional | ui/ssh_menu.py             |
| click          | >= 8.0   | Optional | ui/ssh_menu.py             |
| pydantic       | >= 2.0   | Optional | services/forge_upgrade.py  |
| pytest         | >= 7.0   | Test     | tests/                     |
| pytest-cov     | >= 4.0   | Test     | tests/                     |
| pytest-asyncio | >= 0.21  | Test     | tests/                     |

Alle anderen Imports (sqlite3, asyncio, json, os, sys, subprocess,
signal, shutil, time, random, math, etc.) sind Teil der
Python-Standardbibliothek.


## Paketstruktur

```
code/
|
|-- initialisierung.py          # Entry Point (Lazy-Loading)
|-- hybrid_orchestrator.py      # Async State Machine (Hauptschleife)
|-- config.json                 # Hauptkonfiguration
|
|-- models/                     # Zentrale Datenmodelle
|   |-- player.py               # Player (Stats, Gold, XP, Kampf)
|   |-- enemy.py                # Enemy (HP, Loot, Rewards)
|   |-- inventory.py            # Inventar (unbegrenzt, Auto-Verwertung)
|   |-- character_db.py         # RAM-Disk DB mit SD-Sync
|   |-- season_manager.py       # Biom-Rotation (4 Jahreszeiten)
|
|-- game/                       # Spiellogik
|   |-- core.py                 # Game Engine (Lazy-Loading)
|   |-- game_loop.py            # Haupt-Loop (PVE/PVP)
|   |-- game_logic.py           # PVE-Autonommodus
|   |-- pve_game_loop.py        # PVE Loop (30s Delay-Start)
|   |-- pvp_game.py             # PVP Modus
|   |-- combat.py               # Schadensberechnung
|   |-- mode_switcher.py        # PVE/PVP Umschaltung
|   |-- save_handler.py         # Save-System (Hot/Cold)
|   |-- hot_cold_storage.py     # RAM/SQLite Speichermanager
|   |-- hot_storage.py          # RAM-Speicher (100MB)
|   |-- ble_beacon.py           # BLE Spielererkennung (50m)
|   |-- ai/ai_logic.py          # KI-Entscheidungen
|   |-- backup/backup_system.py # Backup alle 20 Min
|   |-- leaderboard/leaderboard.py  # Top-10 Rangliste
|   |-- levels/levels_data.py   # Endlose Floor-Progression
|   |-- models/player.py        # Re-Export -> models/player.py
|   |-- models/enemy.py         # Re-Export -> models/enemy.py
|   |-- network/network.py      # Netzwerk-Basis
|
|-- engine/
|   |-- battle_engine.py        # 100-Punkte-Kampfsystem
|
|-- controllers/                # Netzwerk-Kommunikation
|   |-- net_manager.py          # wlan0/tun0 Isolation
|   |-- battle_client.py        # TCP P2P Client
|   |-- battle_server.py        # TCP P2P Server
|   |-- battle_connector.py     # WiFi Direct Connector
|
|-- services/                   # Spielmechaniken
|   |-- battle_pve_service.py   # PVE Service (Lazy)
|   |-- battle_pvp_service.py   # PVP Service (Lazy)
|   |-- inventory.py            # Re-Export -> models/inventory.py
|   |-- shop.py                 # Rotierender Shop (24h)
|   |-- levelup.py              # XP/Level-Progression
|   |-- runes.py                # Runen-Crafting
|   |-- forge_upgrade.py        # Waffen-Upgrades (+1 bis +5)
|   |-- worldboss.py            # Weltboss-Raids (5 Tiers)
|   |-- lore_generator.py       # Markov-Chain Chroniken
|   |-- base_manager.py         # Basis-Ausbau
|   |-- sync_profile.py         # DB->JSON Sync (5 Min)
|   |-- ssh_menu.py             # SSH System-Management
|
|-- ui/                         # Benutzeroberflaeche
|   |-- main_menu.py            # Hauptmenue (-> WarRoom)
|   |-- ssh_menu.py             # Dashboard (Rich/PIL)
|   |-- settings.py             # Einstellungen
|   |-- language.py             # Sprachmodul (-> language_config)
|   |-- dashboard/dashboard.py  # Dashboard-Anzeige
|   |-- options/war_room.py     # War Room Menue
|   |-- options/war_room_options.py  # Menue-Parsing
|   |-- options/language_config.py   # DE/EN Uebersetzungen
|
|-- db/
|   |-- database.py             # SQLite Basis-Stub
|
|-- game_balance/               # Balancing
|   |-- enemies.json            # Gegner-Konfiguration
|   |-- player_balances.py      # Spieler-Skalierung
|   |-- tuners.py               # Balance-Anpassungen
|
|-- tests/                      # Unit Tests
|-- performance/                # Benchmarks
|-- config/                     # Zusatz-Konfiguration
|-- scripts/                    # Deploy-Skripte
```


## Abhaengigkeitsgraph (Wer importiert was)

### Entry Points

initialisierung.py:
  -> ui.options.war_room.WarRoom
  -> ui.settings.Settings
  -> game.game_loop.GameLoop

hybrid_orchestrator.py (Lazy):
  -> controllers.net_manager.NetworkHandler
  -> models.character_db.CharacterDB
  -> engine.battle_engine.BattleEngine
  -> ui.ssh_menu.SSHMenu


### models/ (Keine externen Abhaengigkeiten)

models/player.py:      typing
models/enemy.py:       typing
models/inventory.py:   json, typing, datetime
models/character_db.py: json, os, signal, datetime, typing, pathlib, collections
models/season_manager.py: typing, datetime, enum, math


### game/ (Abhaengig von models/)

game/game_loop.py:
  -> game.pve_game_loop.PVEGameLoop (Lazy)
  -> game.pvp_game.PVPGame (Lazy)
  -> game.levels.levels_data.Levels (Lazy)

game/core.py:
  -> game.hot_storage.HotStorageManager (Lazy)
  -> game.hot_storage.ColdStorageManager (Lazy)
  -> game.ble_beacon.BLEBeacon (Lazy)

game/models/player.py -> models.player.Player (Re-Export)
game/models/enemy.py  -> models.enemy.Enemy (Re-Export)


### engine/ (Standalone)

engine/battle_engine.py: random, socket, datetime, typing
  (Implementiert das 100-Punkte-Gesetz deterministisch)


### controllers/ (Netzwerk-Schicht)

controllers/net_manager.py: asyncio, subprocess, socket, json,
                           pathlib, datetime, typing, enum, time
controllers/battle_client.py: socket, json, asyncio, datetime, typing
controllers/battle_server.py: socket, json, asyncio, datetime, typing
controllers/battle_connector.py: subprocess, socket, json, asyncio,
                                uuid, datetime, typing


### services/ (Abhaengig von models/ und game/)

services/battle_pve_service.py -> game.pve_game_loop (Lazy)
services/battle_pvp_service.py -> game.pvp_game (Lazy)
services/inventory.py -> models.inventory.Inventory (Re-Export)
services/forge_upgrade.py: pydantic (extern!), typing, pathlib,
                          datetime, math
services/shop.py: datetime, typing, random
services/levelup.py: datetime, typing
services/runes.py: random, typing
services/worldboss.py: random, datetime, typing
services/lore_generator.py: random, typing
services/sync_profile.py: json, datetime, pathlib, typing, shutil
services/ssh_menu.py: os, subprocess, typing, datetime


### ui/ (Abhaengig von models/ und services/)

ui/ssh_menu.py:
  PIL (extern, optional)
  rich (extern, optional)
  click (extern, optional)

ui/main_menu.py -> ui.options.war_room.WarRoom (Lazy)
ui/language.py -> ui.options.language_config.LanguageSwitcher
ui/options/war_room.py -> ui.options.language_config.LanguageSwitcher
ui/options/war_room_options.py -> ui.options.language_config.LanguageSwitcher
ui/dashboard/dashboard.py -> ui.language.Language


## Lazy-Loading Strategie

Alle Dienste werden erst geladen wenn sie tatsaechlich benoetigt
werden. Das spart RAM auf dem Pi Zero (512MB):

1. hybrid_orchestrator.py: Nutzt Funktionen (_get_net_handler,
   _get_character_db, etc.) die erst beim ersten Aufruf importieren
2. game/game_loop.py: _get_pve_loop(), _get_pvp_game(), _get_levels()
3. game/core.py: _get_hot_storage(), _get_cold_storage(), _get_ble_beacon()
4. services/battle_pve_service.py: _ensure_loaded() vor jedem Zugriff
5. services/battle_pvp_service.py: _ensure_loaded() vor jedem Zugriff
6. ui/main_menu.py: _ensure_loaded() fuer WarRoom

Muster:
    def _get_something(self):
        if self._something is None:
            from modul.name import Something
            self._something = Something()
        return self._something


## Redundanz-Aufloesung

Folgende Dateien waren urspruenglich doppelt vorhanden und wurden
konsolidiert:

| Zentral (Quelle)      | Re-Export (Wrapper)        |
|------------------------|----------------------------|
| models/player.py       | game/models/player.py      |
| models/enemy.py        | game/models/enemy.py       |
| models/inventory.py    | services/inventory.py      |

Die Re-Export-Dateien existieren nur fuer Abwaertskompatibilitaet
und importieren lediglich aus dem zentralen Modul.


## Netzwerk-Architektur

wlan0 (192.168.4.1):
  - SSH Management (Port 2222)
  - hostapd Access Point
  - DHCP via dnsmasq (.10-.50)
  - Strikt isoliert von tun0!

tun0 (10.42.0.0/24):
  - P2P Tunnel fuer PVP
  - WiFi Direct Verbindungen
  - TCP Battle-Daten (Port 5005)

iptables:
  - FORWARD=DROP (Standard)
  - Kein Traffic zwischen wlan0 und tun0
  - secure_split_tunnel.sh konfiguriert Regeln


## Speicher-Architektur

Hot Storage (RAM):
  - /dev/shm/ (RAM-Disk)
  - /tmp/hot_storage/
  - ~100MB fuer aktive Spielddaten

Cold Storage (SD-Karte):
  - /home/ZTB_Service/cold_storage.db (SQLite)
  - Sync alle 20 Min (Hot -> Cold)
  - Emergency Save bei PVP/WorldBoss

Backup:
  - /home/ZTB_Service/battle_game/backups/
  - Automatisch alle 5 Min (Checkpoint)
  - Max 10 Backups (aelteste werden geloescht)
