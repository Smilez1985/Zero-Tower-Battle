# Balancing — Schadensformel und Klassen-Gleichgewicht

Stand: 2026-09-28

## Das 100-Punkte-Gesetz

Jede Klasse verteilt exakt 100 Punkte auf vier Attribute:

| Klasse  | Typ    | ATK | DEF | SPD | LUK | Summe |
|---------|--------|-----|-----|-----|-----|-------|
| Krieger | Stein  |  25 |  40 |  20 |  15 |   100 |
| Schurke | Schere |  25 |  15 |  40 |  20 |   100 |
| Magier  | Papier |  45 |  10 |  20 |  25 |   100 |

Pro Level-Up kommen 5 frei verteilbare Bonuspunkte dazu (max. 50 pro Attribut).
Die Basis-Stats bleiben unveraendert.

## Der Fehler bis September 2026

`deterministic_battle.py` (PVP/Raid) und `engine/battle_engine.py` (PVE)
verwendeten **zwei unterschiedliche Schadensformeln**. Die PVE-Engine hatte
bereits die korrigierte V2-Formel, die PVP-Engine noch die alte:

```python
# ALT (deterministic_battle.py)
raw            = (atk * 125 * level) // 1000   # ATK skaliert MIT Level
defense_reduce = (defender_def * 50) // 100    # DEF skaliert NICHT
base_damage    = max(5, raw - defense_reduce)  # lineare Subtraktion
```

Drei Probleme daran:

1. **ATK wuchs mit Level, DEF nicht.** Ab etwa Level 8 war Verteidigung
   wirkungslos.
2. **Subtraktive Ruestung.** Zu Beginn uebermaechtig (DEF 40 gegen Rohschaden 6
   = unverwundbar), spaeter wertlos.
3. **HP wuchs linear** (`80 + level*10`), der Schaden quadratisch.

Auswirkung — simuliert ueber alle Klassenpaarungen, 1500 Kaempfe je Paarung:

| Level | Krieger | Schurke | Magier | Ø Runden |
|-------|---------|---------|--------|----------|
|  1    |   49 %  |   50 %  |  49 %  |   15,9   |
|  5    |   50 %  |    1 %  |  98 %  |   11,2   |
| 10    |   50 %  |   34 %  |  65 %  |    4,1   |
| 20    |   46 %  |   42 %  |  61 %  |    2,3   |
| 50    |   21 %  |   68 %  |  59 %  |    1,3   |

Ab Level 20 endete ein Kampf nach durchschnittlich zwei Runden; es gewann
faktisch, wer mehr SPD hatte. Welche Klasse dominierte, haing allein vom Level
ab — deshalb wirkten Beobachtungen auf zwei verschieden weit fortgeschrittenen
Geraeten widerspruechlich.

## Die korrigierte Formel (V2)

Beide Engines rechnen jetzt identisch:

```
1. Raw     = ATK x (100 + (Level-1) x 5) // 100
2. DefPct  = DEF x 100 // (DEF + 50)            # asymptotisch, nie 100 %
3. Schaden = max(3, Raw x (100 - DefPct) // 100)
4. Varianz = 90-110 %
5. Typ     = x1.25 (Vorteil) / x0.8 (Nachteil)
6. Krit    = LUK x 5 / 1000 Chance -> x2
```

Die Verteidigungskurve `DEF / (DEF + K)` ist Standard in League of Legends,
Dota 2, Warframe und Diablo. Sie hat abnehmenden Grenzertrag: DEF 20 = 28 %
Reduktion, DEF 40 = 44 %, DEF 80 = 61 %. Vollpanzer wird nie zur dominanten
Strategie, aber Verteidigung bleibt auf jedem Level relevant.

Max-HP beruecksichtigt jetzt ebenfalls DEF:

```
MaxHP = 100 + (Level-1) x 17 + DEF x 3 // 2
```

### SPD als echter Stat

SPD bestimmte vorher nur die Zugreihenfolge und war damit fast wertlos — der
Schurke verlor systematisch. Neu: Wer mehr SPD hat, hat eine Chance auf einen
**Extra-Angriff** pro Runde.

```
Chance = min(45 %, SPD-Differenz x 1,5 %)
```

## Ergebnis

Basis-Stats, 500 Kaempfe je Paarung:

| Level | Krieger | Schurke | Magier | Spread | Ø Runden |
|-------|---------|---------|--------|--------|----------|
|  1    |   51 %  |   45 %  |  52 %  |   7    |   4,9    |
|  5    |   50 %  |   43 %  |  56 %  |  13    |   5,9    |
| 10    |   50 %  |   42 %  |  57 %  |  15    |   7,0    |
| 20    |   50 %  |   45 %  |  54 %  |   9    |   8,2    |
| 30    |   50 %  |   46 %  |  53 %  |   7    |   8,6    |
| 50    |   50 %  |   45 %  |  54 %  |   9    |   9,4    |

Mit gleichmaessiger Bonuspunkt-Verteilung (Auto-Modus) liegt der Spread
zwischen 3 und 8 Prozentpunkten.

**Faustregel:** Ein faires System erkennt man daran, dass keine Klasse ueber
55 % Siegquote gegen das Gesamtfeld kommt.

## Bekannte Schwaeche: Extrem-Spezialisierung

Wer alle Bonuspunkte in ein einziges Attribut kippt (50 Punkte in DEF bzw.
ATK), bricht das Gleichgewicht weiterhin:

| Level | Krieger | Schurke | Magier | Spread |
|-------|---------|---------|--------|--------|
| 10    |   50 %  |    7 %  |  93 %  |   86   |
| 30    |   84 %  |   48 %  |  17 %  |   67   |
| 50    |   79 %  |   48 %  |  21 %  |   58   |

Das ist kein Formelfehler, sondern eine Design-Entscheidung: `MAX_BONUS_PER_STAT`
erlaubt 50 Punkte auf ein Attribut — ein Drittel des gesamten Basis-Budgets.

Moegliche Gegenmassnahmen (noch nicht umgesetzt):

- `MAX_BONUS_PER_STAT` auf 20-25 senken
- Bonuspunkte pro Stat mit abnehmendem Ertrag gewichten
- Mindestpunkte pro Attribut erzwingen (z. B. 10 % der Gesamtsumme)

## Simulation reproduzieren

```bash
python3 test_balancing.py      # PVE-Floors, Idle-Walls pro Klasse
python3 -m pytest tests/ -q    # Unit-Tests
```
