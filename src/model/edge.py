# src/model/edge.py
from dataclasses import dataclass
from typing import Tuple, Dict, Any


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