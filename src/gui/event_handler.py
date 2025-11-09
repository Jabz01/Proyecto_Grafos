# src/gui/event_handler.py
import threading
from typing import Optional, Tuple, List, Dict
import networkx as nx
import matplotlib.pyplot as plt
import threading

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
    - Gnx: networkx.Graph compartido (vista devuelta por graph_model.ToNetworkX())
    - pos, radii: mapas de posiciones y radios (coordenadas en la misma escala que pos)
    - redraw_callback: función para redibujar la vista
    - set_instruction_callback: función para mostrar texto instructivo en la figura
    - fig: figura matplotlib (necesaria si el handler crea widgets en el futuro)
    """
    def __init__(self, graph_model, Gnx: nx.Graph, pos: Dict[int, Tuple[float,float]], radii: Dict[int, float],
                 redraw_callback=None, set_instruction_callback=None, fig: plt.Figure = None):
        self.graph_model = graph_model
        # inicializar referencias con la vista que nos pasan (se sincronizará si el modelo cambia)
        self.G = Gnx
        self.pos = pos
        self.radii = radii
        self._redraw = redraw_callback or (lambda: None)
        self._set_instruction = set_instruction_callback or (lambda t: None)
        self.fig = fig
        self._state_lock = threading.RLock()

        # estado interactivo
        self.mode = MODE_NONE
        self.route_selection_stage = 0
        self.route_origin: Optional[int] = None
        self.route_target: Optional[int] = None
        self.current_path: Optional[List[int]] = None

        self._clear_timer = None

    # ------------------ sincronización central ------------------
    def _pick_node_at_display(self, xdata: float, ydata: float) -> Optional[int]:
        """
        Devuelve el id del nodo cuyo marcador en pantalla contiene el punto (xdata,ydata).
        Calcula el radio visual a partir del node_size usado en la vista (node_size = BASE_NODE_SIZE*radius*scale).
        """
        try:
            # transformador data -> display (pixels)
            trans = self.fig.axes[0].transData if (self.fig and self.fig.axes) else None
            if trans is None:
                trans = self.fig.canvas.renderer.transform if hasattr(self.fig.canvas, "renderer") else None
            # fallback simple: usar transData desde matplotlib global (plt.gca)
            if trans is None:
                trans = plt.gca().transData

            click_px = trans.transform((xdata, ydata))

            # recuperar dpi para convertir puntos -> pixels
            dpi = self.fig.dpi if self.fig is not None else plt.gcf().dpi

            # calcular marker area (points^2) como en universe: node_size = BASE_NODE_SIZE * radius * scale
            # Reusar la misma BASE_NODE_SIZE que usas en universe (500.0)
            BASE_NODE_SIZE = 500.0

            best = None
            for n, (nx_, ny_) in self.pos.items():
                node_px = trans.transform((nx_, ny_))
                # determinar node_size (points^2) usado en el dibujo:
                radius = self.radii.get(n, 1.0)
                hyper = False
                try:
                    hyper = bool(self.G.nodes[n].get("hypergiant", False))
                except Exception:
                    pass
                scale = 1.6 if hyper else 1.0
                marker_area_points2 = BASE_NODE_SIZE * radius * scale
                # matplotlib marker radius in points = sqrt(area)/2
                marker_r_points = (marker_area_points2 ** 0.5) / 2.0
                # convertir points -> pixels: 1 point = dpi/72 pixels
                marker_r_px = marker_r_points * (dpi / 72.0)
                dx = click_px[0] - node_px[0]
                dy = click_px[1] - node_px[1]
                dist_px = (dx*dx + dy*dy) ** 0.5
                if dist_px <= marker_r_px:
                    best = n
                    break
            return best
        except Exception:
            # fallback: usar nearest_node_by_radius con mayor threshold
            return nearest_node_by_radius(self.pos, self.radii, xdata, ydata, threshold_mult=1.6)
    def _sync_from_model(self):
        """
        Refresca self.G, self.pos y self.radii desde el graph_model.
        No sobreescribe coordenadas existentes salvo que la vista nueva las contenga.
        """
        try:
            new_G = self.graph_model.ToNetworkX()
        except Exception as exc:
            print(f"[EventHandler] _sync_from_model: ToNetworkX() falló: {exc}")
            return

        # si punteros distintos, reemplazamos la referencia
        if id(new_G) != id(self.G):
            # para depuración durante desarrollo
            print(f"[EventHandler] sincronizando vista NetworkX (old id={id(self.G)} new id={id(new_G)})")
            self.G = new_G

        # actualizar pos/radii conservando valores existentes cuando falte info en la vista
        try:
            for n in list(self.pos.keys()):
                if n in self.G.nodes:
                    coords = self.G.nodes[n].get("coordinates")
                    if coords and ("x" in coords) and ("y" in coords):
                        self.pos[n] = (coords["x"], coords["y"])
                    # radius: si la vista trae radius lo usamos, si no, preservamos el existente
                    if "radius" in self.G.nodes[n]:
                        try:
                            self.radii[n] = float(self.G.nodes[n].get("radius", self.radii.get(n, 1.0)))
                        except Exception:
                            # mantener el valor previo si conversión falla
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

    # ------------------ evento de click ------------------

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
                self.route_origin = node
                self.route_selection_stage = 2
                self._set_instruction("Seleccionar estrella de destino")
                self._redraw()
                return
            elif self.route_selection_stage == 2:
                self.route_target = node
                if self.route_origin == self.route_target:
                    with self._state_lock:
                        self.current_path = [self.route_origin]
                    self._set_instruction("Origen y destino iguales")
                    self._start_clear_instruction_timer(2.0)
                    self.route_selection_stage = 0
                    self.mode = MODE_NONE
                    self._redraw()
                    return

                # Lanzar cálculo de ruta en background para no bloquear la UI
                origin = self.route_origin
                target = self.route_target

                def _compute_route_worker():
                    try:
                        # usar grafo filtrado (copia) para evitar que shortest_path mutile la vista
                        Gf = filtered_graph_nx(self.G)
                        res = shortest_path_dijkstra(Gf, origin, target, weight="yearsCost")
                        if res is None:
                            # no path
                            with self._state_lock:
                                self.current_path = None
                            # actualizar instrucciones y pedir redraw seguro
                            self._set_instruction("No hay ruta entre origen y destino")
                            self._start_clear_instruction_timer(2.0)
                        else:
                            path, total = res
                            with self._state_lock:
                                self.current_path = path
                            # usar formato ligero para instrucción
                            self._set_instruction(f"Ruta encontrada (cost={total})")
                            self._start_clear_instruction_timer(2.0)
                    except Exception as exc:
                        # logging mínimo para depuración
                        print(f"[EventHandler] route worker failed: {exc}")
                        with self._state_lock:
                            self.current_path = None
                        self._set_instruction("Error al calcular ruta")
                        self._start_clear_instruction_timer(2.0)
                    finally:
                        # garantizar que la UI se redibuje desde el hilo de eventos de matplotlib
                        try:
                            if self.fig is not None and hasattr(self.fig.canvas, "draw_idle"):
                                self.fig.canvas.draw_idle()
                            else:
                                # fallback: llamar a redraw (puede ser menos seguro si no estamos en hilo UI)
                                self._redraw()
                        except Exception:
                            try:
                                self._redraw()
                            except Exception:
                                pass

                # cambiar estado interactivo y lanzar thread
                self.route_selection_stage = 0
                self.mode = MODE_NONE
                worker = threading.Thread(target=_compute_route_worker, daemon=True)
                worker.start()
                return
    # ------------------ bloqueo de arista ------------------

    def _handle_block_click(self, x: float, y: float):
        avg_radius = (sum(self.radii.values()) / len(self.radii)) if self.radii else 1.0
        threshold = max(0.25, avg_radius * 0.6)
        pick = pick_nearest_edge(x, y, self.G.edges(), self.pos, threshold)
        if pick is None:
            return
        (u, v), dist = pick

        # Intentamos alternar el estado en el modelo (GraphModel es la fuente de verdad)
        try:
            # ToggleEdgeBlocked(u, v) debe devolver el nuevo estado booleano
            new_state = self.graph_model.ToggleEdgeBlocked(u, v)
            # asegurar que la vista se sincronice con lo que el modelo tiene ahora
            self._sync_from_model()
        except Exception as exc:
            # Log corto para depuración en desarrollo
            print(f"[EventHandler] ToggleEdgeBlocked failed for ({u},{v}): {exc}")
            # Fallback razonable: mutar localmente para mantener la UX responsiva
            try:
                cur = self.G[u][v].get("blocked", False)
                self.G[u][v]["blocked"] = not cur
            except Exception:
                pass

        # invalidar ruta calculada (si existía) y redibujar
        self.current_path = None
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
                # preferir draw_idle para notificar al hilo de eventos
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