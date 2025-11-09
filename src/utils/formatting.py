# src/utils/formatting.py
import math
from typing import Any

def round_sig(x: float, sig: int = 3) -> float:
    """Redondea x a sig cifras significativas; maneja 0 y None."""
    if x is None:
        return 0.0
    try:
        x = float(x)
    except Exception:
        return 0.0
    if x == 0.0:
        return 0.0
    sign = -1.0 if x < 0 else 1.0
    x = abs(x)
    exp = math.floor(math.log10(x))
    factor = 10 ** (sig - 1 - exp)
    return sign * round(x * factor) / factor

def format_edge_label(attrs: dict, sig: int = 3) -> str:
    """Devuelve una representación string para la etiqueta de arista (distanceLy o yearsCost)."""
    val = attrs.get("distanceLy", attrs.get("yearsCost", 0.0))
    try:
        v = float(val)
    except Exception:
        v = 0.0
    r = round_sig(v, sig=sig)
    # evitar notación científica en la mayoría de casos
    if abs(r) >= 1:
        # si es entero tras rounding, mostrar sin decimales
        if float(r).is_integer():
            return f"{int(r)}"
        return f"{r}"
    # para números < 1 mostrar con sig-1 decimales razonables
    decimals = max(0, sig - 1 - int(math.floor(math.log10(abs(r)))) ) if r != 0 else 0
    fmt = f"{{:.{decimals}f}}"
    return fmt.format(r)