# src/gui/event_handler.py
import threading
from typing import Optional, Tuple, List, Dict, Callable
import networkx as nx
import matplotlib.pyplot as plt

from src.model.edge import pick_nearest_edge
from src.utils.visual import nearest_node_by_radius
from src.utils.graph_utils import filtered_graph_nx
from src.planner.dijkstra_planner import shortest_path_dijkstra
from src.gui.route_form import RouteForm

# constantes a nivel de módulo (usadas desde universe.py)
MODE_NONE = 0
MODE_BLOCK = 1
MODE_ROUTE_SELECT = 2

class EventHandler:
    """
    Controlador de interacción (GUI).
    - graph_model: dominio con ToggleEdgeBlocked si existe
    - Gnx: networkx.Graph compartido (vista devuelta por graph_model.ToNetworkX())
    - pos, radii: mapas de posiciones y radios (coordenadas en la misma escala que pos)
    - redraw_callback: función para redibujar la vista
    - set_instruction_callback: función para mostrar texto instructivo en la figura
    - fig: figura matplotlib (necesaria si el handler crea widgets en el futuro)
    """
    def __init__(self, graph_model, Gnx: nx.Graph, pos: Dict[int, Tuple[float,float]], radii: Dict[int, float],
                 redraw_callback: Optional[Callable[[], None]] = None,
                 set_instruction_callback: Optional[Callable[[str], None]] = None,
                 fig: Optional[plt.Figure] = None):
        self.graph_model = graph_model
        self.G = Gnx
        self.pos = pos
        self.radii = radii
        self._redraw = redraw_callback or (lambda: None)
        self._set_instruction = set_instruction_callback or (lambda t: None)
        self.fig = fig

        # locks / estado
        self._state_lock = threading.RLock()

        # interacción
        self.mode = MODE_NONE
        self.route_selection_stage = 0
        self.route_origin: Optional[int] = None
        self.route_target: Optional[int] = None
        self.current_path: Optional[List[int]] = None

        # selección / propuesta / formulario
        self.selected_origin: Optional[int] = None
        self.selected_target: Optional[int] = None
        self.proposed_path: Optional[List[int]] = None
        self.proposed_sums: Optional[dict] = None  # {"sum_ly": float, "sum_years": float}
        self.form: Optional[RouteForm] = None

        self._clear_timer = None

    # ------------------ helpers visual / sync ------------------

    def _pick_node_at_display(self, xdata: float, ydata: float) -> Optional[int]:
        """Pick node if click falls anywhere inside its visual marker (pixels)."""
        try:
            ax = self.fig.axes[0] if (self.fig and self.fig.axes) else plt.gca()
            trans = ax.transData
            click_px = trans.transform((xdata, ydata))
            dpi = self.fig.dpi if self.fig is not None else plt.gcf().dpi
            BASE_NODE_SIZE = 500.0

            for n, (nx_, ny_) in self.pos.items():
                node_px = trans.transform((nx_, ny_))
                radius = self.radii.get(n, 1.0)
                hyper = bool(self.G.nodes[n].get("hypergiant", False)) if n in self.G.nodes else False
                scale = 1.6 if hyper else 1.0
                area_pts2 = BASE_NODE_SIZE * radius * scale
                r_pts = (area_pts2 ** 0.5) / 2.0
                r_px = r_pts * (dpi / 72.0)
                dx = click_px[0] - node_px[0]
                dy = click_px[1] - node_px[1]
                if (dx*dx + dy*dy) ** 0.5 <= r_px:
                    return n
            return None
        except Exception:
            return nearest_node_by_radius(self.pos, self.radii, xdata, ydata, threshold_mult=1.6)

    def _sync_from_model(self):
        """Refresca self.G, self.pos y self.radii desde el graph_model."""
        try:
            new_G = self.graph_model.ToNetworkX()
        except Exception as exc:
            print(f"[EventHandler] _sync_from_model: ToNetworkX() falló: {exc}")
            return

        if id(new_G) != id(self.G):
            self.G = new_G

        try:
            for n in list(self.pos.keys()):
                if n in self.G.nodes:
                    coords = self.G.nodes[n].get("coordinates")
                    if coords and ("x" in coords) and ("y" in coords):
                        self.pos[n] = (coords["x"], coords["y"])
                    if "radius" in self.G.nodes[n]:
                        try:
                            self.radii[n] = float(self.G.nodes[n].get("radius", self.radii.get(n, 1.0)))
                        except Exception:
                            pass
        except Exception as exc:
            print(f"[EventHandler] _sync_from_model: fallo al sincronizar pos/radii: {exc}")

    # ------------------ API pública (botones) ------------------

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
        """Comienza la selección de origen y destino."""
        self.mode = MODE_ROUTE_SELECT
        self.route_selection_stage = 1
        self.route_origin = None
        self.route_target = None
        self.current_path = None
        # limpiar propuestas previas
        self.proposed_path = None
        self.proposed_sums = None
        self.selected_origin = None
        self.selected_target = None
        self._set_instruction("Seleccionar estrella de origen")
        self._redraw()

    def reset_mode(self):
        self.mode = MODE_NONE
        self.route_selection_stage = 0
        self.route_origin = None
        self.route_target = None
        self.current_path = None
        self.selected_origin = None
        self.selected_target = None
        self.proposed_path = None
        self.proposed_sums = None
        self._set_instruction("")
        self._redraw()

    # ------------------ eventos de interacción ------------------

    def on_click(self, event):
        if event.xdata is None or event.ydata is None:
            return

        if self.mode == MODE_BLOCK:
            self._handle_block_click(event.xdata, event.ydata)
            return

        if self.mode == MODE_ROUTE_SELECT and self.route_selection_stage in (1, 2):
            node = self._pick_node_at_display(event.xdata, event.ydata)
            if node is None:
                return

            if self.route_selection_stage == 1:
                # seleccionar origen
                self.route_origin = node
                self.selected_origin = node
                self.route_selection_stage = 2
                self._set_instruction("Seleccionar estrella de destino")
                self._redraw()
                return

            elif self.route_selection_stage == 2:
                # seleccionar destino y proponer ruta
                self.route_target = node
                self.selected_target = node

                if self.route_origin == self.route_target:
                    with self._state_lock:
                        self.current_path = [self.route_origin]
                    self._set_instruction("Origen y destino iguales")
                    self._start_clear_instruction_timer(2.0)
                    self.route_selection_stage = 0
                    self.mode = MODE_NONE
                    self._redraw()
                    return

                origin = self.route_origin
                target = self.route_target

                # lanzar worker que calcula propuesta y abre el formulario cuando termine
                def _worker():
                    try:
                        Gf = filtered_graph_nx(self.G)
                        res = shortest_path_dijkstra(Gf, origin, target, weight="yearsCost")
                        if res is None:
                            with self._state_lock:
                                self.proposed_path = None
                                self.proposed_sums = {"sum_ly": 0.0, "sum_years": 0.0}
                            self._set_instruction("No hay ruta entre origen y destino")
                            self._start_clear_instruction_timer(2.0)
                        else:
                            path, total = res
                            sum_years = 0.0
                            sum_ly = 0.0
                            for a, b in zip(path[:-1], path[1:]):
                                attrs = self.G.get_edge_data(a, b) or {}
                                if attrs.get("blocked"):
                                    continue
                                try:
                                    sum_years += float(attrs.get("yearsCost", 0.0))
                                except Exception:
                                    pass
                                try:
                                    sum_ly += float(attrs.get("distanceLy", 0.0))
                                except Exception:
                                    pass
                            with self._state_lock:
                                self.proposed_path = path
                                self.proposed_sums = {"sum_ly": sum_ly, "sum_years": sum_years}

                            origin_label = self.G.nodes[origin].get("label", str(origin))
                            target_label = self.G.nodes[target].get("label", str(target))
                            burro_info = {"estado": "pendiente"}

                            # abrir formulario en hilo de eventos
                            try:
                                # crear form si no existe
                                if self.form is None:
                                    self.form = RouteForm(self.fig,
                                                          on_compute=self.finalize_route_calculation,
                                                          on_close=self.close_form)
                                # show debe ejecutarse en hilo principal; draw_idle garantiza seguridad
                                self.form.show(origin_label, target_label, sum_ly, sum_years, burro_info)
                            except Exception as exc:
                                print(f"[EventHandler] fallo abriendo formulario: {exc}")

                    except Exception as exc:
                        print(f"[EventHandler] route proposal worker failed: {exc}")
                        with self._state_lock:
                            self.proposed_path = None
                            self.proposed_sums = {"sum_ly": 0.0, "sum_years": 0.0}
                        self._set_instruction("Error al calcular propuesta de ruta")
                        self._start_clear_instruction_timer(2.0)
                    finally:
                        try:
                            if self.fig is not None and hasattr(self.fig.canvas, "draw_idle"):
                                self.fig.canvas.draw_idle()
                            else:
                                self._redraw()
                        except Exception:
                            try:
                                self._redraw()
                            except Exception:
                                pass

                self.route_selection_stage = 0
                self.mode = MODE_NONE
                threading.Thread(target=_worker, daemon=True).start()
                return

    # ------------------ bloqueo de arista ------------------

    def _handle_block_click(self, x: float, y: float):
        avg_radius = (sum(self.radii.values()) / len(self.radii)) if self.radii else 1.0
        threshold = max(0.25, avg_radius * 0.6)
        pick = pick_nearest_edge(x, y, self.G.edges(), self.pos, threshold)
        if pick is None:
            return
        (u, v), dist = pick

        try:
            new_state = self.graph_model.ToggleEdgeBlocked(u, v)
            self._sync_from_model()
        except Exception as exc:
            print(f"[EventHandler] ToggleEdgeBlocked failed for ({u},{v}): {exc}")
            try:
                cur = self.G[u][v].get("blocked", False)
                self.G[u][v]["blocked"] = not cur
            except Exception:
                pass

        self.current_path = None
        self._redraw()

    # ------------------ formulario / confirmación ------------------

    def _open_route_form(self):
        if not self.proposed_path or not self.proposed_sums:
            return
        origin = self.selected_origin
        target = self.selected_target
        if origin is None or target is None:
            return
        origin_label = self.G.nodes[origin].get("label", str(origin))
        target_label = self.G.nodes[target].get("label", str(target))
        burro_info = {"estado": "pendiente"}
        if self.form is None:
            self.form = RouteForm(self.fig,
                                  on_compute=self.finalize_route_calculation,
                                  on_close=self.close_form)
        self.form.show(origin_label, target_label, self.proposed_sums["sum_ly"], self.proposed_sums["sum_years"], burro_info)

    def close_form(self):
        if self.form:
            try:
                self.form.hide()
            except Exception:
                pass
        # no aplicar la ruta; mantener selección visible
        self._redraw()

    def finalize_route_calculation(self):
        """Callback cuando el usuario pulsa 'Calcular' en el formulario."""
        with self._state_lock:
            if not self.proposed_path:
                self._set_instruction("No hay ruta propuesta")
                self._start_clear_instruction_timer(2.0)
                return
            self.current_path = list(self.proposed_path)

        # cerrar formulario y confirmar
        self.close_form()
        self._set_instruction("Ruta confirmada")
        self._start_clear_instruction_timer(2.0)
        self._redraw()

    # ------------------ temporizador para limpiar instrucciones ------------------

    def _start_clear_instruction_timer(self, seconds: float):
        if self._clear_timer and self._clear_timer.is_alive():
            try:
                self._clear_timer.cancel()
            except Exception:
                pass
        def _clear():
            try:
                self._set_instruction("")
                if self.fig is not None and hasattr(self.fig.canvas, "draw_idle"):
                    try:
                        self.fig.canvas.draw_idle()
                    except Exception:
                        self._redraw()
                else:
                    self._redraw()
            except Exception:
                pass
        t = threading.Timer(seconds, _clear)
        t.daemon = True
        t.start()
        self._clear_timer = t