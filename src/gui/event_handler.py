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
from src.sim.run_simulation import simulate_path
from src.sim.burro_state import BurroState
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

        self._block_mode_locked = False
        self._route_worker_active = False

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
        
        initial_state_dict = self.graph_model.options.params.get("initial_state", {})
        self.burro_state = BurroState.build_initial_burro_state_from_json(initial_state_dict)
        try:
            initial_state_dict = self.graph_model.options.params.get("initial_state", {})
            print("[DEBUG] JSON recibido para estado inicial:", initial_state_dict)
            self.burro_state = BurroState.build_initial_burro_state_from_json(initial_state_dict)
        except Exception as e:
            print("[ERROR] No se pudo cargar el estado inicial del burro:", e)
            self.burro_state = None

        self._tooltip_texts = []
        self._tooltip_box = None
        self._tooltip_visible = False
        if self.fig is not None and hasattr(self.fig.canvas, "mpl_connect"):
            try:
                self.fig.canvas.mpl_connect('motion_notify_event', self.on_motion)
            except Exception:
                pass
        


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
        """
        Solo permitir entrar/salir de MODO_BLOCK cuando estemos en modo por defecto (MODE_NONE)
        y no haya bloqueo impuesto por un proceso de selección/cálculo.
        """
        # si hay un bloqueo explícito por proceso en curso, ignorar
        if getattr(self, "_block_mode_locked", False):
            try:
                self._set_instruction("No puede bloquear aristas durante selección o cálculo de ruta")
                self._start_clear_instruction_timer(1.5)
            except Exception:
                pass
            return

        # permitir toggle únicamente si estamos en modo por defecto (evita cambiar desde otros modos)
        if self.mode != MODE_NONE:
            try:
                self._set_instruction("Cambie a modo normal antes de bloquear aristas")
                self._start_clear_instruction_timer(1.5)
            except Exception:
                pass
            return

        # Toggle real
        self.mode = MODE_BLOCK if self.mode != MODE_BLOCK else MODE_NONE
        # al entrar a bloqueo, limpiamos cualquier selección para evitar confusiones
        if self.mode == MODE_BLOCK:
            self.route_selection_stage = 0
            self.route_origin = None
            self.route_target = None
            self.selected_origin = None
            self.selected_target = None
            # no tocamos current_path (si hay ruta confirmada, permanece visible)
            title = "Modo: Bloquear aristas (clic sobre arista)"
        else:
            title = ""
        self._set_instruction(title)
        self._redraw()
    def start_route_selection(self):
        # limpiar selecciones previas para evitar colores colgantes
        with self._state_lock:
            self.selected_origin = None
            self.selected_target = None
            self.route_origin = None
            self.route_target = None
            self.proposed_path = None
            self.proposed_sums = None

        # bloquear entrada a modo bloquear mientras dura el flujo de selección/cálculo
        self._block_mode_locked = True

        # salir de modo bloqueo si estuviera activo
        if self.mode == MODE_BLOCK:
            self.mode = MODE_NONE

        self.mode = MODE_ROUTE_SELECT
        self.route_selection_stage = 1
        self.current_path = None
        self._set_instruction("Seleccionar estrella de origen")
        self._redraw()
        
    def reset_mode(self):
        """
        Reinicia el modo: cierra/oculta el formulario, restaura botón calcular,
        borra selecciones y rutas confirmadas, y vuelve a estado por defecto.
        """
        # cerrar y restaurar form si existe
        try:
            if self.form:
                try:
                    self.form.hide()
                except Exception:
                    pass
                try:
                    self.form.reset_compute_button()
                except Exception:
                    pass
        except Exception:
            pass

        with self._state_lock:
            self.mode = MODE_NONE
            self.route_selection_stage = 0
            self.route_origin = None
            self.route_target = None
            self.selected_origin = None
            self.selected_target = None
            self.proposed_path = None
            self.proposed_sums = None
            self.current_path = None

            # liberar bloqueos si hubiera
            self._block_mode_locked = False
            self._route_worker_active = False

        self._set_instruction("")
        try:
            self._redraw()
        except Exception:
            pass
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
                # seleccionar destino y mostrar color inmediatamente
                self.route_target = node
                self.selected_target = node

                # limpiar la instrucción YA que el usuario seleccionó el destino
                try:
                    self._set_instruction("")   # desaparece el texto "Seleccionar estrella de destino"
                except Exception:
                    pass

                # forzar redraw para que el destino cambie de color de inmediato
                try:
                    self._redraw()
                except Exception:
                    pass

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

                # worker que prepara la propuesta (path + sumas) pero NO muestra las sumas en el form
                def _worker():
                    self._route_worker_active = True


                    try:
                        Gf = filtered_graph_nx(self.G)
                        res = shortest_path_dijkstra(Gf, origin, target, weight="yearsCost")
                        if res is None:
                            with self._state_lock:
                                self.proposed_path = None
                                self.proposed_sums = {"sum_ly": 0.0, "sum_years": 0.0}
                                # reset selections/colors
                                self.selected_origin = None
                                self.selected_target = None
                                self.route_origin = None
                                self.route_target = None
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

                            # labels para el formulario
                            origin_label = self.G.nodes[origin].get("label", str(origin))
                            target_label = self.G.nodes[target].get("label", str(target))

                            # obtener factor desde el modelo (fallback a 0.05)
                            try:
                                factor = float(getattr(self.graph_model, "options").params.get("distanceLyToYearsFactor", 0.05))
                            except Exception:
                                try:
                                    factor = float(getattr(self.graph_model, "options").get("params", {}).get("distanceLyToYearsFactor", 0.05))
                                except Exception:
                                    factor = 0.05

                            # abrimos el formulario PERO pasando sumas como None para que muestren "Desconocido"
                            burro_info = {"estado": "pendiente"}
                            try:
                                if self.form is None:
                                    self.form = RouteForm(self.fig,
                                                        on_compute=self.finalize_route_calculation,
                                                        on_close=self.close_form)
                                # show recibe sum_ly/sum_years opcionales; pasamos None para que muestre "Desconocido"
                                burro_before = self.burro_state
                                burro_info = {
                                    "before": burro_before,
                                    "after": None  # aún no se ha calculado
                                }
                                self.form.show(origin_label, target_label, None, None, burro_info, factor=factor)

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
                        self._route_worker_active = False
                        self._block_mode_locked = False
                        with self._state_lock:
                            if getattr(self, "proposed_path", None) is None:
                                self.selected_origin = None
                                self.selected_target = None
                                self.route_origin = None
                                self.route_target = None
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

                # finalizar selección localmente y lanzar worker
                self.route_selection_stage = 0
                self.mode = MODE_NONE
                threading.Thread(target=_worker, daemon=True).start()
                return
                
    # ----------------- bloqueo de arista ------------------

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
        """
        Cierra/oculta el formulario.
        - Restaura el botón 'Calcular' para futuras operaciones.
        - Si la ruta NO fue confirmada (no hay current_path), reinicia selección y colores.
        """
        try:
            if self.form:
                try:
                    self.form.hide()
                except Exception:
                    pass
                try:
                    # restaurar botón para la próxima vez que se abra el form
                    self.form.reset_compute_button()
                except Exception:
                    pass
        except Exception:
            pass

        # Si no se ha confirmado la ruta, limpiar selección para resetear colores
        with self._state_lock:
                self.selected_origin = None
                self.selected_target = None
                self.route_origin = None
                self.route_target = None
                self.current_path = None
                self.proposed_path = None
                self.proposed_sums = None

        # forzar redraw para que los colores vuelvan al estado base
        try:
            self._redraw()
        except Exception:
            pass

    def finalize_route_calculation(self):
        """Callback cuando el usuario pulsa 'Calcular' en el formulario.
        Mantiene el formulario visible y actualiza con los valores finales.
        """
        with self._state_lock:
            if not self.proposed_path:
                self._set_instruction("No hay ruta propuesta")
                self._start_clear_instruction_timer(2.0)
                return
            # aplicar la ruta confirmada
            self.current_path = list(self.proposed_path)
            sums = dict(self.proposed_sums or {"sum_ly": 0.0, "sum_years": 0.0})
            
        rules = self.graph_model.options.params.get("rules", {})
        # actualizar el formulario para mostrar los valores confirmados (en español)
        try:
            if self.form:
                origin_label = self.G.nodes[self.selected_origin].get("label", str(self.selected_origin))
                target_label = self.G.nodes[self.selected_target].get("label", str(self.selected_target))
                # mostrar los valores reales en el formulario (ya no "Desconocido")
                burro_before = self.burro_state
                burro_after, sums, events = simulate_path(burro_before, self.proposed_path, self.G, rules)
                self.burro_state = burro_after
                self.current_path = self.proposed_path
                self.form.update(
                    origin_label=origin_label,
                    target_label=target_label,
                    sum_ly=sums.get("sum_ly"),
                    sum_years=sums.get("sum_years"),
                    burro_info={"before": burro_before, "after": burro_after},
                    factor=self.form._last_values.get("factor")
                )

                try:
                    self.form.set_compute_enabled(False)
                except Exception:
                    pass
        except Exception:
            pass

        # confirmar en UI sin cerrar el form
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
        
        
        # ------------------ Hover / tooltip (Matplotlib) ------------------

    def on_motion(self, event):
        """Handler para motion_notify_event: muestra tooltip cuando el cursor está sobre un nodo."""
        try:
            if event.xdata is None or event.ydata is None:
                self._hide_tooltip()
                return
            # detectar nodo bajo cursor (usar mismo pick logic pero sin click)
            node = self._pick_node_at_display(event.xdata, event.ydata)
            if node is None:
                self._hide_tooltip()
                return
            # construir tooltip context y renderizar
            star_attrs = dict(self.G.nodes[node]) if node in self.G.nodes else {}
            # obtener rules desde graph_model (se asume graph_model.options.params o similar)
            rules = {}
            try:
                rules = getattr(self.graph_model, "options").params.get("rules", {}) if getattr(self.graph_model, "options", None) else {}
            except Exception:
                # fallback: intentar graph_model.options.get("params")
                try:
                    rules = getattr(self.graph_model, "options").get("params", {}).get("rules", {})
                except Exception:
                    rules = {}
            # Si las rules están en la raíz (no dentro de 'rules'), permitir ambos
            if not rules:
                # intentar graph_model.options.params directamente
                try:
                    rules = getattr(self.graph_model, "options").params
                except Exception:
                    pass

            from src.gui.ui_helpers import build_star_tooltip
            ctx = build_star_tooltip(star_attrs, rules or {}, getattr(self, "burro_state", None))
            # render
            self._render_tooltip(node, event.xdata, event.ydata, ctx)
        except Exception:
            # en caso de fallo, asegurar que tooltip desaparece y no rompe UI
            try:
                self._hide_tooltip()
            except Exception:
                pass

    def _render_tooltip(self, node, xdata, ydata, ctx):
        """Dibuja la info-box simple con redraw completo."""
        try:
            ax = self.fig.axes[0] if (self.fig and self.fig.axes) else None
            if ax is None:
                return

            # ocultar anterior
            self._hide_tooltip()

            # posicion en datos -> transformar a display para offset
            trans = ax.transData
            x_px, y_px = trans.transform((xdata, ydata))

            # construir texto lines
            lines = []
            lines.append(ctx.get("title", f"Star #{ctx.get('id','?')}"))
            lines.append(f"Investigación: {ctx.get('investigation_years_s','?')} años/visita")
            lines.append(f"Comer: {ctx.get('time_per_kg_years_s','?')} años/kg")
            lines.append(f"Consumo energía por visita: {ctx.get('energy_consumption_per_visit_pct_s','?')} %")
            if ctx.get("recovery_per_1kg_pct_s") is not None:
                lines.append(f"Recuperación por 1 kg: +{ctx.get('recovery_per_1kg_pct_s')} % ({ctx.get('recovery_note','')})")
            lines.append(ctx.get("feeding_max_kg_text", ""))
            lines.append(ctx.get("grass_text", ""))

            # add notes if any
            for n in ctx.get("notes", []):
                lines.append(n)

            # create bbox axes relative to figure using add_axes with transform = figure coords
            # compute figure coords from display px
            fig_w, fig_h = self.fig.get_size_inches() * self.fig.dpi
            # convert px back to figure fraction
            fx = x_px / fig_w
            fy = y_px / fig_h

            # offset to top-right by small amount (clamp to [0,1])
            off_x = 0.02
            off_y = 0.02
            fx += off_x
            fy += off_y
            fx = min(max(0.01, fx), 0.95)
            fy = min(max(0.05, fy), 0.95)

            # width/height heuristics
            w = 0.22
            h = max(0.10, 0.04 * len(lines))

            # create axes for tooltip
            ax_box = self.fig.add_axes([fx, fy - h, w, h], zorder=50)
            ax_box.set_facecolor("#1c1c1c")
            ax_box.set_xticks([])
            ax_box.set_yticks([])
            for spine in ax_box.spines.values():
                spine.set_color("#444444")

            y_rel = 0.88
            text_artists = []
            for ln in lines:
                t = ax_box.text(0.05, y_rel, ln, color="white", fontsize=9,
                                transform=ax_box.transAxes, ha="left", va="center")
                text_artists.append(t)
                y_rel -= 0.14

            # save
            self._tooltip_box = ax_box
            self._tooltip_texts = text_artists
            self._tooltip_visible = True
            # force redraw
            try:
                if hasattr(self.fig.canvas, "draw_idle"):
                    self.fig.canvas.draw_idle()
                else:
                    self._redraw()
            except Exception:
                self._redraw()
        except Exception:
            pass

    def _hide_tooltip(self):
        try:
            if getattr(self, "_tooltip_texts", None):
                for t in list(self._tooltip_texts):
                    try:
                        t.remove()
                    except Exception:
                        pass
                self._tooltip_texts = []
            if getattr(self, "_tooltip_box", None):
                try:
                    self._tooltip_box.remove()
                except Exception:
                    pass
                self._tooltip_box = None
            self._tooltip_visible = False
            # redraw to remove artifacts
            try:
                if hasattr(self.fig.canvas, "draw_idle"):
                    self.fig.canvas.draw_idle()
                else:
                    self._redraw()
            except Exception:
                self._redraw()
        except Exception:
            pass
