#!/bin/bash
# Zero Tower Battle - Deploy Script for Raspberry Pi Zero 2W

echo "🚀 Deploying Zero Tower Battle..."
echo "Testing on Pi Zero 2W via SSH..."

# Backup + Sync Files
cp -r /home/ZTB_Service/battle_game/* /home/ZTB_Service/Battle-Pi/
# Start Game
ssh pi@pi2.example.com "cd /home/ZTB_Service/Battle-Pi && python3 initialisierung.py"

echo "✅ Deployment Complete!"
echo "✅ Tests Started!"
