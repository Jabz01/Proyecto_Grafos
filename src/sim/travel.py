# src/sim/travel.py
from typing import Dict, Tuple, List
from src.sim.burro_state import BurroState

def simulate_travel(state: BurroState, edge_attrs: Dict, rules: Dict) -> Tuple[BurroState, List[str]]:
    """
    Simula el viaje entre nodos usando edge_attrs que deben incluir 'distanceLy' (o 'yearsCost').
    Retorna (new_state, events_list).

    Effects:
      - Resta life_years_left = distanceLy * distanceLyToYearsFactor (si useDistanceAsYearsOfLifeLoss True)
      - Consume energy en base a rules.energy.energyConsumptionPerLyPercent por ly
    """
    s = state.clone()
    events: List[str] = []

    distance_ly = float(edge_attrs.get("distanceLy", edge_attrs.get("ly", 0.0)))
    taf = rules.get("timeAndLife", {}).get("distanceLyToYearsFactor", 0.05)
    use_dist = rules.get("timeAndLife", {}).get("useDistanceAsYearsOfLifeLoss", True)

    # calcular pérdida de años de vida
    years_loss = distance_ly * taf if use_dist else float(edge_attrs.get("yearsCost", 0.0))
    s.apply_life_delta(-years_loss)
    events.append(f"Travelled {distance_ly:.3f} ly, life {(-years_loss):+.6f}y")
    s.add_log(f"Travelled {distance_ly:.3f} ly, life {(-years_loss):+.6f}y")

    # consumo de energía por ly
    eco_pct_per_ly = rules.get("energy", {}).get("energyConsumptionPerLyPercent", 0.0)
    energy_loss = distance_ly * eco_pct_per_ly
    s.apply_energy_delta(-energy_loss, rules)
    events.append(f"Energy {-energy_loss:.4f}% for travel")
    s.add_log(f"Energy {-energy_loss:.4f}% for travel")

    # marcar muerte si aplica
    if getattr(s, "life_years_left", 0.0) <= 0.0:
        s.health = "Dead"
        events.append("DIED_DURING_TRAVEL")
        s.add_log("Death during travel")

    return s, events