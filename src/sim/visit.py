# src/sim/visit.py
from typing import Dict, Tuple, Optional, List
from src.sim.burro_state import BurroState

def simulate_visit(state: BurroState, star_attrs: Dict, rules: Dict, user_overrides: Optional[Dict]=None) -> Tuple[BurroState, List[str]]:
    """
    Simula la llegada y estancia en una estrella usando años como unidad para tiempos.
    star_attrs puede contener:
      - time_per_kg_years: float (años para consumir 1 kg)
      - investigation_years: años asignados para investigación
      - invest_energy_per_year_pct: energy % loss por año de investigación
      - effects: dict con 'life_delta_years' y 'health_delta'
      - hypergiant: bool
      - max_kg_consumable_per_visit_kg: optional cap
    Returns (new_state, events_list)
    """
    s = state.clone()
    events: List[str] = []
    uo = user_overrides or {}

    # años destinados a investigación en esta visita
    inv_years = float(uo.get("investigation_years", star_attrs.get("investigation_years", 0.0)))

    # máximo de años permitidos para comer
    max_frac = rules.get("timeAndLife", {}).get("maxFractionOfStayForEating", 0.5)
    time_per_kg_years = float(star_attrs.get("time_per_kg_years", star_attrs.get("time_to_consume_kg_years", 1.0)))
    max_eat_years = inv_years * max_frac
    max_kg_by_time = (max_eat_years / time_per_kg_years) if time_per_kg_years > 0 else float('inf')

    # reglas de alimentación
    eat_threshold = rules.get("feeding", {}).get("eatOnlyIfEnergyBelowPercent", 50)
    min_kg = rules.get("feeding", {}).get("minKgPerEat", 0.1)
    max_kg_cap = star_attrs.get("max_kg_consumable_per_visit_kg", rules.get("feeding", {}).get("maxKgConsumablePerVisitKg"))
    if max_kg_cap is None:
        max_kg_cap = float('inf')

    ate_kg = 0.0
    if s.energy_pct < eat_threshold and s.grass_kg > 0 and max_kg_by_time > 0:
        desired = max_kg_by_time
        # garantizar al menos min_kg si queremos comer algo
        if desired < min_kg:
            desired = min_kg
        desired = min(desired, s.grass_kg, max_kg_cap)
        eg_map = rules.get("energy", {}).get("energyGainPerKgByHealthPercent", {})
        # fallback a "Good" si no se encuentra la salud exacta
        gain_per_kg = eg_map.get(s.health, eg_map.get("Good", 3))
        old_energy = s.energy_pct
        s.grass_kg = max(0.0, s.grass_kg - desired)
        s.apply_energy_delta(gain_per_kg * desired, rules)
        ate_kg = desired
        gained = s.energy_pct - old_energy
        events.append(f"ate {desired:.3f}kg (+{gained:.4f}%)")
        s.add_log(f"Ate {desired:.6f} kg -> +{gained:.4f}% energy")

    # investigación: consumo por año
    invest_energy_pct_per_year = star_attrs.get("invest_energy_per_year_pct", rules.get("energy", {}).get("energyLossPerInvestigationYearPercent", 0.0))
    total_invest_loss = inv_years * float(invest_energy_pct_per_year)
    # aplicamos pérdida (positivo = pérdida)
    old_energy = s.energy_pct
    s.apply_energy_delta(-total_invest_loss, rules)
    lost = s.energy_pct - old_energy
    # lost será negativo o cero, queremos mostrar el cambio real
    events.append(f"Investigated {inv_years:.4f}y -> energy {-total_invest_loss:.4f}%")
    s.add_log(f"Investigated {inv_years:.4f}y -> energy {-total_invest_loss:.4f}%")

    # aplicar efectos de estrella (JSON o overrides)
    effects = {}
    effects.update(star_attrs.get("effects", {}) or {})
    effects.update(uo.get("effects", {}) or {})
    life_delta = float(effects.get("life_delta_years", 0.0))
    health_delta = effects.get("health_delta", None)

    if life_delta != 0.0:
        s.apply_life_delta(life_delta)
        events.append(f"life_delta {life_delta:+.4f}y")
        s.add_log(f"Life delta {life_delta:+.4f}y")

    if health_delta:
        s.health = health_delta
        events.append(f"health_set_to {health_delta}")
        s.add_log(f"Health set to {health_delta}")

    # hipergigante: +50 puntos porcentuales de energía, capped at 100; duplicar pasto
    if star_attrs.get("hypergiant"):
        hg = rules.get("hypergiant", {})
        old_e = s.energy_pct
        s.apply_energy_delta(50.0, rules)  # añade 50 puntos porcentuales
        dup = hg.get("grassDuplicateMultiplier", 2)
        s.grass_kg *= dup
        events.append(f"Hypergiant +{s.energy_pct - old_e:.4f} energy, grass x{dup}")
        s.add_log(f"Used hypergiant: +{s.energy_pct - old_e:.4f} energy, grass x{dup}")

    # marcar visitado (asegurar que exista set)
    if not hasattr(s, "visited") or s.visited is None:
        s.visited = set()
    s.visited.add(s.node)

    # chequeo muerte
    if s.energy_pct <= 0 or getattr(s, "life_years_left", 1e9) <= 0:
        s.health = "Dead"
        events.append("DIED_DURING_VISIT")
        s.add_log("Death during visit")

    return s, events