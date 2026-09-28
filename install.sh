#!/bin/bash
# Zero Tower Battle - One-Click Installer
# Pi Zero 2 WH (DietPi Headless + Raspbian)
# ==========================================
#
# Erstellt einen dedizierten Service-User (ZTB_Service),
# installiert alle Abhaengigkeiten, richtet Bluetooth ein,
# konfiguriert RAMdisk, zRAM, Swap, und startet den Service.
#
# Verwendung:
#   sudo bash install.sh

set -e  # Exit on error

# ANSI Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ============================================================================
# DEFAULTS
# ============================================================================

SERVICE_USER="ZTB_Service"
SERVICE_HOME="/home/${SERVICE_USER}"
GAME_DIR="${SERVICE_HOME}/battle_game"
CONFIG_FILE="${GAME_DIR}/config.json"
DEFAULT_PASSWORD="${ZTB_DEFAULT_PASSWORD:-}"   # per ENV setzen oder Installer fragt interaktiv
HOT_STORAGE_RAMDISK="/tmp/ztb_hot_storage"
HOT_STORAGE_MAX_MB=100
ZTB_GROUP="ztb"

# ============================================================================
# DEFAULT-USER ERKENNUNG (wer hat sudo ausgefuehrt?)
# ============================================================================
# Automatisch den User erkennen der den Installer gestartet hat.
# Dieser User bekommt Lese-/SCP-Zugriff auf das Game-Dir.

if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
    DEFAULT_USER="$SUDO_USER"
else
    # Fallback: ersten nicht-root User mit UID >= 1000 finden
    DEFAULT_USER=$(awk -F: '$3 >= 1000 && $3 < 65534 && $1 != "nobody" {print $1; exit}' /etc/passwd)
    if [ -z "$DEFAULT_USER" ]; then
        DEFAULT_USER="dietpi"  # Letzter Fallback
    fi
fi

# ============================================================================
# HELPER FUNCTIONS (bilingual)
# ============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  ZERO TOWER BATTLE - Installation${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${CYAN}--- $1 ---${NC}"
}

print_ok() {
    echo -e "${GREEN}  [OK] $1${NC}"
}

print_warn() {
    echo -e "${YELLOW}  [!]  $1${NC}"
}

print_err() {
    echo -e "${RED}  [X]  $1${NC}"
}

# ============================================================================
# ROOT CHECK
# ============================================================================

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}  [X] This script must be run as root (sudo bash install.sh)${NC}"
    exit 1
fi

# ============================================================================
# SPRACHE / LANGUAGE SELECTION
# ============================================================================

print_header

echo -e "${BLUE}  Sprache / Language${NC}"
echo ""
echo "  [1] Deutsch"
echo "  [2] English"
echo ""
read -p "  Auswahl / Choice [1/2]: " LANG_CHOICE

case "$LANG_CHOICE" in
    2|en|EN|english|English)
        GAME_LANG="en"
        echo ""
        echo -e "${GREEN}  Language: English${NC}"
        MSG_SYSTEM_DETECT="System Detection"
        MSG_CONFIG="Configuration"
        MSG_DEVICE_NAME="Device Name"
        MSG_HOSTNAME="Hostname (unique per Pi)"
        MSG_USER_SETUP="Service User Setup"
        MSG_USER_CREATE="Creating dedicated service user"
        MSG_USER_EXISTS="Service user already exists"
        MSG_USER_PW_PROMPT="Set password for ${SERVICE_USER} (default: ${DEFAULT_PASSWORD})"
        MSG_USER_PW_SET="Password set"
        MSG_HOSTNAME_SET="Hostname set"
        MSG_SYS_UPDATE="System Update (apt dist-upgrade)"
        MSG_SYS_PKG="Installing System Packages"
        MSG_PY_PKG="Installing Python Dependencies"
        MSG_BT="Configuring Bluetooth"
        MSG_GAMEDIR="Setting Up Game Directory"
        MSG_WIFI="WiFi Configuration"
        MSG_SERVICE="Creating systemd Service"
        MSG_LOCALE="Locale Setup"
        MSG_RAMDISK="RAMdisk for Hot Storage"
        MSG_ZRAM="zRAM Compression"
        MSG_SWAP="Swap Configuration"
        MSG_DONE="INSTALLATION COMPLETE!"
        MSG_NEXT="Next Steps"
        MSG_START_SVC="Start the service:"
        MSG_CHECK_SVC="Check service status:"
        MSG_VIEW_LOGS="View logs:"
        MSG_SSH="SSH Access (login as ${SERVICE_USER})"
        MSG_FINISHED="Installation finished!"
        MSG_DEFAULT="default"
        MSG_PW_CHANGE="You can change the password later with: sudo passwd ${SERVICE_USER}"
        MSG_SD_CHECK="SD Card Check"
        MSG_SD_SIZE="SD card size"
        MSG_SD_FREE="Free space"
        MSG_SWAP_CURRENT="Current swap"
        MSG_SWAP_TARGET="Target swap size"
        MSG_SWAP_QUESTION="Set swap to"
        MSG_UPDATE_QUESTION="Run full system update first? (recommended)"
        MSG_YES_NO="[y/n]"
        MSG_ONBOARD_TITLE="HOW TO CONNECT FROM YOUR PHONE"
        MSG_ONBOARD_STEP1="1. Install 'Termux' from F-Droid (NOT Google Play!)"
        MSG_ONBOARD_STEP2="2. Connect your phone to this WiFi network:"
        MSG_ONBOARD_STEP3="3. Open Termux and type:"
        MSG_ONBOARD_STEP4="4. Password:"
        MSG_ONBOARD_STEP5="5. The War Room starts automatically after login!"
        MSG_ONBOARD_STEP6="6. On first login you will create your character."
        MSG_ONBOARD_TIP="TIP: Install 'openssh' in Termux first:"
        MSG_ONBOARD_TIP_CMD="pkg install openssh"
        MSG_CHAR_FIRST="Character will be created on first SSH login"
        ;;
    *)
        GAME_LANG="de"
        echo ""
        echo -e "${GREEN}  Sprache: Deutsch${NC}"
        MSG_SYSTEM_DETECT="Systemerkennung"
        MSG_CONFIG="Konfiguration"
        MSG_DEVICE_NAME="Geraetename"
        MSG_HOSTNAME="Hostname (eindeutig pro Pi)"
        MSG_USER_SETUP="Service-Benutzer einrichten"
        MSG_USER_CREATE="Erstelle dedizierten Service-User"
        MSG_USER_EXISTS="Service-User existiert bereits"
        MSG_USER_PW_PROMPT="Passwort fuer ${SERVICE_USER} setzen (Standard: ${DEFAULT_PASSWORD})"
        MSG_USER_PW_SET="Passwort gesetzt"
        MSG_HOSTNAME_SET="Hostname gesetzt"
        MSG_SYS_UPDATE="Systemaktualisierung (apt dist-upgrade)"
        MSG_SYS_PKG="Systempakete installieren"
        MSG_PY_PKG="Python-Abhaengigkeiten installieren"
        MSG_BT="Bluetooth konfigurieren"
        MSG_GAMEDIR="Spielverzeichnis einrichten"
        MSG_WIFI="WiFi-Konfiguration"
        MSG_SERVICE="systemd-Service erstellen"
        MSG_LOCALE="Locale einrichten"
        MSG_RAMDISK="RAMdisk fuer Hot Storage"
        MSG_ZRAM="zRAM Komprimierung"
        MSG_SWAP="Swap Konfiguration"
        MSG_DONE="INSTALLATION ABGESCHLOSSEN!"
        MSG_NEXT="Naechste Schritte"
        MSG_START_SVC="Service starten:"
        MSG_CHECK_SVC="Service-Status pruefen:"
        MSG_VIEW_LOGS="Logs ansehen:"
        MSG_SSH="SSH-Zugang (login als ${SERVICE_USER})"
        MSG_FINISHED="Installation abgeschlossen!"
        MSG_DEFAULT="Standard"
        MSG_PW_CHANGE="Passwort spaeter aendern mit: sudo passwd ${SERVICE_USER}"
        MSG_SD_CHECK="SD-Karten Pruefung"
        MSG_SD_SIZE="SD-Karten Groesse"
        MSG_SD_FREE="Freier Speicher"
        MSG_SWAP_CURRENT="Aktueller Swap"
        MSG_SWAP_TARGET="Ziel-Swap Groesse"
        MSG_SWAP_QUESTION="Swap setzen auf"
        MSG_UPDATE_QUESTION="Volles System-Update durchfuehren? (empfohlen)"
        MSG_YES_NO="[j/n]"
        MSG_ONBOARD_TITLE="SO VERBINDEST DU DICH VOM HANDY"
        MSG_ONBOARD_STEP1="1. Installiere 'Termux' von F-Droid (NICHT Google Play!)"
        MSG_ONBOARD_STEP2="2. Verbinde dein Handy mit diesem WLAN-Netzwerk:"
        MSG_ONBOARD_STEP3="3. Oeffne Termux und tippe:"
        MSG_ONBOARD_STEP4="4. Passwort:"
        MSG_ONBOARD_STEP5="5. Der War Room startet automatisch nach dem Login!"
        MSG_ONBOARD_STEP6="6. Beim ersten Login erstellst du deinen Charakter."
        MSG_ONBOARD_TIP="TIPP: Installiere zuerst 'openssh' in Termux:"
        MSG_ONBOARD_TIP_CMD="pkg install openssh"
        MSG_CHAR_FIRST="Charakter wird beim ersten SSH-Login erstellt"
        ;;
