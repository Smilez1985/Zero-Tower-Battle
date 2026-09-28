#!/bin/bash
# ============================================
# ZERO TOWER BATTLE - Autostart Script
# ============================================
# Raspberry Pi Zero 2 WH (Headless + WiFi)
#
# Ablauf:
#   1. Warte bis Netzwerk bereit (max 60s)
#   2. SSH aktivieren
#   3. Verzeichnisse + Hot Storage bereinigen
#   4. System-Info loggen
#   5. Hybrid Orchestrator starten
# ============================================

set -euo pipefail

# Dynamischer User (aus config.json oder Fallback)
SERVICE_USER="${ZTB_USER:-ZTB_Service}"
SERVICE_HOME=$(eval echo "~${SERVICE_USER}" 2>/dev/null || echo "/home/${SERVICE_USER}")
GAME_DIR="${SERVICE_HOME}/battle_game"
COLD_STORAGE="${SERVICE_HOME}/ztb_cold_storage"
HOT_STORAGE="/tmp/ztb_hot_storage"
LOG_FILE="/var/log/zero-tower-battle.log"
PID_FILE="/var/run/zero-tower-battle.pid"
STARTUP_DELAY=10

export PYTHONPATH="$GAME_DIR"
export PYTHONUNBUFFERED=1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# ============================================
# 1. Verzeichnisse sicherstellen
# ============================================
mkdir -p "$COLD_STORAGE"
mkdir -p "$HOT_STORAGE"
mkdir -p "$(dirname "$LOG_FILE")"

log "============================================"
log "ZERO TOWER BATTLE - Autostart"
log "  User: ${SERVICE_USER}"
log "  Home: ${SERVICE_HOME}"
log "============================================"

# ============================================
# 2. Warte bis Netzwerk bereit
# ============================================
log "Warte auf Netzwerk..."
counter=0
while [ $counter -lt 60 ]; do
    if ip route 2>/dev/null | grep -q "default"; then
        log "Netzwerk bereit"
        break
    fi
    counter=$((counter + 1))
    sleep 1
done

if [ $counter -ge 60 ]; then
    log "WARN: Netzwerk Timeout (60s) - starte trotzdem"
fi

# ============================================
# 3. SSH aktivieren
# ============================================
log "SSH aktivieren..."
systemctl start ssh 2>/dev/null || service ssh start 2>/dev/null || true

# ============================================
# 4. Verzoegerter Start (System stabilisieren)
# ============================================
log "Warte ${STARTUP_DELAY}s (System-Stabilisierung)..."
sleep "$STARTUP_DELAY"

# ============================================
# 5. Cold Storage Recovery Check
# ============================================
if [ -f "$COLD_STORAGE/character_data.json" ]; then
    log "Cold Storage Spielstand gefunden -> Recovery"
else
    log "Kein Spielstand -> Neues Spiel (Erststart)"
fi

# ============================================
# 6. Hot Storage bereinigen
# ============================================
if [ -d "$HOT_STORAGE" ]; then
    rm -rf "${HOT_STORAGE:?}"/*
    log "Hot Storage bereinigt"
fi

# ============================================
# 7. System-Info
# ============================================
log "System-Info:"
log "  RAM: $(free -m 2>/dev/null | awk '/Mem:/{print $2}')MB total, $(free -m 2>/dev/null | awk '/Mem:/{print $7}')MB frei"
log "  Disk: $(df -h / 2>/dev/null | awk 'NR==2{print $4}') frei"
log "  Cold Storage: $(ls -1 "$COLD_STORAGE"/*.json 2>/dev/null | wc -l) Dateien"

# ============================================
# 8. BLE-Adapter pruefen
# ============================================
if hciconfig hci0 2>/dev/null | grep -q "UP RUNNING"; then
    log "BLE-Adapter: aktiv"
else
    log "WARN: BLE-Adapter nicht verfuegbar - PVP/Gossip nur via WiFi"
    hciconfig hci0 up 2>/dev/null || true
fi

# ============================================
# 9. Orchestrator starten
# ============================================
log "Starte Hybrid Orchestrator..."
log "  -> PVE-Loop aktiv"
log "  -> BLE-Scan im 90s Cooldown"
log "  -> Checkpoint alle 5 Min"

cd "$GAME_DIR" 2>/dev/null || {
    log "FATAL: $GAME_DIR nicht gefunden!"
    exit 1
}

# PID speichern
echo $$ > "$PID_FILE"

# Orchestrator starten (laedt selbst aus Cold Storage)
exec python3 -u "$GAME_DIR/hybrid_orchestrator.py" 2>&1 | tee -a "$LOG_FILE"
