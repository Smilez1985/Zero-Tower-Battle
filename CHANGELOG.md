# Changelog / Aenderungsprotokoll

All notable changes to Zero Tower Battle are documented in this file.

Alle wichtigen Aenderungen an Zero Tower Battle sind in dieser Datei dokumentiert.

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
