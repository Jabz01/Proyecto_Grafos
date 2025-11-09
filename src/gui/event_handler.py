# src/gui/event_handler.py
import threading
from typing import Optional, Tuple, List, Dict
import networkx as nx
import matplotlib.pyplot as plt

from src.model.edge import pick_nearest_edge
from src.utils.visual import nearest_node_by_radius
from src.utils.graph_utils import filtered_graph_nx
from src.planner.dijkstra_planner import shortest_path_dijkstra

# constantes a nivel de módulo (usadas desde universe.py)
MODE_NONE = 0
MODE_BLOCK = 1
MODE_ROUTE_SELECT = 2

class EventHandler:
    """
    Controlador de interacción (GUI).
    - graph_model: dominio con ToggleEdgeBlocked si existe
    - Gnx: networkx.Graph compartido
    - pos, radii: mapas de posiciones y radios
    - redraw_callback: función para redibujar la vista
    - set_instruction_callback: función para mostrar texto instructivo en la figura
    - fig: figura matplotlib (necesaria si el handler crea widgets en el futuro)
    """
    def __init__(self, graph_model, Gnx: nx.Graph, pos: Dict[int, Tuple[float,float]], radii: Dict[int, float],
                 redraw_callback, set_instruction_callback, fig: plt.Figure):
        self.graph_model = graph_model
        self.G = Gnx
        self.pos = pos
        self.radii = radii
        self._redraw = redraw_callback
        self._set_instruction = set_instruction_callback
        self.fig = fig

        # estado
        self.mode = MODE_NONE
        self.route_selection_stage = 0
        self.route_origin: Optional[int] = None
        self.route_target: Optional[int] = None
        self.current_path: Optional[List[int]] = None

        self._clear_timer = None

    # API pública usada por los botones
    def toggle_block_mode(self):
        self.mode = MODE_BLOCK if self.mode != MODE_BLOCK else MODE_NONE
        self.route_selection_stage = 0
        self.route_origin = None
        self.route_target = None
        self.current_path = None
        title = "Modo: Bloquear aristas (clic sobre arista)" if self.mode == MODE_BLOCK else ""
        self._set_instruction(title)
        self._redraw()

    def start_route_selection(self):
        self.mode = MODE_ROUTE_SELECT
        self.route_selection_stage = 1
        self.route_origin = None
        self.route_target = None
        self.current_path = None
        self._set_instruction("Seleccionar estrella de origen")
        self._redraw()

    def reset_mode(self):
        self.mode = MODE_NONE
        self.route_selection_stage = 0
        self.route_origin = None
        self.route_target = None
        self.current_path = None
        self._set_instruction("")
        self._redraw()

    # evento de click registrado en la figura
    def on_click(self, event):
        if event.xdata is None or event.ydata is None:
            return

        if self.mode == MODE_BLOCK:
            self._handle_block_click(event.xdata, event.ydata)
            return

        if self.mode == MODE_ROUTE_SELECT and self.route_selection_stage in (1, 2):
            node = nearest_node_by_radius(self.pos, self.radii, event.xdata, event.ydata, threshold_mult=0.9)
            if node is None:
                return
            if self.route_selection_stage == 1:
                self.route_origin = node
                self.route_selection_stage = 2
                self._set_instruction("Seleccionar estrella de destino")
                self._redraw()
                return
            elif self.route_selection_stage == 2:
                self.route_target = node
                if self.route_origin == self.route_target:
                    self.current_path = [self.route_origin]
                else:
                    # calcular ruta sobre grafo filtrado (sin blocked)
                    Gf = filtered_graph_nx(self.G)
                    res = shortest_path_dijkstra(Gf, self.route_origin, self.route_target, weight="yearsCost")
                    if res is None:
                        self.current_path = None
                        self._set_instruction("No hay ruta entre origen y destino")
                        self._start_clear_instruction_timer(2.0)
                    else:
                        path, total = res
                        self.current_path = path
                        self._set_instruction(f"Ruta encontrada (cost={total})")
                        self._start_clear_instruction_timer(2.0)
                self.route_selection_stage = 0
                self.mode = MODE_NONE
                self._redraw()
                return

    # bloqueo de arista: usa pick_nearest_edge del model.edge
    def _handle_block_click(self, x: float, y: float):
        avg_radius = (sum(self.radii.values()) / len(self.radii)) if self.radii else 1.0
        threshold = max(0.25, avg_radius * 0.6)
        pick = pick_nearest_edge(x, y, self.G.edges(), self.pos, threshold)
        if pick is None:
            return
        (u, v), dist = pick
        cur = self.G[u][v].get("blocked", False)
        self.G[u][v]["blocked"] = not cur
        # sincronizar con modelo de dominio si existe
        try:
            self.graph_model.ToggleEdgeBlocked(u, v, self.G[u][v]["blocked"])
        except Exception:
            pass
        self.current_path = None
        self._redraw()

    # temporizador para limpiar instrucciones
    def _start_clear_instruction_timer(self, seconds: float):
        if self._clear_timer and self._clear_timer.is_alive():
            try:
                self._clear_timer.cancel()
            except Exception:
                pass
        def _clear():
            try:
                self._set_instruction("")
                self._redraw()
            except Exception:
                pass
        t = threading.Timer(seconds, _clear)
        t.daemon = True
        t.start()
        self._clear_timer = t