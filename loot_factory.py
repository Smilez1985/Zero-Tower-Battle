#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Loot Factory (Gacha-System)
======================================================
Dediziertes Item-Generierungs-Modul.

Verantwortlichkeiten:
  - Prozedurale Item-Generierung nach Seltenheitsstufen
  - LUK-beeinflusste Drop-Raten
  - Shiny-Erkennung (1:8192 -> garantiert Legendaer)
  - Runen-Slot-System (1 Rune pro Item, Fusion ueber Schmiede)
  - Schmiede-kompatible Items (Upgrade-Level, Name-Suffix)
  - Biom-spezifische Loot-Tabellen (Saison-Rotation)
  - Boss-Loot (staerker, garantiert ab Tier 3)
  - Codex-kompatible Monster-Drops

Referenz: Battle-Pi_Konsolidiert.txt Abschnitt 6B, 6C, 6D, 6E
"""

import random
import time
import hashlib
from typing import Dict, Any, Optional, List, Tuple


# =============================================
# Seltenheitsstufen (Spec Abschnitt 6B)
# =============================================

RARITIES = {
    "common": {
        "name_de": "Gewoehnlich",
        "name_en": "Common",
        "color": "white",
        "weight": 0.75,         # 75% Basis-Chance
        "stat_min": 2,
        "stat_max": 7,
        "value_multiplier": 1,
        "upgrade_cap": 3        # Max +3 in der Schmiede
    },
    "rare": {
        "name_de": "Selten",
        "name_en": "Rare",
        "color": "cyan",
        "weight": 0.20,         # 20% Basis-Chance
        "stat_min": 8,
        "stat_max": 14,
        "value_multiplier": 2,
        "upgrade_cap": 5        # Max +5
    },
    "legendary": {
        "name_de": "Legendaer",
        "name_en": "Legendary",
        "color": "gold",
        "weight": 0.05,         # 5% Basis-Chance
        "stat_min": 15,
        "stat_max": 25,
        "value_multiplier": 5,
        "upgrade_cap": 10       # Max +10
    }
}

# =============================================
# Item-Typen (Spec Abschnitt 6C)
# =============================================

ITEM_TYPES = {
    "Waffe": {
        "primary_stat": "atk",
        "secondary_stat": "spd",
        "equip_slot": "weapon"
    },
    "Ruestung": {
        "primary_stat": "def",
        "secondary_stat": "luk",
        "equip_slot": "armor"
    }
}

# =============================================
# Namens-Pools (prozedural)
# =============================================

WEAPON_NAMES = {
    "common": {
        "prefixes": ["Rostig", "Alt", "Schlicht", "Einfach", "Stumpf"],
        "bases": ["Schwert", "Dolch", "Axt", "Knueppel", "Speer", "Keule"]
    },
    "rare": {
        "prefixes": ["Fein", "Geschliffen", "Magisch", "Verzaubert", "Stark"],
        "bases": ["Klinge", "Saebel", "Streitaxt", "Stab", "Hammer", "Bogen"]
    },
    "legendary": {
        "prefixes": ["Episch", "Mythisch", "Goettlich", "Legendaer", "Uralte"],
        "bases": ["Flammenklinge", "Seelenschneider", "Schicksalsaxt",
                  "Donnerhammer", "Sturmbrecher", "Schattendolch"]
    }
}

ARMOR_NAMES = {
    "common": {
        "prefixes": ["Leder", "Flicken", "Duenn", "Einfach", "Grob"],
        "bases": ["Schild", "Helm", "Weste", "Stiefel", "Handschuhe", "Mantel"]
    },
    "rare": {
        "prefixes": ["Verstärkt", "Magisch", "Gehärtet", "Meister", "Ritter"],
        "bases": ["Brustpanzer", "Turmschild", "Kettenhemd",
                  "Eisenhelm", "Plattenhandschuhe", "Umhang"]
    },
    "legendary": {
        "prefixes": ["Episch", "Mythisch", "Goettlich", "Uralte", "Drachen"],
        "bases": ["Aegis", "Kronenhelm", "Seelenruestung",
                  "Schattenstiefel", "Titanenschild", "Nebelmantel"]
    }
}

# =============================================
# Biom-spezifische Loot-Tabellen (Saison)
# =============================================

BIOME_MODIFIERS = {
    "Eis": {
        "bonus_stat": "def",
        "bonus_amount": 2,
        "special_prefix": "Frost",
        "element": "ice"
    },
    "Feuer": {
        "bonus_stat": "atk",
        "bonus_amount": 2,
        "special_prefix": "Flammen",
        "element": "fire"
    },
    "Blitz": {
        "bonus_stat": "spd",
        "bonus_amount": 2,
        "special_prefix": "Blitz",
        "element": "lightning"
    },
    "Neutral": {
        "bonus_stat": None,
        "bonus_amount": 0,
        "special_prefix": None,
        "element": "neutral"
    }
}

# =============================================
# Shiny-Konstanten
# =============================================

SHINY_CHANCE = 8192          # 1:8192
SHINY_GOLD_MULTIPLIER = 10  # 10x Gold
SHINY_GUARANTEED_RARITY = "legendary"


# =============================================
# Loot Factory
# =============================================

class LootFactory:
    """
    Prozedurale Item-Generierung (Gacha-System).

    Generiert Items basierend auf:
    - Seltenheitswurf (LUK-beeinflusst)
    - Biom-Modifikatoren (Saison)
    - Boss-Bonus (besserer Loot)
    - Shiny-Chance (1:8192)
    """

    def __init__(self, seed: int = None):
        """
        Args:
            seed: Optionaler RNG-Seed (fuer deterministische Tests/P2P)
        """
        self._rng = random.Random(seed)

    def set_seed(self, seed: int):
        """RNG-Seed setzen (fuer P2P-Synchronisation)."""
        self._rng = random.Random(seed)

    def generate_deterministic_seed(self, player_name: str, opponent_name: str) -> int:
        """
        Deterministischen Seed aus Spielernamen + Timestamp generieren.
        Garantiert gleiches Ergebnis auf beiden Pis.

        Args:
            player_name: Eigener Name
            opponent_name: Gegner-Name

        Returns:
            int: Deterministischer Seed
        """
        # Sortiere Namen damit beide Pis den gleichen Seed bekommen
        names = sorted([player_name, opponent_name])
        timestamp = int(time.time())
        seed_str = f"{names[0]}:{names[1]}:{timestamp}"
        return int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16)

    # -----------------------------------------
    # Item-Generierung
    # -----------------------------------------

    def generate_item(
        self,
        player_luk: int = 10,
        floor: int = 1,
        biome: str = "Neutral",
        is_boss: bool = False,
        force_rarity: Optional[str] = None,
        force_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ein neues Item generieren.

        Args:
            player_luk: LUK-Attribut (beeinflusst Seltenheit)
            floor: Aktuelles Stockwerk (beeinflusst Item-Level)
            biome: Aktuelles Biom (Eis/Feuer/Blitz/Neutral)
            is_boss: True wenn Boss-Drop (bessere Chancen)
            force_rarity: Seltenheit erzwingen (fuer Tests/Shiny)
            force_type: Item-Typ erzwingen ("Waffe"/"Ruestung")

        Returns:
            Vollstaendiges Item-Dict
        """
        # 1. Seltenheit bestimmen
        rarity = force_rarity or self._roll_rarity(player_luk, is_boss)
        rarity_data = RARITIES[rarity]

        # 2. Item-Typ wuerfeln
        item_type = force_type or self._rng.choice(list(ITEM_TYPES.keys()))
        type_data = ITEM_TYPES[item_type]

        # 3. Stats generieren
        primary_mod = self._rng.randint(rarity_data["stat_min"], rarity_data["stat_max"])
        secondary_mod = self._rng.randint(
            max(1, rarity_data["stat_min"] // 2),
            max(2, rarity_data["stat_max"] // 2)
        )

        # 4. Biom-Bonus
        biome_data = BIOME_MODIFIERS.get(biome, BIOME_MODIFIERS["Neutral"])
        biome_bonus_stat = biome_data["bonus_stat"]
        biome_bonus_amount = biome_data["bonus_amount"]

        # 5. Stockwerk-Skalierung (Items werden mit Fortschritt staerker)
        floor_bonus = floor // 50  # +1 pro 50 Stockwerke
        primary_mod += floor_bonus
        secondary_mod += floor_bonus // 2

        # 6. ATK/DEF bestimmen basierend auf Item-Typ
        if item_type == "Waffe":
            atk_mod = primary_mod
            def_mod = secondary_mod
        else:
            atk_mod = secondary_mod
            def_mod = primary_mod

        # Biom-Bonus anwenden
        if biome_bonus_stat == "atk":
            atk_mod += biome_bonus_amount
        elif biome_bonus_stat == "def":
            def_mod += biome_bonus_amount

        # 7. Wert berechnen (fuer Shop: Kaufpreis = Wert x 2, Verkauf = Wert x 1)
        total_stats = atk_mod + def_mod
        base_value = total_stats * 5
        value = int(base_value * rarity_data["value_multiplier"])

        # 8. Name generieren
        name = self._generate_name(item_type, rarity, biome_data)

        # 9. Eindeutige ID
        item_id = self._generate_item_id()

        return {
            "id": item_id,
            "name": name,
            "type": item_type,
            "rarity": rarity,
            "rarity_de": rarity_data["name_de"],
            "rarity_color": rarity_data["color"],
            "equip_slot": type_data["equip_slot"],

            # Stats
            "atk_mod": atk_mod,
            "def_mod": def_mod,
            "total_stats": atk_mod + def_mod,

            # Schmiede (Spec Abschnitt 6D)
            "upgrade_level": 0,
            "upgrade_cap": rarity_data["upgrade_cap"],

            # Runen (Spec Abschnitt 6C: max 1 Rune pro Item)
            "rune_slot": None,       # None = leer, Dict = eingesetzte Rune

            # Wirtschaft (Spec Abschnitt 6E)
            "value": value,          # Basiswert
            "buy_price": value * 2,  # Kaufpreis = Wert x 2
            "sell_price": value,     # Verkaufspreis = Wert x 1

            # Meta
            "equipped": False,
            "floor_found": floor,
            "biome": biome,
            "element": biome_data["element"],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def generate_boss_loot(
        self,
        boss_tier: int = 1,
        player_luk: int = 10,
        floor: int = 10,
        biome: str = "Neutral"
    ) -> Dict[str, Any]:
        """
        Boss-Loot generieren (staerker als normal).

        Boss alle 10 SF, besserer Loot.
        Ab Tier 3: garantiert rare+

        Args:
            boss_tier: Boss-Tier (1-5)
            player_luk: LUK-Attribut
            floor: Stockwerk
            biome: Aktuelles Biom
        """
        # Ab Tier 3: mindestens Rare
        if boss_tier >= 3:
            force_rarity = "rare"
        else:
            force_rarity = None

        item = self.generate_item(
            player_luk=player_luk,
            floor=floor,
            biome=biome,
            is_boss=True,
            force_rarity=force_rarity
        )

        # Boss-Items haben hoehere Stats
        boss_bonus = boss_tier * 2
        item["atk_mod"] += boss_bonus
        item["def_mod"] += boss_bonus
        item["total_stats"] = item["atk_mod"] + item["def_mod"]
        item["name"] = f"Boss-{item['name']}"

        # Wert neu berechnen
        rarity_mult = RARITIES[item["rarity"]]["value_multiplier"]
        item["value"] = item["total_stats"] * 5 * rarity_mult
        item["buy_price"] = item["value"] * 2
        item["sell_price"] = item["value"]

        return item

    def generate_shiny_loot(
        self,
        player_luk: int = 10,
        floor: int = 1,
        biome: str = "Neutral"
    ) -> Dict[str, Any]:
        """
        Shiny-Loot generieren (1:8192, garantiert Legendaer).

        Shiny-Items haben:
        - Garantiert Legendaere Seltenheit
        - Maximale Stats fuer die Seltenheit
        - Speziellen Namenspraefix "Shiny"
        - 10x Gold-Wert

        Args:
            player_luk: LUK-Attribut
            floor: Stockwerk
            biome: Aktuelles Biom
        """
        item = self.generate_item(
            player_luk=player_luk,
            floor=floor,
            biome=biome,
            force_rarity=SHINY_GUARANTEED_RARITY
        )

        # Shiny-Bonus: maximale Stats
        legendary = RARITIES["legendary"]
        item["atk_mod"] = legendary["stat_max"] + (floor // 25)
        item["def_mod"] = legendary["stat_max"] + (floor // 25)
        item["total_stats"] = item["atk_mod"] + item["def_mod"]

        # Shiny-Markierung
        item["is_shiny"] = True
        item["name"] = f"Shiny {item['name']}"
        item["rarity_color"] = "yellow"  # Blinkend gelb im Terminal

        # 10x Wert
        item["value"] = item["total_stats"] * 5 * legendary["value_multiplier"] * SHINY_GOLD_MULTIPLIER
        item["buy_price"] = item["value"] * 2
        item["sell_price"] = item["value"]

        return item

    # -----------------------------------------
    # Shop-Items (Spec Abschnitt 6E)
    # -----------------------------------------

    def generate_shop_inventory(
        self,
        player_level: int = 1,
        player_floor: int = 1,
        biome: str = "Neutral"
    ) -> List[Dict[str, Any]]:
        """
        3 Shop-Items generieren (rotierendes Angebot).

        Shop-Regeln (Spec Abschnitt 6E):
        - 3 Items pro Rotation
        - Erneuert bei neuem Gegner-Kontakt
        - Kaufpreis = Wert x 2

        Args:
            player_level: Spieler-Level (beeinflusst Item-Qualitaet)
            player_floor: Aktuelles Stockwerk
            biome: Aktuelles Biom
        """
        items = []
        for _ in range(3):
            # Shop hat leicht bessere Items (LUK-Bonus simuliert)
            item = self.generate_item(
                player_luk=15,  # Shop hat "Basis-Glueck"
                floor=player_floor,
                biome=biome
            )
            items.append(item)
        return items

    # -----------------------------------------
    # Schmiede-Integration (Spec Abschnitt 6D)
    # -----------------------------------------

    @staticmethod
    def upgrade_item(item: Dict[str, Any], scrap_available: int) -> Dict[str, Any]:
        """
        Item in der Schmiede upgraden.

        Kosten: Upgrade-Level x 15 Scrap
        Effekt: +2 ATK oder +2 DEF pro Upgrade
        Name-Suffix: "Schwert" -> "Schwert +1" -> "Schwert +2"

        Args:
            item: Item-Dict
            scrap_available: Verfuegbarer Scrap

        Returns:
            Dict mit result, item, cost
        """
        current_level = item.get("upgrade_level", 0)
        upgrade_cap = item.get("upgrade_cap", 3)

        # Cap pruefen
        if current_level >= upgrade_cap:
            return {
                "result": "ERROR",
                "error": f"Max Upgrade-Level {upgrade_cap} erreicht.",
                "item": item,
                "cost": 0
            }

        # Kosten berechnen
        next_level = current_level + 1
        cost = next_level * 15

        if scrap_available < cost:
            return {
                "result": "ERROR",
                "error": f"Benoetigt {cost} Scrap, hast {scrap_available}.",
                "item": item,
                "cost": cost
            }

        # Upgrade anwenden
        item["upgrade_level"] = next_level

        # +2 auf Primaer-Stat
        if item.get("type") == "Waffe":
            item["atk_mod"] = item.get("atk_mod", 0) + 2
        else:
            item["def_mod"] = item.get("def_mod", 0) + 2

        item["total_stats"] = item.get("atk_mod", 0) + item.get("def_mod", 0)

        # Name aktualisieren (+1, +2, etc.)
        base_name = item["name"].split(" +")[0]
        item["name"] = f"{base_name} +{next_level}"

        # Wert neu berechnen
        rarity_mult = RARITIES.get(item.get("rarity", "common"), RARITIES["common"])["value_multiplier"]
        item["value"] = item["total_stats"] * 5 * rarity_mult
        item["buy_price"] = item["value"] * 2
        item["sell_price"] = item["value"]

        return {
            "result": "SUCCESS",
            "item": item,
            "cost": cost,
            "new_level": next_level
        }

    # -----------------------------------------
    # Runen-System (Spec Abschnitt 6C)
    # -----------------------------------------

    @staticmethod
    def attach_rune(item: Dict[str, Any], rune: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rune an ein Item anbringen (max 1 Rune pro Item).

        Args:
            item: Item-Dict
            rune: Rune-Dict mit name, effect, bonus

        Returns:
            Dict mit result, item
        """
        if item.get("rune_slot") is not None:
            return {
                "result": "ERROR",
                "error": "Item hat bereits eine Rune. Zuerst entfernen.",
                "item": item
            }

        item["rune_slot"] = rune

        # Runen-Bonus auf Stats
        if rune.get("bonus_atk"):
            item["atk_mod"] = item.get("atk_mod", 0) + rune["bonus_atk"]
        if rune.get("bonus_def"):
            item["def_mod"] = item.get("def_mod", 0) + rune["bonus_def"]
        item["total_stats"] = item.get("atk_mod", 0) + item.get("def_mod", 0)

        return {
            "result": "SUCCESS",
            "item": item,
            "rune": rune
        }

    @staticmethod
    def remove_rune(item: Dict[str, Any]) -> Dict[str, Any]:
        """Rune von einem Item entfernen."""
        rune = item.get("rune_slot")
        if rune is None:
            return {
                "result": "ERROR",
                "error": "Keine Rune vorhanden.",
                "item": item
            }

        # Bonus zuruecknehmen
        if rune.get("bonus_atk"):
            item["atk_mod"] = max(0, item.get("atk_mod", 0) - rune["bonus_atk"])
        if rune.get("bonus_def"):
            item["def_mod"] = max(0, item.get("def_mod", 0) - rune["bonus_def"])
        item["total_stats"] = item.get("atk_mod", 0) + item.get("def_mod", 0)

        item["rune_slot"] = None

        return {
            "result": "SUCCESS",
            "item": item,
            "removed_rune": rune
        }

    # -----------------------------------------
    # Drop-Chance + Shiny-Check
    # -----------------------------------------

    def roll_drop(
        self,
        player_luk: int = 10,
        floor: int = 1,
        biome: str = "Neutral",
        is_boss: bool = False,
        bonus_chance: float = 0.0
    ) -> Dict[str, Any]:
        """
        Vollstaendiger Drop-Wurf: Chance, Shiny, Item.

        Drop-Chance: 15% + (LUK x 0.5%) + Bonus
        Shiny: 1:8192 (10x Gold, garantiert Legendaer)

        Args:
            player_luk: LUK-Attribut
            floor: Aktuelles Stockwerk
            biome: Biom
            is_boss: Boss-Kampf
            bonus_chance: Zusaetzliche Chance

        Returns:
            Dict mit dropped (bool), is_shiny, item
        """
        # Drop-Chance berechnen
        base_chance = 0.15 + (player_luk * 0.005) + bonus_chance
        if is_boss:
            base_chance += 0.30  # Boss: +30% Drop-Chance
        base_chance = min(0.95, base_chance)  # Cap bei 95%

        # Wuerfeln
        if self._rng.random() >= base_chance:
            return {"dropped": False, "is_shiny": False, "item": None}

        # Shiny-Check
        is_shiny = self._rng.randint(1, SHINY_CHANCE) == 1

        if is_shiny:
            item = self.generate_shiny_loot(player_luk, floor, biome)
        elif is_boss:
            boss_tier = max(1, floor // 10)
            item = self.generate_boss_loot(boss_tier, player_luk, floor, biome)
        else:
            item = self.generate_item(player_luk, floor, biome)

        return {
            "dropped": True,
            "is_shiny": is_shiny,
            "item": item
        }

    # -----------------------------------------
    # Auto-Salvage (fuer Inventar-Integration)
    # -----------------------------------------

    @staticmethod
    def calculate_salvage_value(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Salvage-Wert eines Items berechnen.

        Items mit total_stats <= 5 werden als "schlecht" markiert
        und zum Auto-Salvage vorgeschlagen.

        Args:
            item: Item-Dict

        Returns:
            Dict mit gold, scrap, should_salvage
        """
        total = item.get("total_stats", 0)
        rarity = item.get("rarity", "common")

        # Gold zurueck (50% des Verkaufspreises)
        gold = max(1, item.get("sell_price", 5) // 2)

        # Scrap (basierend auf Seltenheit)
        scrap = 1
        if rarity == "rare":
            scrap = 3
        elif rarity == "legendary":
            scrap = 10

        # Schwaches Item? (Auto-Salvage-Vorschlag)
        should_salvage = total <= 5

        return {
            "gold": gold,
            "scrap": scrap,
            "total_stats": total,
            "should_salvage": should_salvage,
            "item_name": item.get("name", "Unbekannt")
        }

    # -----------------------------------------
    # Interne Hilfsfunktionen
    # -----------------------------------------

    def _roll_rarity(self, player_luk: int, is_boss: bool = False) -> str:
        """
        Seltenheit wuerfeln, beeinflusst durch LUK.

        Pro 10 LUK: +1% Legendaer, +2% Selten
        Boss: +5% Legendaer, +10% Selten
        """
        legendary_chance = RARITIES["legendary"]["weight"]
        rare_chance = RARITIES["rare"]["weight"]

        # LUK-Bonus
        legendary_chance += (player_luk // 10) * 0.01
        rare_chance += (player_luk // 10) * 0.02

        # Boss-Bonus
        if is_boss:
            legendary_chance += 0.05
            rare_chance += 0.10

        # Sicherstellen dass common nicht unter 10% faellt
        common_chance = max(0.10, 1.0 - legendary_chance - rare_chance)

        roll = self._rng.random()
        if roll < legendary_chance:
            return "legendary"
        elif roll < legendary_chance + rare_chance:
            return "rare"
        return "common"

    def _generate_name(
        self,
        item_type: str,
        rarity: str,
        biome_data: Dict
    ) -> str:
        """Prozeduralen Item-Namen generieren."""
        if item_type == "Waffe":
            pool = WEAPON_NAMES.get(rarity, WEAPON_NAMES["common"])
        else:
            pool = ARMOR_NAMES.get(rarity, ARMOR_NAMES["common"])

        prefix = self._rng.choice(pool["prefixes"])
        base = self._rng.choice(pool["bases"])

        # Biom-Prefix hinzufuegen (wenn vorhanden)
        biome_prefix = biome_data.get("special_prefix")
        if biome_prefix and self._rng.random() < 0.40:  # 40% Chance
            return f"{biome_prefix}-{base}"

        # Grammatik-Anpassung (deutsch)
        if prefix.endswith("e"):
            return f"{prefix} {base}"
        elif prefix.endswith("h") or prefix.endswith("k"):
            return f"{prefix}es {base}"
        else:
            return f"{prefix}er {base}"

    def _generate_item_id(self) -> str:
        """Eindeutige Item-ID generieren."""
        timestamp = int(time.time() * 1000)
        rand_part = self._rng.randint(1000, 9999)
        return f"item_{timestamp}_{rand_part}"


# =============================================
# Standalone-Test
# =============================================
if __name__ == "__main__":
    factory = LootFactory(seed=42)

    print("=== ITEM-GENERIERUNG ===")
    for rarity in ["common", "rare", "legendary"]:
        item = factory.generate_item(player_luk=15, floor=50, force_rarity=rarity)
        print(f"  [{rarity:>10}] {item['name']:30s} "
              f"ATK:{item['atk_mod']:>3} DEF:{item['def_mod']:>3} "
              f"Wert:{item['value']:>5}g ({item['type']})")

    print("\n=== BIOM-LOOT ===")
    for biome in ["Eis", "Feuer", "Blitz"]:
        item = factory.generate_item(player_luk=20, floor=100, biome=biome)
        print(f"  [{biome:>6}] {item['name']:30s} "
              f"ATK:{item['atk_mod']:>3} DEF:{item['def_mod']:>3} "
              f"Element:{item['element']}")

    print("\n=== BOSS-LOOT ===")
    for tier in [1, 3, 5]:
        item = factory.generate_boss_loot(boss_tier=tier, player_luk=20, floor=tier * 10)
        print(f"  [Tier {tier}] {item['name']:30s} "
              f"ATK:{item['atk_mod']:>3} DEF:{item['def_mod']:>3} "
              f"({item['rarity']})")

    print("\n=== SHINY-LOOT ===")
    shiny = factory.generate_shiny_loot(player_luk=25, floor=200)
    print(f"  {shiny['name']:30s} ATK:{shiny['atk_mod']:>3} DEF:{shiny['def_mod']:>3} "
          f"Wert:{shiny['value']:>6}g")

    print("\n=== SCHMIEDE-UPGRADE ===")
    item = factory.generate_item(force_rarity="rare", force_type="Waffe")
    print(f"  Vorher:  {item['name']:30s} ATK:{item['atk_mod']:>3}")
    for scrap in [100, 100, 100, 100, 100]:
        result = LootFactory.upgrade_item(item, scrap)
        if result["result"] == "SUCCESS":
            print(f"  +{result['new_level']:>1}:      {item['name']:30s} "
                  f"ATK:{item['atk_mod']:>3} (Kosten: {result['cost']} Scrap)")
        else:
            print(f"  FEHLER: {result['error']}")

    print("\n=== RUNEN-SYSTEM ===")
    item = factory.generate_item(force_rarity="rare")
    rune = {"name": "Feuer-Rune", "bonus_atk": 5, "bonus_def": 0}
    print(f"  Vorher:  ATK:{item['atk_mod']:>3} DEF:{item['def_mod']:>3}")
    LootFactory.attach_rune(item, rune)
    print(f"  +Rune:   ATK:{item['atk_mod']:>3} DEF:{item['def_mod']:>3} (Feuer-Rune)")
    LootFactory.remove_rune(item)
    print(f"  -Rune:   ATK:{item['atk_mod']:>3} DEF:{item['def_mod']:>3}")

    print("\n=== DROP-SIMULATION (100 Wuerfe, LUK=20) ===")
    drops = {"common": 0, "rare": 0, "legendary": 0, "none": 0, "shiny": 0}
    for _ in range(100):
        result = factory.roll_drop(player_luk=20, floor=50)
        if result["dropped"]:
            if result["is_shiny"]:
                drops["shiny"] += 1
            else:
                drops[result["item"]["rarity"]] += 1
        else:
            drops["none"] += 1
    print(f"  Kein Drop: {drops['none']}x | "
          f"Common: {drops['common']}x | Rare: {drops['rare']}x | "
          f"Legendary: {drops['legendary']}x | Shiny: {drops['shiny']}x")

    print("\n=== SALVAGE-CHECK ===")
    weak_item = factory.generate_item(force_rarity="common")
    weak_item["atk_mod"] = 2
    weak_item["def_mod"] = 2
    weak_item["total_stats"] = 4
    salvage = LootFactory.calculate_salvage_value(weak_item)
    print(f"  {weak_item['name']}: Stats={salvage['total_stats']} -> "
          f"Salvage={salvage['should_salvage']} ({salvage['gold']}g, {salvage['scrap']} Scrap)")
