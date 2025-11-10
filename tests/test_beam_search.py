# tests/test_beam_search.py  (añadir o reemplazar test simplificado)
import networkx as nx
from src.utils.parser import BuildParserOutputFromJson
from src.planner.beam_search import beam_search
from src.sim.burro_state import BurroState
from src.sim.travel import simulate_travel
from src.sim.visit import simulate_visit

SIMPLE_DATA = {
    "meta": {"simulationSeed": 42},
    "stars": [
        {"id": 1, "coordinates": {"x": 0, "y": 0}},
        {"id": 2, "coordinates": {"x": 1, "y": 0}},
        {"id": 3, "coordinates": {"x": 2, "y": 0}},
        {"id": 4, "coordinates": {"x": 3, "y": 0}}
    ],
    "edges": [
        {"u": 1, "v": 2, "distanceLy": 1.0},
        {"u": 2, "v": 3, "distanceLy": 1.0},
        {"u": 3, "v": 4, "distanceLy": 1.0}
    ]
}

def _graph_from_parsed(parsed):
    G = nx.Graph()
    for s in parsed["stars"]:
        G.add_node(s["id"], **dict(s))
    for e in parsed["edges"]:
        G.add_edge(e["u"], e["v"], **e)
    return G

def _print_header():
    print("=" * 64)
    print("STEP | ACTION  | NODE | ENERGY(%) | LIFE(y)  | GRASS(kg) | NOTE")
    print("-" * 64)

def _print_simple(step, action, node, state, note=""):
    print(f"{step:4d} | {action:7s} | {node:4d} | {state.energy_pct:9.3f} | {state.life_years_left:7.3f} | {state.grass_kg:9.3f} | {note}")

def _clone_state(s):
    return BurroState(
        node=s.node,
        life_years_left=s.life_years_left,
        health=s.health,
        energy_pct=s.energy_pct,
        grass_kg=s.grass_kg,
    )

def test_beam_search_simple_trace():
    parsed, warnings, errors = BuildParserOutputFromJson(SIMPLE_DATA)
    assert not errors
    G = _graph_from_parsed(parsed)

    rules = {
        "timeAndLife": {"distanceLyToYearsFactor": 0.05, "useDistanceAsYearsOfLifeLoss": True, "maxFractionOfStayForEating": 0.5},
        "energy": {"energyConsumptionPerLyPercent": 0.5, "energyLossPerInvestigationYearPercent": 0.2, "energyGainPerKgByHealthPercent": {"Excellent":5,"Good":3,"Bad":2,"NearDeath":1,"Dead":0}, "applyEnergyCap100": True},
        "feeding": {"eatOnlyIfEnergyBelowPercent": 50, "minKgPerEat": 0.1},
        "planning": {"heuristicDefaults": {"beamWidth": 6, "maxDepth": 10}}
    }

    init = parsed.get("initial_state", {"initialEnergyPercent":100,"currentAgeYears":0,"deathAgeYears":100,"grassKg":10,"healthState":"Good"})
    start = BurroState(
        node=1,
        life_years_left=init["deathAgeYears"] - init["currentAgeYears"],
        health=init.get("healthState","Good"),
        energy_pct=init.get("initialEnergyPercent",100),
        grass_kg=init.get("grassKg",10),
    )

    path, meta = beam_search(start, G, rules, beam_width=6, max_depth=10)

    # Asserts básicos
    assert isinstance(path, list)
    assert meta["visited_count"] == len(set(path))
    assert path[0] == 1

    # Imprimir traza simple
    print("\nSimple route trace from beam_search result:")
    _print_header()

    s = _clone_state(start)
    s.visited = {s.node}
    step = 0
    _print_simple(step, "START", s.node, s, "initial")

    for next_node in path[1:]:
        edge = G.get_edge_data(s.node, next_node) or {}
        before = _clone_state(s)

        s_travel, travel_events = simulate_travel(_clone_state(s), dict(edge), rules)
        step += 1
        note_travel = travel_events[0] if travel_events else ""
        _print_simple(step, "TRAVEL", next_node, s_travel, note_travel)

        if s_travel.life_years_left <= 0:
            s = s_travel
            break

        s_travel.node = next_node
        s_after, visit_events = simulate_visit(s_travel, dict(G.nodes[next_node]), rules)
        step += 1
        note_visit = visit_events[0] if visit_events else ""
        _print_simple(step, "VISIT", next_node, s_after, note_visit)

        s = s_after
        s.visited = getattr(s, "visited", set()) | {next_node}

        if s.life_years_left <= 0:
            break

    print("=" * 64)
    print("Meta:", {"path": path, "visited": meta["visited_count"], "reason": meta["reason_stop"]})