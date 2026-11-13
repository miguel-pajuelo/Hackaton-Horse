"""
Método determinista: detección de la máquina penalizante con el método de flechas
(arrow-based / turning point, Kuo-Lim-Meerkov 1996; Li-Chang-Ni 2009).

En una línea serie, para cada par de etapas consecutivas (j, j+1) se compara
    bloqueo de j      = SAT_j / TR_j      (j espera porque j+1 no le acepta la pieza)
    hambre de j+1     = DES_{j+1} / TR    (j+1 espera porque j no le entrega la pieza)
- Si SAT_j > DES_{j+1}  la flecha apunta hacia abajo (→): el problema está aguas abajo.
- Si no, apunta hacia arriba (←): el problema está aguas arriba.

Una etapa es cuello de botella (máquina penalizante) si las flechas convergen en ella:
la de antes está saturada por ella y la de después está desabastecida por ella.

Severidad (Kuo et al.):
    S_j = (SAT_{j-1} + DES_{j+1}) - (SAT_j + DES_j)       en fracción de TR
    S_1 = DES_2 - SAT_1 ;  S_M = SAT_{M-1} - DES_M         (extremos de la línea)

Horas inducidas: para cada cuello se recorre su zona de influencia
    - aguas arriba mientras las flechas apunten hacia él, sumando la SAT de esas etapas
    - aguas abajo mientras las flechas apunten hacia él, sumando la DES de esas etapas
Es una estimación de cuántas horas de parada inducida provocó en el resto de la línea,
y es la puntuación con la que se ordenan las máquinas (comparable con el modelo ML).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C

DER, IZQ = "→", "←"


def _analizar_periodo(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("Orden_etapa").reset_index(drop=True)
    m = len(g)
    tr = g["TR"].replace(0, np.nan)
    bl = (g["SAT"] / tr).fillna(0).to_numpy()
    st = (g["DES"] / tr).fillna(0).to_numpy()
    sat_h, des_h = g["SAT"].to_numpy(), g["DES"].to_numpy()

    # flecha[k] = flecha entre la etapa k y la k+1
    flecha = np.where(bl[:-1] > st[1:], DER, IZQ)

    entrada = np.array([""] + list(flecha))     # flecha entre j-1 y j
    salida = np.array(list(flecha) + [""])      # flecha entre j y j+1
    es_cuello = ((entrada == "") | (entrada == DER)) & ((salida == "") | (salida == IZQ))

    sev = np.empty(m)
    for j in range(m):
        if m == 1:
            sev[j] = 0.0
        elif j == 0:
            sev[j] = st[1] - bl[0]
        elif j == m - 1:
            sev[j] = bl[m - 2] - st[m - 1]
        else:
            sev[j] = (bl[j - 1] + st[j + 1]) - (bl[j] + st[j])

    h_arriba = np.zeros(m)
    h_abajo = np.zeros(m)
    zona_ini = np.arange(m)
    zona_fin = np.arange(m)
    for j in np.flatnonzero(es_cuello):
        k = j - 1
        while k >= 0 and flecha[k] == DER:
            h_arriba[j] += sat_h[k]
            k -= 1
        zona_ini[j] = k + 1
        k = j + 1
        while k < m and flecha[k - 1] == IZQ:
            h_abajo[j] += des_h[k]
            k += 1
        zona_fin[j] = k - 1

    out = g[["Periodo", "Etapa", "Orden_etapa"]].copy()
    out["bloqueo"] = bl
    out["hambre"] = st
    out["flecha_entrada"] = entrada
    out["flecha_salida"] = salida
    out["es_cuello"] = es_cuello
    out["severidad"] = sev
    out["horas_inducidas_arriba"] = h_arriba
    out["horas_inducidas_abajo"] = h_abajo
    out["horas_inducidas"] = h_arriba + h_abajo
    out["zona_desde"] = np.where(es_cuello, g["Etapa"].to_numpy()[zona_ini], "")
    out["zona_hasta"] = np.where(es_cuello, g["Etapa"].to_numpy()[zona_fin], "")

    # Ranking: primero los cuellos por horas inducidas, luego el resto por severidad
    orden = out.assign(_c=~out["es_cuello"]).sort_values(
        ["_c", "horas_inducidas", "severidad"], ascending=[True, False, False]
    ).index
    out.loc[orden, "rango_det"] = np.arange(1, m + 1)
    out["rango_det"] = out["rango_det"].astype(int)
    out["es_principal"] = out["rango_det"] == 1
    return out


def analizar(agregado: pd.DataFrame) -> pd.DataFrame:
    """Aplica el método a cada periodo, solo sobre las etapas de la cadena serie."""
    cadena = agregado[agregado["en_cadena"]]
    partes = [_analizar_periodo(g) for _, g in cadena.groupby("Periodo", sort=False)]
    return pd.concat(partes, ignore_index=True)


def resumen_dias(det_dia: pd.DataFrame) -> pd.DataFrame:
    """
    Consolida el análisis diario por etapa: cuántos días fue cuello / cuello principal.
    Sirve para ver si el cuello de botella es estable o va cambiando de máquina.
    """
    n = det_dia["Periodo"].nunique()
    r = det_dia.groupby(["Etapa", "Orden_etapa"], as_index=False).agg(
        dias_cuello=("es_cuello", "sum"),
        dias_principal=("es_principal", "sum"),
        horas_inducidas_total=("horas_inducidas", "sum"),
        horas_inducidas_media=("horas_inducidas", "mean"),
        severidad_media=("severidad", "mean"),
        rango_medio=("rango_det", "mean"),
    )
    r["pct_dias_cuello"] = r["dias_cuello"] / n
    r["pct_dias_principal"] = r["dias_principal"] / n
    return r.sort_values(["horas_inducidas_total"], ascending=False).reset_index(drop=True)
