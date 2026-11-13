"""
Comparación entre el método determinista y el modelo ML.

- Correlación de Spearman entre las puntuaciones (horas inducidas) de ambos métodos.
- Solapamiento del top-K: cuántas máquinas aparecen en el top-K de los dos.
- Etiqueta de acuerdo por máquina, para enseñarla en la interfaz.
La comparación se hace sobre las etapas de la cadena serie (las únicas que puntúa el determinista).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from . import config as C


def unir(det: pd.DataFrame, ml: pd.DataFrame, k: int = C.TOP_K) -> pd.DataFrame:
    cols_det = ["Periodo", "Etapa", "Orden_etapa", "es_cuello", "severidad", "horas_inducidas", "rango_det"]
    cols_ml = ["Periodo", "Etapa", "horas_inducidas_ml", "horas_DES_provocada", "horas_SAT_provocada"]
    u = det[cols_det].merge(ml[cols_ml], on=["Periodo", "Etapa"], how="left")
    u["horas_inducidas_ml"] = u["horas_inducidas_ml"].fillna(0)
    # Re-rango ML solo dentro de la cadena para que sea comparable
    u["rango_ml"] = u.groupby("Periodo")["horas_inducidas_ml"].rank(ascending=False, method="first").astype(int)
    top_det, top_ml = u["rango_det"] <= k, u["rango_ml"] <= k
    u["acuerdo"] = np.select(
        [top_det & top_ml, top_det, top_ml],
        ["ambos", "solo determinista", "solo ML"],
        default="",
    )
    return u.sort_values(["Periodo", "rango_det"]).reset_index(drop=True)


def metricas(unido: pd.DataFrame, k: int = C.TOP_K) -> pd.DataFrame:
    """Una fila por periodo con el grado de acuerdo entre métodos."""
    filas = []
    for periodo, g in unido.groupby("Periodo"):
        rho = spearmanr(g["horas_inducidas"], g["horas_inducidas_ml"]).statistic if len(g) > 2 else np.nan
        top_det = set(g.nsmallest(k, "rango_det")["Etapa"])
        top_ml = set(g.nsmallest(k, "rango_ml")["Etapa"])
        filas.append({
            "Periodo": periodo,
            "spearman": rho,
            f"solape_top{k}": len(top_det & top_ml) / k,
            "principal_det": g.loc[g["rango_det"].idxmin(), "Etapa"],
            "principal_ml": g.loc[g["rango_ml"].idxmin(), "Etapa"],
        })
    m = pd.DataFrame(filas)
    m["misma_principal"] = m["principal_det"] == m["principal_ml"]
    return m