esac

# ============================================================================
# SYSTEM CHECK + SD CARD DETECTION
# ============================================================================

print_section "$MSG_SYSTEM_DETECT"

if [ -f /etc/dietpi/dietpi-version ]; then
    print_ok "DietPi $(cat /etc/dietpi/dietpi-version 2>/dev/null | head -1)"
    IS_DIETPI=1
else
    print_warn "Raspbian / Raspberry Pi OS"
    IS_DIETPI=0
fi

ARCH=$(uname -m)
print_ok "Architecture: $ARCH"

# RAM
RAM_TOTAL_MB=$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo "0")
print_ok "RAM: ${RAM_TOTAL_MB} MB"

# ============================================================================
# SD CARD SIZE DETECTION
# ============================================================================

print_section "$MSG_SD_CHECK"

# Root-Partition Device finden
ROOT_DEV=$(findmnt -no SOURCE / 2>/dev/null | sed 's/[0-9]*$//' | sed 's/p$//')
if [ -z "$ROOT_DEV" ]; then
    ROOT_DEV="/dev/mmcblk0"
fi

# SD-Karten Gesamtgroesse in GB
SD_SIZE_BYTES=$(lsblk -bno SIZE "$ROOT_DEV" 2>/dev/null | head -1)
if [ -z "$SD_SIZE_BYTES" ] || [ "$SD_SIZE_BYTES" = "0" ]; then
    # Fallback: blockdev
    SD_SIZE_BYTES=$(blockdev --getsize64 "$ROOT_DEV" 2>/dev/null || echo "0")
fi
SD_SIZE_GB=$(( SD_SIZE_BYTES / 1073741824 ))

# Freier Speicher auf /
FREE_SPACE_MB=$(df -m / 2>/dev/null | awk 'NR==2 {print $4}')
FREE_SPACE_GB=$(( FREE_SPACE_MB / 1024 ))

# Aktueller Swap
CURRENT_SWAP_MB=$(awk '/SwapTotal/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo "0")

print_ok "$MSG_SD_SIZE: ${SD_SIZE_GB} GB"
print_ok "$MSG_SD_FREE: ${FREE_SPACE_GB} GB (${FREE_SPACE_MB} MB)"
print_ok "$MSG_SWAP_CURRENT: ${CURRENT_SWAP_MB} MB"

# ============================================================================
# SWAP SIZE BERECHNUNG (25% der SD, gerundet auf runde Zahlen)
# ============================================================================

# Schritt 1: 25% der SD-Karte in MB
RAW_SWAP_MB=$(( SD_SIZE_GB * 1024 / 4 ))

# Schritt 2: Auf naechste runde Zahl aufrunden
# Runde Zahlen: 1024 (1GB), 2048 (2GB), 3072 (3GB), 4096 (4GB),
#               5120 (5GB), 6144 (6GB), 7168 (7GB), 8192 (8GB)
# -> Aufrunden auf naechste volle 1024 MB (= 1 GB Schritte)
RECOMMENDED_SWAP_MB=$(( ((RAW_SWAP_MB + 1023) / 1024) * 1024 ))

# Minimum: 1024 MB (1 GB)
if [ "$RECOMMENDED_SWAP_MB" -lt 1024 ]; then
    RECOMMENDED_SWAP_MB=1024
fi

# Maximum: 8192 MB (8 GB)
if [ "$RECOMMENDED_SWAP_MB" -gt 8192 ]; then
    RECOMMENDED_SWAP_MB=8192
fi

# Label fuer Anzeige
SWAP_LABEL="$(( RECOMMENDED_SWAP_MB / 1024 )) GB"

echo ""
echo -e "  ${BOLD}SD: ${SD_SIZE_GB}GB -> ${MSG_SWAP_QUESTION} ${SWAP_LABEL}? ${MSG_YES_NO}${NC}"
read -p "  " SWAP_CONFIRM

case "$SWAP_CONFIRM" in
    j|J|y|Y|ja|yes|"")
        ADJUST_SWAP=1
        print_ok "${MSG_SWAP_TARGET}: ${SWAP_LABEL} (${RECOMMENDED_SWAP_MB} MB)"
        ;;
    *)
        ADJUST_SWAP=0
        print_ok "Swap bleibt bei ${CURRENT_SWAP_MB} MB"
        ;;
