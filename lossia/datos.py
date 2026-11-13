"""
Carga de los datos limpios, construcción de etapas y agregación por periodo.

Conceptos:
- Operación: máquina/puesto tal y como viene en los datos (Operacion_norm).
- Etapa: unidad de análisis. Normalmente una operación; las estaciones en paralelo
  se fusionan en una sola etapa (tiempos promediados, piezas y paradas sumadas).
- Periodo: 'GLOBAL' (todos los días) o un día 'S40-D2'.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C

TIEMPOS = ["TBF", "TAP", "DES", "SAT", "T_no_registrado"]
CONTADORES = ["NAP", "NPR"]


def cargar(dir_limpios: Path = C.DIR_LIMPIOS) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Devuelve (datos, config, registro) solo con las operaciones que entran al análisis."""
    datos = pd.read_csv(dir_limpios / "datos_limpios.csv")
    config = pd.read_csv(dir_limpios / "config_limpia.csv")
    with open(dir_limpios / "registro_limpieza.json", encoding="utf-8") as f:
        registro = json.load(f)

    datos = datos[datos["incluir_analisis"]].copy()
    config = config[config["incluir_analisis"]].copy()
    datos["Dia"] = "S" + datos["Week"].astype(str) + "-D" + datos["Jour"].astype(str)
    # Piezas no fiables: no se usan para ratios por pieza (Tcy, Fpm)
    datos.loc[datos["flag_npr_invalido"], "NPR"] = np.nan
    return datos, config, registro


def grupos_paralelo(config: pd.DataFrame, registro: dict) -> list[list[str]]:
    """Grupos de operaciones en paralelo (ver config.GRUPOS_PARALELO)."""
    if C.GRUPOS_PARALELO is not None:
        return [list(g) for g in C.GRUPOS_PARALELO]

    sospechosas = {
        e["operacion"] for e in registro.get("entradas", []) if e.get("categoria") == "posible_paralelo"
    }
    cand = config[config["Operacion"].isin(sospechosas) | config["Operacion_norm"].isin(sospechosas)]
    cand = cand.sort_values("Orden_OP")
    grupos: list[list[str]] = []
    ultimo_orden = None
    for _, fila in cand.iterrows():
        if grupos and fila["Orden_OP"] - ultimo_orden <= C.DISTANCIA_MAX_PARALELO:
            grupos[-1].append(fila["Operacion_norm"])
        else:
            grupos.append([fila["Operacion_norm"]])
        ultimo_orden = fila["Orden_OP"]
    return [g for g in grupos if len(g) > 1]


def mapa_etapas(config: pd.DataFrame, grupos: list[list[str]]) -> pd.DataFrame:
    """Tabla Operacion_norm -> Etapa, con orden de la etapa y si entra en la cadena serie."""
    m = config[["Operacion_norm", "Orden_OP", "Tipo"]].copy()
    m["Etapa"] = m["Operacion_norm"]
    for g in grupos:
        nombre = "+".join(sorted(g))
        m.loc[m["Operacion_norm"].isin(g), "Etapa"] = nombre
    m["n_paralelo"] = m.groupby("Etapa")["Operacion_norm"].transform("count")
    m["Orden_etapa"] = m.groupby("Etapa")["Orden_OP"].transform("min")
    m["en_cadena"] = ~m["Tipo"].isin(C.TIPOS_FUERA_CADENA)
    return m


def por_etapa_dia(datos: pd.DataFrame, mapa: pd.DataFrame) -> pd.DataFrame:
    """Una fila por (Dia, Etapa). Paralelos: tiempos medios, NAP/NPR sumados."""
    d = datos.merge(mapa[["Operacion_norm", "Etapa"]], on="Operacion_norm")
    agg = {c: "mean" for c in TIEMPOS} | {c: lambda s: s.sum(min_count=1) for c in CONTADORES}
    out = d.groupby(["Week", "Jour", "Dia", "Etapa"], as_index=False).agg(agg)
    info = mapa.drop_duplicates("Etapa")[["Etapa", "Orden_etapa", "Tipo", "en_cadena", "n_paralelo"]]
    out = out.merge(info, on="Etapa")
    out["TAI"] = out["DES"] + out["SAT"]
    return out.sort_values(["Week", "Jour", "Orden_etapa"]).reset_index(drop=True)


def agregar(etapa_dia: pd.DataFrame, nivel: str) -> pd.DataFrame:
    """
    Agrega a la granularidad pedida. Devuelve columnas 'Periodo' + Etapa + horas y contadores.
    - 'dia':    tal cual (Periodo = 'S40-D2').
    - 'global': suma de todos los días (Periodo = 'GLOBAL'), con n_dias para medias.
    """
    if nivel == "dia":
        out = etapa_dia.copy()
        out.insert(0, "Periodo", out["Dia"])
        out["n_dias"] = 1
    elif nivel == "global":
        agg = {c: "sum" for c in TIEMPOS + ["TAI"]} | {c: lambda s: s.sum(min_count=1) for c in CONTADORES}
        agg |= {"Dia": "nunique", "Orden_etapa": "first", "Tipo": "first",
                "en_cadena": "first", "n_paralelo": "first"}
        out = etapa_dia.groupby("Etapa", as_index=False).agg(agg).rename(columns={"Dia": "n_dias"})
        out.insert(0, "Periodo", C.GLOBAL)
    else:
        raise ValueError(f"Nivel desconocido: {nivel!r} (usa {C.NIVELES})")
    out["TR"] = out["TBF"] + out["TAP"] + out["DES"] + out["SAT"]
    return out.sort_values(["Periodo", "Orden_etapa"]).reset_index(drop=True)
