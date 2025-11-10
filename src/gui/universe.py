# src/gui/universe.py
import json
import math
import matplotlib.pyplot as plt
import networkx as nx
import matplotlib.patheffects as pe
from typing import Dict, Tuple, Optional

from src.gui.ui_buttons import create_buttons
from src.gui.loadGraph import LoadGraphFromJson
from src.gui.event_handler import EventHandler
from src.utils.visual import node_size
from src.utils.formatting import round_sig, format_edge_label
from src.utils.graph_utils import path_total_cost, filtered_graph_nx

def VisualizeUniverse(config_path: str = "config/config.json", rules_path: str = "config/rules.json") -> None:
    # cargar reglas y grafo
    with open(rules_path, "r", encoding="utf-8") as f:
        rules = json.load(f).get("rules", {})
    graph, warnings, errors = LoadGraphFromJson(config_path, rules)
    if errors:
        print("Errors encountered while loading graph:")
        for e in errors:
            print("-", e)
        return
    if warnings:
        print("Warnings:")
        for w in warnings:
            print("-", w)

    Gnx = graph.ToNetworkX()
    from src.sim.populate_star_defaults import populate_star_defaults
    populate_star_defaults(Gnx.nodes(data=True), seed=graph.options.params.get("simulationSeed"))

    constellations = graph.options.params.get("constellations", [])

    # mapear color y constelación por estrella (valores por defecto)
    starToColor: Dict[int, str] = {}
    starToConstellation: Dict[int, str] = {}
    for c in constellations:
        color = c.get("color", "#999999")
        name = c.get("name", c.get("id"))
        for sid in c.get("stars", []):
            starToColor[sid] = color
            starToConstellation[sid] = name


    # posiciones y radios
    pos: Dict[int, Tuple[float, float]] = {}
    radii: Dict[int, float] = {}
    for n in Gnx.nodes:
        coords = Gnx.nodes[n].get("coordinates", {"x": 0, "y": 0})
        pos[n] = (coords.get("x", 0), coords.get("y", 0))
        radii[n] = float(Gnx.nodes[n].get("radius", 1.0))

    # figura y ax (no toggle automático a pantalla completa)
    fig = plt.figure(figsize=(11, 8), facecolor="black")
    ax = fig.add_axes([0.0, 0.08, 1.0, 0.90])
    ax.set_facecolor("black")

    handler: Optional[EventHandler] = None  # definido después

    def redraw():
        # sincronizar vista del handler con el modelo antes de dibujar
        if handler is not None:
            try:
                handler._sync_from_model()
            except Exception:
                pass

        ax.clear()
        ax.set_facecolor("black")

        # dibujar etiquetas de constelación por debajo (se dibujan primero)
        max_r = max(radii.values()) if radii else 1.0
        for c in constellations:
            stars = [sid for sid in c.get("stars", []) if sid in pos]
            if not stars:
                continue
            xs = [pos[sid][0] for sid in stars]
            ys = [pos[sid][1] for sid in stars]
            cx, cy = sum(xs) / len(xs), max(ys) + (max_r * 6.0)
            bbox_props = dict(boxstyle="round,pad=0.3", facecolor=c.get("color", "#666666"), alpha=0.85, edgecolor="none")
            ax.text(cx, cy, c.get("name", c.get("id")), fontsize=12, fontweight="bold",
                    ha="center", va="center", color="white", bbox=bbox_props)

        # nodos: calcular colores con prioridad: selección origen/destino > hypergiant rojo > constelación color > fallback
        node_colors = []
        for n in Gnx.nodes:
            # determinar si pertenece a más de una constelación
            constelation_count = sum(1 for c in constellations if n in c.get("stars", []))
            is_multi_constellation = constelation_count >= 2

            # color base: rojo si pertenece a más de una constelación, si no usar color de constelación
            base_color = "#ff3333" if is_multi_constellation else starToColor.get(n, "#444444")

            # override por selección en handler
            if handler and getattr(handler, "selected_origin", None) == n:
                node_colors.append("yellow")
            elif handler and getattr(handler, "selected_target", None) == n:
                node_colors.append("deepskyblue")
            else:
                node_colors.append(base_color)


        node_sizes = [node_size(radii.get(n, 1.0), Gnx.nodes[n].get("hypergiant", False)) for n in Gnx.nodes]
        nx.draw_networkx_nodes(Gnx, pos, node_color=node_colors, node_size=node_sizes,
                               linewidths=1.0, edgecolors="white", alpha=0.95, ax=ax)
        labels = {n: Gnx.nodes[n].get("label", str(n)) for n in Gnx.nodes}
        nx.draw_networkx_labels(Gnx, pos, labels=labels, font_size=9, font_color="white", ax=ax)

        # aristas: color y grosor
        edge_colors = []
        edge_widths = []
        for u, v, attrs in Gnx.edges(data=True):
            edge_colors.append("red" if attrs.get("blocked") else "#aaaaaa")
            years = attrs.get("yearsCost", 0)
            try:
                years_val = float(years)
            except Exception:
                years_val = 0.0
            edge_widths.append(3.0 if years_val > 5 else 1.4)
        nx.draw_networkx_edges(Gnx, pos, edge_color=edge_colors, width=edge_widths, alpha=0.95, ax=ax)

        # etiquetas de arista (sin bbox, centradas en la línea)
        edge_labels = {}
        for u, v, attrs in Gnx.edges(data=True):
            edge_labels[(u, v)] = format_edge_label(attrs, sig=3)
        edge_label_dict = nx.draw_networkx_edge_labels(Gnx, pos, edge_labels=edge_labels,
                                                       font_color="white", ax=ax, label_pos=0.5, font_size=8, rotate=False)

        # aplicar halo / máscara a cada etiqueta para "borrar" la línea que pasa por detrás del texto
        if isinstance(edge_label_dict, dict):
            bg_color = ax.get_facecolor() if hasattr(ax, "get_facecolor") else "black"
            for txt in edge_label_dict.values():
                try:
                    txt.set_bbox(None)
                except Exception:
                    pass
                try:
                    txt.set_path_effects([pe.Stroke(linewidth=3.0, foreground=bg_color), pe.Normal()])
                    txt.set_color("white")
                    try:
                        txt.set_zorder(10)
                    except Exception:
                        pass
                except Exception:
                    try:
                        x, y = txt.get_position()
                        ax.text(x, y, txt.get_text(), transform=txt.get_transform(),
                                color=bg_color, fontsize=txt.get_fontsize(), ha=txt.get_ha(), va=txt.get_va(), zorder=9)
                        txt.set_color("white")
                    except Exception:
                        pass

        # resaltar ruta confirmada si existe (handler.current_path)
        try:
            if handler and getattr(handler, "current_path", None):
                path = handler.current_path
                if len(path) >= 1:
                    nx.draw_networkx_nodes(Gnx, pos, nodelist=path, node_color="gold",
                                           node_size=[node_size(radii.get(n, 1.0), Gnx.nodes[n].get("hypergiant", False)) * 1.2 for n in path],
                                           edgecolors="black", ax=ax)
                if len(path) >= 2:
                    path_edges = list(zip(path[:-1], path[1:]))
                    nx.draw_networkx_edges(Gnx, pos, edgelist=path_edges, edge_color="yellow", width=4.0, ax=ax)
                    # calcular costo total con util
                    total_cost = path_total_cost(Gnx, path, weight='yearsCost')
                    total_sig = round_sig(total_cost, sig=3)
        except Exception:
            pass

        ax.axis("equal")
        ax.axis("off")
        plt.draw()

    # instruction setter que usa EventHandler
    instruction_artist = {"artist": None}
    def set_instruction(text: str):
        if instruction_artist["artist"]:
            try:
                instruction_artist["artist"].remove()
            except Exception:
                pass
            instruction_artist["artist"] = None
        if text:
            instruction_artist["artist"] = fig.text(0.5, 0.96, text, ha='center', va='center',
                                                    color='white', fontsize=12, fontweight='bold',
                                                    bbox=dict(facecolor='black', alpha=0.0, edgecolor='none'))
        plt.draw()

    # instanciar handler y registrar clicks
    handler = EventHandler(graph, Gnx, pos, radii, redraw_callback=redraw, set_instruction_callback=set_instruction, fig=fig)
    fig.canvas.mpl_connect('button_press_event', handler.on_click)

    # botones (usar select_route como botón global para iniciar selección)
    buttons = create_buttons(fig, {
        "toggle_block_mode": handler.toggle_block_mode,
        "select_route": handler.start_route_selection,
        "reset_mode": handler.reset_mode
    })

    # primer redraw
    redraw()
    plt.show()


if __name__ == "__main__":
    VisualizeUniverse()