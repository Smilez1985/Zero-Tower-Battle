# Zero-Tower-Battle
Zero Tower Battle ist ein mobiler, headless P2P-Auto-Battler für den Raspberry Pi Zero 2 W. Als autonomer "Pocket-Server" grindet er in der Tasche einen endlosen PVE-Turm. Trifft er auf andere Pis, führt er serverlose PVP-Kämpfe über BLE und WiFi-Direct aus. Verwaltet wird das RPG rein über ein SSH-Terminal.

**⚔️ ZERO TOWER BATTLE**
*Autonomer P2P-Underground-Battler für den Raspberry Pi Zero 2 W* (ein perfektes "Set it and forget it"-Projekt...)

***"Dein Pi langweilt sich in der Schublade. Schenk ihm eine Bestimmung. Lass ihn für dich kämpfen."***

Zero Tower Battle ist kein gewöhnliches Spiel. Es ist ein dezentrales, autonomes Ökosystem für Technik-Enthusiasten und Urban-Hacker. Während du deinen Alltag bestreitest, jagt dein Pi in deiner Tasche nach anderen Warriors. Keine Cloud, kein Internet, kein Tracking – nur pure Mathematik und dezentrale Kommunikation im „Ghost Mode“.

**📡 Die Architektur (Warum Techies es lieben)**

Dieses Projekt wurde aus der Notwendigkeit geboren, die Grenzen des Single-Radio-Chips am Pi Zero 2 W zu sprengen.

- **Ghost Mode & Stealth:** Der Management-Access-Point (für dein Handy) läuft mit versteckter SSID. Discovery findet ausschließlich via BLE-Beacons (0xFEAA) statt.
- **Split-Tunneling Excellence:** SSH-Management via wlan0 (z.B. 192.168.4.1) bleibt stabil, während P2P-Kämpfe über ein isoliertes virtuelles tun0-Interface abgewickelt werden.
- **Deterministische Engine:** Kämpfe basieren auf dem 100-Punkte-Gesetz ($\text{ATK} + \text{DEF} + \text{SPD} + \text{LUK} = 100$). Das Ergebnis ist mathematisch fixiert, sobald der Handshake steht.

**🛠️ Installation (DietPi Quickstart)**

Dieses Projekt ist für DietPi (x64) optimiert, um den RAM-Footprint minimal zu halten (~50MB inklusive RAM-Disk).

**1. Vorbereitung**
Flashe ein frisches DietPi auf deine SD-Karte. Nutze dietpi-software, um Python 3 und Git zu installieren.

**2. Der One-Line-Installer**
Logge dich per SSH ein und starte die Transformation:

```bash```
```
curl -sSL https://github.com/Smilez1985/Zero-Tower-Battle/raw/main/install_battle_os.sh | bash
```

**3. Was das Skript macht:**
- Konfiguriert den Access Point (Hostname & IP nach deiner Wahl).
- Installiert die Battle-Services (Scanner & Server).
- Generiert deinen persönlichen Konnektivitäts-QR-Code direkt im Terminal.
  
**🎮 Gameplay & Stats**

Dein Warrior wird über das TUI (Text User Interface) verwaltet. Verbinde dich einfach mit deinem Handy via SSH:

- **Krieger:** Fokus auf DEF & HP.
- **Schurke:** Fokus auf SPD & LUK (Crits!).
- **Magier:** Fokus auf ATK & Spezialeffekte

**📍 Die Jagd in der Realität**

Dank der Sticker-Kampagne wächst das Netzwerk organisch. Halte in der City (besonders in Saarbrücken!) Ausschau nach dem Zero-Tower-Logo. Wenn dein Pi abends im Log einen erfolgreichen Kampf anzeigt, weißt du: Irgendwo da draußen ist ein Gleichgesinnter.

**🎨 Über das Design**

Das visuelle Konzept (Logo, Sticker und Hardware-Ästhetik) wurde entwickelt, um die rohe Kraft des Pi Zero 2 W zu zelebrieren.


