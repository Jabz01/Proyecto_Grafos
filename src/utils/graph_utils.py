# src/utils/graph_utils.py
from typing import Any, List
import networkx as nx

def filtered_graph_nx(G: nx.Graph) -> nx.Graph:
    """Devuelve una copia de G sin las aristas marcadas con blocked=True."""
    Gf = G.copy()
    to_remove = [(u, v) for u, v, attrs in Gf.edges(data=True) if attrs.get("blocked")]
    Gf.remove_edges_from(to_remove)
    return Gf

def path_total_cost(G: nx.Graph, path: List[int], weight: str = 'yearsCost') -> float:
    """Suma el peso weight a lo largo de path (lista de nodos). Omite aristas blocked."""
    total = 0.0
    if not path or len(path) < 2:
        return total
    for a, b in zip(path[:-1], path[1:]):
        attrs = G.get_edge_data(a, b) or {}
        if attrs.get("blocked"):
            continue
        total += float(attrs.get(weight, attrs.get('distanceLy', 0.0)))
    return total