# src/main/universe.py
import json
import matplotlib.pyplot as plt
import networkx as nx
from typing import Optional
from src.main.loadGraph import LoadGraphFromJson

def VisualizeUniverse(config_path: str = "config/config.json", rules_path: str = "config/rules.json") -> None:
    """
    Load graph from config and rules, then visualize it with constellations, labels and attributes.
    """
    # Cargar reglas
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
    constellations = graph.options.params.get("constellations", [])

    # Mapear estrella -> color y estrella -> constelación (nombre)
    starToColor = {}
    starToConstellation = {}
    for c in constellations:
        color = c.get("color", "#999999")
        name = c.get("name", c.get("id"))
        for sid in c.get("stars", []):
            starToColor[sid] = color
            starToConstellation[sid] = name

    # Posiciones
    pos = {n: (Gnx.nodes[n]["coordinates"]["x"], Gnx.nodes[n]["coordinates"]["y"]) for n in Gnx.nodes}

    # Preparar figura con fondo negro
    plt.figure(figsize=(10, 8), facecolor="black")
    ax = plt.gca()
    ax.set_facecolor("black")

    # Dibujar nodos con color por constelación y borde para hipergigantes
    node_colors = [starToColor.get(n, "#444444") for n in Gnx.nodes]
    # TAMAÑOS aumentados: hipergigantes mucho más grandes
    node_sizes = [2000 if Gnx.nodes[n].get("hypergiant") else 1000 for n in Gnx.nodes]
    nx.draw_networkx_nodes(
        Gnx,
        pos,
        node_color=node_colors,
        node_size=node_sizes,
        linewidths=1.0,
        edgecolors="white",
        alpha=0.95
    )

    # Etiquetas de estrellas (nombre) en blanco
    labels = {n: Gnx.nodes[n]["label"] for n in Gnx.nodes}
    nx.draw_networkx_labels(Gnx, pos, labels=labels, font_size=9, font_color="white")

    # Aristas: color y grosor según atributos
    edge_colors = ["red" if Gnx[u][v].get("blocked") else "#aaaaaa" for u, v in Gnx.edges]
    edge_widths = [2.8 if Gnx[u][v].get("yearsCost", 0) > 5 else 1.2 for u, v in Gnx.edges]
    nx.draw_networkx_edges(Gnx, pos, edge_color=edge_colors, width=edge_widths, alpha=0.9)

    # Etiquetas de constelaciones sobre el centro del grupo (más arriba)
    for c in constellations:
        stars = [sid for sid in c.get("stars", []) if sid in pos]
        if not stars:
            continue
        xs = [pos[sid][0] for sid in stars]
        ys = [pos[sid][1] for sid in stars]
        cx, cy = sum(xs) / len(xs), max(ys) + 10.0  # desplazamiento más alto
        # Dibujar un recuadro semitransparente con el color de la constelación y texto en blanco
        bbox_props = dict(boxstyle="round,pad=0.3", facecolor=c.get("color", "#666666"), alpha=0.85, edgecolor="none")
        plt.text(cx, cy, c.get("name", c.get("id")), fontsize=12, fontweight="bold",
                 ha="center", va="center", color="white", bbox=bbox_props)

    plt.title("Universe — grafo con constelaciones", color="white", fontsize=14)
    plt.axis("equal")
    plt.axis("off")  # ocultar ejes para estética en fondo negro
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    VisualizeUniverse()