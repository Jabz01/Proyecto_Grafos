# src/sim/burro_state.py
from dataclasses import dataclass, field
from typing import Set, Optional, Dict, Any, List
import copy
import random

@dataclass
class BurroState:
    # node opcional: None indica "sin posición asignada; elegir origen en UI"
    node: Optional[int] = None
    life_years_left: float = 0.0
    health: str = "Excellent"  # "Excellent", "Good", "Bad", "NearDeath", "Dead"
    energy_pct: float = 100.0  # 0..100
    grass_kg: float = 0.0
    age_years: float = 0.0
    visited: Set[int] = field(default_factory=set)
    log: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    # New structured event support
    last_event: Optional[Dict[str, Any]] = None
    event_log: List[Dict[str, Any]] = field(default_factory=list)

    # Optional RNG instance for reproducible randomness per-state (can be None)
    rng: Optional[random.Random] = None

    def clone(self) -> "BurroState":
        # deep copy but keep RNG reference shallow (so cloning does not reseed)
        new = copy.deepcopy(self)
        # keep same RNG object reference (not deepcopied)
        new.rng = self.rng
        return new

    def is_dead(self) -> bool:
        return self.health == "Dead'".replace("'", "") or self.life_years_left <= 0.0 or self.energy_pct <= 0.0

    def apply_energy_delta(self, delta_pct: float, rules: Dict = None) -> None:
        self.energy_pct += delta_pct
        if rules and rules.get("energy", {}).get("applyEnergyCap100", True):
            self.energy_pct = min(100.0, self.energy_pct)
        if self.energy_pct < 0:
            self.energy_pct = 0.0

    def apply_life_delta(self, delta_years: float) -> None:
        self.life_years_left += delta_years
        if self.life_years_left < 0:
            self.life_years_left = 0.0

    def add_log(self, msg: str) -> None:
        self.log.append(msg)

    # Helper to get RNG (state rng -> rules rng -> global)
    def get_rng(self, rules: Dict = None):
        if self.rng is not None:
            return self.rng
        seed = None
        if rules:
            seed = rules.get("rng_seed", None)
        if seed is not None:
            r = random.Random(seed)
            # store it so subsequent calls are consistent
            self.rng = r
            return r
        # return a Random instance (not the module) for consistent API
        return random.Random()
    
    def build_initial_burro_state_from_json(initial_state_dict: Optional[Dict[str, Any]]) -> "BurroState":
        """
        Construye un BurroState a partir del bloque 'initial_state' del JSON.
        No asigna nodo (node=None); espera que el usuario lo elija luego.
        """
        init = initial_state_dict or {}

        energy = float(init.get("initialEnergyPercent", init.get("initial_energy_percent", 100)))
        health = init.get("healthState", init.get("health", "Excellent"))
        grass = float(init.get("grassKg", init.get("grass_kg", 0.0)))
        current_age = float(init.get("currentAgeYears", init.get("current_age_years", 0.0)))
        death_age = float(init.get("deathAgeYears", init.get("death_age_years", 100.0)))
        life_left = max(0.0, death_age - current_age)

        return BurroState(
            node=None,
            energy_pct=energy,
            health=health,
            grass_kg=grass,
            age_years=current_age,
            life_years_left=life_left,
            meta={"initial_state_raw": init}
        )