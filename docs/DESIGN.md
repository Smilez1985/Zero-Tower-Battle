# Zero Tower Battle — Designdokument

Stand: 2026-09-28 · Status: Pre-Alpha

Dieses Dokument haelt die tragenden Entscheidungen fest: was ZTB ist, warum
es so gebaut ist und welche Regeln nicht verhandelbar sind. Es ist die
Referenz fuer alle, die am Code arbeiten — Menschen wie Agenten.

**Blaupause des Projekts:** `docs/DESIGN.md` (was und warum) +
`docs/ROADMAP.md` (was noch fehlt) + `CHANGELOG.md` (was passiert ist).
Wer etwas aendert, das hier beschrieben ist, aendert zuerst dieses Dokument.

---

## 1. Was ZTB ist

Ein headless Auto-Battler-RPG fuer den Raspberry Pi Zero 2 W. Der Pi
steckt in der Tasche, klettert autonom einen endlosen Turm hoch und
kaempft serverlos gegen andere Pis, die ihm physisch begegnen. Verwaltet
wird er abends per SSH vom Handy.

**Das Motto:** Der Turm ist das Zuhause, die Strasse ist die Arena.

### 1.1 Was ZTB nicht ist

- **Kein Echtzeit-Spiel.** Es gibt nichts zu klicken, waehrend es laeuft.
- **Kein Online-Dienst.** Keine Cloud, kein Account, kein Server, der
  abgeschaltet werden kann.
- **Kein Free-to-Play-Modell.** Keine Werbung, keine Waehrung fuer echtes
  Geld, kein Fortschritt hinter einer Bezahlschranke.
- **Kein Grafikspiel.** Der Pi Zero 2 W hat keine brauchbare GPU. Alles
  laeuft im Terminal.

### 1.2 Die drei Saeulen

| Saeule | Beschreibung |
|--------|--------------|
| **PVE — der Turm** | Laeuft dauerhaft im Hintergrund. Alle 90 Sekunden ein Tick: eine Etage, Gold, Erschoepfung. |
| **PVP — die Begegnung** | BLE-Scan alle 30 Sekunden. Trifft der Pi einen anderen, laeuft binnen 2 Sekunden ein deterministischer Kampf. |
| **Raid — der Weltboss** | Ab 3 Geraeten in Funkreichweite. Alle 3 Tage, 2-Stunden-Fenster, gemeinsamer HP-Pool. |

---

## 2. Die tragenden Entscheidungen

### 2.1 Das 100-Punkte-Gesetz

Jeder Champion verteilt exakt 100 Punkte auf vier Attribute:

```
ATK + DEF + SPD + LUK = 100
```

Nicht verhandelbar. Es ist ein Nullsummenspiel — niemand kann stark sein,
ohne anderswo schwach zu werden. Pro Level-Up kommen 5 frei verteilbare
Bonuspunkte dazu.

| Klasse  | Typ    | Fokus       | ATK | DEF | SPD | LUK |
|---------|--------|-------------|-----|-----|-----|-----|
| Krieger | Stein  | Defensive   |  25 |  40 |  20 |  15 |
| Schurke | Schere | Tempo       |  25 |  15 |  40 |  20 |
| Magier  | Papier | Glaskanone  |  45 |  10 |  20 |  25 |
| *Jäger* | *Schere* | *Allrounder* | *25* | *25* | *25* | *25* |

*Der Jäger ist geplant, aber noch nicht implementiert (ROADMAP 1.4).*

Grenzen: min. 1, max. 50 pro Attribut, max. 50 Bonuspunkte pro Attribut.

### 2.2 Determinismus ist das Fundament

Ohne zentralen Server gibt es keine Schiedsinstanz. Deshalb gilt:

> **Gleicher Seed + gleiche Eingaben = gleiches Ergebnis. Auf jedem Geraet.**

Daraus folgen drei harte Regeln:

1. **Integer-only in der Kampfberechnung.** Float-Rundung ist
   plattformabhaengig. Jede Formel rechnet in Prozent oder Promille.
2. **Der Seed haengt an beiden Teilnehmern**, nicht an einem. Er wird aus
   sortierten Werten gebildet, damit die Reihenfolge egal ist.
3. **Die Rollenvergabe ist symmetrisch.** Wer Spieler A ist, entscheidet
   ein sortierbares Merkmal (IP-Suffix bzw. Name) — niemals "wer gerade
   rechnet".

