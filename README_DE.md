# Zero Tower Battle

## Was ist es?

**Zero Tower Battle (ZTB)** ist ein autonomes Idle-Tower-RPG und Auto-Battler, das headless auf einem Raspberry Pi Zero 2 WH läuft. Dein Champion erklimmt einen unendlichen Turm und kämpft Stockwerk für Stockwerk gegen prozedural generierte Monster. Wenn zwei Pi-Spieler in der Nähe sind, verbinden sie sich automatisch per Bluetooth Low Energy (BLE) für PVP-Kämpfe und sozialen Austausch über das "Gossip Taverne"-System.

Das Spiel benötigt keinen Monitor, keine Tastatur und keine Maus – alles läuft vollständig im Hintergrund und wird über SSH verwaltet.

## Hauptmerkmale

- **Autonomes Turm-Klettern (PVE)** mit Auto-Kämpfen – dein Champion kämpft selbstständig
- **Peer-to-Peer PVP per BLE** bei Erkennung nahegelegener Pi-Spieler
- **3 Klassen:** Krieger (Stein), Schurke (Schere), Magier (Papier) mit Schere-Stein-Papier Typvorteil
- **100-Punkte-Statsystem** (ATK/DEF/SPD/LUK summieren sich exakt auf 100, max 50 pro Stat)
- **Schmiede-System** für Charaktererstellung und Item-Upgrades
- **Loot-System:** Gewöhnlich (75%), Selten (20%), Legendär (5%)
- **Shiny-Begegnungen** (1:8192 Chance) mit 10x Gold und garantiert Legendär
- **Runen-Crafting** (Feuer/Gift/Blitz)
- **"Gossip Taverne" Sozialsystem:** Trinkbuddy-Buff, P2P-Bestenliste, Paketrelay, Weltboss-Trigger
- **Weltboss-Raids** (3+ Spieler in der Nähe lösen Boss aus)
- **Drei Währungen:** Gold, Diamanten (PVP/Weltboss), Seelensplitter (Turm ab Stockwerk 100)
- **Psyche-System** mit Erschöpfung, Moral und Trauma (nur milde Debuffs)
- **ECC-Kryptografie** für sichere P2P-Kommunikation (Curve25519/Ed25519)
- **Vollständige Lokalisierung** auf Deutsch und Englisch
- **SSH-basiertes War-Room-Menü** für Interaktion
- **Hot/Cold-Speichersystem** optimiert für 512MB RAM

## Hardware-Anforderungen

- Raspberry Pi Zero 2 WH (512MB RAM, integriertes WiFi + BLE)
- microSD-Karte (mindestens 8GB, 16GB empfohlen)
- DietPi oder Raspberry Pi OS Lite
- Netzteil (5V/2,5A Micro-USB)
- Kein Monitor, Tastatur oder Maus nötig (komplett headless)

## Installation

```bash
# 1. DietPi oder Raspberry Pi OS Lite auf microSD flashen
# 2. SSH aktivieren und WiFi konfigurieren
# 3. Per SSH verbinden
ssh pi@<ip-adresse>

# 4. Repository klonen
git clone https://github.com/Smilez1985/Zero-Tower-Battle.git /home/ZTB_Service/battle_game

# 5. One-Click-Installer ausführen
cd /home/ZTB_Service/battle_game
sudo bash install.sh

# 6. Das Spiel startet automatisch als Systemdienst
```

## Wie spielt man?

Das Spiel läuft **vollständig automatisch** im Hintergrund. Dein Champion kämpft, sammelt Erfahrung, steigt auf und sammelt Loot, während du schläfst oder andere Dinge tust.

**Zugriff auf das War Room Menü:**
```bash
ssh pi@<geraetename>
```

Im War-Room kannst du:
- Deine Stats einsehen
- Dein Inventar verwalten
- Den Shop besuchen
- In der Schmiede upgraden
- Runen verwalten
- Den Monster-Codex einsehen
- Taverne-Status überprüfen
- Und vieles mehr

**Progression:**
- Dein Champion klettert automatisch den Turm hinauf
- Alle 500 EXP gibt es ein Level-Up mit +5 verteilbaren Bonuspunkten
- Alle besiegten Monster geben Loot und Erfahrung
- PVP-Kämpfe passieren automatisch, wenn ein anderer Pi mit ZTB in der Nähe ist (BLE-Reichweite)
- Das Spiel speichert alle 5 Minuten und macht alle 20 Minuten ein volles Backup

## Dienst-Verwaltung

```bash
sudo systemctl status zero-tower-battle    # Status prüfen
sudo systemctl restart zero-tower-battle   # Neustart
sudo systemctl stop zero-tower-battle      # Stoppen
journalctl -u zero-tower-battle -f         # Logs anzeigen
```

## Projektstruktur

- `hybrid_orchestrator.py` – Haupt-Spielschleife (State Machine)
- `init_game.py` – Erststart-Setup, DB-Initialisierung
- `engine/battle_engine.py` – Kampfsystem
- `forge.py` – Charaktererstellung
- `loot_factory.py` – Item-Generierung
- `rewards.py` – Belohnungsberechnung
- `champion_psyche.py` – Erschöpfung/Moral-System
- `gossip_taverne.py` – P2P-Sozialfunktionen
- `ecc_crypto.py` – BLE-Verschlüsselung
- `ui/options/war_room.py` – SSH-Menü
- `i18n/` – Übersetzungen (DE/EN)

## Lizenz

Siehe LICENSE Datei für Details.
