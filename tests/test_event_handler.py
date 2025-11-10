import pytest
import networkx as nx
from src.gui.event_handler import EventHandler, MODE_NONE

@pytest.fixture
def simple_handler():
    G = nx.Graph()
    G.add_node(1, coordinates={"x": 0, "y": 0}, radius=1.0)
    G.add_node(2, coordinates={"x": 1, "y": 1}, radius=1.0)
    G.add_edge(1, 2, yearsCost=5, distanceLy=10)

    pos = {1: (0, 0), 2: (1, 1)}
    radii = {1: 1.0, 2: 1.0}
    handler = EventHandler(graph_model=None, Gnx=G, pos=pos, radii=radii)
    return handler

def test_reset_mode_clears_state(simple_handler):
    h = simple_handler
    h.selected_origin = 1
    h.selected_target = 2
    h.route_origin = 1
    h.route_target = 2
    h.current_path = [1, 2]
    h.mode = 99  # cualquier modo activo

    h.reset_mode()

    assert h.selected_origin is None
    assert h.selected_target is None
    assert h.route_origin is None
    assert h.route_target is None
    assert h.current_path is None
    assert h.mode == MODE_NONE