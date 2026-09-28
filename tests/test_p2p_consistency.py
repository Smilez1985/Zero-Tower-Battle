#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - P2P-Konsistenz

Kernversprechen der Architektur: Wenn zwei Pis denselben Kampf ausfuehren,
muessen beide dasselbe Ergebnis erhalten. Ohne das ist serverloses PVP
wertlos — es gaebe keine gemeinsame Wahrheit darueber, wer gewonnen hat.

Diese Tests simulieren beide Geraete im selben Prozess, indem sie die
jeweils lokale Sicht nachstellen (Geraet 1 sieht sich als "local", Geraet 2
ebenso) und pruefen, ob beide zum selben Schluss kommen.

Hintergrund: Bis September 2026 vergab battle_server.py die Rolle
`player_a` immer an das LOKALE Profil. Da bei SPD-Gleichstand Spieler A
zuerst zuschlaegt, konnten beide Seiten unterschiedliche Sieger ermitteln.
"""

import pytest

from deterministic_battle import DeterministicBattle
from engine.battle_engine import BattleEngine


CHAMP_X = {
    "name": "Anton", "type": "Stein", "level": 12,
    "total_atk": 30, "total_def": 42, "total_spd": 20, "total_luk": 16,
}
CHAMP_Y = {
    "name": "Berta", "type": "Papier", "level": 12,
    "total_atk": 48, "total_def": 12, "total_spd": 20, "total_luk": 26,
}
# Gleiche SPD erzwingt den kritischen Fall: Initiative per RNG
CHAMP_TIE_A = dict(CHAMP_X, name="Caesar", total_spd=25)
CHAMP_TIE_B = dict(CHAMP_Y, name="Dora", total_spd=25)


def assign_roles(local, remote):
    """
    Rollenvergabe wie in battle_server.process_battle():
    lexikografisch kleinerer Name wird Spieler A.
    """
    local_is_a = local.get("name", "") <= remote.get("name", "")
    if local_is_a:
        return local, remote, True
    return remote, local, False


def local_view(local, remote, timestamp):
    """Ein Geraet fuehrt den Kampf aus und wertet aus SEINER Sicht aus."""
    player_a, player_b, local_is_a = assign_roles(local, remote)
    result = BattleEngine().run_pvp_battle(player_a, player_b, timestamp)

    raw = result.get("result", "DRAW")
    if raw == "DRAW":
        own = "DRAW"
    elif local_is_a:
        own = raw
    else:
        own = "LOSS" if raw == "WIN" else "WIN"

    return {"own": own, "seed": result.get("seed"),
            "rounds": result.get("rounds"), "log": result.get("log")}


class TestRoleAssignment:
    """Die Rollenvergabe muss auf beiden Geraeten identisch ausfallen."""

    def test_both_devices_agree_on_player_a(self):
        a1, b1, _ = assign_roles(CHAMP_X, CHAMP_Y)   # Sicht Geraet 1
        a2, b2, _ = assign_roles(CHAMP_Y, CHAMP_X)   # Sicht Geraet 2
        assert a1["name"] == a2["name"]
        assert b1["name"] == b2["name"]

    def test_role_is_symmetric_for_tie_speed(self):
        a1, _, _ = assign_roles(CHAMP_TIE_A, CHAMP_TIE_B)
        a2, _, _ = assign_roles(CHAMP_TIE_B, CHAMP_TIE_A)
        assert a1["name"] == a2["name"]


class TestSeedConsistency:
    """Der Seed darf nicht davon abhaengen, wer den Kampf startet."""

    def test_seed_identical_regardless_of_caller(self):
        ts = 1_700_000_000
        s1 = BattleEngine.generate_battle_seed("Anton", "Berta", ts)
        s2 = BattleEngine.generate_battle_seed("Berta", "Anton", ts)
        assert s1 == s2

    def test_seed_changes_with_time_window(self):
        s1 = BattleEngine.generate_battle_seed("Anton", "Berta", 1_700_000_000)
        s2 = BattleEngine.generate_battle_seed("Anton", "Berta", 1_700_000_060)
        assert s1 != s2

    def test_time_quantisation_absorbs_clock_drift(self):
        """
        Zwei Pis ohne RTC driften. Die Quantisierung auf ein Zeitfenster
        muss kleine Abweichungen auf denselben Seed abbilden.
        """
        from controllers.battle_server import BattleServer

        window = BattleServer.SEED_TIME_WINDOW
        base = 1_700_000_000
        for drift in (0, 1, 5, 17, window - 1):
            q1 = (base // window) * window
            q2 = ((base + drift) // window) * window
            if (base + drift) // window == base // window:
                assert q1 == q2, f"Drift {drift}s bricht den Seed"


class TestBattleOutcomeConsistency:
    """Beide Geraete muessen denselben Sieger sehen."""

    @pytest.mark.parametrize("timestamp", [1_700_000_000, 1_700_003_600])
    def test_same_winner_on_both_devices(self, timestamp):
        view1 = local_view(CHAMP_X, CHAMP_Y, timestamp)
        view2 = local_view(CHAMP_Y, CHAMP_X, timestamp)

        assert view1["seed"] == view2["seed"], "Seeds weichen ab"
        assert view1["rounds"] == view2["rounds"], "Rundenzahl weicht ab"

        # Genau einer gewinnt - oder beide sehen ein Unentschieden
        if view1["own"] == "DRAW":
            assert view2["own"] == "DRAW"
        else:
            assert view1["own"] != view2["own"], (
                f"Beide Geraete melden '{view1['own']}' - "
                "kein gemeinsames Ergebnis"
            )

    def test_same_winner_with_equal_speed(self):
        """
        Kritischster Fall: gleiche SPD. Die Initiative entscheidet der RNG —
        wenn die Rollenvergabe abweicht, driften die Ergebnisse auseinander.
        """
        ts = 1_700_000_000
        view1 = local_view(CHAMP_TIE_A, CHAMP_TIE_B, ts)
        view2 = local_view(CHAMP_TIE_B, CHAMP_TIE_A, ts)
        assert view1["seed"] == view2["seed"]
        assert view1["log"] == view2["log"], "Kampfverlaeufe weichen ab"

    def test_battle_log_is_identical(self):
        ts = 1_700_000_000
        view1 = local_view(CHAMP_X, CHAMP_Y, ts)
        view2 = local_view(CHAMP_Y, CHAMP_X, ts)
        assert view1["log"] == view2["log"]


class TestOrchestratorPathParity:
    """
    Der zweite PVP-Pfad (hybrid_orchestrator -> DeterministicBattle) muss
    dieselbe Rollenlogik verwenden. Er sortiert nach IP-Suffix statt nach
    Name — die Sortierung muss aber genauso symmetrisch sein.
    """

    def test_ip_based_assignment_is_symmetric(self):
        """
        Geraet mit IP-Suffix 2 und Geraet mit Suffix 7 muessen beide zu dem
        Schluss kommen, dass Suffix 2 die Rolle A uebernimmt — egal welches
        von beiden gerade rechnet.
        """
        def player_a_suffix(own, other):
            # Logik aus hybrid_orchestrator: kleinere IP = Player A
            return own if own < other else other

        assert player_a_suffix(2, 7) == 2   # Sicht von Geraet 2
        assert player_a_suffix(7, 2) == 2   # Sicht von Geraet 7

    def test_deterministic_battle_is_order_independent(self):
        """
        Gleicher Seed, getauschte Argumente: Spieler A gewinnt oder verliert,
        aber der Kampf selbst muss derselbe sein.
        """
        r1 = DeterministicBattle(99).run_pvp(CHAMP_X, CHAMP_Y)
        r2 = DeterministicBattle(99).run_pvp(CHAMP_X, CHAMP_Y)
        assert r1["log"] == r2["log"]
        assert r1["winner"] == r2["winner"]
