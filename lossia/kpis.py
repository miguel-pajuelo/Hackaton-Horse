"""
Indicadores por etapa y periodo, y comprobación contra las referencias del reto.

- Dp  = TBF / (TBF + TAP)              disponibilidad propia   (objetivo >= 90 %)
- Tcy = TBF / NPR  [cmin por pieza]    tiempo de ciclo         (objetivo <= 80 cmin)
- Fpm = NAP / NPR * 1000               paradas propias por cada mil piezas
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def calcular(agregado: pd.DataFrame) -> pd.DataFrame:
    """Recibe la salida de datos.agregar() y añade los KPIs."""
    k = agregado.copy()
    npr = k["NPR"].where(k["NPR"] > 0)
    k["Dp"] = k["TBF"] / (k["TBF"] + k["TAP"]).replace(0, np.nan)
    k["Tcy_cmin"] = k["TBF"] * C.CMIN_POR_HORA / npr
    k["Fpm"] = k["NAP"] / npr * 1000
    for c in ["TAP", "DES", "SAT", "TAI"]:
        k[f"pct_{c}"] = k[c] / k["TR"].replace(0, np.nan)
    k["TAP_medio_dia"] = k["TAP"] / k["n_dias"]
    k["TAI_medio_dia"] = k["TAI"] / k["n_dias"]
    k["cumple_Dp"] = k["Dp"] >= C.DP_MIN
    k["cumple_Tcy"] = (k["Tcy_cmin"] <= C.TCY_MAX_CMIN).where(k["Tcy_cmin"].notna())
    k["semaforo"] = np.select(
        [~k["cumple_Dp"] & (k["cumple_Tcy"] == False), ~k["cumple_Dp"] | (k["cumple_Tcy"] == False)],  # noqa: E712
        ["rojo", "ambar"],
        default="verde",
    )
    return k
