"""
Procedural Monster Sprite Generator mit ANSI Terminal Art Konvertierung.

Dieses Modul erstellt symmetrische Monster-Sprites mittels Pillow und wandelt diese
in ANSI-farbige Terminalausgaben um. Unterstützt mehrere Größen (16x16, 32x32, 64x64),
Seltenheitsstufen (Common, Rare, Legendary) und deterministische Generierung basierend
auf Seed-Werten für Reproduzierbarkeit.

Optimiert für ressourceneffiziente Ausführung auf Systemen mit begrentem Speicher
(z.B. Raspberry Pi Zero 2W mit 512 MB RAM).

Rarity-Farben:
  - common: (100, 150, 100) grün-grau
  - rare: (0, 100, 255) blau
  - legendary: (255, 215, 0) gold

Verwendungsbeispiel:
    gen = MonsterSpriteGenerator()
    ansi_art = gen.generate_monster_ansi(size_choice=1, seed=42, rarity="rare")
    print(ansi_art)
"""

import random
from typing import Tuple, Optional
from PIL import Image, ImageDraw


# ANSI 256-Farb-Palette
ANSI_256_COLORS = [
    (0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0),
    (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
    (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0),
    (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
]

# Erweiterte Farbtabelle für Codes 16-231 (6x6x6 RGB-Würfel)
for r in range(6):
    for g in range(6):
        for b in range(6):
            ANSI_256_COLORS.append((r * 51, g * 51, b * 51))

# Graustufen für Codes 232-255
for i in range(24):
    gray = 8 + i * 10
    ANSI_256_COLORS.append((gray, gray, gray))


class MonsterSpriteGenerator:
    """
    Generator für prozedural erzeugte Monster-Sprites mit symmetrischem Design.

    Erstellt symmetrische Monster durch zufällige Füllung der linken Hälfte und
    Spiegelung zur rechten Seite. Unterstützt deterministische Generierung durch
    Seed-Werte sowie Konvertierung zu ANSI-Terminalart.
    """

    # Größen-Mappings: choice -> Pixelgröße
    SIZE_MAP = {
        0: 16,
        1: 32,
        2: 64,
    }

    # Rarity-Farben: rarity_string -> RGB-Tuple
    RARITY_COLORS = {
        "common": (100, 150, 100),      # Grün-Grau
        "rare": (0, 100, 255),          # Blau
        "legendary": (255, 215, 0),     # Gold
    }

    def __init__(self):
        """Initialisiere den Monster-Sprite-Generator."""
        pass

    def generate_monster(
        self,
        size_choice: int = 1,
        seed: Optional[int] = None,
        rarity: str = "common",
    ) -> Image.Image:
        """
        Erstelle ein symmetrisches Monster-Sprite als PIL Image.

        Die linke Hälfte wird basierend auf dem Seed zufällig gefüllt, dann zur
        rechten Seite gespiegelt. Das Ergebnis ist vollständig symmetrisch.

        Args:
            size_choice: Größenwahl (0=16x16, 1=32x32, 2=64x64). Standardwert: 1.
            seed: Optional Seed für deterministische Generierung. Wenn None,
                  wird eine neue zufällige Sequenz generiert.
            rarity: Seltenheitsstufe ("common", "rare", "legendary").
                   Standardwert: "common".

        Returns:
            PIL.Image.Image: Das generierte Monster-Sprite als RGB-Bild.

        Raises:
            ValueError: Falls size_choice oder rarity ungültig sind.
        """
        if size_choice not in self.SIZE_MAP:
            raise ValueError(
                f"size_choice must be in {list(self.SIZE_MAP.keys())}, "
                f"got {size_choice}"
            )
        if rarity not in self.RARITY_COLORS:
            raise ValueError(
                f"rarity must be one of {list(self.RARITY_COLORS.keys())}, "
                f"got {rarity}"
            )

        # Setze Seed für Reproduzierbarkeit
        if seed is not None:
            random.seed(seed)

        size = self.SIZE_MAP[size_choice]
        color = self.RARITY_COLORS[rarity]

        # Erstelle ein neues RGB-Bild mit weißem Hintergrund
        img = Image.new("RGB", (size, size), color=(255, 255, 255))
        pixels = img.load()

        # Pixel-Größe der Zellen (für ein 32x32 Sprite: 1 Pixel = 1 "Zelle")
        cell_size = 1

        # Halbiere die Breite für die linke Seite
        half_width = size // 2

        # Fülle die linke Hälfte zufällig
        for x in range(half_width):
            for y in range(size):
                if random.random() < 0.7:  # 70% Wahrscheinlichkeit für gefüllt
                    pixels[x, y] = color

        # Spiegele die linke Hälfte zur rechten Seite
        for x in range(half_width):
            for y in range(size):
                mirror_x = size - 1 - x
                pixels[mirror_x, y] = pixels[x, y]

        return img

    @staticmethod
    def _find_closest_ansi_color(rgb: Tuple[int, int, int]) -> int:
        """
        Finde den nächsten ANSI 256-Farb-Code für eine RGB-Farbe.

        Verwendet euklidische Distanz im RGB-Raum zur Bestimmung der
        nächsten verfügbaren ANSI-Farbe.

        Args:
            rgb: Tuple (r, g, b) mit Werten 0-255.

        Returns:
            int: ANSI-Farb-Code 0-255.
        """
        r, g, b = rgb
        min_distance = float("inf")
        closest_code = 0

        for code, (ar, ag, ab) in enumerate(ANSI_256_COLORS):
            distance = (r - ar) ** 2 + (g - ag) ** 2 + (b - ab) ** 2
            if distance < min_distance:
                min_distance = distance
                closest_code = code

        return closest_code

    @staticmethod
    def image_to_ansi(img: Image.Image, terminal_width: int = 32) -> str:
        """
        Konvertiere ein PIL Image zu ANSI-farbiger Terminalausgabe.

        Das Bild wird auf die gewünschte Terminalbreite reskaliert und dann
        mittels Half-Block-Zeichen (▀▄) zu ANSI-Code konvertiert. Dies ermöglicht
        eine 2x vertikale Auflösung bei 1x horizontaler Auflösung.

        Args:
            img: PIL.Image.Image im RGB-Modus.
            terminal_width: Gewünschte Ausgabebreite in Zeichen (Standardwert: 32).

        Returns:
            str: Multi-line String mit ANSI-Escape-Sequenzen und Half-Block-Zeichen.
        """
        # Konvertiere zu RGB falls nötig
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Berechne das Seitenverhältnis und reskaliere
        width, height = img.size
        aspect_ratio = height / width
        new_height = int(terminal_width * aspect_ratio * 2)  # *2 wegen Half-Blocks
        new_height = max(2, new_height)

        # Reskaliere mit Lanczos-Filter
        img_resized = img.resize(
            (terminal_width, new_height),
            Image.Resampling.LANCZOS,
        )

        pixels = img_resized.load()
        lines = []

        # Verarbeite das Bild in Zwei-Zeilen-Schritten (für Half-Blocks)
        for y in range(0, new_height - 1, 2):
            line = ""
            for x in range(terminal_width):
                # Hole oberes und unteres Pixel
                rgb_top = pixels[x, y]
                rgb_bottom = pixels[x, y + 1]

                # Finde nächste ANSI-Farben
                code_top = MonsterSpriteGenerator._find_closest_ansi_color(rgb_top)
                code_bottom = (
                    MonsterSpriteGenerator._find_closest_ansi_color(rgb_bottom)
                )

                # Erstelle ANSI-Sequenz mit oberer Farbe als Vordergrund
                # und unterer Farbe als Hintergrund
                ansi_seq = f"\033[38;5;{code_top}m\033[48;5;{code_bottom}m▀\033[0m"
                line += ansi_seq

            lines.append(line)

        # Reset-Sequenz am Ende hinzufügen
        return "\n".join(lines) + "\033[0m"

    def generate_monster_ansi(
        self,
        size_choice: int = 1,
        seed: Optional[int] = None,
        rarity: str = "common",
        terminal_width: int = 32,
    ) -> str:
        """
        Generiere ein Monster-Sprite und konvertiere es direkt zu ANSI-Terminalart.

        Dies ist eine Convenience-Funktion, die die Monster-Generierung und
        ANSI-Konvertierung kombiniert.

        Args:
            size_choice: Größenwahl (0=16x16, 1=32x32, 2=64x64). Standardwert: 1.
            seed: Optional Seed für deterministische Generierung.
            rarity: Seltenheitsstufe ("common", "rare", "legendary").
                   Standardwert: "common".
            terminal_width: Gewünschte Ausgabebreite in Zeichen (Standardwert: 32).

        Returns:
            str: ANSI-farbiger Terminalausgabe-String.
        """
        img = self.generate_monster(size_choice, seed, rarity)
        return self.image_to_ansi(img, terminal_width)


# Module-Level-Convenience-Funktionen

def generate_monster(
    size_choice: int = 1,
    seed: Optional[int] = None,
    rarity: str = "common",
) -> Image.Image:
    """
    Generiere ein Monster-Sprite als PIL Image.

    Siehe MonsterSpriteGenerator.generate_monster() für Details.

    Args:
        size_choice: Größenwahl (0=16x16, 1=32x32, 2=64x64). Standardwert: 1.
        seed: Optional Seed für deterministische Generierung.
        rarity: Seltenheitsstufe ("common", "rare", "legendary").

    Returns:
        PIL.Image.Image: Das generierte Monster-Sprite.
    """
    gen = MonsterSpriteGenerator()
    return gen.generate_monster(size_choice, seed, rarity)


def image_to_ansi(img: Image.Image, terminal_width: int = 32) -> str:
    """
    Konvertiere ein PIL Image zu ANSI-farbiger Terminalausgabe.

    Siehe MonsterSpriteGenerator.image_to_ansi() für Details.

    Args:
        img: PIL.Image.Image im RGB-Modus.
        terminal_width: Gewünschte Ausgabebreite in Zeichen (Standardwert: 32).

    Returns:
        str: Multi-line String mit ANSI-Escape-Sequenzen.
    """
    return MonsterSpriteGenerator.image_to_ansi(img, terminal_width)


def generate_monster_ansi(
    size_choice: int = 1,
    seed: Optional[int] = None,
    rarity: str = "common",
    terminal_width: int = 32,
) -> str:
    """
    Generiere ein Monster-Sprite und konvertiere es direkt zu ANSI-Terminalart.

    Siehe MonsterSpriteGenerator.generate_monster_ansi() für Details.

    Args:
        size_choice: Größenwahl (0=16x16, 1=32x32, 2=64x64). Standardwert: 1.
        seed: Optional Seed für deterministische Generierung.
        rarity: Seltenheitsstufe ("common", "rare", "legendary").
        terminal_width: Gewünschte Ausgabebreite in Zeichen (Standardwert: 32).

    Returns:
        str: ANSI-farbige Terminalausgabe.
    """
    gen = MonsterSpriteGenerator()
    return gen.generate_monster_ansi(size_choice, seed, rarity, terminal_width)


if __name__ == "__main__":
    """Demonstrationscode für die Monster-Sprite-Generierung."""
    import sys

    print("=" * 50)
    print("Monster Sprite Generator - Demo")
    print("=" * 50)
    print()

    # Beispiel 1: Generiere ein Common-Monster (32x32)
    print("Common Monster (32x32, Seed=42):")
    print("-" * 50)
    ansi_common = generate_monster_ansi(
        size_choice=1,
        seed=42,
        rarity="common",
        terminal_width=24,
    )
    print(ansi_common)
    print()

    # Beispiel 2: Generiere ein Rare-Monster (32x32)
    print("Rare Monster (32x32, Seed=123):")
    print("-" * 50)
    ansi_rare = generate_monster_ansi(
        size_choice=1,
        seed=123,
        rarity="rare",
        terminal_width=24,
    )
    print(ansi_rare)
    print()

    # Beispiel 3: Generiere ein Legendary-Monster (16x16)
    print("Legendary Monster (16x16, Seed=999):")
    print("-" * 50)
    ansi_legendary = generate_monster_ansi(
        size_choice=0,
        seed=999,
        rarity="legendary",
        terminal_width=20,
    )
    print(ansi_legendary)
    print()

    # Beispiel 4: Zeige Symmetrie durch zwei Aufrufe mit gleichem Seed
    print("Deterministic Generation Test (Seed=777):")
    print("-" * 50)
    ansi_1 = generate_monster_ansi(size_choice=1, seed=777, rarity="rare")
    ansi_2 = generate_monster_ansi(size_choice=1, seed=777, rarity="rare")
    print("First call == Second call:", ansi_1 == ansi_2)
    print()

    print("=" * 50)
    print("Demo completed successfully!")
    print("=" * 50)
