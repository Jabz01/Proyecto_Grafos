from typing import Tuple, List, Dict, Any
from src.sim.burro_state import BurroState
from src.sim.travel import simulate_travel
from src.sim.visit import simulate_visit

def simulate_path(state: BurroState, path: List[int], G: Any, rules: Dict) -> Tuple[BurroState, Dict[str, float], List[str]]:
    """
    Simula el recorrido completo del burro por una ruta de nodos.
    Aplica efectos de viaje y visita en cada paso.
    Retorna: (estado final, sumas acumuladas, lista de eventos)
    """
    s = state.clone()
    events = []
    sum_ly = 0.0
    sum_years = 0.0

    # Si el burro no tiene nodo asignado, lo colocamos en el primero sin penalización
    start_idx = 0
    if s.node is None and path:
        s.node = path[0]
        start_idx = 1

    for i in range(start_idx, len(path)):
        u = s.node
        v = path[i]

        # Simular viaje si cambia de nodo
        if u is not None and u != v:
            edge_attrs = G.get_edge_data(u, v) or {}
            sum_ly += float(edge_attrs.get("distanceLy", 0.0))
            sum_years += float(edge_attrs.get("yearsCost", 0.0))
            try:
                s, evs_travel = simulate_travel(s, u, v, edge_attrs, rules)
                events.extend(evs_travel)
            except Exception:
                s.apply_life_delta(-float(edge_attrs.get("yearsCost", 0.0)))
                events.append(f"travel {u}->{v} -{edge_attrs.get('yearsCost', 0.0)}y")
            s.node = v

        # Simular visita
        try:
            s, evs_visit = simulate_visit(s, G.nodes[v], rules)
            events.extend(evs_visit)
        except Exception:
            s.visited.add(v)
            events.append(f"visited {v}")

    return s, {"sum_ly": sum_ly, "sum_years": sum_years}, events