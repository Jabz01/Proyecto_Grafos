from dataclasses import dataclass, field
from typing import Set, Optional, Dict, Any
import copy

@dataclass
class BurroState:
    node: int
    life_years_left: float
    health: str  # "Excellent", "Good", "Bad", "NearDeath", "Dead"
    energy_pct: float  # 0..100
    grass_kg: float
    age_years: float = 0.0
    visited: Set[int] = field(default_factory=set)
    log: list = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def clone(self) -> "BurroState":
        return copy.deepcopy(self)

    def is_dead(self) -> bool:
        return self.health == "Dead" or self.life_years_left <= 0.0 or self.energy_pct <= 0.0

    def apply_energy_delta(self, delta_pct: float, rules: Dict = None) -> None:
        self.energy_pct += delta_pct
        if rules and rules.get("energy", {}).get("applyEnergyCap100", True):
            self.energy_pct = min(100.0, self.energy_pct)
        # floor at 0 but don't change health here
        if self.energy_pct < 0:
            self.energy_pct = 0.0

    def apply_life_delta(self, delta_years: float) -> None:
        self.life_years_left += delta_years
        if self.life_years_left < 0:
            self.life_years_left = 0.0

    def add_log(self, msg: str) -> None:
        self.log.append(msg)