> Regel 3 wurde bis September 2026 verletzt: `battle_server.py` machte
> immer das lokale Profil zu Spieler A. Beide Geraete kamen dadurch zu
> verschiedenen Ergebnissen. Abgesichert durch
> `tests/test_p2p_consistency.py`.

### 2.3 Eine Schadensformel, zwei Engines

`engine/battle_engine.py` (PVE) und `deterministic_battle.py` (PVP/Raid)
**muessen identisch rechnen**:

```
1. Raw     = ATK x (100 + (Level-1) x 5) // 100
2. DefPct  = DEF x 100 // (DEF + 50)            # asymptotisch, nie 100 %
3. Schaden = max(3, Raw x (100 - DefPct) // 100)
4. Varianz = 90-110 %
5. Typ     = x1.25 (Vorteil) / x0.8 (Nachteil)
6. Krit    = LUK x 5 / 1000 Chance -> x2
```

**Warum `DEF / (DEF + K)` und nicht Subtraktion:** Subtraktive Ruestung ist
zu Beginn uebermaechtig und spaeter wertlos. Die asymptotische Kurve hat
abnehmenden Grenzertrag (DEF 20 = 28 %, DEF 40 = 44 %, DEF 80 = 61 %) und
erreicht nie 100 %. Standard in League of Legends, Dota 2, Diablo.

**SPD gewaehrt eine Chance auf einen Extra-Angriff**
(`min(45 %, SPD-Differenz x 1,5 %)`). Ohne das bestimmt SPD nur die
Zugreihenfolge und ist praktisch wertlos.

Abgesichert durch `tests/test_battle_parity.py`. Details und Messreihen in
`docs/BALANCING.md`.

### 2.4 Schere-Stein-Papier als Klassenachse

Stein schlaegt Schere, Schere schlaegt Papier, Papier schlaegt Stein.
Vorteil x1.25, Nachteil x0.8. Der Faktor ist bewusst klein: Er soll einen
Ausgang kippen koennen, aber keine Stat-Entscheidung ersetzen.

### 2.5 Hardware-Realismus

Der Pi Zero 2 W hat 512 MB RAM, 1 GHz Quad-Core und **einen** Funkchip fuer
BLE und WiFi. Das praegt die gesamte Architektur:

| Grenze | Antwort im Design |
|--------|-------------------|
| 512 MB RAM | Single-Process, kein Multi-Threading. Ziel: unter 50 MB. |
| SD-Karten-Verschleiss | SQLite auf `tmpfs`-RAM-Disk, Sync auf SD alle 5 Min. |
| Schwache CPU | Durchgehend `async/await`, bewusste `sleep`-Pausen. |
| Keine GPU | Headless. `rich` rendert nur bei Aenderung. |
| Ein Funkchip | Time-Slicing zwischen BLE-Scan und WiFi-Direct. |

**Konsequenz:** Ein 5-Sekunden-BLE-Scan darf den Turm-Tick nicht
blockieren. Alles, was blockiert, ist ein Bug.

### 2.6 Split-Tunneling: SSH darf nie einfrieren

```
wlan0  192.168.4.1     Access Point, SSH-Management (versteckte SSID)
tun0   10.42.0.x/24    virtuelles Interface, ausschliesslich P2P
```

Beide Interfaces sind per `iptables` getrennt (`FORWARD = DROP`). Man kann
live zusehen, wie der Pi im Hintergrund kaempft, ohne dass die Session
stockt.

**IP-Kollisionen** werden praeventiv geloest: Das vierte Oktett der
virtuellen IP reist im BLE-Beacon mit. Scannen zwei Pis identische
Suffixe, wuerfelt der mit der hoeheren MAC neu und aktualisiert seinen
Beacon — noch vor dem WiFi-Direct-Handshake.

### 2.7 Zero-Touch

Kein manueller Handshake, keine Bestaetigung, kein Pairing-Dialog. Der
gesamte Weg — BLE-Scan, Handshake, tun0, Kampf, Log — laeuft ohne
Zutun. Jede Interaktion zur Laufzeit zerstoert die Idee des autonomen
Begleiters.

Das ist ein Anspruch mit Preis: Sicherheit muss ohne Nutzerinteraktion
funktionieren (siehe Abschnitt 4).

---

## 3. Spielmechaniken

### 3.1 Progression

