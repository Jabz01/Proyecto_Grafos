# src/model/graph.py
from typing import Dict, List, Optional, Tuple, Any
from .star import Star
from .edge import Edge
import networkx as nx


class GraphOptions:
    """
    Container for effective simulation parameters (merged rules).
    Keep simple mapping-like attributes used by Graph methods.
    """
    def __init__(self, params: Dict[str, Any]):
        # params expected keys: distanceLyToYearsFactor, etc.
        self.params = params

    def Get(self, key: str, default=None):
        return self.params.get(key, default)


class GraphModel:
    """High-level graph model owning Star and Edge instances."""
    def __init__(self, options: Optional[GraphOptions] = None):
        # Diccionario de estrellas por id
        self._stars: Dict[int, Star] = {}
        # Diccionario de aristas por clave (min(u,v), max(u,v))
        self._edges: Dict[Tuple[int, int], Edge] = {}
        # Opciones/parametros de simulación inyectadas
        self.options = options or GraphOptions({})

    # ------- Gestión de nodos (Stars) -------

    def AddStar(self, star: Star) -> None:
        """Añade una estrella al grafo; reemplaza si ya existía."""
        self._stars[star.id] = star

    def GetStar(self, starId: int) -> Optional[Star]:
        """Devuelve la instancia Star por id o None si no existe."""
        return self._stars.get(starId)

    def AllStars(self) -> List[Star]:
        """Lista de todas las estrellas en el grafo."""
        return list(self._stars.values())

    # ------- Gestión de aristas (Edges) -------

    @staticmethod
    def _edgeKey(u: int, v: int) -> Tuple[int, int]:
        """Canonical key for undirected edges."""
        return (u, v) if u <= v else (v, u)

    def AddEdge(self, edge: Edge) -> None:
        """Añade una arista; si existe, se actualiza la metadata mínima."""
        key = self._edgeKey(edge.u, edge.v)
        self._edges[key] = edge

    def GetEdge(self, u: int, v: int) -> Optional[Edge]:
        """Obtiene la arista entre u y v, o None si no existe."""
        return self._edges.get(self._edgeKey(u, v))

    def SetEdgeBlocked(self, u: int, v: int, blocked: bool) -> None:
        """Marca/desmarca una arista como bloqueada."""
        edge = self.GetEdge(u, v)
        if edge:
            edge.ToggleBlocked(blocked)

    def Neighbors(self, nodeId: int) -> List[int]:
        """Lista de ids vecinos (considerando aristas existentes, incluso si bloqueadas)."""
        nbrs: List[int] = []
        for (a, b), e in self._edges.items():
            if a == nodeId:
                nbrs.append(b)
            elif b == nodeId:
                nbrs.append(a)
        return nbrs

    # ------- Conversión y utilidades -------

    def ToNetworkX(self) -> nx.Graph:
        """
        Export graph to a networkx.Graph for visualization or algorithm libraries.
        Node attributes and edge attributes are preserved.
        """
        G = nx.Graph()
        # Añadir nodos
        for s in self._stars.values():
            G.add_node(s.id, **{
                "label": s.label,
                "coordinates": s.coordinates,
                "radius": s.radius,
                "timeToEatHoursPerKg": s.timeToEatHoursPerKg,
                "hypergiant": s.hypergiant,
                "investigations": [inv.__dict__ for inv in s.investigations]
            })
        # Añadir aristas
        for e in self._edges.values():
            G.add_edge(e.u, e.v, **{
                "distanceLy": e.distanceLy,
                "yearsCost": e.yearsCost,
                "blocked": e.blocked,
                "meta": e.meta or {}
            })
        return G

    def ComputeShortestPath(self, source: int, target: int, weightKey: str = "yearsCost") -> List[int]:
        """
        Compute shortest path using networkx weighted shortest path ignoring blocked edges.
        Returns list of node ids. Raises networkx.NetworkXNoPath if none found.
        """
        # Crear un grafo temporal de networkx que excluya aristas bloqueadas
        G = nx.Graph()
        for s in self._stars.values():
            G.add_node(s.id)
        for e in self._edges.values():
            if not e.blocked:
                # usar weightKey si existe en meta, sino fallback a yearsCost
                weight = getattr(e, weightKey, e.yearsCost) if hasattr(e, weightKey) else e.yearsCost
                G.add_edge(e.u, e.v, weight=weight)
        path = nx.shortest_path(G, source=source, target=target, weight="weight")
        return path

    def ExportReport(self, visitedNodes: List[int]) -> Dict[str, Any]:
        """Genera un reporte simple con las estrellas visitadas y sus investigaciones."""
        report = {"visited": [], "summary": {"totalVisited": len(visitedNodes)}}
        for nid in visitedNodes:
            s = self.GetStar(nid)
            if not s:
                continue
            report["visited"].append({
                "id": s.id,
                "label": s.label,
                "investigations": [inv.__dict__ for inv in s.investigations]
            })
        return report

    # ------- Factory helper para construir desde parser output -------

    @classmethod
    def BuildFromParserOutput(cls, parserOutput: Dict[str, Any], options: Optional[GraphOptions] = None) -> "GraphModel":
        """
        Build a GraphModel instance from parser output (stars list, edges list, constellations, initial_state).
        ParserOutput expected keys: 'stars', 'edges', 'constellations', 'initial_state'.
        """
        gm = cls(options=options)
        stars = parserOutput.get("stars", [])
        edges = parserOutput.get("edges", [])

        # Añadir estrellas
        for s in stars:
            # crear instancia Star usando el diccionario (se espera shape compatible)
            starObj = Star(
                id=int(s["id"]),
                label=s.get("label", s.get("etiqueta", f"star{s['id']}")),
                coordinates={"x": float(s["coordinates"]["x"]), "y": float(s["coordinates"]["y"])},
                radius=float(s.get("radius", 0.5)),
                timeToEatHoursPerKg=float(s.get("timeToEatHoursPerKg", s.get("timeToEatHoursPerKg", 1))),
                hypergiant=bool(s.get("hypergiant", False)),
                investigations=[]
            )
            # Si el parser ya dejó investigaciones en formato dict, crear objetos Investigation
            for inv in s.get("investigations", []):
                from .star import Investigation  # import local para evitar circularidad en anotaciones
                invObj = Investigation(
                    name=inv.get("name", "unknown"),
                    time_hours=float(inv.get("time_hours", inv.get("timeHours", 0))),
                    energyConsumedPercent=float(inv.get("energyConsumedPercent", inv.get("energyConsumedPercent", 0))),
                    randomYearsEffectSigned=float(inv.get("randomYearsEffectSigned", inv.get("randomYearsEffectSigned", 0)))
                )
                starObj.AddInvestigation(invObj)
            gm.AddStar(starObj)

        # Añadir aristas calculando distancia euclidiana y yearsCost basado en options
        distanceFactor = 0.05
        if options:
            distanceFactor = options.Get("distanceLyToYearsFactor", options.Get("yearsPerLy", distanceFactor))

        for e in edges:
            u = int(e["u"])
            v = int(e["v"])
            blocked = bool(e.get("blocked", e.get("bloqueada", False)))
            su = gm.GetStar(u)
            sv = gm.GetStar(v)
            if not su or not sv:
                # Ignorar aristas que referencian nodos inexistentes
                continue
            distanceLy = su.DistanceTo(sv)
            yearsCost = distanceLy * distanceFactor
            edgeObj = Edge(u=u, v=v, distanceLy=distanceLy, yearsCost=yearsCost, blocked=blocked, meta={})
            gm.AddEdge(edgeObj)

        return gm