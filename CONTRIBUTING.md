# CONTRIBUTING / MITWIRKEN

## Mitwirken

### Wie man beitraegt

Wir freuen uns ueber Beitraege! So funktioniert es:

1. **Fork**: Erstelle einen Fork des Repositories auf GitHub
2. **Branch**: Erstelle einen neuen Branch fuer deine Aenderung: `git checkout -b feature/dein-feature`
3. **Commit**: Committe deine Aenderungen: `git commit -am 'Beschreibung der Aenderung'`
4. **Push**: Pushe zu deinem Fork: `git push origin feature/dein-feature`
5. **Pull Request**: Oeffne einen Pull Request mit einer Beschreibung deiner Aenderungen

### Code-Standards

**Python 3.9+**: Zero Tower Battle zielt auf Python 3.9+ ab.

**Keine externen Dependencies ohne Diskussion**: Bevor du eine neue externe Library hinzufuegst, bitte eroeffne ein Issue zur Diskussion. Der Pi Zero 2 hat nur 512MB RAM und wir versuchen, die Abhaengigkeiten minimal zu halten.

**Lazy Imports**: Der Code nutzt Lazy Imports zur RAM-Optimierung. Neue Module sollten auch lazy imports verwenden, wenn sie nicht sofort beim Start geladen werden.

```python
# Statt:
from module import something

# Nutze Lazy Loading (falls das Modul nicht immer gebraucht wird):
_something = None

def _get_something():
    global _something
    if _something is None:
        from module import something
        _something = something
    return _something
```

### Benennungskonventionen

- **Deutsche Variablennamen fuer Spiellogik**: Variablen in der Spiellogik (Champion, Items, Kaempfe) sollten auf Deutsch benannt sein: `champion_name`, `schaden`, `erfahrung`, `inventar`
- **Englische Namen fuer technische Module**: Technische Module, Funktionen und Klassen sollten auf Englisch benannt sein: `BattleEngine`, `HotStorageManager`, `get_battle_result()`

### Tests ausfuehren

Tests mit pytest ausfuehren:

```bash
python3 -m pytest tests/
```

Mit Coverage-Report:

```bash
python3 -m pytest tests/ --cov=. --cov-report=html
```

### Pi-Zero-Constraints beachten

Der Raspberry Pi Zero 2 hat nur 512MB RAM und ist sehr ressourcenlimitiert. Bitte beachte:

1. **Speicher-Verbrauch**: Teste deine Aenderungen auf RAM-Verbrauch. Der Hybrid Orchestrator versucht, unter 45MB bei SSH-Sessions zu bleiben.

2. **Integer-basierte Berechnungen**: Verwende Integer statt Floating-Point fuer kritische Berechnungen (z.B. Schadensberechnung), um Genauigkeit bei P2P zu gewaehrleisten.

3. **Keine Pydantic fuer Core-Logik**: Pydantic ist schwer und wird nur optionell verwendet. Core-Module sollten Pydantic nicht nutzen.

4. **Lazy Imports verwenden**: Nur Module laden, die gerade benoetigt werden.

---

## Contributing

### How to Contribute

We welcome contributions! Here's how it works:

1. **Fork**: Create a fork of the repository on GitHub
2. **Branch**: Create a new branch for your changes: `git checkout -b feature/your-feature`
3. **Commit**: Commit your changes: `git commit -am 'Description of changes'`
4. **Push**: Push to your fork: `git push origin feature/your-feature`
5. **Pull Request**: Open a pull request with a description of your changes

### Code Standards

**Python 3.9+**: Zero Tower Battle targets Python 3.9 and above.

**No external dependencies without discussion**: Before adding a new external library, please open an issue for discussion. The Pi Zero 2 has only 512MB RAM and we aim to keep dependencies minimal.

**Lazy Imports**: The codebase uses lazy imports for RAM optimization. New modules should also use lazy imports if they're not needed immediately at startup.

```python
# Instead of:
from module import something

# Use lazy loading (if the module isn't always needed):
_something = None

def _get_something():
    global _something
    if _something is None:
        from module import something
        _something = something
    return _something
```

### Naming Conventions

- **German variable names for game logic**: Variables in game logic (champion, items, battles) should be named in German: `champion_name`, `schaden`, `erfahrung`, `inventar`
- **English names for technical modules**: Technical modules, functions, and classes should be named in English: `BattleEngine`, `HotStorageManager`, `get_battle_result()`

### Running Tests

Run tests with pytest:

```bash
python3 -m pytest tests/
```

With coverage report:

```bash
python3 -m pytest tests/ --cov=. --cov-report=html
```

### Pi Zero Constraints to Keep in Mind

The Raspberry Pi Zero 2 has only 512MB RAM and is very resource-limited. Please consider:

1. **Memory usage**: Test your changes for RAM consumption. The Hybrid Orchestrator aims to stay under 45MB during SSH sessions.

2. **Integer-based calculations**: Use integers instead of floating-point for critical calculations (e.g., damage calculations) to ensure accuracy in P2P scenarios.

3. **No Pydantic for core logic**: Pydantic is heavy and is only used optionally. Core modules should not use Pydantic.

4. **Use lazy imports**: Only load modules when they're actually needed.