| Ereignis | EXP |
|----------|-----|
| Sieg | 100 |
| Niederlage | 30 |

Auch Niederlagen zahlen — ein Kampf soll sich immer lohnen. Level-Up alle
500 EXP, dazu 5 Bonuspunkte.

### 3.2 Erschoepfung und Psyche

Der Champion ist kein Werkzeug, sondern eine Figur mit Zustand.

- +2 % Erschoepfung pro Turm-Kampf
- ab ~80 %: PVP-Ablehnung, -20 % ATK
- bei 100 %: Der Champion verweigert den Kampf und schlaeft

Unterhalb von 20 % HP koennen **Trauma-Ereignisse** auftreten, abhaengig
von der Etage (Klaustrophobie, Waffenangst, Dungeon-Angst, Hoehenangst).

**Zweck:** Anti-Grind ohne kuenstliche Energieleiste. 24/7-Farming
funktioniert nicht, aber niemand wird zum Spielen gezwungen.

### 3.3 PVP-Cooldown

Derselbe Gegner (per MAC) kann nur alle **30 Minuten** bekaempft werden.
Ohne diese Sperre erzeugen zwei Pis, die acht Stunden im selben Buero
stehen, tausende Logs und leere Akkus.

### 3.4 Der Shiny-Effekt

Jeder Turm-Gegner hat eine Chance von **1:8192**, ein Shiny zu sein —
zehnfaches Gold, garantierter epischer Loot.

Der Clou liegt in der Asynchronitaet: Man erfaehrt es erst abends beim
SSH-Login. Entweder der seltene Fang — oder die Meldung
*"⚠️ DU HAST EIN SHINY VERPASST!"*.

### 3.5 Weltboss-Raid

Ab drei Geraeten in Funkreichweite, alle 3 Tage in einem 2-Stunden-Fenster.
Der Boss hat so viele HP, dass ein einzelner Pi ihn nicht schaffen kann.
Jeder Teilnehmer steuert DPS nach seinen Stats bei; Belohnung sind
Diamanten und Raid-Marken fuer kosmetische Upgrades.

### 3.6 Zwei gueltige Spielweisen

Beide Wege sind vollwertig und nutzen dieselbe Datenbank:

- **Der Turmsteiger:** nie PVP, klettert bis Etage 50.000, sammelt Runen.
- **Der Strassenkaempfer:** bleibt auf Etage 1, kaempft nur in der U-Bahn.

Keiner erzwingt den anderen. Wer beides macht, ist effizienter — aber nicht
ueberlegen.

---

## 4. Sicherheitskonzept

### 4.1 Bedrohungsmodell

ZTB laeuft im oeffentlichen Raum und nimmt unaufgefordert Verbindungen von
fremden Geraeten an. Angenommen wird:

- Der Funkverkehr ist mitlesbar (BLE-Beacons sind Broadcasts).
- Der Gegner kann luegen (manipulierte Profile, gefaelschte Ergebnisse).
- Der Gegner kann angreifen (Payload Injection ueber Port 5005).

### 4.2 Ghost Mode — was er leistet und was nicht

`ignore_broadcast_ssid=1` verbirgt den Access Point vor gewoehnlichen
Scannern. **Das ist Unauffaelligkeit, keine Sicherheit.** Wer gezielt
sucht, findet den Pi.

Der BLE-Beacon selbst ist unverschluesselt — 31 Bytes lassen keinen
Spielraum. Geraetepraesenz und MAC sind damit oeffentlich lesbar. Das ist
eine bewusste Abwaegung zugunsten der Latenz (ROADMAP 4.1).

### 4.3 ECC statt Klartext-PSK

Ein frueher Entwurf sah vor, den WPA2-PSK im offenen Beacon zu
uebertragen. Die eigene Analyse verwarf das als *"kritisches
Sicherheitsrisiko — ein trivialer Smartphone-Sniffer reicht"*.

Stattdessen: **Curve25519** fuer den Schluesselaustausch, **Ed25519** fuer
Signaturen. Der Sitzungsschluessel entsteht per ECDH aus dem Handshake, der
PSK reist nie im Klartext.

Regel: **Kryptografie niemals selbst implementieren.** Nur etablierte
Bibliotheken (`cryptography`, libsodium).

### 4.4 Input-Validierung — offener Kernpunkt

Port 5005 nimmt JSON-Profile entgegen und reicht sie **ohne Schema-Pruefung**
an die Engine weiter. Die Planungsanalyse benennt das Risiko klar:

