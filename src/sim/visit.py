from typing import Dict, Tuple, Optional, List, Any
from src.sim.burro_state import BurroState

def _degrade_health(curr: str) -> str:
    order = ["Excellent", "Good", "Bad", "NearDeath", "Dead"]
    try:
        i = order.index(curr)
    except ValueError:
        return curr
    if i < len(order) - 1:
        return order[i + 1]
    return curr

def _improve_health(curr: str) -> str:
    order = ["Excellent", "Good", "Bad", "NearDeath", "Dead"]
    try:
        i = order.index(curr)
    except ValueError:
        return curr
    if i == 0:
        return curr
    return order[i - 1]

def simulate_visit(state: BurroState, star_attrs: Dict, rules: Dict, user_overrides: Optional[Dict]=None) -> Tuple[BurroState, List[str]]:
    """
    Simula la visita del burro a una estrella.
    Reglas aplicadas:
     - inv_years: años dedicados a investigación (puede venir por override)
     - Comer: solo si energy_pct < threshold; limitado por tiempo disponible (maxFractionOfStayForEating * inv_years)
             y por stock de la nave (s.grass_kg). No hay coste por comer, solo ganancia por kg según salud.
     - Investigación: consume energía = inv_years * invest_energy_per_year_pct.
     - Outcomes de investigación (illness / success / neutral) se aplican una única vez y se registran en last_event.
     - Hypergiant: recarga relativa (+50% del nivel actual) y duplica stock de pasto según reglas.
    """
    s = state.clone()
    events: List[str] = []
    uo = user_overrides or {}

    # INVESTIGATION YEARS (override > star_attrs)
    inv_years = float(uo.get("investigation_years", star_attrs.get("investigation_years", 0.0)))

    # -------------- EATING (limitado por tiempo y stock; no cap reglamentario) --------------
    max_frac = rules.get("timeAndLife", {}).get("maxFractionOfStayForEating", 0.5)
    # time_per_kg_years debe estar en años por kg (model usa años)
    time_per_kg_years = float(star_attrs.get("time_per_kg_years", star_attrs.get("time_to_consume_kg_years", 1.0)))
    # máximo de años que puede dedicar a comer durante la visita
    max_eat_years = inv_years * float(max_frac)
    # cuántos kg permite ese tiempo (años disponibles / años por kg)
    max_kg_by_time = (max_eat_years / time_per_kg_years) if time_per_kg_years > 0 else float('inf')

    # reglas de alimentación mínimas del sistema
    eat_threshold = rules.get("feeding", {}).get("eatOnlyIfEnergyBelowPercent", 50)
    min_kg = rules.get("feeding", {}).get("minKgPerEat", 0.1)

    ate_kg = 0.0
    # Comer solo si energía por debajo del umbral y hay stock en la nave
    if s.energy_pct < eat_threshold and getattr(s, "grass_kg", 0.0) > 0 and max_kg_by_time > 0:
        desired = max_kg_by_time
        if desired < min_kg:
            desired = min_kg
        # limitar por stock disponible del burro/nave (no hay cap reglamentario)
        desired = min(desired, s.grass_kg)
        if desired > 0:
            eg_map = rules.get("energy", {}).get("energyGainPerKgByHealthPercent", {})
            gain_per_kg = eg_map.get(s.health, eg_map.get("Good", 3))
            old_energy = s.energy_pct
            # consumir stock de la nave
            s.grass_kg = max(0.0, s.grass_kg - desired)
            # aplicar ganancia (sin coste)
            s.apply_energy_delta(gain_per_kg * desired, rules)
            ate_kg = desired
            gained = s.energy_pct - old_energy
            events.append(f"ate {desired:.3f}kg (+{gained:.4f}%)")
            s.add_log(f"Ate {desired:.6f} kg -> +{gained:.4f}% energy")

    # -------------- INVESTIGATION ENERGY CONSUMPTION (solo por investigar) --------------
    invest_energy_pct_per_year = star_attrs.get(
        "invest_energy_per_year_pct",
        rules.get("energy", {}).get("energyLossPerInvestigationYearPercent", 0.0)
    )
    total_invest_loss = inv_years * float(invest_energy_pct_per_year)
    old_energy = s.energy_pct
    s.apply_energy_delta(-total_invest_loss, rules)
    events.append(f"Investigated {inv_years:.4f}y -> energy {-total_invest_loss:.4f}%")
    s.add_log(f"Investigated {inv_years:.4f}y -> energy {-total_invest_loss:.4f}%")

    # -------------- EFFECTS from star (life_delta, health_delta) --------------
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

    # -------------- Investigation outcome (illness / success / neutral) --------------
    inv_cfg = rules.get("timeAndLife", {}).get("investigation", {})
    p_ill = float(inv_cfg.get("p_illness", 0.0))
    p_succ = float(inv_cfg.get("p_success", 0.0))
    ill_range = inv_cfg.get("illness_life_loss_range", [1.0, 3.0])
    succ_range = inv_cfg.get("success_life_gain_range", [0.0, 1.0])
    succ_improve_p = float(inv_cfg.get("success_improve_health_p", 0.0))

    rng = s.get_rng(rules)
    r = rng.random()

    outcome_struct: Dict[str, Any] = {
        "type": "investigation",
        "outcome": "neutral",
        "life_delta": 0.0,
        "health_from": s.health,
        "health_to": s.health,
        "energy_delta": s.energy_pct - old_energy,
        "note": ""
    }

    if inv_years > 0 and (p_ill > 0.0 or p_succ > 0.0):
        # illness
        if r < p_ill:
            life_loss = -float(rng.uniform(float(ill_range[0]), float(ill_range[1])))
            old_health = s.health
            new_health = _degrade_health(old_health)
            s.apply_life_delta(life_loss)
            s.health = new_health
            outcome_struct.update({"outcome": "illness", "life_delta": life_loss, "health_from": old_health, "health_to": new_health})
            events.append(f"investigate:illness({life_loss:.2f}y)->health {old_health}->{new_health}")
            s.add_log(f"Investigation caused illness: {life_loss:.2f}y, health {old_health}->{new_health}")
        # success
        elif r < (p_ill + p_succ):
            life_gain = float(rng.uniform(float(succ_range[0]), float(succ_range[1])))
            old_health = s.health
            s.apply_life_delta(life_gain)
            improved = False
            if succ_improve_p > 0.0:
                r2 = rng.random()
                if r2 < succ_improve_p:
                    new_health = _improve_health(old_health)
                    if new_health != old_health:
                        s.health = new_health
                        improved = True
            outcome_struct.update({"outcome": "successful", "life_delta": life_gain, "health_from": old_health, "health_to": s.health})
            if improved:
                events.append(f"investigate:successful(+{life_gain:.2f}y)->health {old_health}->{s.health}")
                s.add_log(f"Investigation success improved health: {old_health}->{s.health}")
            else:
                events.append(f"investigate:successful(+{life_gain:.2f}y)")
                s.add_log(f"Investigation success: +{life_gain:.2f}y")
        else:
            outcome_struct["outcome"] = "neutral"
            events.append("investigate:neutral")
            s.add_log("Investigation neutral")

    # register structured event
    s.last_event = outcome_struct
    s.event_log.append(outcome_struct)

    # -------------- Hypergiant handling --------------
    if star_attrs.get("hypergiant"):
        hg = rules.get("hypergiant", {})
        # Aplicar recarga relativa: +50% del nivel actual (si quieres usar multiplier de rules,
        # ajusta la línea siguiente para usar hg.get('energyRechargeMultiplier'))
        relative_recharge_fraction = 0.5
        old_e = s.energy_pct
        s.apply_energy_delta(old_e * relative_recharge_fraction, rules)
        dup = int(hg.get("grassDuplicateMultiplier", 2))
        s.grass_kg = s.grass_kg * dup
        events.append(f"Hypergiant +{s.energy_pct - old_e:.4f} energy, grass x{dup}")
        s.add_log(f"Used hypergiant: +{s.energy_pct - old_e:.4f} energy, grass x{dup}")

    # -------------- mark visited --------------
    if not hasattr(s, "visited") or s.visited is None:
        s.visited = set()
    s.visited.add(s.node)

    # -------------- death check --------------
    if s.energy_pct <= 0 or getattr(s, "life_years_left", 1e9) <= 0:
        s.health = "Dead"
        events.append("DIED_DURING_VISIT")
        s.add_log("Death during visit")

    return s, events