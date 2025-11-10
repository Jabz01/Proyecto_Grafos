# tests/test_event_handler_flow.py
import pytest
import networkx as nx
from src.gui.event_handler import EventHandler
from src.gui.route_form import RouteForm
import matplotlib.pyplot as plt

@pytest.fixture
def setup_handler_with_form():
    G = nx.Graph()
    G.add_node(1, label="Sol", coordinates={"x": 0, "y": 0}, radius=1.0)
    G.add_node(2, label="Alpha Centauri", coordinates={"x": 1, "y": 1}, radius=1.0)
    G.add_edge(1, 2, yearsCost=4.5, distanceLy=10.0)

    pos = {1: (0, 0), 2: (1, 1)}
    radii = {1: 1.0, 2: 1.0}
    fig = plt.figure()

    handler = EventHandler(graph_model=None, Gnx=G, pos=pos, radii=radii, fig=fig)
    form = RouteForm(fig, on_compute=handler.finalize_route_calculation, on_close=handler.close_form)
    handler.form = form

    return handler, form

def test_full_route_flow(setup_handler_with_form):
    handler, form = setup_handler_with_form

    # Simular selección
    handler.selected_origin = 1
    handler.selected_target = 2
    handler.route_origin = 1
    handler.route_target = 2

    # Simular propuesta de ruta
    handler.proposed_path = [1, 2]
    handler.proposed_sums = {"sum_ly": 10.0, "sum_years": 4.5}

    # Mostrar formulario con datos iniciales
    form.show("Sol", "Alpha Centauri", sum_ly=None, sum_years=None, factor=0.1)

    # Confirmar ruta
    handler.finalize_route_calculation()

    # Verificar que la ruta fue aplicada
    assert handler.current_path == [1, 2]

    # Verificar que el formulario se actualizó con los valores reales
    texts = [t.get_text() for t in form._texts]
    assert any("Años luz total: 10" in t for t in texts)
    assert any("Años de costo" in t and "4.5" in t for t in texts)

    # Verificar que el botón fue deshabilitado
    assert form.btn_compute.label.get_text() == "Calculado"