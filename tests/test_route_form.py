import matplotlib.pyplot as plt
from src.gui.route_form import RouteForm

def test_form_shows_desconocido_initially():
    fig = plt.figure()
    form = RouteForm(fig, on_compute=lambda: None, on_close=lambda: None)

    form.show("Sol", "Alpha Centauri", sum_ly=None, sum_years=None, burro_info=None, factor=0.05)

    texts = [t.get_text() for t in form._texts]
    assert any("Desconocido" in t for t in texts)
    assert any("Origen: Sol" in t for t in texts)
    assert any("Destino: Alpha Centauri" in t for t in texts)