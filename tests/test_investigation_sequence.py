# tests/test_investigation_sequence.py
import pytest
from copy import deepcopy
import random
from src.sim.burro_state import BurroState
from src.sim.visit import simulate_visit

STAR_ATTRS = {
    "id": 100,
    "investigation_years": 2.0,
    "time_per_kg_years": 1.0,
}

BASE_RULES = {
    "timeAndLife": {
        "distanceLyToYearsFactor": 0.05,
        "useDistanceAsYearsOfLifeLoss": True,
        "maxFractionOfStayForEating": 0.5,
        "investigation": {
            "p_illness": 0.4,
            "p_success": 0.4,
            "illness_life_loss_range": [1.0, 3.0],
            "success_life_gain_range": [0.0, 1.0],
            "success_improve_health_p": 0.5
        }
    },
    "energy": {
        "maxEnergyPercent": 100,
        "energyConsumptionPerLyPercent": 1.0,
        "energyLossPerInvestigationYearPercent": 1.0,
        "energyGainPerKgByHealthPercent": {
            "Excellent": 5,
            "Good": 3,
            "Bad": 2,
            "NearDeath": 1,
            "Dead": 0
        },
        "applyEnergyCap100": True
    },
    "feeding": {
        "eatOnlyIfEnergyBelowPercent": 50,
        "minKgPerEat": 0.1,
        "maxKgConsumablePerVisitKg": None
    }
}

HEALTH_ORDER = ["Excellent", "Good", "Bad", "NearDeath", "Dead"]

def health_index(h):
    try:
        return HEALTH_ORDER.index(h)
    except ValueError:
        return len(HEALTH_ORDER)

def make_initial_state(seed=None):
    st = BurroState(
        node=100,
        life_years_left=100.0,
        health="Good",
        energy_pct=100.0,
        grass_kg=5.0,
        age_years=0.0
    )
    if seed is not None:
        st.rng = random.Random(seed)
    return st

def test_multiple_investigations_print_events_and_health_improvements():
    rules = deepcopy(BASE_RULES)

    # Inyectar seed en el estado para determinismo robusto entre clones
    state = make_initial_state(seed=12345)
    visits = 8

    print("\n=== Investigation sequence (per visit) ===")
    s = state
    improved_count = 0
    for i in range(visits):
        s_before = s
        s_after, events = simulate_visit(s_before, STAR_ATTRS, rules)
        s = s_after

        ev = getattr(s, "last_event", None)
        if ev is not None:
            outcome = ev.get("outcome")
            life_delta = ev.get("life_delta", 0.0)
            hf = ev.get("health_from", s.health)
            ht = ev.get("health_to", s.health)
            e_delta = ev.get("energy_delta", 0.0)
            note = ev.get("note", "")

            # detectar mejora con índices (menor índice = mejor salud)
            improved = ""
            if ev.get("outcome") == "successful" and hf != ht:
                if health_index(ht) < health_index(hf):
                    improved = "(improved)"
                    improved_count += 1

            print(f"Visit {i+1:02d}: outcome={outcome:10s} | life_delta={life_delta:+.2f}y | health {hf}->{ht} {improved} | energy_delta={e_delta:+.3f}% {note}")
        else:
            txt = "; ".join(events) if events else "(no events)"
            print(f"Visit {i+1:02d}: {txt}")

    # Asserts básicos
    final = s
    assert len(final.event_log) >= visits
    expected_max_energy = 100.0 - (STAR_ATTRS["investigation_years"] * rules["energy"]["energyLossPerInvestigationYearPercent"] * visits)
    assert final.energy_pct <= 100.0 and final.energy_pct <= expected_max_energy + 1e-6
    assert 0.0 <= final.life_years_left <= 100.0
    for ev in final.event_log[:visits]:
        assert ev["type"] == "investigation"
        assert ev["outcome"] in ("illness", "neutral", "successful")
        assert "life_delta" in ev
        assert "health_from" in ev and "health_to" in ev
        assert "energy_delta" in ev

    # Con seed fijo e inyección RNG esperamos al menos una mejora en 8 visitas
    assert improved_count >= 1