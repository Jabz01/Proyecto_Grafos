# src/gui/route_form.py
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from typing import Optional, Callable


class RouteForm:
    """
    Overlay (formulario) sobre Matplotlib en la esquina superior izquierda.
    Muestra origen, destino, suma de años luz, suma de yearsCost (años de vida) y datos del burro (placeholder),
    con botones 'Calcular' y 'Cerrar'.

    Uso:
      form = RouteForm(fig, on_compute=handler.finalize_route_calculation, on_close=handler.close_form)
      form.show(origin_label, target_label, sum_ly, sum_years, burro_info, factor=factor)
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
        self.ax_close = fig.add_axes([0.18, 0.78, 0.14, 0.05])

        # Widgets
        self.btn_compute = Button(self.ax_compute, "Calcular")
        self.btn_close = Button(self.ax_close, "Cerrar")

        # Estado de visibilidad y datos mostrados
        self._visible = False
        self._texts = []
        self._last_values = {
            "origin_label": "",
            "target_label": "",
            "sum_ly": None,
            "sum_years": None,
            "factor": None,
            "burro_info": None
        }

        # Conectar callbacks
        self.btn_compute.on_clicked(lambda evt: self._safe_call(self.on_compute))
        self.btn_close.on_clicked(lambda evt: self.hide() or self._safe_call(self.on_close))

        # Estética inicial de la caja
        self._style_axes()

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
             sum_ly: Optional[float],
             sum_years: Optional[float],
             burro_info: Optional[dict] = None,
             factor: Optional[float] = None):
        """
        Dibuja/actualiza el contenido del formulario y lo hace visible.
        sum_ly / sum_years pueden ser None -> mostramos 'Desconocido' hasta confirmar.
        factor: valor distanceLyToYearsFactor (ej. 0.05). Mostramos conversión legible.
        """
        self._visible = True
        self._clear_texts()

        # Guardar últimos valores para poder actualizar después
        self._last_values.update({
            "origin_label": origin_label,
            "target_label": target_label,
            "sum_ly": sum_ly,
            "sum_years": sum_years,
            "factor": factor,
            "burro_info": burro_info
        })

        # preparar strings con fallback "Desconocido"
        sum_ly_s = f"{sum_ly:.3g}" if (sum_ly is not None) else "Desconocido"
        sum_years_s = f"{sum_years:.3g}" if (sum_years is not None) else "Desconocido"

        # conversión legible: si factor > 0 mostramos 1 año de vida ≈ (1/factor) años luz
        factor_text = "Desconocido"
        try:
            if factor is not None and float(factor) > 0.0:
                conv = 1.0 / float(factor)
                factor_text = f"1 año de vida ≈ {round(conv, 3)} años luz"
        except Exception:
            factor_text = "Desconocido"

        # textos en español y con formato final cuando corresponda
        lines = [
            f"Origen: {origin_label}",
            f"Destino: {target_label}",
            f"Años luz total: {sum_ly_s}",
            f"Años de costo (años de vida) total: {sum_years_s}",
            f"Factor conversión: {factor_text}",
        ]
        if burro_info:
            for k, v in burro_info.items():
                lines.append(f"Burro {k}: {v}")
        else:
            lines.append("Burro: (pendiente)")

        y = 0.85
        for ln in lines:
            txt = self.ax_box.text(0.05, y, ln, color="white", fontsize=10,
                                   transform=self.ax_box.transAxes, ha="left", va="center")
            self._texts.append(txt)
            y -= 0.16

        self._set_axes_visible(True)
        self.fig.canvas.draw_idle()

    def update(self,
               origin_label: Optional[str] = None,
               target_label: Optional[str] = None,
               sum_ly: Optional[float] = None,
               sum_years: Optional[float] = None,
               burro_info: Optional[dict] = None,
               factor: Optional[float] = None):
        """
        Actualiza el contenido manteniendo el overlay visible.
        Si no se pasan sum_ly/sum_years se conservan los últimos o "Desconocido".
        """
        if not self._visible:
            return
        cur = self._last_values.copy()
        if origin_label is not None:
            cur["origin_label"] = origin_label
        if target_label is not None:
            cur["target_label"] = target_label
        if sum_ly is not None:
            cur["sum_ly"] = sum_ly
        if sum_years is not None:
            cur["sum_years"] = sum_years
        if burro_info is not None:
            cur["burro_info"] = burro_info
        if factor is not None:
            cur["factor"] = factor
        self.show(cur["origin_label"], cur["target_label"], cur["sum_ly"], cur["sum_years"], cur["burro_info"], factor=cur["factor"])

    def _current_values(self):
        """
        Intenta parsear el contenido actual del overlay (best-effort).
        Útil para update si no se pasan todos los parámetros.
        """
        return self._last_values.copy()

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
    def set_compute_enabled(self, enabled: bool):
        """
        Habilita o deshabilita el botón 'Calcular'.
        Cambia la apariencia y la etiqueta para dar feedback.
        """
        try:
            # cambiar estado de interacción
            self.btn_compute.ax.set_visible(True)  # asegurarnos de que el eje está visible
            if enabled:
                self.btn_compute.label.set_text("Calcular")
                for spine in self.ax_compute.spines.values():
                    spine.set_color("#444444")
                self.btn_compute.ax.set_facecolor("#f0f0f0")
            else:
                self.btn_compute.label.set_text("Calculado")
                self.btn_compute.ax.set_facecolor("#dddddd")
            # no existe API pública para disabled; usar onclick swap: desconectar y reconectar
            if enabled:
                # reconectar al callback original
                self.btn_compute.on_clicked(lambda evt: self._safe_call(self.on_compute))
            else:
                # reemplazar por handler que no hace nada salvo safe-print
                self.btn_compute.on_clicked(lambda evt: None)
        except Exception:
            pass
    
    
    def reset_compute_button(self):
        """
        Restaurar el botón 'Calcular' a su estado inicial (habilitado y etiqueta "Calcular").
        Reconecta el callback original on_compute.
        """
        try:
            # Etiqueta visible
            try:
                self.btn_compute.label.set_text("Calcular")
            except Exception:
                pass
            # Apariencia
            try:
                self.btn_compute.ax.set_facecolor("#f0f0f0")
            except Exception:
                pass
            # Reconectar callback: eliminar handlers previos no es trivial en matplotlib,
            # así que añadimos una reconexión que ejecuta on_compute (acepta múltiples binds).
            try:
                self.btn_compute.on_clicked(lambda evt: self._safe_call(self.on_compute))
            except Exception:
                pass
            # refrescar
            try:
                self.fig.canvas.draw_idle()
            except Exception:
                pass
        except Exception:
            pass
    def set_status_text(self, text: Optional[str]):
        """
        Mostrar un texto de estado breve dentro del overlay (no sustituye a los campos principales).
        Si text es None, borra el estado previo.
        """
        try:
            # reutilizamos una línea al final para status; la colocamos en la última posición
            # limpiamos cualquier status viejo
            # (implementación simple: añadir/actualizar un text en self._status_text)
            if hasattr(self, "_status_text") and self._status_text:
                try:
                    self._status_text.remove()
                except Exception:
                    pass
                self._status_text = None
            if text:
                self._status_text = self.ax_box.text(0.05, 0.02, text, color="#cccccc", fontsize=9,
                                                    transform=self.ax_box.transAxes, ha="left", va="bottom")
            else:
                self._status_text = None
            self.fig.canvas.draw_idle()
        except Exception:
            pass