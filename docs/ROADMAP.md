# Roadmap — offene Punkte

Stand: 2026-09-28

Diese Datei sammelt alles, was beim Code-Review und Balancing-Durchlauf
aufgefallen ist, aber bewusst **nicht** sofort behoben wurde — weil es eine
Design-Entscheidung braucht, Hardware voraussetzt oder ueber eine reine
Fehlerkorrektur hinausgeht.

**Blaupause des Projekts:** `docs/DESIGN.md` (Entscheidungen und Regeln) +
`docs/ROADMAP.md` (diese Datei) + `CHANGELOG.md` (Historie).
Was bereits erledigt ist, steht im Changelog; Messreihen zum Balancing in
`docs/BALANCING.md`.

---

## 0. Geplant, aber nie implementiert

Diese Punkte stehen in den Planungsdokumenten und fehlen im Code. Sie sind
keine neuen Ideen, sondern verlorenes Wissen auf dem Weg von der Planung zur
Umsetzung.

### 0.1 Die vierte Klasse: Jäger
**Prioritaet: mittel**

Geplant war ein Allrounder mit gleichmaessiger Verteilung:

| Klasse | Typ | Fokus | ATK | DEF | SPD | LUK |
|--------|-----|-------|-----|-----|-----|-----|
| Jäger | Schere | Allrounder | 25 | 25 | 25 | 25 |

Bemerkenswert: In der Balancing-Simulation war genau diese gleichmaessige
Verteilung die stabilste. Der Jäger waere damit die verlaesslichste Klasse —
unauffaellig, aber nie chancenlos.

Betroffen: `data/classes.json`, `forge.py`, `engine/battle_engine.py`
(CLASS_STATS), Uebersetzungen.

### 0.2 Klassen-Skills
**Prioritaet: mittel**

Jede Klasse sollte eine Spezialfaehigkeit haben:

| Klasse | Skill | Effekt |
|--------|-------|--------|
| Magier | Manabrand | Verbraucht Punkte des Gegners |
| Krieger | Schildstoss | Betaeubt (SPD sinkt kurzzeitig) |
| Schurke | Meucheln | Garantierter Krit, wenn SPD > Gegner-SPD |
| Jäger | Praezisionsschuss | Ignoriert 20 % der Ruestung |

Der Praezisionsschuss ist mehr als Geschmack: Ruestungsdurchschlag ist das
Standardgegenmittel gegen Ruestungssaettigung und wuerde Punkt 1.1
entschaerfen. Das Design hatte die Antwort auf das Balancing-Problem
bereits — der Code kennt sie nicht.

### 0.3 Patzer (Fumble)
**Prioritaet: niedrig**

Geplant war LUK als beidseitiger Hebel: erhoeht die Krit-Chance **und**
senkt das Risiko eines Patzers (halber Schaden). Implementiert ist nur der
Krit. LUK ist dadurch ein reiner Bonus-Stat ohne Absicherungsfunktion.

---

## 1. Balancing

### 1.1 Extrem-Spezialisierung bricht das Gleichgewicht
**Prioritaet: hoch — Design-Entscheidung noetig**

`services/levelup.py` erlaubt `MAX_BONUS_PER_STAT = 50`. Ein Drittel des
gesamten Basis-Budgets (100 Punkte) kann damit in ein einziges Attribut
fliessen. Die Klassenbalance haelt das nicht aus:

| Level | Krieger | Schurke | Magier | Spread |
|-------|---------|---------|--------|--------|
| 10    |   50 %  |    7 %  |  93 %  |   86   |
| 30    |   84 %  |   48 %  |  17 %  |   67   |
| 50    |   79 %  |   48 %  |  21 %  |   58   |

Zum Vergleich: mit gleichmaessiger Verteilung liegt der Spread bei 3–8
Prozentpunkten.

Moegliche Ansaetze (noch zu entscheiden):

