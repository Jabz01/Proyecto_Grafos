# src/utils/visual.py
import math
from typing import Dict, Tuple, Optional

BASE_NODE_SIZE = 500.0

def node_size(radius: float, hypergiant: bool = False) -> float:
    """Calcula el tamaño de nodo para matplotlib a partir del radius y si es hypergiant."""
    scale = 1.6 if hypergiant else 1.0
    return BASE_NODE_SIZE * float(radius) * scale

def nearest_node_by_radius(pos: Dict[int, Tuple[float, float]],
                           radii: Dict[int, float],
                           x: float, y: float,
                           threshold_mult: float = 0.9) -> Optional[int]:
    """
    Devuelve el nodo cuyo centro está más cercano al punto (x,y) si la distancia <= radius * threshold_mult.
    """
    best, bestd = None, float('inf')
    for n, (nx_, ny_) in pos.items():
        d = math.hypot(nx_ - x, ny_ - y)
        if d < bestd:
            best, bestd = n, d
    if best is None:
        return None
    r = radii.get(best, 1.0)
    if bestd <= (r * threshold_mult):
        return best
    return None