#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - Engine-Paritaet und Determinismus

Diese Tests existieren wegen des Bugs vom September 2026: PVE
(engine/battle_engine.py) und PVP (deterministic_battle.py) rechneten mit
zwei verschiedenen Schadensformeln. Die PVE-Engine hatte bereits die
korrigierte V2-Formel, die PVP-Engine noch die alte, bei der ATK mit dem
Level skalierte, DEF aber nicht.

Ein einziger Vergleichstest haette das sofort gezeigt.
"""

import random

import pytest

from deterministic_battle import DeterministicBattle
from engine.battle_engine import BattleEngine


STAT_CASES = [
    (25, 40),   # Krieger-artig
    (25, 15),   # Schurke-artig
    (45, 10),   # Magier-artig
    (60, 25),
    (95, 5),    # Extrem-Spezialisierung
]
LEVELS = [1, 2, 5, 10, 20, 30, 50]


class TestFormulaParity:
    """Beide Engines muessen bei gleichen Eingaben gleich rechnen."""

    @pytest.mark.parametrize("level", LEVELS)
    @pytest.mark.parametrize("atk,dfs", STAT_CASES)
    def test_real_damage_methods_match(self, level, atk, dfs):
        """
        Ruft die ECHTEN Methoden beider Engines auf, statt die Formel im
        Test nachzubauen. Ein nachgerechneter Test wuerde eine divergierende
        Implementierung nicht bemerken — genau das war der Bug.

        Varianz und Krit werden neutralisiert, indem beide Engines einen
        RNG bekommen, der feste Werte liefert (variance=100, kein Krit).
        """

        class FixedRNG:
            """randint(90, 110) -> 100 (neutrale Varianz),
               randint(1, 1000) -> 1000 (nie Krit, da > luk*5)."""

            @staticmethod
            def randint(a, b):
                return 100 if (a, b) == (90, 110) else b

        attacker = {"total_atk": atk, "total_luk": 0, "type": "Stein",
                    "level": level}
        defender = {"total_def": dfs, "type": "Stein"}

        engine_result = BattleEngine().calculate_damage(
            attacker, defender, rng=FixedRNG()
        )
        engine_damage = engine_result["damage"]

        battle = DeterministicBattle(seed=1234)
        battle._rng = FixedRNG()
        battle_damage = battle._calc_damage(
            atk=atk, defender_def=dfs, level=level, type_factor=100, luk=0
        )

        assert engine_damage == battle_damage, (
            f"PVE und PVP rechnen verschieden: "
            f"ATK={atk} DEF={dfs} Lv={level} -> "
            f"PVE {engine_damage} vs PVP {battle_damage}"
        )

    def test_constants_are_identical(self):
        engine = BattleEngine()
        battle = DeterministicBattle(seed=1)
        assert engine.MIN_DAMAGE == battle.MIN_DAMAGE
        assert engine.LEVEL_AMP_PER_LEVEL == battle.LEVEL_AMP_PER_LEVEL
        assert engine.DEFENSE_SOFTCAP == battle.DEFENSE_SOFTCAP
        assert engine.HP_PER_LEVEL == battle.HP_PER_LEVEL

    @pytest.mark.parametrize("level", [1, 10, 30])
    @pytest.mark.parametrize("dfs", [0, 10, 25, 40, 80])
    def test_max_hp_matches(self, level, dfs):
        engine_hp = BattleEngine.calculate_max_hp(level, dfs)
        battle_hp = DeterministicBattle._get_effective_hp(
            {"level": level, "total_def": dfs}
        )
        assert engine_hp == battle_hp


class TestDefenseCurve:
    """Verteidigung muss asymptotisch bleiben - nie 0 %, nie 100 %."""

    @pytest.mark.parametrize("dfs", [0, 1, 10, 40, 100, 500, 9999])
    def test_never_reaches_full_immunity(self, dfs):
        pct = dfs * 100 // (dfs + BattleEngine.DEFENSE_SOFTCAP)
        assert 0 <= pct < 100

    def test_diminishing_returns(self):
        """Jeder weitere DEF-Punkt bringt weniger als der vorherige."""
        def pct(d):
            return d * 100 / (d + BattleEngine.DEFENSE_SOFTCAP)

        gain_low = pct(20) - pct(10)
        gain_high = pct(110) - pct(100)
        assert gain_high < gain_low

    def test_defense_stays_relevant_at_high_level(self):
        """
        Kernregression: frueher war DEF ab ca. Level 8 wirkungslos, weil
        ATK mit dem Level skalierte, der DEF-Abzug aber konstant blieb.
        """
        atk, level = 45, 50
        amp = 100 + (level - 1) * BattleEngine.LEVEL_AMP_PER_LEVEL
        raw = atk * amp // 100

        dmg_no_def = raw * (100 - (0 * 100 // (0 + 50))) // 100
        dmg_tank = raw * (100 - (80 * 100 // (80 + 50))) // 100

        # Ein Tank muss auch auf Level 50 spuerbar weniger Schaden nehmen
        assert dmg_tank < dmg_no_def * 0.5


class TestDeterminism:
    """
    Kernversprechen des P2P-Designs: derselbe Seed erzeugt auf jedem
    Geraet denselben Kampfverlauf. Ohne das ist PVP wertlos.
    """

    PLAYER_A = {
        "name": "A", "type": "Stein", "level": 10,
        "total_atk": 25, "total_def": 40, "total_spd": 20, "total_luk": 15,
    }
    PLAYER_B = {
        "name": "B", "type": "Papier", "level": 10,
        "total_atk": 45, "total_def": 10, "total_spd": 20, "total_luk": 25,
    }

    def test_same_seed_same_result(self):
        r1 = DeterministicBattle(seed=42).run_pvp(self.PLAYER_A, self.PLAYER_B)
        r2 = DeterministicBattle(seed=42).run_pvp(self.PLAYER_A, self.PLAYER_B)
        assert r1["winner"] == r2["winner"]
        assert r1["rounds"] == r2["rounds"]
        assert r1["log"] == r2["log"]

    def test_different_seed_can_differ(self):
        results = {
            DeterministicBattle(seed=s).run_pvp(self.PLAYER_A, self.PLAYER_B)["rounds"]
            for s in range(30)
        }
        assert len(results) > 1, "Seed hat keinerlei Einfluss - RNG kaputt?"

    def test_no_float_in_damage_log(self):
        """
        Integer-only ist Voraussetzung fuer Konsistenz ueber Geraete hinweg
        (Float-Rundung ist plattformabhaengig).
        """
        result = DeterministicBattle(seed=7).run_pvp(self.PLAYER_A, self.PLAYER_B)
        for entry in result["log"]:
            assert isinstance(entry["damage"], int)
            assert isinstance(entry["a_hp"], int)
            assert isinstance(entry["b_hp"], int)

    def test_battle_terminates(self):
        """Kein Kampf darf ueber MAX_ROUNDS hinauslaufen."""
        for seed in range(50):
            result = DeterministicBattle(seed=seed).run_pvp(
                self.PLAYER_A, self.PLAYER_B
            )
            assert result["rounds"] <= DeterministicBattle.MAX_ROUNDS


class TestClassBalance:
    """
    Regressionsschutz fuer das Balancing. Keine Klasse darf das Feld
    dominieren - Faustregel: unter 60 % Siegquote.
    """

    CLASSES = {
        "Krieger": {"type": "Stein", "total_atk": 25, "total_def": 40,
                    "total_spd": 20, "total_luk": 15},
        "Schurke": {"type": "Schere", "total_atk": 25, "total_def": 15,
                    "total_spd": 40, "total_luk": 20},
        "Magier": {"type": "Papier", "total_atk": 45, "total_def": 10,
                   "total_spd": 20, "total_luk": 25},
    }

    @pytest.mark.parametrize("level", [1, 10, 30, 50])
    def test_no_class_dominates(self, level):
        import itertools

        wins = {c: 0 for c in self.CLASSES}
        games = {c: 0 for c in self.CLASSES}

        for na, nb in itertools.permutations(self.CLASSES, 2):
            pa = dict(self.CLASSES[na], name=na, level=level)
            pb = dict(self.CLASSES[nb], name=nb, level=level)
            for seed in range(120):
                res = DeterministicBattle(seed).run_pvp(pa, pb)
                games[na] += 1
                games[nb] += 1
                winner = res.get("winner")
                if winner in ("A", na):
                    wins[na] += 1
                elif winner in ("B", nb):
                    wins[nb] += 1

        rates = {c: wins[c] * 100 // games[c] for c in self.CLASSES}
        for cls, rate in rates.items():
            assert 35 <= rate <= 65, f"Level {level}: {cls} bei {rate}% ({rates})"

    def test_battles_last_multiple_rounds(self):
        """
        Regression: mit der alten Formel endeten Kaempfe ab Level 20 nach
        einer einzigen Runde - der Gewinner stand allein ueber SPD fest.
        """
        pa = dict(self.CLASSES["Krieger"], name="A", level=30)
        pb = dict(self.CLASSES["Magier"], name="B", level=30)
        rounds = [
            DeterministicBattle(s).run_pvp(pa, pb)["rounds"] for s in range(60)
        ]
        assert sum(rounds) / len(rounds) >= 3.0