esac

# ============================================================================
# USER INPUT (Hostname, Device — KEIN Charaktername hier!)
# ============================================================================

print_section "$MSG_CONFIG"

CURRENT_HOSTNAME=$(hostname 2>/dev/null || echo "unknown")
echo -e "  ${BOLD}Current Hostname: ${CURRENT_HOSTNAME}${NC}"
echo ""

read -p "  $MSG_HOSTNAME ($MSG_DEFAULT: ztb-tower-01): " NEW_HOSTNAME
NEW_HOSTNAME=${NEW_HOSTNAME:-"ztb-tower-01"}
# Hostname sanitize: lowercase, nur a-z 0-9 und Bindestrich
NEW_HOSTNAME=$(echo "$NEW_HOSTNAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/--*/-/g' | sed 's/^-//' | sed 's/-$//')

read -p "  $MSG_DEVICE_NAME ($MSG_DEFAULT: ${NEW_HOSTNAME}): " DEVICE_NAME
DEVICE_NAME=${DEVICE_NAME:-"$NEW_HOSTNAME"}

# Kein HERO_NAME hier! Charakter wird beim ersten SSH-Login erstellt.
echo ""
echo -e "  ${YELLOW}$MSG_CHAR_FIRST${NC}"

print_ok "$MSG_HOSTNAME: $NEW_HOSTNAME"
print_ok "$MSG_DEVICE_NAME: $DEVICE_NAME"

# ============================================================================
# FULL SYSTEM UPDATE (apt update + dist-upgrade)
# ============================================================================

print_section "$MSG_SYS_UPDATE"

echo ""
echo -e "  ${BOLD}$MSG_UPDATE_QUESTION ${MSG_YES_NO}${NC}"
read -p "  " UPDATE_CONFIRM

case "$UPDATE_CONFIRM" in
    j|J|y|Y|ja|yes|"")
        print_ok "apt-get update..."
        apt-get update -qq 2>&1 | tail -3 || print_warn "apt-get update had issues"

        print_ok "apt-get dist-upgrade (kann einige Minuten dauern)..."
        DEBIAN_FRONTEND=noninteractive apt-get dist-upgrade -y -qq 2>&1 | tail -5 || print_warn "dist-upgrade had issues"

        # Aufraeumen
        DEBIAN_FRONTEND=noninteractive apt-get autoremove -y -qq 2>/dev/null || true
        apt-get autoclean -qq 2>/dev/null || true
        print_ok "System aktualisiert"
        ;;
    *)
        print_ok "apt-get update (nur Paketlisten)..."
        apt-get update -qq > /dev/null 2>&1 || print_warn "apt-get update had issues"
        print_ok "Dist-Upgrade uebersprungen"
        ;;
esac

# ============================================================================
# CREATE DEDICATED SERVICE USER (ZTB_Service)
# ============================================================================

print_section "$MSG_USER_SETUP"

# Shared Group erstellen (fuer Zugriff von Default-User auf Game-Dir)
if ! getent group "${ZTB_GROUP}" > /dev/null 2>&1; then
    groupadd "${ZTB_GROUP}" 2>/dev/null || true
    print_ok "Gruppe '${ZTB_GROUP}' erstellt"
else
    print_ok "Gruppe '${ZTB_GROUP}' existiert bereits"
fi

if id "${SERVICE_USER}" &>/dev/null; then
    print_ok "$MSG_USER_EXISTS (${SERVICE_USER})"
else
    print_ok "$MSG_USER_CREATE (${SERVICE_USER})..."

    # User erstellen mit Home-Dir, bash shell, Primary Group = ztb
    useradd -m -s /bin/bash -g "${ZTB_GROUP}" -G sudo "${SERVICE_USER}" 2>/dev/null || {
        print_err "Failed to create user ${SERVICE_USER}"
        exit 1
    }
    print_ok "User ${SERVICE_USER} created (primary group: ${ZTB_GROUP})"
fi

# Service-User zur ztb-Gruppe hinzufuegen (falls User schon existierte)
usermod -aG "${ZTB_GROUP}" "${SERVICE_USER}" 2>/dev/null || true

# Gruppen sicherstellen (bluetooth, gpio falls vorhanden, dialout fuer Serial)
for grp in bluetooth gpio dialout i2c spi; do
    if getent group "$grp" > /dev/null 2>&1; then
        usermod -aG "$grp" "${SERVICE_USER}" 2>/dev/null || true
    fi
done
print_ok "Groups: ${ZTB_GROUP}, bluetooth, gpio, dialout (where available)"

# Default-User (z.B. dietpi) in die ztb-Gruppe aufnehmen
# -> Damit kann der Default-User via SCP auf das Game-Dir zugreifen
if id "${DEFAULT_USER}" &>/dev/null; then
    usermod -aG "${ZTB_GROUP}" "${DEFAULT_USER}" 2>/dev/null || true
    print_ok "Default-User '${DEFAULT_USER}' zur Gruppe '${ZTB_GROUP}' hinzugefuegt"
    print_ok "  -> ${DEFAULT_USER} kann jetzt per SCP auf ${GAME_DIR} zugreifen"
else
    print_warn "Default-User '${DEFAULT_USER}' nicht gefunden"
fi

# Passwort setzen
echo ""
echo -e "  ${BOLD}$MSG_USER_PW_PROMPT${NC}"
echo ""
read -s -p "  Password [Enter = ${DEFAULT_PASSWORD}]: " USER_PASSWORD
echo ""
USER_PASSWORD=${USER_PASSWORD:-"$DEFAULT_PASSWORD"}

echo "${SERVICE_USER}:${USER_PASSWORD}" | chpasswd 2>/dev/null || {
    print_warn "chpasswd failed, trying alternative..."
    echo -e "${USER_PASSWORD}\n${USER_PASSWORD}" | passwd "${SERVICE_USER}" 2>/dev/null || {
        print_err "Could not set password. Set manually: sudo passwd ${SERVICE_USER}"
    }
}
print_ok "$MSG_USER_PW_SET (${SERVICE_USER})"
echo -e "  ${YELLOW}$MSG_PW_CHANGE${NC}"

