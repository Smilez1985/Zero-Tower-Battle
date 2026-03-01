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

**🛡️ FAQ für Skeptics & Tech-Admins**

Wenn man von „serverlosem P2P-Warfare“ hört, gehen bei erfahrenen SysAdmins die Alarmglocken an. Hier sind die Antworten auf die brennendsten Fragen:

**1. „Versteckte SSID? Ist das nicht nur Security by Obscurity?“**

- Antwort: Absolut. Aber im Ghost Mode geht es nicht um kryptographische Unbesiegbarkeit, sondern um digitale Unauffälligkeit im öffentlichen Raum.
- Durch ignore_broadcast_ssid=1 taucht dein Pi in 99 % aller Smartphone-Scanner in der Bahn gar nicht erst auf.
- Der eigentliche Handshake für den Kampf erfolgt über einen temporären ECC-basierten PSK, der nur via BLE-Beacon geflüstert wird.

**2. „Zerstört der ständige Scan meinen Akku?“**

- Nein. Wir nutzen ein hocheffizientes Duty-Cycle-Verfahren.
- Der Pi scannt nur alle 30 Sekunden für exakt 5 Sekunden die Umgebung.
- In der restlichen Zeit sendet er nur passiv seinen Beacon, was die CPU-Last des Pi Zero 2 W bei unter 2 % hält und die Powerbank schont.

**3. „Müllt mir das P2P-Interface nicht die SSH-Verbindung zu?“**

- Hier kommt die Split-Tunneling-Architektur ins Spiel.
- Dein Management-Interface (wlan0) und das Kampf-Interface (tun0) sind logisch voneinander getrennt.
- Selbst wenn ein Kampf gerade 100 % der P2P-Bandbreite beansprucht, bleibt dein Terminal am Handy flüssig, da es auf einer priorisierten statischen Route liegt.

**4. „Wie fair ist das Kampfsystem wirklich?“**

- Das gesamte Balancing basiert auf einem 100-Punkte-Gesetz.

- Es ist ein Nullsummenspiel: $$ATK + DEF + SPD + LUK = 100$$

- Kein Spieler kann „overpowered“ sein, ohne massive Schwächen in anderen Bereichen in Kauf zu nehmen. Ein Sieg hängt von der Spezialisierung deiner Ausrüstung und dem Glück beim Würfeln (LUK) ab.




