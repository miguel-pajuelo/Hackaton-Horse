"""
Prioridades de actuación: dos listas separadas y una vista unificada para la interfaz.

1. Máquinas penalizantes (método determinista): las que frenan la línea y provocan paradas
   inducidas a sus vecinas. Se actúa sobre su capacidad / ciclo.
2. Prioridad de mantenimiento: las que más tiempo pierden por parada propia (TAP).
   Una máquina puede pararse mucho sin penalizar a la línea (tiene capacidad sobrante o
   un buffer la protege), pero sigue siendo un problema de mantenimiento.

La vista unificada junta ambas con el motivo en lenguaje llano, para que un novato y un
experto vean la misma información.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def mantenimiento(k: pd.DataFrame) -> pd.DataFrame:
    """
    Recibe la salida de kpis.calcular() y ordena por horas de parada propia por día.
    Marca si la parada propia o las piezas no son fiables en algún día del periodo.
    """
    m = k[["Periodo", "Etapa", "Orden_etapa", "Tipo", "n_dias", "TAP", "TAP_medio_dia", "NAP",
           "Dp", "Tcy_cmin", "Fpm", "cumple_Dp", "cumple_Tcy", "dia_tap_dudoso", "dia_averia_atipica", "dia_npr_invalido"]].copy()
    m["datos_dudosos"] = (m["dia_tap_dudoso"] > 0) | (m["dia_npr_invalido"] > 0)
    m["rango_mant"] = m.groupby("Periodo")["TAP_medio_dia"].rank(ascending=False, method="first").astype(int)
    return m.sort_values(["Periodo", "rango_mant"]).reset_index(drop=True)


def _motivos(f: pd.Series) -> str:
    m = []
    if f["es_relevante"]:
        m.append(f"Frena la línea: la anterior la espera y la siguiente se queda sin piezas "
                 f"(severidad {f['severidad']:.0%})")
    if f["cumple_Dp"] == False:  # noqa: E712
        m.append(f"Disponibilidad {f['Dp']:.0%} < {C.DP_MIN:.0%}: {f['TAP_medio_dia']:.1f} h/día de parada propia")
    if f["cumple_Tcy"] == False:  # noqa: E712 (NaN = sin dato)
        m.append(f"Ciclo lento: {f['Tcy_cmin']:.0f} cmin/pieza > {C.TCY_MAX_CMIN:.0f}")
    if f["dia_averia_atipica"] > 0:
        m.append(f"Avería anormalmente larga en {int(f['dia_averia_atipica'])} día(s)")
    if f["datos_dudosos"]:
        m.append("Datos dudosos: revisar sensor/contador antes de actuar")
    return " · ".join(m)


def vista(k: pd.DataFrame, det: pd.DataFrame) -> pd.DataFrame:
    """
    Tabla única por (Periodo, Etapa) con ambas clasificaciones, categoría y motivo.
    `orden_vista` ordena para mostrar: penalizantes relevantes (por severidad), luego
    incumplimientos de disponibilidad (por TAP), luego de ciclo, luego el resto.
    """
    m = mantenimiento(k)
    d = det[["Periodo", "Etapa", "es_cuello", "es_relevante", "severidad", "horas_inducidas", "rango_det"]]
    v = m.merge(d, on=["Periodo", "Etapa"], how="left")
    v["es_cuello"] = v["es_cuello"].astype("boolean").fillna(False).astype(bool)
    v["es_relevante"] = v["es_relevante"].astype("boolean").fillna(False).astype(bool)
    v["en_cadena"] = v["rango_det"].notna()

    falla_dp = v["cumple_Dp"] == False   # noqa: E712
    falla_tcy = v["cumple_Tcy"] == False  # noqa: E712
    v["categoria"] = np.select(
        [v["es_relevante"] & (falla_dp | falla_tcy), v["es_relevante"], falla_dp, falla_tcy],
        ["Penalizante + KPI", "Penalizante", "Baja disponibilidad", "Ciclo lento"],
        default="",
    )
    v["motivo"] = v.apply(_motivos, axis=1)
    grupo = np.select([v["es_relevante"], falla_dp, falla_tcy], [0, 1, 2], default=3)
    clave = np.where(grupo == 0, -v["severidad"].fillna(0), -v["TAP_medio_dia"])
    v = v.assign(_g=grupo, _k=clave).sort_values(["Periodo", "_g", "_k"])
    v["orden_vista"] = v.groupby("Periodo").cumcount() + 1
    return v.drop(columns=["_g", "_k"]).reset_index(drop=True)
