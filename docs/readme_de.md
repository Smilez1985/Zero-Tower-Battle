# Zero Tower Battle - User Guide (Nutzerdokumentation)

## 🎮 Was ist Zero Tower Battle?

Eine **multiplayer-fähige Tower Defense**-Simulation für **Pi Zero 2W** mit:
- **Kampfsimulation** (PvE - autonomer Kampf)
- **Team Battle** (PvP - multiplayer)
- **Weltboss Raids**
- **Leaderboards**

## 🚀 Quick Start

### 1. Systemvoraussetzungen
- **Hardware**: Raspberry Pi Zero 2W
- **RAM**: 512MB + 4GB Swap
- **SD-Karte**: 4GB+ MicroSD
- **Netzwerk**: WiFi + Bluetooth

### 2. Installation
```bash
cd /home/ZTB_Service/battle_game
systemctl start battle-pve
```

### 3. Spiel starten
Im War Room Menü:
1. Sprache wählen (Deutsch/Englisch)
2. PvP wählen (Kampfsimulation)
3. Spiel starten

## 🎮 Steuerung

| Taste | Funktion |
|-------|----------|
| `Enter` | Menü bestätigen |
| `↑`/`↓` | Oben/Unten |
| `→`/`←` | Links/Rechts |
| `ESC` | Menü pausieren |
| `Ctrl+C` | Beenden |

## ⚙️ Einstellungen (Sprache + Optionen)

### Im War Room:
1. Menü öffnen (`ESC`)
2. **Settings** wählen
3. **Sprache**: Deutsch ↔ English

### Optionen:
- **Resolution**: 480×640 (Standard)
- **Sound**: ON/OFF
- **Difficulty**: Easy/Medium/Hard
- **Backup Interval**: 20 Minuten
- **PvP Timeout**: 60 Sekunden

## 🏆 Spielmodi

### PVE (Kampfsimulation)
- **Autonomer Kampf** gegen Bots
- **AI gesteuerte Tower**
- **Weltboss Raids**
- **Alle 20min Auto-Save**

### PvP (Team Battle)
- **Multiplayer** (WiFi Direct)
- **BLE Beacon** für Spieler-Suche
- **Sofortiges Backup** bei PvP
- **Team-Kämpfe**

## 📊 Spielstatus

```
Level    Score    Health    Enemies Defeated
Level 1  1,000    100/100  10
```

## 💾 Datenspeicherung

- **Hot Storage**: RAM (Temp)
- **Cold Storage**: SD (SQLite/MySQL)
- **Backup**: Alle 20min → SD
- **Emergency**: Sofort bei PvP/WorldBoss

## 🔧 Wartung

### Updates prüfen
```bash
sudo systemctl status battle-pve
```

### Logs ansehen
```bash
tail -f /home/ZTB_Service/battle_game/logs/battle.log
```

### Datenbank zurücksetzen (Nur Advanced)
```bash
sqlite3 /home/ZTB_Service/cold_storage.db "VACUUM;"
```

## 🆘 Support

### Bei Problemen
1. Logs ansehen: `tail -f battle.log`
2. Sprache im War Room ändern
3. Backup-Logs prüfen: `ls -la /home/ZTB_Service/cold_storage.db`
4. Support-Dokumente: `./docs/`

---

**Viel Spaß Spielen! 🏆👊**
