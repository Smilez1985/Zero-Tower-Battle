# Roadmap — offene Punkte

Stand: 2026-09-28

Diese Datei sammelt alles, was beim Code-Review und Balancing-Durchlauf
aufgefallen ist, aber bewusst **nicht** sofort behoben wurde — weil es eine
Design-Entscheidung braucht, Hardware voraussetzt oder ueber eine reine
Fehlerkorrektur hinausgeht.

Was bereits erledigt ist, steht im CHANGELOG und in `docs/BALANCING.md`.

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

### 2.2 Keine Tests fuer die Kampf-Engines
**Prioritaet: hoch**

Der gravierendste Bug des Projekts — zwei divergierende Schadensformeln in
`deterministic_battle.py` und `engine/battle_engine.py` — waere durch einen
einzigen Test aufgefallen, der beide Engines mit identischen Eingaben
vergleicht. Fehlt bislang.

Vorschlag:

```python
def test_engines_agree_on_damage():
    """PVE- und PVP-Engine muessen identisch rechnen."""
    for level in (1, 10, 30, 50):
        for atk, dfs in [(25, 40), (45, 10), (60, 25)]:
            assert pve_damage(atk, dfs, level) == pvp_damage(atk, dfs, level)
```

Dazu ein Property-Test: derselbe Seed muss auf zwei Instanzen denselben
Kampfverlauf erzeugen (Kernversprechen des P2P-Designs, bisher ungetestet).

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
