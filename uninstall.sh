#!/bin/bash
# ============================================
# ZERO TOWER BATTLE - Uninstaller
# ============================================
# Entfernt alle ZTB-Komponenten sauber.
# ACHTUNG: Spielstaende werden geloescht!
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

# Dynamischer User
SERVICE_USER="${ZTB_USER:-ZTB_Service}"
SERVICE_HOME=$(eval echo "~${SERVICE_USER}" 2>/dev/null || echo "/home/${SERVICE_USER}")
GAME_DIR="${SERVICE_HOME}/battle_game"

echo -e "${RED}ZERO TOWER BATTLE - Uninstaller${NC}"
echo "================================="
echo ""
echo -e "  Service User: ${SERVICE_USER}"
echo -e "  Game Dir:     ${GAME_DIR}"
echo ""
echo -e "${YELLOW}WARNUNG: Alle Spielstaende werden geloescht!${NC}"
read -p "Wirklich deinstallieren? (ja/nein): " CONFIRM

if [ "$CONFIRM" != "ja" ] && [ "$CONFIRM" != "j" ] && [ "$CONFIRM" != "yes" ] && [ "$CONFIRM" != "y" ]; then
    echo "Abgebrochen."
    exit 0
fi

# 1. Service stoppen und deaktivieren
echo "Service stoppen..."
systemctl stop zero-tower-battle.service 2>/dev/null || true
systemctl disable zero-tower-battle.service 2>/dev/null || true
rm -f /etc/systemd/system/zero-tower-battle.service 2>/dev/null || true
systemctl daemon-reload 2>/dev/null || true

# 2. Autostart entfernen
echo "Autostart entfernen..."
rm -f /etc/init.d/battle-daemon 2>/dev/null || true
update-rc.d -f battle-daemon remove 2>/dev/null || true

# 3. Spielstaende loeschen
echo "Spielstaende loeschen..."
rm -rf "${SERVICE_HOME}/ztb_cold_storage" 2>/dev/null || true
rm -rf "${GAME_DIR}/backups" 2>/dev/null || true
rm -f "${SERVICE_HOME}/cold_storage.db" 2>/dev/null || true

# 4. Hot Storage bereinigen
echo "Hot Storage bereinigen..."
rm -rf /tmp/ztb_hot_storage 2>/dev/null || true
rm -f /dev/shm/ztb.db* 2>/dev/null || true

# 5. Log-Dateien loeschen
echo "Logs loeschen..."
rm -rf "${GAME_DIR}/logs" 2>/dev/null || true
rm -f /var/log/zero-tower-battle.log 2>/dev/null || true

# 6. PID-Datei
rm -f /var/run/zero-tower-battle.pid 2>/dev/null || true

# 7. Config-Verzeichnis
rm -rf /etc/zero-tower-battle 2>/dev/null || true

# 8. Sudoers-Datei
rm -f /etc/sudoers.d/ztb-service 2>/dev/null || true

# 9. Spielverzeichnis (optional)
echo ""
read -p "Auch ${GAME_DIR} komplett loeschen? (ja/nein): " DELETE_GAME

if [ "$DELETE_GAME" = "ja" ] || [ "$DELETE_GAME" = "j" ] || [ "$DELETE_GAME" = "yes" ] || [ "$DELETE_GAME" = "y" ]; then
    echo "Spielverzeichnis loeschen..."
    rm -rf "${GAME_DIR}" 2>/dev/null || true
    echo -e "${GREEN}Komplett entfernt.${NC}"
else
    echo "Spielverzeichnis bleibt erhalten."
fi

# 10. Service-User loeschen (optional)
echo ""
read -p "Auch den User '${SERVICE_USER}' loeschen? (ja/nein): " DELETE_USER

if [ "$DELETE_USER" = "ja" ] || [ "$DELETE_USER" = "j" ] || [ "$DELETE_USER" = "yes" ] || [ "$DELETE_USER" = "y" ]; then
    echo "User ${SERVICE_USER} loeschen..."
    userdel -r "${SERVICE_USER}" 2>/dev/null || true
    echo -e "${GREEN}User entfernt.${NC}"
else
    echo "User bleibt erhalten."
fi

# 11. tmux-Session beenden
tmux kill-session -t ztb 2>/dev/null || true

echo ""
echo -e "${GREEN}Deinstallation abgeschlossen.${NC}"
echo "Python-Pakete (bleak, cryptography, etc.) wurden nicht entfernt."
echo "Zum Entfernen: pip3 uninstall bleak cryptography readchar rich pillow"
