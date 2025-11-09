# src/gui/ui_buttons.py
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from typing import Callable, Dict

def create_buttons(fig, callbacks: Dict[str, Callable]) -> Dict[str, Button]:
    """
    Crea botones y los asocia a callbacks.
    callbacks puede tener:
      - 'toggle_block_mode' -> fn()
      - 'compute_route' -> fn()
      - 'reset_mode' -> fn()
      - 'export' -> fn()  (opcional; no lo usamos pero está disponible)

    Devuelve un dict con los botones creados.
    """
    # Coordenadas pensadas para ocupar la esquina inferior izquierda
    ax_block = fig.add_axes([0.02, 0.02, 0.14, 0.06])
    ax_route = fig.add_axes([0.18, 0.02, 0.14, 0.06])
    ax_reset = fig.add_axes([0.34, 0.02, 0.14, 0.06])

    btn_block = Button(ax_block, "Modo: Bloquear")
    btn_route = Button(ax_route, "Calcular Ruta")
    btn_reset = Button(ax_reset, "Reiniciar modo")

    # estilo básico de los ejes de botones
    for ax in (ax_block, ax_route, ax_reset):
        ax.set_facecolor("#f0f0f0")

    # asociar callbacks si existen
    if 'toggle_block_mode' in callbacks:
        btn_block.on_clicked(lambda evt: callbacks['toggle_block_mode']())
    if 'compute_route' in callbacks:
        btn_route.on_clicked(lambda evt: callbacks['compute_route']())
    if 'reset_mode' in callbacks:
        btn_reset.on_clicked(lambda evt: callbacks['reset_mode']())

    return {
        "btn_block": btn_block,
        "btn_route": btn_route,
        "btn_reset": btn_reset
    }