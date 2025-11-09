# src/planner/dijkstra_planner.py
import networkx as nx
from typing import List, Optional, Tuple

def shortest_path_dijkstra(G: nx.Graph, source: int, target: int, weight: str = "yearsCost") -> Optional[Tuple[List[int], float]]:
    """
    Ejecuta Dijkstra en G desde source a target usando 'weight' como atributo.
    Retorna (path, total_weight) o None si no hay camino.
    """
    try:
        path = nx.shortest_path(G, source=source, target=target, weight=weight)
        total = nx.shortest_path_length(G, source=source, target=target, weight=weight)
        return path, float(total)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None