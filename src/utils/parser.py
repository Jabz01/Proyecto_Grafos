import json
import math
import random
from typing import Tuple, Dict, List, Any

# Constantes por defecto
DISTANCE_TO_YEARS_FACTOR_DEFAULT = 0.05
MAX_HYPERGIANTS_PER_CONSTELLATION_DEFAULT = 2

INVESTIGATION_YEARS_RANGE = (1.0, 5.0)
TIME_PER_KG_YEARS_RANGE = (1.0, 5.0)
INVEST_ENERGY_PCT_RANGE = (0.05, 0.5)


class JSONValidationError(Exception):
    """Raised when input JSON structure is invalid."""
    pass

def EuclideanDistance(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Compute Euclidean distance between two points with keys 'x' and 'y'."""
    dx = a["x"] - b["x"]
    dy = a["y"] - b["y"]
    return math.hypot(dx, dy)

def LoadJson(path: str) -> Dict[str, Any]:
    """Load a JSON file and return the parsed object."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def BuildParserOutputFromJson(
    data: Dict[str, Any],
    distanceToYearsFactor: float = DISTANCE_TO_YEARS_FACTOR_DEFAULT,
    enforceBidirectional: bool = True,
    repairMissingInverseEdge: bool = True,
    maxHypergiantsPerConstellation: int = MAX_HYPERGIANTS_PER_CONSTELLATION_DEFAULT
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    warnings: List[str] = []
    errors: List[str] = []

    if not isinstance(data, dict):
        raise JSONValidationError("Root JSON must be an object.")

    meta = data.get("meta", {})
    constellationsInput = data.get("constellations", [])
    starsInput = data.get("stars", [])
    edgesInput = data.get("edges", [])
    initialStateInput = data.get("initial_state", {})

    # ---- Validar unicidad y estructura de estrellas (igual que antes) ----
    starsById: Dict[int, Dict[str, Any]] = {}
    for s in starsInput:
        sid = s.get("id")
        if sid is None:
            errors.append("Found star without 'id'. Integer unique id required.")
            continue
        if sid in starsById:
            errors.append(f"Duplicate star definition with id={sid}.")
            continue

        coords = s.get("coordinates")
        if not coords or "x" not in coords or "y" not in coords:
            errors.append(f"Star id={sid} lacks valid coordinates.")
            coordX, coordY = 0.0, 0.0
        else:
            coordX, coordY = float(coords["x"]), float(coords["y"])

        starsById[sid] = {
            "id": int(sid),
            "label": s.get("label", f"star{sid}"),
            "coordinates": {"x": coordX, "y": coordY},
            "radius": float(s.get("radius", 0.5)),
            # campo legacy preserved but we will generate time_per_kg_years (years) below
            "timeToEatHoursPerKg": float(s.get("timeToEatHoursPerKg", 1)),
            "hypergiant": bool(s.get("hypergiant", False)),
            "investigations": list(s.get("investigations", []))
        }

    if errors:
        return {}, warnings, errors

    # ---- Validar hipergigantes por constelación (igual que antes) ----
    for c in constellationsInput:
        cid = c.get("id", c.get("name", "<no-id>"))
        cStars = c.get("stars", [])
        hipCount = sum(1 for sid in cStars if starsById.get(sid, {}).get("hypergiant"))
        if hipCount > maxHypergiantsPerConstellation:
            warnings.append(f"Constellation {cid} contains {hipCount} hypergiants (max {maxHypergiantsPerConstellation}).")

    # ---- Normalizar aristas (igual que antes) ----
    edgesNorm: List[Dict[str, Any]] = []
    for e in edgesInput:
        u = e.get("u")
        v = e.get("v")
        if u is None or v is None:
            warnings.append(f"Invalid edge (missing u/v): {e}")
            continue
        if u not in starsById or v not in starsById:
            warnings.append(f"Edge references undefined node(s): {u}, {v}. Ignored.")
            continue
        blocked = bool(e.get("blocked", False))
        edgesNorm.append({"u": int(u), "v": int(v), "blocked": blocked})

    # ---- Añadir aristas inversas si falta (igual que antes) ----
    if enforceBidirectional:
        seen = set((a["u"], a["v"]) for a in edgesNorm)
        toAdd = []
        for a in edgesNorm:
            if (a["v"], a["u"]) not in seen:
                if repairMissingInverseEdge:
                    toAdd.append({"u": a["v"], "v": a["u"], "blocked": a["blocked"]})
                    seen.add((a["v"], a["u"]))
                else:
                    warnings.append(f"Unidirectional edge detected {a['u']} -> {a['v']}")
        edgesNorm.extend(toAdd)

    # ---- Construir listas finales de estrellas y aristas ----
    # Antes de construir starsOut, rellenamos atributos aleatorios por estrella si faltan
    seed = meta.get("simulationSeed", None)
    rng = random.Random(seed)

    # ranges (podemos permitir que vengan en meta si se desea)
    invest_years_min, invest_years_max = INVESTIGATION_YEARS_RANGE
    time_per_kg_min, time_per_kg_max = TIME_PER_KG_YEARS_RANGE
    invest_pct_min, invest_pct_max = INVEST_ENERGY_PCT_RANGE

    # rellenar atributos por estrella (en starsById)
    for sid, attr in starsById.items():
        # Respect existing explicit attrs if present (mantener compatibilidad)
        if "investigation_years" not in attr or attr.get("investigation_years") is None:
            attr["investigation_years"] = round(rng.uniform(invest_years_min, invest_years_max), 4)
        if "time_per_kg_years" not in attr or attr.get("time_per_kg_years") is None:
            attr["time_per_kg_years"] = round(rng.uniform(time_per_kg_min, time_per_kg_max), 4)
        if "invest_energy_per_year_pct" not in attr or attr.get("invest_energy_per_year_pct") is None:
            attr["invest_energy_per_year_pct"] = round(rng.uniform(invest_pct_min, invest_pct_max), 6)

    starsOut = list(starsById.values())

    edgesOut = []
    for e in edgesNorm:
        u, v = e["u"], e["v"]
        coordU = starsById[u]["coordinates"]
        coordV = starsById[v]["coordinates"]
        distanceLy = EuclideanDistance(coordU, coordV)
        yearsCost = distanceLy * distanceToYearsFactor
        edgesOut.append({
            "u": u,
            "v": v,
            "blocked": e["blocked"],
            "distanceLy": distanceLy,
            "yearsCost": yearsCost
        })

    # ---- Validar estado inicial ----
    initialOut = dict(initialStateInput)
    if "initialEnergyPercent" not in initialOut:
        warnings.append("Missing 'initialEnergyPercent'. Defaulting to 100.")
        initialOut["initialEnergyPercent"] = 100
    if "currentAgeYears" not in initialOut or "deathAgeYears" not in initialOut:
        warnings.append("Missing 'currentAgeYears' or 'deathAgeYears'. Defaulting to 0/100.")
        initialOut.setdefault("currentAgeYears", 0)
        initialOut.setdefault("deathAgeYears", 100)

    # Validar referencias en constelaciones
    for c in constellationsInput:
        cid = c.get("id", c.get("name", "<no-id>"))
        for sid in c.get("stars", []):
            if sid not in starsById:
                warnings.append(f"Constellation {cid} references star id={sid} that does not exist.")

    parserOutput = {
        "meta": meta,
        "constellations": constellationsInput,
        "stars": starsOut,
        "edges": edgesOut,
        "initial_state": initialOut
    }

    return parserOutput, warnings, errors
