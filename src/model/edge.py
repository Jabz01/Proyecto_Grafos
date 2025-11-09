# src/model/edge.py
from dataclasses import dataclass
import math
from typing import Optional, Tuple, Iterable, Dict, Any

def point_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """
    Distancia mínima punto -> segmento (x1,y1)-(x2,y2).
    Función pura, sin efectos laterales.
    """
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x, proj_y = x1 + t * dx, y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)

def pick_nearest_edge(px: float,
                      py: float,
                      edges_iterable: Iterable[Tuple[int, int]],
                      pos: Dict[int, Tuple[float, float]],
                      threshold: float) -> Optional[Tuple[Tuple[int, int], float]]:
    """
    Recorre edges_iterable (iterable de pares (u,v)) y devuelve ((u,v), distancia)
    de la arista más cercana cuyo distance <= threshold. Si no hay ninguna, devuelve None.

    - px,py: coordenadas del click
    - edges_iterable: iterable sobre pares (u,v) (puede venir de networkx.Graph.edges())
    - pos: mapping node -> (x,y)
    - threshold: umbral en unidades de coordenadas
    """
    best_edge = None
    best_dist = float('inf')
    for u, v in edges_iterable:
        # manejar caso donde pos no tenga la clave por seguridad
        if u not in pos or v not in pos:
            continue
        x1, y1 = pos[u]
        x2, y2 = pos[v]
        d = point_segment_distance(px, py, x1, y1, x2, y2)
        if d < best_dist:
            best_dist = d
            best_edge = (u, v)
    if best_edge is None or best_dist > threshold:
        return None
    return best_edge, best_dist

@dataclass
class Edge:
    """Domain model for an undirected edge between two stars."""
    u: int
    v: int
    distanceLy: float
    yearsCost: float
    blocked: bool = False
    meta: Dict[str, Any] = None

    def Endpoints(self) -> Tuple[int, int]:
        """Return tuple (u, v) for convenience."""
        return (self.u, self.v)

    def ToggleBlocked(self, value: bool) -> None:
        """Set blocked flag for this edge."""
        self.blocked = bool(value)

    def IsBlocked(self) -> bool:
        """Return whether the edge is blocked."""
        return self.blocked

    def ToDict(self) -> Dict[str, Any]:
        """Serialize edge to a dict (for networkx or reports)."""
        return {
            "u": self.u,
            "v": self.v,
            "distanceLy": self.distanceLy,
            "yearsCost": self.yearsCost,
            "blocked": self.blocked,
            "meta": self.meta or {}
        }