> *"Ein manipuliertes JSON-Objekt […] reicht aus, um eine Root-Shell auf
> dem System zu erzwingen."*

Erforderlich: strikte Schema-Validierung (Pydantic) vor jeder Verarbeitung,
Laengenbegrenzung, Typpruefung, Plausibilitaetscheck der Stats
(Summe = 100 + 5 x (Level-1)). **Bis dahin duerfen keine fremden Geraete
ausserhalb einer kontrollierten Umgebung angenommen werden.**
Siehe ROADMAP 4.4.

### 4.5 Ergebnis-Integritaet — offener Kernpunkt

Die Engine ist deterministisch, aber nichts hindert ein manipuliertes
Geraet daran, ein beliebiges Ergebnis zu behaupten. Geplant: Beide Seiten
signieren einen Hash ueber `(seed, rounds, winner, log)` mit Ed25519.
Abweichung = Kampf verworfen. Siehe ROADMAP 4.2 und 5.5.

### 4.6 Netzwerk-Isolation

`iptables FORWARD = DROP` zwischen `wlan0` und `tun0`. Ein kompromittierter
P2P-Kanal erreicht die SSH-Session nicht. SSH akzeptiert keine
Passwort-Authentifizierung; der Installer legt einen dedizierten
Dienstbenutzer an.

---

## 5. Architekturregeln

Diese Regeln existieren, weil ihre Verletzung dieses Projekt bereits
Monate gekostet hat.

### Regel 1 — Keine Logik zweimal implementieren

Schadensformel, Seed-Erzeugung und Rollenvergabe waren jeweils an zwei
Stellen unterschiedlich umgesetzt. Alle drei Divergenzen blieben lange
unbemerkt, weil kein Test sie verglich.

**Wer eine Formel aendert, aendert sie an genau einer Stelle** — oder
schreibt einen Test, der beide Stellen gegeneinander prueft.

### Regel 2 — Tests rufen echte Methoden auf

Ein Test, der eine Formel nachrechnet statt sie aufzurufen, prueft nichts.
Der erste Entwurf von `test_battle_parity.py` bestand die Gegenprobe mit
der fehlerhaften Formel — genau der Fehler, der den Bug ermoeglicht hatte.

**Jeder Regressionstest braucht eine Gegenprobe:** Alten Zustand
wiederherstellen, pruefen ob der Test rot wird.

### Regel 3 — Keine Secrets im Repository

SSIDs, Passphrasen, Tokens, Geraete- und Benutzernamen, lokale Pfade und
private Adressen gehoeren nie in versionierte Dateien. Konfiguration liegt
als `*.example`-Vorlage mit Platzhaltern vor; die echten Werte erzeugt der
Installer.

### Regel 4 — Nichts blockiert die Hauptschleife

Jeder Netzwerk- oder Dateizugriff ist `async`. Externe Kommandos laufen
ueber `_safe_run()`, das fehlende Binaries abfaengt statt den Prozess zu
beenden.

### Regel 5 — Der Pi ist die Zielplattform, nicht der Entwicklungsrechner

Was auf einem Desktop laeuft, muss nicht auf 512 MB laufen. Speicher- und
CPU-Annahmen gelten fuer den Pi Zero 2 W.

---

## 6. Verzeichnisstruktur

```
engine/           Kampf-Engine (PVE), Stat-Berechnung, Rewards
deterministic_battle.py   PVP- und Raid-Engine, Seed-Erzeugung
controllers/      Netzwerk: AP, tun0, Battle-Server/-Client
game/             BLE-Beacon, Hot/Cold Storage, Save-System
models/           Datenmodelle: Champion, Inventar, Gegner, Season
services/         Shop, Schmiede, Level-Up
ui/               SSH-Dashboard (rich), Menues, War Room
game_balance/     Encounter-Tuning, dynamische Schwierigkeit
i18n/             Uebersetzungen (DE/EN)
tests/            pytest-Suite
docs/             DESIGN.md, ROADMAP.md, BALANCING.md, Nutzerhandbuecher
```

---

## 7. Namensgebung

Das Projekt hiess urspruenglich *Tower of Shadows*. Der Name wurde wegen
Markenrechtsbedenken verworfen. **Gueltig ist ausschliesslich
"Zero Tower Battle" (ZTB).** Jede Fundstelle des alten Namens ist ein Bug.
