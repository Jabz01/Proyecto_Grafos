# src/planner/beam_search.py
from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
import math
import heapq
import networkx as nx

# Importar los tipos/funciones de tu proyecto
from src.sim.burro_state import BurroState
from src.sim.travel import simulate_travel
from src.sim.visit import simulate_visit

@dataclass(frozen=True)
class _StateKey:
    node: int
    visited: Tuple[int, ...]
    life_rounded: float
    energy_rounded: float
    grass_rounded: float

def _make_key(s: BurroState) -> _StateKey:
    # Redondear para agrupar estados similares y reducir duplicados
    return _StateKey(
        node=s.node,
        visited=tuple(sorted(s.visited)) if hasattr(s, "visited") else (s.node,),
        life_rounded=round(s.life_years_left, 2),
        energy_rounded=round(s.energy_pct, 2),
        grass_rounded=round(s.grass_kg, 2),
    )

def _score_for_sort(state: BurroState) -> Tuple[int, float, float]:
    # primary: #visited, secondary: life left, tertiary: energy
    visited_count = len(state.visited) if hasattr(state, "visited") else 0
    return (visited_count, state.life_years_left, state.energy_pct)

def beam_search(
    start_state: BurroState,
    Gnx: nx.Graph,
    rules: Dict[str, Any],
    beam_width: int = 12,
    max_depth: int = 50,
    avoid_revisit: bool = True,
) -> Tuple[List[int], Dict[str, Any]]:
    """
    Beam search planner that attempts to maximize number of visited stars before burro dies.

    Returns:
      best_path: list of node ids visited in order
      meta: info dict with final_state, visited_count, expansions, depth_reached, reason_stop
    """
    # Defensive checks
    if start_state.life_years_left <= 0:
        return ([], {"reason_stop": "start_dead", "final_state": start_state, "visited_count": 0})

    # Ensure start_state has visited set attribute
    if not hasattr(start_state, "visited"):
        start_state.visited = set([start_state.node])
    else:
        start_state.visited = set(start_state.visited) | {start_state.node}

    # Beam elements: (-score_tuple, expansions_order, state, path)
    # We'll use a max-heap by converting score to tuple; but heapq is min-heap so we push negatives where needed.
    beam: List[Tuple[Tuple[int, float, float], int, BurroState, List[int]]] = []
    expansions = 0
    order = 0

    # Initial
    initial_score = _score_for_sort(start_state)
    beam.append((initial_score, order, start_state, [start_state.node]))
    best_state = start_state
    best_path = [start_state.node]
    best_visited = len(start_state.visited)

    # Visited-state seen map for deduplication
    seen: Dict[_StateKey, float] = {}
    depth_reached = 0

    for depth in range(1, max_depth + 1):
        depth_reached = depth
        candidates: List[Tuple[Tuple[int, float, float], int, BurroState, List[int]]] = []

        for score, _, state, path in beam:
            # Expand neighbors
            u = state.node
            neighbors = list(Gnx.neighbors(u))
            for v in neighbors:
                # optionally skip revisits
                if avoid_revisit and v in state.visited:
                    continue

                # Find edge data (support for multigraphs not considered)
                edge_data = Gnx.get_edge_data(u, v) or {}
                # normalize years cost usage; prefer explicit 'yearsCost' else compute from distance if present
                e = dict(edge_data)
                # simulate travel
                state_copy = _clone_state(state)
                state_copy.node = u  # ensure correct
                state_after_travel, tev = simulate_travel(state_copy, e, rules)

                expansions += 1
                if _is_dead(state_after_travel):
                    # reached death during travel; record candidate end-state
                    # we still record as candidate to allow best selection from end states
                    new_path = path + [v]
                    candidates.append((_score_for_sort(state_after_travel), order + expansions, state_after_travel, new_path))
                    continue

                # arrive to v
                state_after_travel.node = v
                # prepare star attrs
                star_attrs = dict(Gnx.nodes[v])
                state_after_visit, vev = simulate_visit(state_after_travel, star_attrs, rules)

                new_path = path + [v]
                # update visited set
                if not hasattr(state_after_visit, "visited"):
                    state_after_visit.visited = set()
                state_after_visit.visited = set(state_after_visit.visited) | set(state.visited) | {v}

                # if died during visit, still consider as candidate final
                candidates.append((_score_for_sort(state_after_visit), order + expansions, state_after_visit, new_path))

        if not candidates:
            reason = "no_candidates"
            break

        # Deduplicate candidates: prefer better life/energy for same key
        unique_candidates: Dict[_StateKey, Tuple[Tuple[int, float, float], int, BurroState, List[int]]] = {}
        for sc, ord_idx, st, pth in candidates:
            key = _make_key(st)
            prev = unique_candidates.get(key)
            if prev is None:
                unique_candidates[key] = (sc, ord_idx, st, pth)
            else:
                # choose the one with higher score (sc is tuple)
                if sc > prev[0]:
                    unique_candidates[key] = (sc, ord_idx, st, pth)

        # Convert to list and sort by score descending
        uniq_list = list(unique_candidates.values())
        uniq_list.sort(key=lambda item: (item[0][0], item[0][1], item[0][2]), reverse=True)

        # Keep top beam_width
        beam = []
        for item in uniq_list[:beam_width]:
            beam.append(item)

        # Update best solution from current beam (prefer more visited)
        for sc, _, st, pth in beam:
            visited_count = len(st.visited)
            if visited_count > best_visited or (visited_count == best_visited and (st.life_years_left > best_state.life_years_left or st.energy_pct > best_state.energy_pct)):
                best_state = st
                best_path = pth
                best_visited = visited_count

        # Termination if all beam states are dead
        if all(_is_dead(st) for _, _, st, _ in beam):
            reason = "all_dead"
            break

    else:
        reason = "max_depth_reached"

    meta = {
        "final_state": best_state,
        "visited_count": best_visited,
        "expansions": expansions,
        "depth_reached": depth_reached,
        "reason_stop": reason,
    }
    return best_path, meta

# Helpers

def _clone_state(s: BurroState) -> BurroState:
    """
    Shallow clone preserving attributes used by beam_search.
    We attempt to use dataclass replace if available, else manual copy.
    """
    try:
        cloned = replace(s)
    except Exception:
        # fallback: construct new BurroState with expected fields
        cloned = BurroState(
            node=s.node,
            life_years_left=s.life_years_left,
            health=s.health,
            energy_pct=s.energy_pct,
            grass_kg=s.grass_kg,
        )
        # copy optional fields
        for attr in ("visited", "age_years"):
            if hasattr(s, attr):
                setattr(cloned, attr, getattr(s, attr))
    # ensure visited is a shallow copy
    if hasattr(s, "visited"):
        cloned.visited = set(s.visited)
    return cloned

def _is_dead(s: BurroState) -> bool:
    # Define death: life years <= 0 or health == 'Dead' or energy <= 0 and no grass and no life
    if getattr(s, "life_years_left", 1e9) <= 0:
        return True
    if getattr(s, "health", "").lower() == "dead":
        return True
    # energy 0 is not necessarily immediate death if life remains; but treat energy 0 + no grass as bad.
    return False