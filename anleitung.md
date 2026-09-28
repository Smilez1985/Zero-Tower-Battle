# 🎮 Zero Tower Battle - Spielanleitung
# ==================================

## 📋 WAS IST ZERO TOWER BATTLE?

**Kurzbeschreibung:**
- 🎮 **Battle-Modus:** SSH-Terminal + TUI + Dashboard
- ⚔️ **Warroom:** Einzelfrontend über SSH
- 🎯 **TUI:** Terminal User Interface

**Alle drei Begriffe** sind ein **einziges Frontend:**
- ✅ **Dashboard** = **TUI** = **Warroom**

---

## 🚀 INSTALLATION (One-Click)

### **Erforderlich:**
- Raspberry Pi Zero 2 WH
- DietPi (OS auf SD-Card)
- SD-Card ≥ 8GB

### **Schritt 1: One-Click Install**

```bash
bash /code/install.sh
```

**Was passiert:**
- ✅ System-Pakete
- ✅ SSH + tmux (für persistente Sessions)
- ✅ systemd Service + Autostart
- ✅ Delayed Start (45Sek)
- ✅ **TUI (Dashboard)** nur bei SSH-Verbindung
- ✅ Berechtigungen

### **Schritt 2: SSH Verbindung**

**Zum Spiel verbinden:**
```bash
ssh pi@zero-tower-battle
```

**Erstes Mal:**
```bash
# Passwort setzen
ssh pi@zero-tower-battle
passwd
# (neu erstellen: root → pi)

# Spiel starten
ssh pi@zero-tower-battle
# → **TUI/Dashboard/Warroom** erscheint
```

---

## 🎮 SPIEL NUTZUNG

### **Modus:**

| Modus | Beschreibung |
|-------|-----|
| **Autonom** | Pi läuft mit Powerbank (Service) |
| **SSH-Verbindung** | **TUI/Dashboard** erscheint (automatisch) |
| **Powerbank** | Autonom laufen |
| **Lazy Loading** | **Dashboard erst bei Bedarf** (lazy) |

---

### **Spiel starten:**

**1. Spiel autonom (Powerbank):**
```bash
# Pi startet → Service + Delay Start
# (45sek nach Boot)
# **Warroom (Dashboard)** läuft
```

**2. SSH verbunden → **Dashboard/TUI erscheint:**
```bash
ssh pi@zero-tower-battle
# → **TUI/Dashboard/Warroom** erscheint automatic!
```

**3. **Dashboard nur bei Bedarf** (Lazy Loading):**
```bash
# Dashboard = TUI = Warroom
# Nur beim Aufbau von SSH-Verbindung
```

---

### **Interface Features:**

**Im TUI:**
- ✅ **Level 1** (Start)
- ✅ **Karte** (Kraftstation + Gegner)
- ✅ **Charakter** (Level, HP, Stats)
- ✅ **Battle** (Kampf)
- ✅ **Chat** (Gegner, Log)
- ✅ **Settings** (Sprache, Difficulty, PowerBank)

**Steuerung:**
- ⬆️ ⬇️ ↑ ← → (Wegen)
- **q** (Leave Dashboard)
- **h** (Help)
- **?** (Commands)

---

### **Powersave-Modus:**

**Wenn nicht verwendet:**
```bash
# Dashboard (TUI) verlassen
# Pi läuft weiter autonom
```

---

### **Login nach Autostart:**

```bash
# Pi startet autonom
# 45sek Verzögerung (delayed)
# SSH verbinden
ssh pi@zero-tower-battle
# → **TUI/Dashboard** erscheint automatic!
```

---

## 🔧 KONFIGURATION

### **Lokalisierung:**

```bash
# Deutsch (default) oder Englisch
nano /etc/default/locale

LANG=de_DE.UTF-8  # Deutsch
LANG=en_US.UTF-8  # Englisch
```

### **Difficulty:**

```bash
# Nano: editieren
nano /etc/zero-tower-battle/conf.json
# difficulty: 1 (easy) → 3 (hard)
```

### **PowerBank Setup:**

```bash
# USB-C Anschluss
# Powerbank Modus
# Auto-Run + Delay-Start
```

---

## 🐛 TROUBLESHOOTING

### **Problem: TUI nicht erscheint**

```bash
# Service prüfen
systemctl status zero-tower-battle.service
# Log:
journalctl -u zero-tower-battle.service -n 100 -f

# Dashboard nur bei SSH-Verbindung
ssh pi@zero-tower-battle
# → TUI sollte erscheinen
```

### **Problem: Service nicht startet**

```bash
# Logfiles
cat /var/log/zero-tower-battle.log -f

# Service start
systemctl start zero-tower-battle.service
```

### **Problem: SD-Karte voll**

```bash
# log2ram
# ZRAM prüfen
zramctl

# SD cleanup
cleaner /tmp
```

---

## 📁 DATEIEN

| Datei | Inhalt |
|-------|--------|
| install.sh | One-Click Install |
| battle_daemon.py | Autostart + TUI |
| zero-tower-battle.service | systemd Service |
| anleitung.md | **Diese Anleitung** |
| project-memory.md | Changelog |

---

## 🚀 QUICKSTART

**Startspiel:**
```bash
bash /code/install.sh
```

**SSH verbinden → Tui erscheint:**
```bash
ssh pi@zero-tower-battle
# → **Dashboard/Warroom/TUI** erscheint
```

**Autonom laufen:**
```bash
# Service läuft
# Pi-Start: 45sek delay
```

**Dashboard verlassen:**
```bash
q (Quit)
# oder SSH verlassen
```

---

## 📞 HILFE

**Issues:**
- https://github.com/Smilez1985/Zero-Tower-Battle/issues

**Support:**
- E-Mail: siehe GitHub-Profil (Issues bevorzugt)
- Discord: #zero-tower-battle-channel

---

## 📜 LICENSE

Zero Tower Battle - All rights reserved
© 2024 Smilez1985

---

**Ende der Anleitung (Updated: dashboard=tui=warroom)**
