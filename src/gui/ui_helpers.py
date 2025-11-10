# src/gui/ui_helpers.py
from typing import Dict, Any, Optional
import math

def _fmt(x, n=2):
    try:
        return f"{float(x):.{n}f}"
    except Exception:
        return str(x)

def build_star_tooltip(star_attrs: Dict[str, Any], rules: Dict[str, Any], burro_state: Optional[Any] = None) -> Dict[str, Any]:
    """
    Normaliza la información que la info-box debe mostrar.
    NO incluye probabilidades ni rangos (por requisito).
    Devuelve dict con claves:
      id, title, investigation_years, time_per_kg_years,
      energy_consumption_per_visit_pct, feeding_max_kg_text,
      recovery_per_1kg_pct (None si no hay burro_state), notes (list)
    """
    ctx: Dict[str, Any] = {}
    sid = star_attrs.get("id", star_attrs.get("node", None))
    ctx["id"] = sid
    ctx["is_hypergiant"] = bool(star_attrs.get("hypergiant", False))
    ctx["title"] = f"Star #{sid}" + (" [Hypergiant]" if ctx["is_hypergiant"] else "")

    # investigation and eating times (use star_attrs fallback to rules default if missing)
    inv_years = star_attrs.get("investigation_years", None)
    if inv_years is None:
        inv_years = rules.get("timeAndLife", {}).get("default_investigation_years", 1.0)
    ctx["investigation_years"] = float(inv_years)

    time_per_kg = star_attrs.get("time_per_kg_years", star_attrs.get("time_to_consume_kg_years", None))
    if time_per_kg is None:
        time_per_kg = rules.get("timeAndLife", {}).get("time_per_kg_default", 1.0)
    ctx["time_per_kg_years"] = float(time_per_kg)

    # energy consumption per visit (percent)
    per_year_pct = star_attrs.get("invest_energy_per_year_pct", rules.get("energy", {}).get("energyLossPerInvestigationYearPercent", 0.0))
    try:
        per_year_pct = float(per_year_pct)
    except Exception:
        per_year_pct = 0.0
    ctx["energy_consumption_per_visit_pct"] = ctx["investigation_years"] * per_year_pct

    # feeding caps
    max_kg_cap = star_attrs.get("max_kg_consumable_per_visit_kg", rules.get("feeding", {}).get("maxKgConsumablePerVisitKg"))
    if max_kg_cap is None:
        feeding_text = "máx por visita: ilimitado"
    else:
        try:
            feeding_text = f"máx por visita: {float(max_kg_cap):.2f} kg"
        except Exception:
            feeding_text = f"máx por visita: {max_kg_cap}"
    ctx["feeding_max_kg_text"] = feeding_text

    # recovery by 1kg now (only if burro_state provided)
    recovery_pct = None
    recovery_note = ""
    if burro_state is not None:
        eg_map = rules.get("energy", {}).get("energyGainPerKgByHealthPercent", {})
        health = getattr(burro_state, "health", None)
        gain_per_kg = eg_map.get(health, None)
        if gain_per_kg is None:
            # fallback to 'Good' or 0
            gain_per_kg = eg_map.get("Good", 0)
        try:
            recovery_pct = float(gain_per_kg)
            recovery_note = f"salud: {health}"
        except Exception:
            recovery_pct = None
    ctx["recovery_per_1kg_pct"] = recovery_pct
    ctx["recovery_note"] = recovery_note

    # grass available (optional)
    grass = star_attrs.get("grass_kg", None)
    if grass is None:
        ctx["grass_text"] = "pasto: desconocido"
    else:
        ctx["grass_text"] = f"pasto: {float(grass):.2f} kg"

    # notes: hypergiant multipliers and anything useful (small list)
    notes = []
    if ctx["is_hypergiant"]:
        hg = rules.get("hypergiant", {})
        if hg:
            notes.append(f"Hypergiant: grass x{hg.get('grassDuplicateMultiplier', 1)}; energía recarga x{hg.get('energyRechargeMultiplier', 1)}")
    # add explicit star label if present
    label = star_attrs.get("label")
    if label:
        notes.append(f"label: {label}")
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