# 📋 ZERO TOWER BATTLE - TODO LISTE

## 🎮 STATUS

| Component | Status | Priority |
|------------|----------|-- -----|
| **Game Engine** | 🟡 **TO DO** | High |
| **Hot Storage** | 🟡 **TO DO** | High |
| **Cold Storage** | 🟡 **TO DO** | Medium |
| **PVE Game Loop** | 🟡 **TO DO** | High |
| **PVP System** | 🔴 **TO DO** | High |
| **BLE Beacon** | 🔴 **TO DO** | High |
| **WiFi Direct** | 🟡 **TO DO** | Medium |
| **Save System** | 🟡 **TO DO** | High |
| **TUI Dashboard** | 🟡 **TO DO** | High |
| **Service Daemon** | 🟢 **DONE** | Done |
| **Install Script** | 🟡 **TO DO** | High |

---

## 💻 MISSING FILES

### **High Priority:**
1. `game/core/` (Empty)
2. `engine/core.py` (Engine)
3. `engine/save_handler.py` (Save System)
4. `hot_storage_manager.py` (RAM)
5. `cold_storage_manager.py` (SD/Cloud)
6. `ble_beacon.py` (PVP Suche)
7. `wifi_direct_split.py` (WiFi Direct)
8. `pve_game_loop.py` (Autonomer PVE)
9. `pvp_game.py` (PVP Kampf)
10. `ui/dashboard.py` (TUI)
11. `services/battle_pve.service` (PVE Service)
12. `services/battle_pvp.service` (PVP Service)
13. `models/enemy.py` (Gegner Model)
14. `models/player.py` (Spieler Model)
15. `models/tower.py` (Turm Model)

### **Medium Priority:**
- `ui/help_pages/`
- `models/battle.json` (Config)
- `models/loadevels.json`
- `audio/` (Sound)

---

## 📝 FILES LIST

### **Core Files:**
1. `engine/core.py` (Game Engine)
2. `game/save_handler.py` (Save Logic)
3. `hot_storage.py` (RAM Storage)
4. `cold_storage.py` (SD/Cloud Storage)
5. `ble_beacon.py` (PVP Find)
6. `wifi_direct.py` (WiFi Direct)
7. `pve_game_loop.py` (PVE Loop)
8. `pvp_game.py` (PVP Kampf)
9. `ui/dashboard.py` (TUI Dashboard)

### **Models:**
1. `models/enemy.py` (Enemy Model)
2. `models/player.py` (Player Model)
3. `models/tower.py` (Tower Model)
4. `models/battle.json` (Config)

### **Services:**
1. `services/battle-pve.service`
2. `services/battle-pvp.service`

---

## 🎯 GOAL

**1. Game Engine**
   - Core loop
   - PVE/PVP switching
   - Save system

**2. Storage**
   - Hot: RAM/RAMDisk
   - Cold: SD/Cloud

**3. PvP**
   - BLE Beacon
   - WiFi Direct

**4. UI**
   - TUI Dashboard
   - Status Display

**5. Service**
   - Delayed Start
   - Autostart

---

## 🔧 UPDATE PLAN

**Step 1:** Core Files
**Step 2:** Game Engine
**Step 3:** Storage
**Step 4:** PVE/PVP
**Step 5:** UI
**Step 6:** Service
**Step 7:** Install Script
**Step 8:** Documentation

---

✅ **Ready to Implement!**
