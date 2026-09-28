#!/bin/bash
# ZERO Tower Battle (ZTB) - Hunt Mode Startup Script
# ===================================================================
# Automatischer Start von:
# ├─ BLE Discovery
# ├─ WiFi Direct
# ├─ net_manager.py
# └─ hybrid_orchestrator.py

set -euo pipefail

CONFIG_DIR="${HOME:-/home/ZTB_Service}/battle_game"
LOG="${CONFIG_DIR}/logs/hunt.log"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $*" | tee -a "$LOG"
}

ensure_directory() {
  mkdir -p "${CONFIG_DIR}/logs"
}

start_wifi_ble() {
  log "Starting WiFi Direct & BLE Discovery..."
  
  # wpa_cli P2P
  wpa_cli -i wlan0 P2P_LISTENER_START
  
  # BLE Discovery
  btmgmt discover || true
  
  log "✅ WiFi Direct & BLE Discovery enabled"
}

start_networks() {
  log "Starting network interfaces..."
  
  # Split-Tunneling Setup
  iptables -P FORWARD DROP
  iptables -P INPUT DROP
  iptables -P OUTPUT ACCEPT
  
  # Allow loopback
  iptables -A INPUT -i lo -j ACCEPT
  iptables -A OUTPUT -o lo -j ACCEPT
  
  # tun0: P2P-Kommunikation
  iptables -A INPUT -i tun0 -j ACCEPT
  iptables -A OUTPUT -o tun0 -j ACCEPT
  
  # WiFi Direct (SSH Management)
  iptables -A INPUT -i wlan0 -j ACCEPT
  
  # Start tun0
  ip addr add 10.42.0.1/24 dev tun0
  ip link set tun0 up
  
  log "✅ Split-Tunneling Network Setup complete"
}

start_daemons() {
  log "Starting P2P daemons..."
  
  # net_manager.py
  python3 "${CONFIG_DIR}/net_manager.py" &
  local PID_NET=$!
  echo $PID_NET > "${CONFIG_DIR}/pid/network.pid"
  
  # inventory.py
  python3 "${CONFIG_DIR}/service/inventory.py" &
  local PID_INV=$!
  echo $PID_INV > "${CONFIG_DIR}/pid/inventory.pid"
  
  # shop.py
  python3 "${CONFIG_DIR}/service/shop.py" &
  local PID_SHOP=$!
  echo $PID_SHOP > "${CONFIG_DIR}/pid/shop.pid"
  
  log "✅ Daemons started"
  log "Network: PID $PID_NET"
  log "Inventory: PID $PID_INV"
  log "Shop: PID $PID_SHOP"
  
  return 0
}

main() {
  ensure_directory
  log "Hunt Mode started at $(date)"
  
  start_wifi_ble
  start_networks
  start_daemons
  
  log "✅ Hunt Mode initialized successfully"
  
  # Keep script running
  while true; do
    sleep 60
  done
}

main "$@"
