# src/model/star.py
from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class Investigation:
    """Represents a single preconfigured investigation for a star."""
    name: str
    time_hours: float
    energyConsumedPercent: float
    randomYearsEffectSigned: float


@dataclass
class Star:
    """Domain model for a star node (planetary/star location)."""
    id: int
    label: str
    coordinates: Dict[str, float]
    radius: float
    timeToEatHoursPerKg: float
    hypergiant: bool = False
    investigations: List[Investigation] = field(default_factory=list)

    # Métodos auxiliares en español para facilitar integraciones en la GUI

    def DistanceTo(self, other: "Star") -> float:
        """Euclidean distance to another star."""
        dx = float(self.coordinates["x"]) - float(other.coordinates["x"])
        dy = float(self.coordinates["y"]) - float(other.coordinates["y"])
        return (dx * dx + dy * dy) ** 0.5

    def AddInvestigation(self, inv: Investigation) -> None:
        """Agregar una investigación preconfigurada (antes de iniciar la simulación)."""
        self.investigations.append(inv)

    def TotalInvestigationsYearsEffect(self) -> float:
        """
        Sum of fixed random years effects for all investigations.
        This value must be pre-generated and fixed before simulation start.
        """
        return sum(inv.randomYearsEffectSigned for inv in self.investigations)

    def ToDict(self) -> Dict[str, Any]:
        """Serialize star to a simple dict (useful for reports)."""
        return {
            "id": self.id,
            "label": self.label,
            "coordinates": self.coordinates,
            "radius": self.radius,
            "timeToEatHoursPerKg": self.timeToEatHoursPerKg,
            "hypergiant": self.hypergiant,
            "investigations": [
                {
                    "name": inv.name,
                    "time_hours": inv.time_hours,
                    "energyConsumedPercent": inv.energyConsumedPercent,
                    "randomYearsEffectSigned": inv.randomYearsEffectSigned
                } for inv in self.investigations
            ]
        }