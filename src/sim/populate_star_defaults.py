# src/sim/populate_star_defaults.py
import random
from typing import Iterable, Tuple, Any, Dict

DEFAULT_INVEST_PCT_RANGE = (0.05, 0.5)  # % energía perdido por año de investigación, por estrella

def populate_star_defaults(
    nodes: Iterable[Tuple[Any, Dict]],
    seed: int | None = None,
    invest_pct_range: Tuple[float, float] = DEFAULT_INVEST_PCT_RANGE,
    investigation_range: Tuple[float, float] = (1.0, 5.0),
    time_per_kg_range: Tuple[float, float] = (1.0, 5.0)
) -> None:
    """
    Modifica in-place los atributos de nodos (forma (node_id, attr_dict) o attr_dict)
    y asegura que cada estrella tiene:
      - investigation_years
      - time_per_kg_years
      - invest_energy_per_year_pct
    Valores generados aleatoriamente en los rangos indicados. Si ya existen, se respetan.
    """
    rng = random.Random(seed)
    min_inv, max_inv = investigation_range
    min_time, max_time = time_per_kg_range
    min_ipct, max_ipct = invest_pct_range

    for item in nodes:
        # aceptar (id, attrs) o attrs directo
        attr = item[1] if isinstance(item, tuple) and len(item) == 2 else item

        if "investigation_years" not in attr or attr.get("investigation_years") is None:
            attr["investigation_years"] = round(rng.uniform(min_inv, max_inv), 4)
        if "time_per_kg_years" not in attr or attr.get("time_per_kg_years") is None:
            attr["time_per_kg_years"] = round(rng.uniform(min_time, max_time), 4)
        if "invest_energy_per_year_pct" not in attr or attr.get("invest_energy_per_year_pct") is None:
            attr["invest_energy_per_year_pct"] = round(rng.uniform(min_ipct, max_ipct), 6)