- `MAX_BONUS_PER_STAT` auf 20–25 senken
- abnehmender Grenzertrag pro investiertem Punkt
- Mindestanteil pro Attribut erzwingen (z. B. 10 % der Summe)
- Bonuspunkte an Klassen-Schwerpunkte koppeln (Magier darf weniger in DEF)

Messreihen reproduzierbar ueber die Simulation in `docs/BALANCING.md`.

### 1.2 Typ-Vorteil vs. Stat-Vorteil
**Prioritaet: mittel**

Der Schere-Stein-Papier-Faktor (x1.25 / x0.8) wirkt multiplikativ auf den
Endschaden. Bei stark spezialisierten Builds wird er dadurch bedeutungslos —
ein Magier mit ATK 95 schlaegt einen Krieger auch mit Typnachteil. Zu pruefen:
Typ-Faktor additiv auf die Rohwerte statt multiplikativ auf den Schaden.

### 1.3 PVE-Walls
**Prioritaet: mittel**

`test_balancing.py` zeigt Idle-Walls im Bereich Floor 14–37, je nach Klasse
und Seed. Der Magier bleibt im Schnitt am fruehesten stecken (Ø 22,3), der
Krieger am spaetesten (Ø 26,9). Ob das gewollt ist, haengt an der
Zielspielzeit — bisher nicht definiert.

---

## 2. Tests

### 2.1 Netzwerk-Tests sind Struktur-, keine Funktionstests
**Prioritaet: mittel**

`tests/test_net_manager.py` prueft nach der Ueberarbeitung nur noch, dass
`setup_network()` ein Dict zurueckgibt. Die tatsaechliche Wirkung (tun0
angelegt, iptables-Regeln gesetzt, Split-Tunneling aktiv) laesst sich ohne
root und ohne echte Hardware nicht verifizieren.

Sinnvoll waere:

- `_safe_run` per Monkeypatch durch einen Recorder ersetzen und die
  abgesetzten Kommandos gegen eine Erwartungsliste pruefen
- Integrationstest, der auf einem echten Pi laeuft (Marker `@pytest.mark.hardware`)

### 2.2 Integrationstest auf echter Hardware
**Prioritaet: mittel**

`tests/test_battle_parity.py` und `tests/test_p2p_consistency.py` decken
Engine-Paritaet, Determinismus und Rollenvergabe inzwischen ab — aber beide
simulieren den zweiten Teilnehmer im selben Prozess.

Was weiterhin fehlt: ein Lauf ueber zwei physische Pis, der die Logs beider
Geraete nach dem Kampf vergleicht. Genau das war beim bisherigen Feldtest
nicht geprueft worden — die Kaempfe liefen durch, aber niemand legte die
Ergebnisse nebeneinander. Die Abweichung in der Rollenvergabe blieb dadurch
unbemerkt.

Vorschlag: Skript, das per SSH auf beide Geraete zugreift, einen Kampf mit
festem Seed ausloest und `battle.log` beider Seiten diff-t. Marker
`@pytest.mark.hardware`, im CI uebersprungen.

### 2.3 Testabdeckung unbekannt
**Prioritaet: niedrig**

`pytest-cov` ist in `requirements-dev.txt`, wurde aber nie ausgewertet.
65 Tests bei 106 Modulen deuten auf erhebliche Luecken.

---

## 3. CI/CD

### 3.1 `.github/workflows/deploy.yml` ist nicht lauffaehig
**Prioritaet: mittel**

```yaml
- name: Create Raspberry Pi Image
  uses: ./.github/workflows/create-image
```

Diese lokale Action existiert nicht. Der Job scheitert beim ersten Release.
Entweder Action implementieren (pi-gen im Container) oder Schritt entfernen.

### 3.2 Workflows sind derzeit nicht im Repo
**Prioritaet: niedrig**

Beim Code-Import wurden `.github/workflows/` ausgespart, weil der verwendete
Token keinen `workflow`-Scope hatte. Nachzureichen, sobald `deploy.yml`
repariert ist.

