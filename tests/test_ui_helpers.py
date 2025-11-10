# tests/test_ui_helpers.py
import pytest
from src.gui.ui_helpers import build_star_tooltip

def make_rules():
    return {
        "energy": {"energyLossPerInvestigationYearPercent": 1.0, "energyGainPerKgByHealthPercent": {"Excellent":5, "Good":3}},
        "feeding": {"maxKgConsumablePerVisitKg": None},
        "hypergiant": {"grassDuplicateMultiplier": 2, "energyRechargeMultiplier": 1.5},
        "timeAndLife": {}
    }

def test_build_star_tooltip_basic():
    star = {"id": 42, "investigation_years": 2.0, "time_per_kg_years": 1.5, "grass_kg": 4.0}
    rules = make_rules()
    ctx = build_star_tooltip(star, rules, None)
    assert ctx["id"] == 42
    assert ctx["investigation_years"] == pytest.approx(2.0)
    assert ctx["time_per_kg_years"] == pytest.approx(1.5)
    assert ctx["energy_consumption_per_visit_pct"] == pytest.approx(2.0)  # 2 years * 1% per year
    assert "máx por visita" in ctx["feeding_max_kg_text"] or "ilimitado" in ctx["feeding_max_kg_text"]
    assert ctx["grass_text"].startswith("pasto:")
    # when no burro_state, recovery is None
    assert ctx["recovery_per_1kg_pct"] is None

def test_build_star_tooltip_with_burro():
    class Dummy:
        health = "Good"
    star = {"id": 1, "investigation_years": 1.0, "time_per_kg_years": 2.0}
    rules = make_rules()
    ctx = build_star_tooltip(star, rules, Dummy())
    assert ctx["recovery_per_1kg_pct"] == pytest.approx(3.0)
    assert ctx["recovery_per_1kg_pct_s"] == "3.00"