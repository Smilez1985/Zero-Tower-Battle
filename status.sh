#!/bin/bash
# Battle-Pi Headless Status
# Pi Zero 2W

echo ""
echo "📊 BATTLE-PI STATUS (Headless)"
echo "==" * 25
echo ""

# 1. CPU
echo "📊 CPU:"
cat /proc/cpuinfo | grep "model name" | head -n 1
uptime

# 2. RAM
echo ""
echo "📊 RAM:"
free -m | grep "^Mem:"

# 3. WiFi
echo ""
echo "📊 WiFi:"
nmcli device status

# 4. Disk
echo ""
echo "📊 Disk:"
df -h | grep -v "tmpfs" | grep -v "^Filesystem"

# 5. Processes
echo ""
echo "📊 Running Processes:"
ps aux | grep -E "python|game|daemon" | grep -v grep | head -n 5

# 6. SSH Status
echo ""
echo "🔑 SSH:"
systemctl status sshd | grep "Active:" | awk '{print $2}'

# 7. Game Status
echo ""
echo "🎮 Game Status:"
if [ -f /usr/bin/battle_main.py ]; then
    echo "    ✅ battle_main.py installed"
else
    echo "    ⚠️  battle_main.py not found"
fi

echo ""
echo "✅ Status Complete!"