### 3.3 `test.yml` bricht bei Coverage-Upload ab
**Prioritaet: niedrig**

`codecov/codecov-action@v3` mit `fail_ci_if_error: true` laesst den Build
fehlschlagen, solange kein Codecov-Token hinterlegt ist. Fuer ein privates
Pre-Alpha-Projekt entweder entfernen oder auf `false` setzen.

---

## 4. Sicherheit

### 4.1 BLE-Beacons sind unverschluesselt
**Prioritaet: mittel — bewusste Entscheidung, dokumentieren**

Laut `SICHERHEIT-ZUSAMMENFASSUNG.md` werden Beacons im Klartext gesendet
(Begruendung: Latenz). Damit sind Geraete-Praesenz und MAC im oeffentlichen
Raum mitlesbar — der "Ghost Mode" verbirgt nur die SSID, nicht den Beacon.

Zu klaeren: rotierende MAC (wie bei Apple/Google Exposure Notifications),
oder explizit als akzeptiertes Restrisiko im README benennen.

### 4.2 Kein Signatur-Check auf Kampfergebnisse
**Prioritaet: hoch (vor jedem oeffentlichen Release)**

Die Engine ist deterministisch, aber nichts hindert einen manipulierten
Client daran, ein beliebiges Ergebnis zu behaupten. `ecc_crypto.py` liefert
Ed25519-Signaturen — sie werden auf das Handshake-Token angewendet, aber
nicht auf das Kampfergebnis selbst.

Vorschlag: beide Seiten signieren den finalen Zustands-Hash, Abweichung =
Kampf ungueltig.

### 4.3 `install.sh` laeuft als root
**Prioritaet: niedrig**

Erwartbar fuer einen Systeminstaller, sollte aber im README stehen, samt
Hinweis darauf, was genau veraendert wird (hostapd, dnsmasq, systemd-Units,
Benutzeranlage).

### 4.4 Keine Input-Validierung auf Port 5005
**Prioritaet: hoch — vor jedem Einsatz im oeffentlichen Raum**

`battle_server` nimmt JSON-Profile fremder Geraete entgegen und reicht sie
per `json.loads()` direkt an die Engine weiter. Keine Schema-Pruefung, keine
Laengenbegrenzung, keine Plausibilitaetspruefung.

Die eigene Planungsanalyse benannte das bereits deutlich:

> *"Der Socket-Server, der auf Port 5005 lauscht, nimmt die JSON-Profile der
> entdeckten Gegner entgegen und reicht sie ohne jegliche Identifizierung
> oder Strukturvalidierung an die Engine weiter. […] Ein manipuliertes
> JSON-Objekt, das ueberlange Strings enthaelt oder bei unsauberer
> Deserialisierung in Python direkt Code ausfuehrt, reicht aus, um eine
> Root-Shell auf dem System zu erzwingen."*

Der Befund ist seit der Planungsphase bekannt und bis heute offen.

Erforderlich:

- Schema-Validierung mit Pydantic vor jeder Verarbeitung
- harte Laengenbegrenzung der empfangenen Bytes
- Plausibilitaetspruefung der Stats: Summe = 100 + 5 x (Level - 1),
  jeder Wert zwischen 1 und 100
- Zeichensatz-Whitelist fuer Namensfelder (verhindert Terminal-Escapes im
  SSH-Dashboard)
- Ablehnung unbekannter Felder statt stillem Ignorieren

Bis dahin sollte ZTB nur in kontrollierter Umgebung mit bekannten Geraeten
laufen.

---

## 5. Architektur

### 5.1 Doppelte Kampf-Engines
**Prioritaet: hoch**

`deterministic_battle.py` und `engine/battle_engine.py` rechnen jetzt
identisch, sind aber weiterhin zwei getrennte Implementierungen. Die naechste
Aenderung an einer Formel laeuft in dieselbe Falle.

Ziel: eine gemeinsame `damage()`-Funktion, die beide importieren.

