#!/bin/bash
# ZERO Tower Battle (ZTB) - Secure Split-Tunneling Script
# ===================================================================
# iptables Regeln:
# ├─ wlan0: SSH Access (Management)
# └─ tun0: P2P Tunnel (Kampf-Daten)
#
# Security:
# ├─ FORWARD=DROP: trenne wlan0 vom Internet
# ├─ wlan0 INPUT DROP: blockiere externe Eingaben
# └─ AUTO-RELOAD: bei System-Neustart

set -euo pipefail

CONFIG_DIR="${HOME:-/home/ZTB_Service}/battle_game"
RULES_FILE="${CONFIG_DIR}/iptables_rules"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $*"
}

cleanup() {
  log "Cleanup: Removing firewall rules for debugging"
  iptables -F
  iptables -X
  iptables -t nat -F
  iptables -t mangle -F
}

apply_rules() {
  log "Applying firewall rules..."
  
  # Basic setup
  iptables -P FORWARD DROP
  iptables -P INPUT DROP
  iptables -P OUTPUT ACCEPT
  
  # Allow loopback
  iptables -A INPUT -i lo -j ACCEPT
  iptables -A OUTPUT -o lo -j ACCEPT
  
  # Allow established connections
  iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
  
  # SSH Access (Management)
  iptables -A INPUT -p tcp --dport 2222 -j ACCEPT
  
  # WiFi Direct (wlan0 für P2P)
  iptables -A INPUT -i wlan0 -j ACCEPT
  
  # tun0: Nur P2P-Kommunikation erlauben
  iptables -A INPUT -i tun0 -j ACCEPT
  
  # Block alles andere
  log "Firewall rules applied"
}

save_rules() {
  log "Saving rules to ${RULES_FILE}"
  iptables-save > "${RULES_FILE}"
  
  # Backup old rules
  if [ -f "${RULES_FILE}.backup" ]; then
    mv "${RULES_FILE}.backup" "${RULES_FILE}.old"
  fi
}

restore_rules() {
  log "Restoring from ${RULES_FILE}"
  if [ -f "${RULES_FILE}" ]; then
    iptables-restore < "${RULES_FILE}"
  fi
  
  # Auto-save
  save_rules
}

auto_reload() {
  log "Auto-reloading iptables rules"
  restore_rules
}

main() {
  case "${1:-load}" in
    load)
      apply_rules
      save_rules
      ;;
    
    clean)
      cleanup
      ;;
    
    reload)
      auto_reload
      ;;
    
    *)
      echo "Usage: $0 {load|clean|reload}"
      exit 1
      ;;
  esac
}

main "$@"

# Auto-save bei Änderung des Regelwerks
trap 'save_rules' EXIT SIGINT SIGTERM
