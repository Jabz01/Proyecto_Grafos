# tests/test_parser_defaults.py
import pytest
from src.utils.parser import BuildParserOutputFromJson

def make_minimal_data(seed=42):
    return {
        "meta": {"simulationSeed": seed},
        "stars": [
            {"id": 1, "coordinates": {"x": 0, "y": 0}},
            {"id": 2, "coordinates": {"x": 1, "y": 0}},
            {"id": 3, "coordinates": {"x": 0, "y": 1}}
        ],
        "edges": [{"u":1,"v":2}, {"u":2,"v":3}]
    }

def test_parser_generates_star_defaults_and_is_deterministic():
    data = make_minimal_data(seed=12345)
    output1, _, _ = BuildParserOutputFromJson(data)
    stars = output1["stars"]

    print("\nValores generados por estrella (con semilla 12345):")
    for s in stars:
        print(f"Estrella {s['id']}:")
        print(f"  investigation_years         = {s['investigation_years']}")
        print(f"  time_per_kg_years           = {s['time_per_kg_years']}")
        print(f"  invest_energy_per_year_pct = {s['invest_energy_per_year_pct']}")
        print()

    # Validaciones
    for s in stars:
        assert 1.0 <= s["investigation_years"] <= 5.0
        assert 1.0 <= s["time_per_kg_years"] <= 5.0
        assert 0.05 <= s["invest_energy_per_year_pct"] <= 0.5