# src/gui/loadGraph.py
import json
from typing import Tuple, List, Optional
from src.utils.parser import LoadJson, BuildParserOutputFromJson
from src.model.graph import GraphModel, GraphOptions

# Nota: imports de visualización se mantienen en la sección __main__ si se usan.
# Este módulo se concentra en cargar/normalizar el grafo y devolver el modelo de dominio.

def LoadGraphFromJson(configPath: str, rulesDict: dict = None) -> Tuple[Optional[GraphModel], List[str], List[str]]:
    """
    Carga el JSON de configuración desde configPath, lo parsea y construye un GraphModel.
    Retorna (graph, warnings, errors). Si hay errores de parseo, graph será None.
    """
    data = LoadJson(configPath)
    parserOutput, warnings, errors = BuildParserOutputFromJson(data)
    if errors:
        return None, warnings, errors

    # Combinar reglas externas con constelaciones del parser (si se entrega)
    rules = rulesDict.copy() if rulesDict else {}
    rules["constellations"] = parserOutput.get("constellations", [])

    options = GraphOptions(rules or {})
    graph = GraphModel.BuildFromParserOutput(parserOutput, options)
    return graph, warnings, errors


# ---------------------------------------------------------------------
# Bloque de ejecución directa / herramientas de debugging local
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import networkx as nx
    import os

    # Rutas por defecto (ajusta según tu estructura)
    configPath = "config/config.json"
    rulesPath = "config/rules.json"

    # --------- Opción: permitir elegir JSON desde el sistema (comentada) ----------
    # Si quieres habilitar la selección de archivos desde tu PC durante desarrollo,
    # descomenta el bloque siguiente. Está comentado por defecto tal como pediste.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        print("Selecciona el archivo JSON de configuración...")
        selected = filedialog.askopenfilename(
            title="Seleccionar config JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if selected:
            configPath = selected
            print("Usando archivo:", configPath)
    except Exception as e:
        print("Advertencia: no se pudo abrir diálogo de archivos. Usando ruta por defecto.", e)
    """

    # Cargar reglas
    try:
        with open(rulesPath, "r", encoding="utf-8") as f:
            rules = json.load(f).get("rules", {})
    except Exception:
        rules = {}

    # Cargar grafo
    graph, warnings, errors = LoadGraphFromJson(configPath, rules)

    if errors:
        print("❌ Errores:")
        for e in errors:
            print("-", e)
    else:
        print("✅ Grafo cargado correctamente")
        # Usar API del GraphModel para informar (evitar acceder a atributos privados)
        try:
            all_nodes = graph.AllStars()
            print("Nodos:", len(all_nodes))
        except Exception:
            # Fallback si la implementación varía
            try:
                Gnx = graph.ToNetworkX()
                print("Nodos (nx):", len(Gnx.nodes()))
            except Exception:
                print("No se pudo determinar el número de nodos (API GraphModel no disponible)")

        # Mostrar warnings si los hay
        if warnings:
            print("⚠️ Advertencias:")
            for w in warnings:
                print("-", w)

        # Visualización rápida (solo para debugging)
        try:
            Gnx = graph.ToNetworkX()
            pos = {n: (Gnx.nodes[n]["coordinates"]["x"], Gnx.nodes[n]["coordinates"]["y"]) for n in Gnx.nodes}
            nx.draw(Gnx, pos, with_labels=True, node_color="skyblue", edge_color="gray", font_size=8)
            plt.title("Visualización del grafo (debug)")
            plt.axis("equal")
            plt.show()
        except Exception as e:
            print("Nota: no se pudo mostrar visualización rápida:", e)