# src/main/loadGraph.py
from typing import Tuple, List
from src.utils.parser import LoadJson, BuildParserOutputFromJson
from src.model.graph import GraphModel, GraphOptions
import matplotlib.pyplot as plt
import networkx as nx

def LoadGraphFromJson(configPath: str, rulesDict: dict = None) -> Tuple[GraphModel, List[str], List[str]]:
    data = LoadJson(configPath)
    parserOutput, warnings, errors = BuildParserOutputFromJson(data)
    if errors:
        return None, warnings, errors
    
    rules = rulesDict.copy() if rulesDict else {}
    rules["constellations"] = parserOutput.get("constellations", [])

    options = GraphOptions(rules or {})
    graph = GraphModel.BuildFromParserOutput(parserOutput, options)
    return graph, warnings, errors

# 🔁 Bloque de ejecución directa
if __name__ == "__main__":
    import json

    # Rutas relativas (ajústalas si usas otras carpetas)
    configPath = "config/config.json"
    rulesPath = "config/rules.json"

    # Cargar reglas
    with open(rulesPath, "r", encoding="utf-8") as f:
        rules = json.load(f)["rules"]

    # Cargar grafo
    graph, warnings, errors = LoadGraphFromJson(configPath, rules)

    if errors:
        print("❌ Errores:")
        for e in errors:
            print("-", e)
    else:
        print("✅ Grafo cargado correctamente")
        print("Nodos:", len(graph.AllStars()))
        print("Aristas:", len(graph._edges))

        if warnings:
            print("⚠️ Advertencias:")
            for w in warnings:
                print("-", w)

        # Visualizar con matplotlib
        Gnx = graph.ToNetworkX()
        pos = {n: (Gnx.nodes[n]["coordinates"]["x"], Gnx.nodes[n]["coordinates"]["y"]) for n in Gnx.nodes}
        nx.draw(Gnx, pos, with_labels=True, node_color="skyblue", edge_color="gray", font_size=8)
        plt.title("Visualización del grafo")
        plt.axis("equal")
        plt.show()