### 5.2 Re-Export-Module
**Prioritaet: niedrig**

`services/inventory.py`, `game/models/player.py` und `game/models/enemy.py`
sind nur noch Weiterleitungen auf `models/`. Sauber fuer die Migration, aber
irgendwann durch direkte Importe ersetzen und entfernen.

### 5.3 `hybrid_orchestrator.py` ist 50 KB gross
**Prioritaet: niedrig**

Groesste Datei nach `ui/options/war_room.py` (118 KB). Beide Kandidaten fuer
eine Aufteilung, sobald sich die Struktur stabilisiert hat.

### 5.4 Zwei getrennte PVP-Pfade mit unterschiedlicher Seed-Logik
**Prioritaet: hoch — Grundsatzentscheidung noetig**

Es existieren zwei vollstaendig getrennte Wege, einen PVP-Kampf auszufuehren:

| | `controllers/battle_server.py` | `hybrid_orchestrator.py` |
|---|---|---|
| Engine | `BattleEngine.run_pvp_battle()` | `DeterministicBattle.run_pvp()` |
| Seed | `SHA256(sortierte Namen + Timestamp)` | `SHA256(MACs nach IP + ECDH-Token)` |
| Rolle A | lexikografisch kleinerer Name | kleineres IP-Suffix |

Beide wurden 2026-09 auf symmetrische Rollenvergabe korrigiert, benutzen
aber weiterhin unterschiedliche Seed-Quellen. Zwei Geraete, die ueber
verschiedene Pfade in denselben Kampf gehen, erzeugen verschiedene Seeds
und damit verschiedene Kampfverlaeufe.

Der Orchestrator-Weg ist der bessere: Der Seed haengt an MACs und dem
ECDH-Handshake-Token, ist also voellig zeitunabhaengig und nicht von aussen
vorhersagbar. Der Server-Weg braucht dagegen synchronisierte Uhren — auf
Pis ohne RTC eine Wette. Als Zwischenloesung quantisiert
`battle_server.SEED_TIME_WINDOW` den Timestamp auf 60-Sekunden-Fenster;
das faengt Drift ab, loest das Grundproblem aber nicht.

Zu entscheiden: Ist `battle_server.py` noch der gewollte Weg, oder soll der
Orchestrator-Pfad der einzige werden? Beim zweiten Fall kann `process_battle()`
entfallen und der Server reicht nur noch Profile durch.

### 5.5 Kein Abgleich der Ergebnisse zwischen den Geraeten
**Prioritaet: hoch**

Beide Seiten rechnen denselben Kampf — aber niemand vergleicht, ob dabei
dasselbe herauskam. Der Server sendet sein Ergebnis (`handle_client`),
der Client las es bis 2026-09 gar nicht aus und uebernimmt es jetzt
ungeprueft.

Solange die Engines identisch rechnen, ist das folgenlos. Weicht eine Seite
ab — andere Version, manipuliertes Binary, Bitfehler —, faellt es nicht auf.

Vorschlag: Beide Seiten bilden einen Hash ueber `(seed, rounds, winner,
log)` und tauschen ihn aus. Abweichung = Kampf verworfen, Vorfall geloggt.
Zusammen mit den Ed25519-Signaturen aus Punkt 4.2 ergibt das ein
belastbares Ergebnis-Protokoll.

---

## 6. Dokumentation

### 6.1 Drei README-Varianten
**Prioritaet: niedrig**

`README.md`, `README_DE.md`, `docs/readme_de.md`, `docs/readme_en.md` und
`docs/README.md` ueberschneiden sich. Eine kanonische Fassung waehlen, den
Rest verlinken.

### 6.2 Kein Beitragsleitfaden fuer den Balancing-Bereich
**Prioritaet: niedrig**

Wer Stats aendert, sollte die Simulation aus `docs/BALANCING.md` laufen
lassen und die neue Siegquoten-Tabelle mitliefern. Gehoert in
`CONTRIBUTING.md`.
