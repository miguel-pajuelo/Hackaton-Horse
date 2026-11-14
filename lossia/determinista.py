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

Máquina penalizante ("relevante"): cumple las dos condiciones
  1. las flechas convergen en ella con severidad >= config.SEVERIDAD_MIN, y
  2. TAP / TAI > config.COCIENTE_TAP_TAI_MIN (criterio de HORSE): se para más por sí misma
     que por culpa de sus vecinas. Si no, es una víctima de su entorno aunque las flechas
     converjan en ella (la saturación de la anterior puede venir de otra causa).
Las máquinas se ordenan por relevancia y severidad (la severidad mide cuánto más esperan
las vecinas que ella misma). En un periodo de varios días, si se pasan las filas diarias
(`etapa_dia`), las penalizantes se ordenan primero por el número de días en que fueron la
penalizante principal y después por severidad: así un empate de severidad en el agregado
lo decide la máquina que más días frena la línea.

Horas inducidas: para cada cuello se recorre su zona de influencia
    - aguas arriba mientras las flechas apunten hacia él, sumando la SAT de esas etapas
    - aguas abajo mientras las flechas apunten hacia él, sumando la DES de esas etapas
Es una estimación de cuántas horas de parada inducida provocó en el resto de la línea
(dato informativo para la interfaz). No se usa para ordenar porque una zona larga con flechas
débiles infla las horas aunque la evidencia sea poca.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C, datos as D

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

    tap = g["TAP"].to_numpy(dtype=float)
    tai = (g["DES"] + g["SAT"]).to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        cociente = np.where(tai > 0, tap / tai, np.where(tap > 0, np.inf, np.nan))
    out["cociente_tap_tai"] = cociente
    out["causa_propia"] = np.nan_to_num(cociente, nan=0.0) > C.COCIENTE_TAP_TAI_MIN
    out["es_relevante"] = (out["es_cuello"] & (out["severidad"] >= C.SEVERIDAD_MIN)
                           & out["causa_propia"])
    return _ordenar(out)


def _ordenar(out: pd.DataFrame) -> pd.DataFrame:
    """
    Ranking de un periodo: penalizantes, luego cuellos no penalizantes, luego el resto.
    Dentro de las penalizantes, por días como principal (si existe la columna) y severidad.
    """
    out = out.copy()
    dias = out["dias_principal"] if "dias_principal" in out else pd.Series(0, index=out.index)
    orden = out.assign(_r=~out["es_relevante"], _c=~out["es_cuello"],
                       _d=dias.where(out["es_relevante"], 0)).sort_values(
        ["_r", "_c", "_d", "severidad"], ascending=[True, True, False, False]
    ).index
    out.loc[orden, "rango_det"] = np.arange(1, len(out) + 1)
    out["rango_det"] = out["rango_det"].astype(int)
    out["es_principal"] = out["rango_det"] == 1
    return out


def analizar(agregado: pd.DataFrame, etapa_dia: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Aplica el método a cada periodo, solo sobre las etapas de la cadena serie.

    etapa_dia: filas (día, etapa) con las que se construyó `agregado`. Si se pasan, se añade
    `dias_principal` (días en que cada etapa fue la penalizante principal) y se usa para
    desempatar el ranking del periodo agregado.
    """
    cadena = agregado[agregado["en_cadena"]]
    out = pd.concat([_analizar_periodo(g) for _, g in cadena.groupby("Periodo", sort=False)],
                    ignore_index=True)
    if etapa_dia is None:
        return out
    diario = analizar(D.agregar(etapa_dia, "dia"))
    dias = diario.groupby("Etapa")["es_principal"].sum()
    out["dias_principal"] = out["Etapa"].map(dias).fillna(0).astype(int)
    return pd.concat([_ordenar(g) for _, g in out.groupby("Periodo", sort=False)],
                     ignore_index=True)


def resumen_dias(det_dia: pd.DataFrame) -> pd.DataFrame:
    """
    Consolida el análisis diario por etapa: cuántos días fue cuello / cuello principal.
    Sirve para ver si el cuello de botella es estable o va cambiando de máquina.
    """
    n = det_dia["Periodo"].nunique()
    r = det_dia.groupby(["Etapa", "Orden_etapa"], as_index=False).agg(
        dias_cuello=("es_cuello", "sum"),
        dias_principal=("es_principal", "sum"),
        dias_relevante=("es_relevante", "sum"),
        horas_inducidas_total=("horas_inducidas", "sum"),
        horas_inducidas_media=("horas_inducidas", "mean"),
        severidad_media=("severidad", "mean"),
        rango_medio=("rango_det", "mean"),
    )
    r["pct_dias_cuello"] = r["dias_cuello"] / n
    r["pct_dias_principal"] = r["dias_principal"] / n
    r["pct_dias_relevante"] = r["dias_relevante"] / n
    return r.sort_values(["dias_principal", "dias_relevante", "severidad_media"],
                         ascending=False).reset_index(drop=True)
