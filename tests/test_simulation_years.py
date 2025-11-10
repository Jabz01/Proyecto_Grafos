# tests/test_simulation_years.py
import pytest
from src.sim.burro_state import BurroState
from src.sim.travel import simulate_travel
from src.sim.visit import simulate_visit

DEFAULT_RULES = {
    "timeAndLife": {"distanceLyToYearsFactor": 0.05, "useDistanceAsYearsOfLifeLoss": True, "maxFractionOfStayForEating": 0.5},
    "energy": {
        "energyConsumptionPerLyPercent": 0.5,
        "energyLossPerInvestigationHourPercent": 0.2,  # key used as fallback name; treated as per-year in visit if not overridden
        "energyGainPerKgByHealthPercent": {"Excellent":5,"Good":3,"Bad":2,"NearDeath":1,"Dead":0},
        "applyEnergyCap100": True
    },
    "feeding": {"eatOnlyIfEnergyBelowPercent": 50, "minKgPerEat": 0.1}
}

def test_simulate_travel_reduces_life_and_energy_years():
    s = BurroState(node=1, life_years_left=10.0, health="Good", energy_pct=80.0, grass_kg=5.0)
    edge = {"distanceLy": 20.0}
    new_s, events = simulate_travel(s, edge, DEFAULT_RULES)
    assert pytest.approx(new_s.life_years_left, rel=1e-6) == 9.0
    assert pytest.approx(new_s.energy_pct, rel=1e-6) == 70.0
    assert events["years_loss"] == -1.0

def test_simulate_visit_eating_and_investigation_and_hypergiant_years():
    s = BurroState(node=2, life_years_left=5.0, health="Excellent", energy_pct=40.0, grass_kg=2.0)
    # star: 1 year per kg, investigation 4 years (1..5 range ok)
    star = {"time_per_kg_years": 1.0, "investigation_years": 4.0, "hypergiant": True}
    new_s, events = simulate_visit(s, star, DEFAULT_RULES)
    # eating: max eat years = 4 * 0.5 = 2y -> max_kg_by_time = 2kg; grass stock 2kg => eat 2kg -> +10% -> 50%
    # then hypergiant adds +50 -> min(100) => 100
    assert new_s.energy_pct <= 100.0
    assert "hypergiant_used" in events
    assert events["ate_kg"] == pytest.approx(2.0, rel=1e-6)

def test_death_on_zero_life_after_travel_years():
    s = BurroState(node=1, life_years_left=0.5, health="Good", energy_pct=50.0, grass_kg=1.0)
    edge = {"distanceLy": 20.0}
    new_s, events = simulate_travel(s, edge, DEFAULT_RULES)
    assert new_s.health == "Dead"
    assert events.get("death", False) is True