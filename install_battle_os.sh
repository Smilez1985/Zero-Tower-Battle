#!/bin/bash
# Zero Tower Battle - One-Line-Installer (Weiterleitung)
# =====================================================
# Diese Datei existiert nur, weil sie im README als curl|bash-Ziel steht.
# Der eigentliche Installer ist install.sh im Repo-Root.
set -euo pipefail

cat <<'BANNER'
  ______ _______ ____
 |___  /|__   __|  _ \
    / /    | |  | |_) |   ZERO TOWER BATTLE
   / /     | |  |  _ <    Pre-Alpha
  / /__    | |  | |_) |
 /_____|   |_|  |____/

BANNER

echo "Dieses Projekt ist im Pre-Alpha-Stadium."
echo "Es laeuft, ist aber weder stabil noch fuer den Produktivbetrieb gedacht."
echo
echo "Installation:"
echo
echo "  git clone https://github.com/Smilez1985/Zero-Tower-Battle.git"
echo "  cd Zero-Tower-Battle"
echo "  sudo ./install.sh"
echo
echo "Voraussetzungen: DietPi (ARM/aarch64), Python 3.8+, Raspberry Pi Zero 2 W."
echo "Konfiguration: *.example-Dateien kopieren und Platzhalter ersetzen"
echo "               (hostapd.conf.example, dnsmasq.conf.example, config.example.json)."
echo
echo "Ein blindes 'curl | bash' wird hier bewusst nicht unterstuetzt."
exit 1
