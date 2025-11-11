# src/gui/ui_helpers.py
from typing import Dict, Any, Optional

def _fmt(x, n=2):
    try:
        return f"{float(x):.{n}f}"
    except Exception:
        return str(x)

def build_star_tooltip(star_attrs: Dict[str, Any], rules: Dict[str, Any], burro_state: Optional[Any] = None) -> Dict[str, Any]:
    """
    Normaliza la información que la info-box debe mostrar.
    NO incluye probabilidades ni rangos.
    Devuelve dict con claves útiles para renderizar la caja.
    """
    ctx: Dict[str, Any] = {}

    # Título: preferir label humano; si no existe usar id/node o genérico
    label = star_attrs.get("label")
    if label:
        ctx["title"] = f"{label}" + (" [Hypergiant]" if star_attrs.get("hypergiant", False) else "")
    else:
        sid = star_attrs.get("id", star_attrs.get("node", None))
        if sid is None:
            base_title = "Star"
        elif isinstance(sid, (int, float)):
            base_title = f"Star #{sid}"
        else:
            base_title = f"Star {sid}"
        ctx["title"] = base_title + (" [Hypergiant]" if star_attrs.get("hypergiant", False) else "")

    ctx["id"] = star_attrs.get("id", star_attrs.get("node", None))
    ctx["is_hypergiant"] = bool(star_attrs.get("hypergiant", False))

    # investigation and eating times (fallbacks desde rules si faltan)
    inv_years = star_attrs.get("investigation_years", None)
    if inv_years is None:
        inv_years = rules.get("timeAndLife", {}).get("default_investigation_years", 1.0)
    ctx["investigation_years"] = float(inv_years)

    time_per_kg = star_attrs.get("time_per_kg_years", star_attrs.get("time_to_consume_kg_years", None))
    if time_per_kg is None:
        time_per_kg = rules.get("timeAndLife", {}).get("time_per_kg_default", 1.0)
    ctx["time_per_kg_years"] = float(time_per_kg)

    # energy consumption per visit (percent) -> solo por INVESTIGACIÓN
    per_year_pct = star_attrs.get("invest_energy_per_year_pct", rules.get("energy", {}).get("energyLossPerInvestigationYearPercent", 0.0))
    try:
        per_year_pct = float(per_year_pct)
    except Exception:
        per_year_pct = 0.0
    ctx["energy_consumption_per_visit_pct"] = ctx["investigation_years"] * per_year_pct

    # --- calcular límites de comida por visita (informativo)
    max_frac = rules.get("timeAndLife", {}).get("maxFractionOfStayForEating", 0.5)
    try:
        time_per_kg_val = float(ctx["time_per_kg_years"]) if ctx.get("time_per_kg_years") is not None else 1.0
    except Exception:
        time_per_kg_val = 1.0
    try:
        max_kg_by_time = (ctx["investigation_years"] * max_frac) / time_per_kg_val
    except Exception:
        max_kg_by_time = float("inf")

    cap = star_attrs.get("max_kg_consumable_per_visit_kg", rules.get("feeding", {}).get("maxKgConsumablePerVisitKg"))
    cap_val: Optional[float]
    if cap is None:
        cap_val = None
    else:
        try:
            cap_val = float(cap)
        except Exception:
            cap_val = None

    ship_stock = None
    if burro_state is not None:
        try:
            ship_stock = float(getattr(burro_state, "grass_kg", 0.0))
        except Exception:
            ship_stock = None

    eff_candidates = []
    if max_kg_by_time != float("inf"):
        eff_candidates.append(max_kg_by_time)
    if cap_val is not None:
        eff_candidates.append(cap_val)
    if ship_stock is not None:
        eff_candidates.append(ship_stock)
    if eff_candidates:
        max_effective = min(eff_candidates)
    else:
        max_effective = float("inf")

    def _fmt_kg(x):
        try:
            if x == float("inf"):
                return "ilimitado"
            return f"{float(x):.2f} kg"
        except Exception:
            return str(x)

    feeding_lines = []
    feeding_lines.append(f"máx por tiempo: {_fmt_kg(max_kg_by_time)}")
    if cap_val is not None:
        feeding_lines.append(f"cap reglamentario: {_fmt_kg(cap_val)}")
    else:
        feeding_lines.append("cap reglamentario: ilimitado")
    if ship_stock is not None:
        feeding_lines.append(f"stock bodega: {_fmt_kg(ship_stock)}")
    feeding_lines.append(f"máx efectivo esta visita: {_fmt_kg(max_effective)}")

    ctx["feeding_max_kg_text"] = " | ".join(feeding_lines)

    # recovery by 1kg now (only if burro_state provided)
    recovery_pct = None
    recovery_note = ""
    if burro_state is not None:
        eg_map = rules.get("energy", {}).get("energyGainPerKgByHealthPercent", {})
        health = getattr(burro_state, "health", None)
        gain_per_kg = eg_map.get(health, None)
        if gain_per_kg is None:
            gain_per_kg = eg_map.get("Good", 3)
        try:
            recovery_pct = float(gain_per_kg)
            recovery_note = f"salud: {health}"
        except Exception:
            recovery_pct = None
    ctx["recovery_per_1kg_pct"] = recovery_pct
    ctx["recovery_note"] = recovery_note

    # grass disponible: indicamos que está en la bodega; grass_text refleja stock si burro_state
    if burro_state is None:
        ctx["grass_text"] = "pasto: (en bodega de la nave)"
    else:
        ctx["grass_text"] = f"pasto bodega: {ship_stock:.2f} kg" if ship_stock is not None else "pasto bodega: desconocido"

    # notes: hypergiant multipliers and key explanatory notes
    notes = []
    if ctx["is_hypergiant"]:
        hg = rules.get("hypergiant", {})
        if hg:
            notes.append(f"Hypergiant: grass x{hg.get('grassDuplicateMultiplier', 1)}; energía recarga x{hg.get('energyRechargeMultiplier', 1)}")

    notes.append(f"Coste energía investigación: {ctx['energy_consumption_per_visit_pct']:.2f} % por visita")
    notes.append("Consumo energía por visita corresponde a la pérdida por INVESTIGACIÓN, no a comer")
    notes.append("Visita = tiempo total en la estrella; comer usa hasta 50% del tiempo; investigar usa el resto")

    ctx["notes"] = notes

    # formatted strings for display (precompute)
    ctx["investigation_years_s"] = _fmt(ctx["investigation_years"], 2)
    ctx["time_per_kg_years_s"] = _fmt(ctx["time_per_kg_years"], 2)
    ctx["energy_consumption_per_visit_pct_s"] = _fmt(ctx["energy_consumption_per_visit_pct"], 2)
    if recovery_pct is not None:
        ctx["recovery_per_1kg_pct_s"] = _fmt(recovery_pct, 2)
    else:
        ctx["recovery_per_1kg_pct_s"] = None

    return ctx