# sudo ohne Passwort fuer den Service (fuer shutdown, systemctl)
SUDOERS_FILE="/etc/sudoers.d/ztb-service"
cat > "$SUDOERS_FILE" << SUDOEOF
# Zero Tower Battle - Service User Permissions
${SERVICE_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop zero-tower-battle.service
${SERVICE_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl start zero-tower-battle.service
${SERVICE_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart zero-tower-battle.service
${SERVICE_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl status zero-tower-battle.service
${SERVICE_USER} ALL=(ALL) NOPASSWD: /sbin/shutdown
${SERVICE_USER} ALL=(ALL) NOPASSWD: /sbin/reboot
SUDOEOF
chmod 440 "$SUDOERS_FILE"
print_ok "Sudoers configured (service + shutdown only)"

# ============================================================================
# GAME FILES KOPIEREN
# ============================================================================
# Kein Git-Repo vorhanden — Dateien werden direkt aus dem
# aktuellen Verzeichnis ins Game-Dir des Service-Users kopiert.
# Spaeter wird dies durch git clone ersetzt wenn ein Repo existiert.

print_section "Game Files kopieren"

# Game-Dir erstellen falls nicht vorhanden
mkdir -p "$GAME_DIR"

# Installer-Verzeichnis erkennen (dort wo install.sh liegt)
INSTALLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$INSTALLER_DIR/hybrid_orchestrator.py" ]; then
    if [ "$INSTALLER_DIR" != "$GAME_DIR" ]; then
        print_ok "Kopiere Dateien: $INSTALLER_DIR -> $GAME_DIR"
        rsync -a --exclude='cold_storage' --exclude='hot_storage' \
              --exclude='logs' --exclude='backups' \
              "$INSTALLER_DIR/" "$GAME_DIR/" 2>/dev/null \
            || {
                print_warn "rsync nicht verfuegbar, nutze cp..."
                cp -a "$INSTALLER_DIR/"* "$GAME_DIR/" 2>/dev/null
                # Versteckte Dateien separat
                cp -a "$INSTALLER_DIR/".* "$GAME_DIR/" 2>/dev/null || true
            }
        FILE_COUNT=$(find "$GAME_DIR" -type f | wc -l)
        print_ok "${FILE_COUNT} Dateien kopiert"
    else
        print_ok "Installer laeuft bereits im Game-Dir"
    fi
else
    print_err "hybrid_orchestrator.py nicht gefunden in $INSTALLER_DIR"
    print_err "Bitte install.sh aus dem Projektverzeichnis starten!"
    exit 1
fi

chown -R "${SERVICE_USER}:${ZTB_GROUP}" "$GAME_DIR" 2>/dev/null

# Home-Dir: 750 damit ztb-Gruppe (Default-User) lesen kann
chmod 750 "${SERVICE_HOME}" 2>/dev/null || true
print_ok "Dateien gehoeren jetzt ${SERVICE_USER}:${ZTB_GROUP}"
print_ok "Home-Dir ${SERVICE_HOME} = 750 (Gruppe ${ZTB_GROUP} darf lesen)"

# ============================================================================
# INSTALL SYSTEM PACKAGES
# ============================================================================

print_section "$MSG_SYS_PKG"

system_packages=(
    "python3"
    "python3-pip"
    "python3-dev"
    "python3-venv"
    "tmux"
    "git"
    "wget"
    "curl"
    "rsync"
    "bluetooth"
    "bluez"
    "libglib2.0-dev"
    "openssh-server"
    "libjpeg-dev"
    "zlib1g-dev"
    "libfreetype6-dev"
    "zram-tools"
    "sqlite3"
)

for pkg in "${system_packages[@]}"; do
    if dpkg -l 2>/dev/null | grep -q "^ii  $pkg"; then
        print_ok "$pkg"
    else
        print_ok "$pkg (installing...)"
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$pkg" > /dev/null 2>&1 || print_warn "Failed: $pkg"
    fi
done

# ============================================================================
# ZRAM KONFIGURATION (50% RAM als komprimierter Swap)
# ============================================================================

print_section "$MSG_ZRAM"

# zRAM Konfiguration: 50% des RAMs als komprimierter Swap-Block
ZRAM_CONFIG="/etc/default/zramswap"
ZRAM_PERCENTAGE=50

if dpkg -l 2>/dev/null | grep -q "^ii  zram-tools"; then
    # zram-tools Konfiguration schreiben
    cat > "$ZRAM_CONFIG" << ZRAMEOF
# Zero Tower Battle - zRAM Configuration
# Komprimierter RAM-Swap fuer Pi Zero 2 W (512MB RAM)
# 50% = ~256MB komprimierter Swap im RAM (effektiv ~500MB durch Kompression)
ALGO=lz4
PERCENT=${ZRAM_PERCENTAGE}
PRIORITY=100
ZRAMEOF

    # zRAM Service aktivieren und starten
    systemctl enable zramswap 2>/dev/null || true
    systemctl restart zramswap 2>/dev/null || true

    # Verifizieren
    ZRAM_SIZE=$(awk '/zram/ {sum += $3} END {printf "%d", sum/1024}' /proc/swaps 2>/dev/null)
    if [ -n "$ZRAM_SIZE" ] && [ "$ZRAM_SIZE" -gt 0 ]; then
        print_ok "zRAM aktiv: ${ZRAM_SIZE} MB (komprimiert, LZ4)"
    else
        print_ok "zRAM konfiguriert (wird nach Reboot aktiv)"
    fi
    print_ok "Algorithmus: LZ4, Groesse: ${ZRAM_PERCENTAGE}% RAM"
else
    print_warn "zram-tools nicht installierbar, versuche manuelles Setup..."

    # Fallback: manuelles zRAM Setup
    if [ -e /sys/block/zram0 ]; then
        print_ok "zRAM Device existiert bereits"
    else
        modprobe zram num_devices=1 2>/dev/null || print_warn "zram Kernel-Modul nicht verfuegbar"
    fi

    if [ -e /sys/block/zram0 ]; then
        # 50% RAM
        ZRAM_SIZE_BYTES=$(( RAM_TOTAL_MB * 1024 * 1024 * ZRAM_PERCENTAGE / 100 ))
        echo lz4 > /sys/block/zram0/comp_algorithm 2>/dev/null || true
        echo "$ZRAM_SIZE_BYTES" > /sys/block/zram0/disksize 2>/dev/null || true
        mkswap /dev/zram0 > /dev/null 2>&1 || true
        swapon -p 100 /dev/zram0 2>/dev/null || true
        print_ok "zRAM manuell aktiviert: $(( ZRAM_SIZE_BYTES / 1048576 )) MB"

        # Persistent machen via systemd service
        if ! systemctl is-enabled ztb-zram.service 2>/dev/null | grep -q "enabled"; then
            cat > /etc/systemd/system/ztb-zram.service << ZRAMSVCEOF
[Unit]
Description=ZTB zRAM Setup
After=local-fs.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'modprobe zram num_devices=1; echo lz4 > /sys/block/zram0/comp_algorithm; echo ${ZRAM_SIZE_BYTES} > /sys/block/zram0/disksize; mkswap /dev/zram0; swapon -p 100 /dev/zram0'
ExecStop=/bin/bash -c 'swapoff /dev/zram0 2>/dev/null; echo 1 > /sys/block/zram0/reset 2>/dev/null'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
ZRAMSVCEOF
            systemctl enable ztb-zram.service 2>/dev/null || true
            print_ok "zRAM Service erstellt (persistent)"
        fi
    else
        print_warn "zRAM nicht verfuegbar (kein Kernel-Support)"
    fi
fi

# ============================================================================
# SWAP KONFIGURATION (SD-basiert)
# ============================================================================

print_section "$MSG_SWAP"

if [ "$ADJUST_SWAP" = "1" ]; then
    SWAP_FILE="/var/swap"

    # DietPi nutzt /var/swap, Raspbian nutzt dphys-swapfile
    if [ "$IS_DIETPI" = "1" ]; then
        # DietPi Swap-Methode
        print_ok "DietPi Swap anpassen: ${RECOMMENDED_SWAP_MB} MB"

        # Alten Swap deaktivieren
        swapoff "$SWAP_FILE" 2>/dev/null || true

        # Neuen Swap erstellen
        dd if=/dev/zero of="$SWAP_FILE" bs=1M count="$RECOMMENDED_SWAP_MB" status=progress 2>&1 || {
            print_warn "dd failed, trying fallocate..."
            fallocate -l "${RECOMMENDED_SWAP_MB}M" "$SWAP_FILE" 2>/dev/null || {
                print_err "Swap-Datei konnte nicht erstellt werden"
                ADJUST_SWAP=0
            }
        }

        if [ "$ADJUST_SWAP" = "1" ]; then
            chmod 600 "$SWAP_FILE"
            mkswap "$SWAP_FILE" > /dev/null 2>&1
            swapon "$SWAP_FILE" 2>/dev/null || true

            # DietPi Swap-Size merken
            echo "$RECOMMENDED_SWAP_MB" > /etc/dietpi/.dietpi-swap_size 2>/dev/null || true

            NEW_SWAP_MB=$(awk '/SwapTotal/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null)
            print_ok "Swap aktiv: ${NEW_SWAP_MB} MB (Ziel: ${RECOMMENDED_SWAP_MB} MB)"
        fi
    else
        # Raspbian dphys-swapfile Methode
        if [ -f /etc/dphys-swapfile ]; then
            print_ok "dphys-swapfile anpassen: ${RECOMMENDED_SWAP_MB} MB"
            dphys-swapfile swapoff 2>/dev/null || true
            sed -i "s/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=${RECOMMENDED_SWAP_MB}/" /etc/dphys-swapfile
            dphys-swapfile setup 2>/dev/null || true
            dphys-swapfile swapon 2>/dev/null || true
            print_ok "Swap angepasst via dphys-swapfile"
        else
            # Generische Methode
            print_ok "Swap-Datei erstellen: ${RECOMMENDED_SWAP_MB} MB"
            swapoff "$SWAP_FILE" 2>/dev/null || true
            fallocate -l "${RECOMMENDED_SWAP_MB}M" "$SWAP_FILE" 2>/dev/null || \
                dd if=/dev/zero of="$SWAP_FILE" bs=1M count="$RECOMMENDED_SWAP_MB" status=progress 2>&1
            chmod 600 "$SWAP_FILE"
            mkswap "$SWAP_FILE" > /dev/null 2>&1
            swapon "$SWAP_FILE" 2>/dev/null || true

            # fstab Eintrag sicherstellen
            if ! grep -q "$SWAP_FILE" /etc/fstab 2>/dev/null; then
                echo "$SWAP_FILE none swap sw 0 0" >> /etc/fstab
            fi
            print_ok "Swap aktiv via $SWAP_FILE"
        fi
    fi
else
    print_ok "Swap unveraendert (${CURRENT_SWAP_MB} MB)"
fi

# Swappiness optimieren fuer Pi (weniger aggressiv swappen)
SWAPPINESS=60
echo "$SWAPPINESS" > /proc/sys/vm/swappiness 2>/dev/null || true
if ! grep -q "vm.swappiness" /etc/sysctl.conf 2>/dev/null; then
    echo "vm.swappiness=${SWAPPINESS}" >> /etc/sysctl.conf
else
    sed -i "s/^vm.swappiness=.*/vm.swappiness=${SWAPPINESS}/" /etc/sysctl.conf
fi
print_ok "vm.swappiness=${SWAPPINESS}"

# ============================================================================
# RAMDISK FUER HOT STORAGE (tmpfs)
# ============================================================================

print_section "$MSG_RAMDISK"

# tmpfs fuer Hot Storage: dynamisch wachsend, maximal HOT_STORAGE_MAX_MB
# tmpfs belegt nur so viel RAM wie tatsaechlich genutzt wird!
# Ein leeres tmpfs mit size=100m verbraucht 0 Bytes RAM.
# Daten gehen bei Reboot verloren -> wird vom Orchestrator aus Cold nachgeladen.

ZTB_UID=$(id -u ${SERVICE_USER} 2>/dev/null || echo 1001)
ZTB_GID=$(id -g ${SERVICE_USER} 2>/dev/null || echo 1001)

FSTAB_ENTRY="tmpfs ${HOT_STORAGE_RAMDISK} tmpfs nodev,nosuid,noexec,size=${HOT_STORAGE_MAX_MB}m,uid=${ZTB_UID},gid=${ZTB_GID},mode=0700 0 0"

# Verzeichnis erstellen
mkdir -p "$HOT_STORAGE_RAMDISK"

# fstab Eintrag pruefen/hinzufuegen
if grep -q "$HOT_STORAGE_RAMDISK" /etc/fstab 2>/dev/null; then
    # Existierenden Eintrag aktualisieren
    sed -i "\|${HOT_STORAGE_RAMDISK}|d" /etc/fstab
fi
echo "$FSTAB_ENTRY" >> /etc/fstab
print_ok "fstab: tmpfs max ${HOT_STORAGE_MAX_MB}MB -> ${HOT_STORAGE_RAMDISK}"
print_ok "tmpfs ist dynamisch: belegt nur so viel RAM wie genutzt"

# Sofort mounten
mount "$HOT_STORAGE_RAMDISK" 2>/dev/null || mount -a 2>/dev/null || true

# Verifizieren
if mountpoint -q "$HOT_STORAGE_RAMDISK" 2>/dev/null; then
    print_ok "RAMdisk gemountet: ${HOT_STORAGE_RAMDISK} (max ${HOT_STORAGE_MAX_MB} MB)"
else
    # Fallback: manuell mounten
    mount -t tmpfs -o "size=${HOT_STORAGE_MAX_MB}m,uid=${ZTB_UID},gid=${ZTB_GID},mode=0700" tmpfs "$HOT_STORAGE_RAMDISK" 2>/dev/null || {
        print_warn "RAMdisk konnte nicht gemountet werden (wird nach Reboot aktiv)"
    }
fi

# Ownership sicherstellen
chown "${SERVICE_USER}:${SERVICE_USER}" "$HOT_STORAGE_RAMDISK" 2>/dev/null || true
chmod 700 "$HOT_STORAGE_RAMDISK" 2>/dev/null || true

print_ok "Hot Storage RAMdisk bereit (dynamisch, max ${HOT_STORAGE_MAX_MB} MB)"

# ============================================================================
# INSTALL PYTHON PACKAGES
# ============================================================================

print_section "$MSG_PY_PKG"

# pip, wheel, setuptools sicherstellen und aktualisieren
print_ok "pip / wheel / setuptools..."
for build_pkg in pip wheel setuptools; do
    if python3 -c "import ${build_pkg}" 2>/dev/null; then
        print_ok "$build_pkg (vorhanden)"
    else
        print_ok "$build_pkg (installing...)"
        apt-get install -y -qq "python3-${build_pkg}" > /dev/null 2>&1 || true
    fi
done
# Upgrade versuchen (kann bei system-managed fehlschlagen — OK)
pip3 install --break-system-packages --upgrade pip wheel setuptools > /dev/null 2>&1 || print_warn "pip upgrade system-managed (OK)"

python_packages=(
    "bleak"
    "cryptography"
    "readchar"
    "rich"
    "pillow"
)

for pkg in "${python_packages[@]}"; do
    if python3 -c "import ${pkg}" 2>/dev/null; then
        print_ok "$pkg (already installed)"
    else
        print_ok "$pkg (installing...)"
        pip3 install --break-system-packages "$pkg" > /dev/null 2>&1 || print_warn "Failed: $pkg"
    fi
done

# Verify all critical imports
print_ok "Verifying Python imports..."
python3 -c "
missing = []
for mod in ['bleak', 'cryptography', 'readchar', 'rich', 'PIL']:
    try:
        __import__(mod)
    except ImportError:
        missing.append(mod)
if missing:
    print(f'  [!] Missing: {missing}')
else:
    print('  [OK] All Python packages verified')
" 2>&1

# ============================================================================
# BLUETOOTH CONFIGURATION
# ============================================================================

print_section "$MSG_BT"

systemctl enable bluetooth > /dev/null 2>&1 || print_warn "bluetooth enable failed"
systemctl start bluetooth > /dev/null 2>&1 || print_warn "bluetooth start failed"
hciconfig hci0 up 2>/dev/null || print_warn "hciconfig hci0 up failed"
print_ok "Bluetooth ready"

# ============================================================================
# GAME DIRECTORY SETUP (Storage + Permissions)
# ============================================================================

print_section "$MSG_GAMEDIR"

# Verzeichnis sollte bereits existieren
if [ ! -d "$GAME_DIR" ]; then
    print_warn "Game directory missing! Creating..."
    mkdir -p "$GAME_DIR"
fi

print_ok "$GAME_DIR exists"

# Storage directories (Cold auf SD, Hot = RAMdisk)
mkdir -p "$GAME_DIR/cold_storage"
mkdir -p "$GAME_DIR/logs"
mkdir -p "$GAME_DIR/backups/character"

# Symlink: hot_storage -> RAMdisk
if [ -L "$GAME_DIR/hot_storage" ]; then
    rm "$GAME_DIR/hot_storage"
elif [ -d "$GAME_DIR/hot_storage" ]; then
    # Existierendes Verzeichnis zu Symlink konvertieren
    rm -rf "$GAME_DIR/hot_storage"
fi
ln -sf "$HOT_STORAGE_RAMDISK" "$GAME_DIR/hot_storage"

print_ok "Cold Storage: $GAME_DIR/cold_storage (SD)"
print_ok "Hot Storage:  $HOT_STORAGE_RAMDISK (RAMdisk/tmpfs)"
print_ok "Backups:      $GAME_DIR/backups"
print_ok "Logs:         $GAME_DIR/logs"

# Python Bytecode Cache erstellen fuer schnelleren Start
find "$GAME_DIR" -name "*.py" -exec python3 -m py_compile {} \; 2>/dev/null || true
print_ok "Python bytecode pre-compiled"

# Permissions: Alles dem Service-User + ztb-Gruppe uebergeben
chown -R "${SERVICE_USER}:${ZTB_GROUP}" "$GAME_DIR" 2>/dev/null || print_warn "chown failed"

# Game-Dir: 750 (Owner rwx, Group rx, Others nichts)
# -> Default-User (in ztb-Gruppe) kann lesen/traversieren
# -> Andere User haben keinen Zugriff
chmod 750 "$GAME_DIR"

# Verzeichnisse: 750 (Gruppe darf lesen+traversieren)
find "$GAME_DIR" -type d -exec chmod 750 {} \; 2>/dev/null

# Dateien: 640 (Gruppe darf lesen)
find "$GAME_DIR" -type f -exec chmod 640 {} \; 2>/dev/null

# Shell-Scripts ausfuehrbar machen
find "$GAME_DIR" -name "*.sh" -exec chmod 750 {} \; 2>/dev/null

# Python-Dateien: Owner+Gruppe lesen, Orchestrator ausfuehrbar
chmod 750 "$GAME_DIR/hybrid_orchestrator.py" 2>/dev/null

# Cold Storage + Backups: NUR Service-User (kein Gruppen-Zugriff)
chmod 700 "$GAME_DIR/cold_storage"
chmod 700 "$GAME_DIR/backups"

# Home-Dir: 750 damit ztb-Gruppe traversieren kann
chmod 750 "${SERVICE_HOME}" 2>/dev/null || true

print_ok "Permissions set (${SERVICE_USER}:${ZTB_GROUP}, 750/640)"
print_ok "  Game-Dir: 750, Dateien: 640, Cold/Backups: 700 (privat)"
print_ok "  Default-User '${DEFAULT_USER}' hat Lese-/SCP-Zugriff"

# ============================================================================
# WRITE CONFIG (Language, Hostname, Paths, Storage — KEIN Charakter!)
# ============================================================================

print_section "config.json"

# Config mit allen Pfaden und Storage-Infos — character.name bleibt leer
# bis der Spieler sich beim ersten SSH-Login einen Charakter erstellt.
python3 -c "
import json, os
config_path = '${CONFIG_FILE}'
config = {}
if os.path.exists(config_path):
    with open(config_path, 'r') as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError:
            config = {}

config.setdefault('character', {})
config['character']['language'] = '${GAME_LANG}'
# Kein character.name hier — wird beim ersten SSH-Login via War Room erstellt

config.setdefault('device', {})
config['device']['name'] = '${DEVICE_NAME}'
config['device']['hostname'] = '${NEW_HOSTNAME}'
config['device']['sd_size_gb'] = ${SD_SIZE_GB}
config['device']['ram_mb'] = ${RAM_TOTAL_MB}

config.setdefault('service', {})
config['service']['user'] = '${SERVICE_USER}'
config['service']['home'] = '${SERVICE_HOME}'
config['service']['game_dir'] = '${GAME_DIR}'

config.setdefault('storage', {})
config['storage']['hot_storage'] = '${HOT_STORAGE_RAMDISK}'
config['storage']['hot_storage_size_mb'] = ${HOT_STORAGE_MAX_MB}
config['storage']['cold_storage'] = '${GAME_DIR}/cold_storage'
config['storage']['swap_mb'] = ${RECOMMENDED_SWAP_MB}
config['storage']['zram_percent'] = ${ZRAM_PERCENTAGE}

# Flag: Erststart noch nicht abgeschlossen (Charakter fehlt)
config.setdefault('state', {})
config['state']['first_start_pending'] = True

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
print('  [OK] config.json written')
" || print_warn "Could not write config.json"

chown "${SERVICE_USER}:${ZTB_GROUP}" "$CONFIG_FILE" 2>/dev/null
chmod 640 "$CONFIG_FILE" 2>/dev/null

# ============================================================================
# WIFI POWER MANAGEMENT
# ============================================================================

print_section "$MSG_WIFI"

iwconfig wlan0 power off 2>/dev/null || print_warn "WiFi power mgmt not available"
print_ok "WiFi power save disabled"

# Persistent via udev-Regel
UDEV_WIFI="/etc/udev/rules.d/99-ztb-wifi-powersave.rules"
echo 'ACTION=="add", SUBSYSTEM=="net", KERNEL=="wlan0", RUN+="/usr/sbin/iwconfig wlan0 power off"' > "$UDEV_WIFI" 2>/dev/null || true
print_ok "WiFi power save persistent (udev rule)"

# ============================================================================
# SYSTEMD SERVICE
# ============================================================================

print_section "$MSG_SERVICE"

cat > /etc/systemd/system/zero-tower-battle.service << SERVICEEOF
[Unit]
Description=Zero Tower Battle Game Service
After=network.target bluetooth.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${GAME_DIR}/hybrid_orchestrator.py
ExecStop=/bin/bash -c 'kill -SIGTERM \$MAINPID; sleep 5'
Restart=on-failure
RestartSec=15
User=${SERVICE_USER}
Group=${ZTB_GROUP}
WorkingDirectory=${GAME_DIR}
Environment="PYTHONUNBUFFERED=1"
Environment="PYTHONPATH=${GAME_DIR}"
Environment="ZTB_HOME=${GAME_DIR}"
MemoryMax=400M
CPUQuota=80%
StandardOutput=journal+console
StandardError=journal+console
LimitNOFILE=4096
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload > /dev/null 2>&1 || print_warn "systemd reload failed"
systemctl enable zero-tower-battle.service 2>/dev/null || print_warn "service enable failed"
print_ok "systemd service created + enabled (User: ${SERVICE_USER})"

# ============================================================================
# LOCALE CONFIGURATION
# ============================================================================

print_section "$MSG_LOCALE"

if command -v locale-gen &> /dev/null; then
    locale-gen en_US.UTF-8 2>/dev/null || true
fi
update-locale LANG=en_US.UTF-8 2>/dev/null || true
print_ok "Locale configured"

# ============================================================================
# HOSTNAME SETZEN (eindeutig pro Device)
# ============================================================================

print_section "Hostname"

OLD_HOSTNAME=$(hostname 2>/dev/null || echo "unknown")

if [ "$NEW_HOSTNAME" != "$OLD_HOSTNAME" ]; then
    # /etc/hostname
    echo "$NEW_HOSTNAME" > /etc/hostname

    # /etc/hosts aktualisieren
    if grep -q "$OLD_HOSTNAME" /etc/hosts 2>/dev/null; then
        sed -i "s/$OLD_HOSTNAME/$NEW_HOSTNAME/g" /etc/hosts
    else
        echo "127.0.1.1  $NEW_HOSTNAME" >> /etc/hosts
    fi

    # Sofort setzen (ohne Reboot)
    hostnamectl set-hostname "$NEW_HOSTNAME" 2>/dev/null || hostname "$NEW_HOSTNAME" 2>/dev/null || true

    print_ok "$MSG_HOSTNAME_SET: $OLD_HOSTNAME -> $NEW_HOSTNAME"
else
    print_ok "Hostname unchanged: $NEW_HOSTNAME"
fi

# ============================================================================
# SSH WRAPPER (War Room via SSH)
# ============================================================================

print_section "SSH War Room Setup"

# SSH-Service sicherstellen
systemctl enable ssh > /dev/null 2>&1 || true
systemctl start ssh > /dev/null 2>&1 || true
print_ok "SSH service enabled"

# .bashrc: War Room automatisch bei SSH Login starten
BASHRC_FILE="${SERVICE_HOME}/.bashrc"
if [ ! -f "$BASHRC_FILE" ]; then
    touch "$BASHRC_FILE"
    chown "${SERVICE_USER}:${ZTB_GROUP}" "$BASHRC_FILE"
fi

# Alte Eintraege entfernen falls vorhanden
sed -i '/# Zero Tower Battle/,/^fi$/d' "$BASHRC_FILE" 2>/dev/null
sed -i '/alias warroom/d' "$BASHRC_FILE" 2>/dev/null
sed -i '/# ===.*Zero Tower/,/^fi$/d' "$BASHRC_FILE" 2>/dev/null

cat >> "$BASHRC_FILE" << 'BASHEOF'

# =============================================
# Zero Tower Battle - Auto War Room on SSH Login
# =============================================
# Alias: 'warroom' startet den War Room manuell
alias warroom='cd ~/battle_game && python3 ~/battle_game/ui/options/war_room.py'

# PYTHONPATH fuer Python-Module setzen
export PYTHONPATH="${HOME}/battle_game:${PYTHONPATH}"

# Automatischer Start NUR bei interaktivem SSH-Login
# (nicht bei scp, rsync, cron, oder wenn schon im War Room)
if [ -n "$SSH_TTY" ] && [ -z "$ZTB_WARROOM_ACTIVE" ]; then
    GAME_DIR="${HOME}/battle_game"
    if [ -f "${GAME_DIR}/ui/options/war_room.py" ]; then
        echo ""
        echo "  ================================================"
        echo "  |       ZERO TOWER BATTLE - War Room           |"
        echo "  |  $(hostname) | $(date '+%H:%M %d.%m.%Y')              |"
        echo "  ================================================"
        echo ""
        echo "  Starte War Room... (Ctrl+C fuer Shell)"
        echo ""
        sleep 1
        export ZTB_WARROOM_ACTIVE=1
        cd "${GAME_DIR}" && python3 "${GAME_DIR}/ui/options/war_room.py"
        # Nach Beenden des War Room: Shell bleibt offen
        echo ""
        echo "  War Room beendet. Shell aktiv."
        echo "  'warroom' -> War Room erneut starten"
        echo "  'exit'    -> SSH beenden"
        echo ""
    fi
fi
BASHEOF

print_ok "Auto War Room on SSH login configured"
print_ok "Alias 'warroom' created"
print_ok "Ctrl+C during startup -> drops to shell"

chown "${SERVICE_USER}:${ZTB_GROUP}" "$BASHRC_FILE"

# ============================================================================
# KERNEL-PARAMETER OPTIMIERUNGEN (Pi Zero)
# ============================================================================

print_section "Kernel-Tuning"

# Dirty-Page Limits reduzieren (weniger RAM fuer Write-Cache)
SYSCTL_ZTB="/etc/sysctl.d/99-ztb.conf"
cat > "$SYSCTL_ZTB" << SYSCTLEOF
# Zero Tower Battle - Pi Zero 2 W Optimierungen
# Weniger RAM fuer Dirty-Page Cache (wichtig bei 512MB)
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5
# Swappiness (60 = balanced)
vm.swappiness = ${SWAPPINESS}
# OOM weniger aggressiv
vm.oom_kill_allocating_task = 1
# Netzwerk-Puffer fuer BLE/WiFi-Direct
net.core.rmem_max = 262144
net.core.wmem_max = 262144
SYSCTLEOF

sysctl -p "$SYSCTL_ZTB" > /dev/null 2>&1 || print_warn "sysctl apply failed"
print_ok "Kernel-Parameter optimiert (dirty_ratio, swappiness, OOM)"

# ============================================================================
# COMPLETION SUMMARY + SSH ONBOARDING
# ============================================================================

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  $MSG_DONE${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "  Hostname:         ${BOLD}${NEW_HOSTNAME}${NC}"
echo "  $MSG_DEVICE_NAME:  $DEVICE_NAME"
echo "  Language:         $GAME_LANG"
echo -e "  Service User:     ${BOLD}${SERVICE_USER}${NC}"
echo -e "  Default User:     ${BOLD}${DEFAULT_USER}${NC} (SCP/Lese-Zugriff via Gruppe '${ZTB_GROUP}')"
echo "  Game Directory:   $GAME_DIR"
echo ""
echo -e "  ${CYAN}--- Storage ---${NC}"
echo "  SD-Karte:         ${SD_SIZE_GB} GB"
echo "  Hot Storage:      ${HOT_STORAGE_RAMDISK} (dynamisch, max ${HOT_STORAGE_MAX_MB} MB)"
echo "  Cold Storage:     ${GAME_DIR}/cold_storage (SD)"
echo "  Swap:             ${SWAP_LABEL} (${RECOMMENDED_SWAP_MB} MB)"
echo "  zRAM:             ${ZRAM_PERCENTAGE}% RAM (~$(( RAM_TOTAL_MB * ZRAM_PERCENTAGE / 100 )) MB, LZ4)"
echo "  RAM:              ${RAM_TOTAL_MB} MB"
echo ""

print_section "$MSG_NEXT"
echo ""
echo "  1. $MSG_START_SVC"
echo "     sudo systemctl start zero-tower-battle"
echo ""
echo "  2. $MSG_CHECK_SVC"
echo "     sudo systemctl status zero-tower-battle"
echo ""
echo "  3. $MSG_VIEW_LOGS"
echo "     sudo journalctl -u zero-tower-battle -f"
echo ""

# ============================================================================
# SSH ONBOARDING — KILLER FEATURE fuer Handy-User
# ============================================================================

IP_ADDR=$(hostname -I 2>/dev/null | awk '{print $1}')
WIFI_SSID=$(iwgetid -r 2>/dev/null || echo "<dein-wlan>")

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  $MSG_ONBOARD_TITLE${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "  ${BOLD}$MSG_ONBOARD_STEP1${NC}"
echo "     https://f-droid.org/packages/com.termux/"
echo ""
echo -e "  ${BOLD}$MSG_ONBOARD_STEP2${NC}"
echo -e "     ${CYAN}${WIFI_SSID}${NC}"
echo ""
echo -e "  ${BOLD}$MSG_ONBOARD_TIP${NC}"
echo -e "     ${CYAN}${MSG_ONBOARD_TIP_CMD}${NC}"
echo ""
echo -e "  ${BOLD}$MSG_ONBOARD_STEP3${NC}"
echo ""
echo -e "     ${GREEN}${BOLD}ssh ${SERVICE_USER}@${IP_ADDR:-${NEW_HOSTNAME}.local}${NC}"
echo ""
echo -e "  ${BOLD}$MSG_ONBOARD_STEP4${NC}"
echo -e "     ${CYAN}${USER_PASSWORD}${NC}"
echo ""
echo -e "  ${BOLD}$MSG_ONBOARD_STEP5${NC}"
echo -e "  ${BOLD}$MSG_ONBOARD_STEP6${NC}"
echo ""
echo -e "  ${YELLOW}$MSG_PW_CHANGE${NC}"
echo ""
echo -e "  ${YELLOW}  HINWEIS: Ein Reboot wird empfohlen damit alle${NC}"
echo -e "  ${YELLOW}  Aenderungen (Kernel, zRAM, Hostname) aktiv werden.${NC}"
echo -e "  ${YELLOW}  -> sudo reboot${NC}"
echo ""
echo -e "${GREEN}  $MSG_FINISHED${NC}"
echo ""
