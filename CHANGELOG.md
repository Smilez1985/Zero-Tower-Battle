# Changelog / Aenderungsprotokoll

All notable changes to Zero Tower Battle are documented in this file.

Alle wichtigen Aenderungen an Zero Tower Battle sind in dieser Datei dokumentiert.

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

Dieses Changelog bildet zusammen mit `docs/DESIGN.md` (Entscheidungen) und
`docs/ROADMAP.md` (offene Punkte) die Blaupause des Projekts.

---

## [Unreleased]

### Fixed / Behoben

#### Kampfsystem — PVE und PVP rechneten unterschiedlich
- `deterministic_battle.py` nutzte eine veraltete Schadensformel, in der ATK
  mit dem Level skalierte (`atk * 125 * level // 1000`), der DEF-Abzug aber
  konstant blieb (`def * 50 // 100`). `engine/battle_engine.py` hatte laengst
  die asymptotische V2-Formel. Ab Level 8 war DEF wirkungslos, ab Level 20
  endeten Kaempfe nach einer Runde.
- Beide Engines nutzen jetzt `DEF / (DEF + 50)` und dieselbe HP-Formel.
  Balance-Konstanten sind in beiden Klassen dokumentiert und per Test
  aneinander gebunden.
- Klassen-Siegquoten ueber alle Level: vorher 0-100 %, jetzt 42-57 %.

#### Kampfsystem — SPD war ein toter Stat
- SPD bestimmte ausschliesslich die Zugreihenfolge. Der Schurke (SPD 40)
  verlor dadurch systematisch.
- Neu: Chance auf einen Extra-Angriff, `min(45 %, SPD-Differenz x 1,5 %)`.

#### P2P — beide Geraete kamen zu verschiedenen Ergebnissen
- `battle_server.process_battle()` vergab die Rolle `player_a` immer an das
  lokale Profil. Da Spieler A bei SPD-Gleichstand zuerst zuschlaegt,
  ermittelten beide Seiten unterschiedliche Sieger. Jetzt entscheidet der
  lexikografisch kleinere Name, analog zur IP-Sortierung im Orchestrator.
- `battle_client.send_profile()` hatte kein `recv()`. Der Server sendete das
  Kampfergebnis, der Client las es nie — er erfuhr nicht, ob er gewonnen hat.
- Der Seed enthielt einen sekundengenauen Timestamp. Auf zwei Pis ohne RTC
  brach das bei Uhrendrift. Quantisierung auf 60-Sekunden-Fenster
  (`SEED_TIME_WINDOW`) als Zwischenloesung, siehe ROADMAP 5.4.

#### Laufzeitfehler
- `services/shop.py`: `check_shop_refresh()` verglich `timedelta` mit `int`
  und warf bei jedem Aufruf einen `TypeError`.
- `controllers/net_manager.py`: `dpkg-query` wurde mit
  `"apt-utils | grep dnsmasq"` als einzelnem Argument aufgerufen — die Pipe
  landete im Paketnamen, der Check konnte nie erfolgreich sein.
- `controllers/net_manager.py`: neuer `_safe_run()`-Wrapper. `check=False`
  faengt nur Fehler-Exitcodes ab, nicht ein fehlendes Binary; `ip`,
  `iptables` und `wpa_cli` brachten den Aufrufer zum Absturz.
- `install_battle_os.sh` war eine leere Datei (1 Byte), obwohl das README sie
  als `curl | bash`-Ziel bewirbt. Verweist jetzt auf `install.sh`.

### Added / Hinzugefuegt

- `docs/DESIGN.md`: tragende Entscheidungen, Spielmechaniken,
  Sicherheitskonzept und fuenf Architekturregeln.
- `docs/ROADMAP.md`: offene Punkte aus dem Review, nach Prioritaet sortiert.
- `docs/BALANCING.md`: Schadensformel, Messreihen, bekannte Schwaechen.
- `tests/test_battle_parity.py`: vergleicht die echten Schadensmethoden
  beider Engines, prueft Determinismus und Klassenbalance.
  Gegenprobe: mit der alten Formel schlagen 35 Faelle fehl.
- `tests/test_p2p_consistency.py`: simuliert beide Geraete und prueft, ob
  sie zu demselben Sieger, derselben Rundenzahl und demselben Log kommen.
  Gegenprobe: mit der alten Rollenvergabe schlagen 6 Faelle fehl.
- `requirements-dev.txt` fuer die Test-Abhaengigkeiten.

### Changed / Geaendert

- `tests/test_shop.py`, `test_inventory.py` und `test_net_manager.py` liefen
  wegen falscher Import-Pfade gar nicht an und pruefte eine API, die es nie
  gab. Neu geschrieben gegen die tatsaechliche Implementierung.
- `tests/conftest.py`: fehlender `pytest`-Import ergaenzt, hartkodierter
  Entwicklungspfad durch relative Aufloesung ersetzt.
