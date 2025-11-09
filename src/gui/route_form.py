# src/gui/route_form.py
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from typing import Optional, Callable


class RouteForm:
    """
    Overlay (formulario) sobre Matplotlib en la esquina superior izquierda.
    Muestra origen, destino, suma de años luz, suma de yearsCost y datos del burro (placeholder),
    con botones 'Calcular' y 'Cerrar'.

    Uso:
      form = RouteForm(fig, on_compute=handler.finalize_route_calculation, on_close=handler.close_form)
      form.show(origin_label, target_label, sum_ly, sum_years, burro_info)

    Notas:
      - No bloquea la UI (no es modal); aparece como overlay.
      - Los callbacks on_compute y on_close deben ser funciones sin argumentos.
      - Llama fig.canvas.draw_idle() para refrescar de forma segura.
    """

    def __init__(self,
                 fig: plt.Figure,
                 on_compute: Callable[[], None],
                 on_close: Callable[[], None]):
        self.fig = fig
        self.on_compute = on_compute
        self.on_close = on_close

        # Axes del overlay (contenedor y controles)
        # Caja principal arriba-izquierda
        self.ax_box = fig.add_axes([0.02, 0.84, 0.30, 0.14])
        # Botones debajo de la caja
        self.ax_compute = fig.add_axes([0.02, 0.78, 0.14, 0.05])
        self.ax_close   = fig.add_axes([0.18, 0.78, 0.14, 0.05])

        # Widgets
        self.btn_compute = Button(self.ax_compute, "Calcular")
        self.btn_close   = Button(self.ax_close,   "Cerrar")

        # Estado de visibilidad
        self._visible = False

        # Conectar callbacks
        self.btn_compute.on_clicked(lambda evt: self._safe_call(self.on_compute))
        self.btn_close.on_clicked(lambda evt: self.hide() or self._safe_call(self.on_close))

        # Estética inicial de la caja
        self._style_axes()

        # Texto interno (artistas)
        self._texts = []

    def _style_axes(self):
        # Caja
        self.ax_box.set_facecolor("#1c1c1c")
        self.ax_box.set_xticks([])
        self.ax_box.set_yticks([])
        for spine in self.ax_box.spines.values():
            spine.set_color("#444444")
        # Botones
        for ax in (self.ax_compute, self.ax_close):
            ax.set_facecolor("#f0f0f0")

    def _safe_call(self, fn: Optional[Callable[[], None]]):
        try:
            if fn:
                fn()
        except Exception as exc:
            print(f"[RouteForm] callback failed: {exc}")

    def show(self,
             origin_label: str,
             target_label: str,
             sum_ly: float,
             sum_years: float,
             burro_info: Optional[dict] = None):
        """
        Dibuja/actualiza el contenido del formulario y lo hace visible.
        """
        self._visible = True
        self._clear_texts()

        # Contenido
        lines = [
            f"Origen: {origin_label}",
            f"Destino: {target_label}",
            f"Años luz total: {sum_ly}",
            f"YearsCost total: {sum_years}",
        ]
        if burro_info:
            # Placeholder: mostrar claves/valores básicos
            for k, v in burro_info.items():
                lines.append(f"Burro {k}: {v}")
        else:
            lines.append("Burro: (pendiente)")

        # Escribir líneas dentro de la caja (ax_box)
        y = 0.85
        for ln in lines:
            txt = self.ax_box.text(0.05, y, ln, color="white", fontsize=10,
                                   transform=self.ax_box.transAxes, ha="left", va="center")
            self._texts.append(txt)
            y -= 0.18  # separación vertical

        # Asegurar que la caja y botones estén visibles
        self._set_axes_visible(True)
        self.fig.canvas.draw_idle()

    def update(self,
               origin_label: Optional[str] = None,
               target_label: Optional[str] = None,
               sum_ly: Optional[float] = None,
               sum_years: Optional[float] = None,
               burro_info: Optional[dict] = None):
        """
        Actualiza el contenido manteniendo el overlay visible.
        """
        if not self._visible:
            return
        # Reconstruir con los nuevos valores; si alguno es None, conservar el texto actual
        cur = self._current_values()
        origin_label = origin_label if origin_label is not None else cur.get("origin_label", "")
        target_label = target_label if target_label is not None else cur.get("target_label", "")
        sum_ly = sum_ly if sum_ly is not None else cur.get("sum_ly", 0.0)
        sum_years = sum_years if sum_years is not None else cur.get("sum_years", 0.0)
        burro_info = burro_info if burro_info is not None else cur.get("burro_info", None)
        self.show(origin_label, target_label, sum_ly, sum_years, burro_info)

    def _current_values(self):
        """
        Intenta parsear el contenido actual del overlay (best-effort).
        Útil para update si no se pasan todos los parámetros.
        """
        vals = {"origin_label": "", "target_label": "", "sum_ly": 0.0, "sum_years": 0.0, "burro_info": None}
        try:
            texts = [t.get_text() for t in self._texts]
            for t in texts:
                if t.startswith("Origen: "):
                    vals["origin_label"] = t.split("Origen: ", 1)[1]
                elif t.startswith("Destino: "):
                    vals["target_label"] = t.split("Destino: ", 1)[1]
                elif t.startswith("Años luz total: "):
                    vals["sum_ly"] = float(t.split("Años luz total: ", 1)[1])
                elif t.startswith("YearsCost total: "):
                    vals["sum_years"] = float(t.split("YearsCost total: ", 1)[1])
                elif t.startswith("Burro "):
                    # si hay info del burro, no la reconstruimos en detalle
                    vals["burro_info"] = {}
        except Exception:
            pass
        return vals

    def hide(self):
        """
        Oculta el overlay sin destruir los ejes (puede reabrirse luego con show).
        """
        self._visible = False
        self._clear_texts()
        self._set_axes_visible(False)
        self.fig.canvas.draw_idle()

    def dispose(self):
        """
        Elimina los ejes y widgets del overlay permanentemente.
        """
        self.hide()
        try:
            self.ax_box.remove()
            self.ax_compute.remove()
            self.ax_close.remove()
        except Exception:
            pass

    def _set_axes_visible(self, visible: bool):
        self.ax_box.set_visible(visible)
        self.ax_compute.set_visible(visible)
        self.ax_close.set_visible(visible)

    def _clear_texts(self):
        for t in self._texts:
            try:
                t.remove()
            except Exception:
                pass
        self._texts = []