- `requirements.txt`: `readchar` entfernt (kein Import im Projekt).
- Test-Suite: 34 laufende Tests (3 Dateien deaktiviert) -> 145, alle gruen.

### Security / Sicherheit

- SSID `Zero-WLAN` und WPA-Passphrase aus `hostapd.conf` entfernt; die Datei
  ist jetzt `hostapd.conf.example` mit Platzhaltern.
- Default-Passwort aus `install.sh` entfernt (jetzt `ZTB_DEFAULT_PASSWORD`
  oder interaktive Abfrage).
- `config.json` und `dnsmasq.conf` zu `*.example`-Vorlagen umgewandelt,
  Geraete- und Charakternamen neutralisiert.
- Private E-Mail-Adresse aus `anleitung.md` entfernt.
- Lokale Entwicklerpfade aus systemd-Units, Deploy-Skript, Doku und
  `conftest.py` entfernt.
- `.gitignore` deckt jetzt Schluessel, Spielstaende, Laufzeit-Konfiguration
  und Session-Material ab.

> Nicht behoben: Port 5005 nimmt JSON-Profile weiterhin ohne
> Schema-Validierung entgegen (ROADMAP 4.4), und Kampfergebnisse werden
> nicht signiert (ROADMAP 4.2). Beides ist vor jedem oeffentlichen Einsatz
> zu schliessen.

---

## [0.1.0] - 2026-04-04

### Added / Hinzugefuegt

#### Core Gameplay
- Hybrid Orchestrator state machine with 9 states: IDLE, BLE_SCAN, PVP_FOUND, BATTLE, GOSSIP, CHECKPOINT, WORLDBOSS, SLEEP, SHUTDOWN
- Autonomous PVE tower climbing with procedurally generated monsters
- Peer-to-peer PVP combat system via Bluetooth Low Energy (BLE)
- Worldboss raid system (3+ nearby players trigger cooperative boss battles)
- Rock-Paper-Scissors class advantage system (Warrior/Rogue/Mage)

#### Character & Combat System
- Character creation forge with 100-point stat distribution system
- Stat limits: ATK/DEF/SPD/LUK, max 50 per stat, sum = 100
- Three character classes: Krieger (Warrior/Rock), Schurke (Rogue/Scissors), Magier (Mage/Paper)
- PVE auto-battle engine with integer-based damage calculations
- Level-up system: Every 500 XP grants +5 distributable bonus points
- Integer-based combat to ensure P2P determinism (no floating-point errors)

#### Progression & Loot
- Loot factory with three rarities: Common (75%), Rare (20%), Legendary (5%)
- Shiny encounter system: 1 in 8192 chance for special monsters with 10x gold and guaranteed legendary items
- Forge upgrade system for character and item enhancements
- Rune crafting system with Fire, Poison, and Lightning runes
- Three-currency economy: Gold, Diamonds, and Soul Shards
- Monster codex tracking system for encountered enemies
- Season biomes affecting loot tables and encounters

#### Social Features (Gossip Taverne)
- Trinkbuddy buff system: +10% gold bonus for 1 hour after meeting another player
- P2P leaderboard with decentralized top-100 rankings
- Packet relay system for asynchronous item and message delivery
- Rune formula exchange between nearby players
- Worldboss trigger coordination for 3+ players
- Drop & Leave system for leaving items as treasures for other players

#### Advanced Systems
- Champion Psyche system with exhaustion, morale, and trauma tracking
- Mild debuff effects only (no stat penalties, only loot/XP/gold reductions)
- ECC cryptography for secure P2P communication using Curve25519/Ed25519
- Hot/Cold storage system optimized for 512MB RAM constraints
- Full localization support: German and English language options
- SSH War Room interactive menu with 11+ features
- PVP cooldown per MAC address: 30 minutes between same-opponent battles
- Auto-save every 5 minutes with full backups every 20 minutes

#### Deployment & Operations
- One-click installer for Raspberry Pi (install.sh)
- Systemd service integration for automatic game startup
- Live log viewing via systemd journal
- Service management commands for status, restart, and stop
- Backup and restoration system for save data

### Architecture / Architektur

- **Single-process architecture**: All game logic runs in one process to minimize RAM usage on Pi Zero 2
- **Lazy import strategy**: Modules loaded on-demand to keep baseline memory under 20MB idle
- **BLE constraint**: Bluetooth scanning only during 90-second PVE cooldown to avoid interference with single-radio chip (BCM43436)
- **Split-tunnel networking**: SSH access (wlan0 AP) and PVP communication (tun0 WiFi-Direct) run in parallel
- **Integer-only arithmetic**: All critical calculations use integer division to ensure deterministic P2P results
- **State machine design**: Game loop uses clear state transitions for maintainability and testability
- **Database-driven storage**: SQLite3 for player data, inventory, and leaderboards
- **RAM budget**: Target under 45MB during SSH sessions with OOM protection at 90% threshold
