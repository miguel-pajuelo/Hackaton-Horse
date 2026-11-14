"""
Simulador "¿qué pasa si mejoro el tiempo de ciclo de X?" (gemelo digital ligero).

Modelo de capacidad (cuello de botella del día, "shifting bottleneck"):

    tiempo disponible_i = TBF_i + DES_i + SAT_i     (todo menos su parada propia)
    ciclo_i            = TBF_i / NPR_i              (horas por motor cuando trabaja)
    capacidad_i        = tiempo disponible_i / ciclo_i
                       = motores que haría si nunca esperase a sus vecinas

En una línea serie, la línea produce lo que permite la etapa con MENOS capacidad ese día:
el cuello de botella del día. Equivale a "la máquina que menos espera" (DES + SAT), porque
capacidad_i / NPR_i = 1 + (DES_i + SAT_i) / TBF_i.

Simular una mejora del Tcy de X en un p % multiplica su capacidad por 1 / (1 - p). La línea
gana motores solo los días en que X era el cuello, y como mucho hasta la capacidad de la
siguiente etapa más limitada: por eso a menudo hay que mejorar varias máquinas a la vez.

Calibración: con los datos actuales, la capacidad mínima reproduce la producción real con
un error medio del ~1,6 % (ver calibracion()).

Limitaciones (es un modelo ligero, no una simulación de eventos):
- No modela buffers ni la dinámica dentro del día; usa totales diarios.
- Las etapas con contador de piezas no fiable no tienen ciclo calculable y se excluyen.
- La parada propia (TAP) no cambia al mejorar el ciclo.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from . import datos as D


def capacidades(etapa_dia: pd.DataFrame) -> pd.DataFrame:
    """
    Capacidad diaria de cada etapa de la cadena serie (salida de datos.por_etapa_dia).
    Devuelve una tabla Dia x Etapa en motores/día. Excluye etapas sin piezas fiables.
    """
    ch = etapa_dia[etapa_dia["en_cadena"] & etapa_dia["NPR"].gt(0)].copy()
    ch["ciclo_h"] = ch["TBF"] / ch["NPR"]
    ch["capacidad"] = (ch["TBF"] + ch["DES"] + ch["SAT"]) / ch["ciclo_h"]
    return ch.pivot(index="Dia", columns="Etapa", values="capacidad")


def produccion_real(etapa_dia: pd.DataFrame) -> pd.Series:
    """Motores/día de la línea: mediana de NPR de las etapas de la cadena con piezas fiables."""
    ch = etapa_dia[etapa_dia["en_cadena"] & etapa_dia["NPR"].gt(0)]
    return ch.groupby("Dia")["NPR"].median()


def calibracion(etapa_dia: pd.DataFrame) -> pd.DataFrame:
    """Producción del modelo (capacidad mínima) frente a la real, por día."""
    cap = capacidades(etapa_dia)
    real = produccion_real(etapa_dia).reindex(cap.index)
    out = pd.DataFrame({"produccion_real": real, "produccion_modelo": cap.min(axis=1),
                        "cuello": cap.idxmin(axis=1)})
    out["error_pct"] = 100 * (out["produccion_modelo"] - out["produccion_real"]) / out["produccion_real"]
    return out


def simular(etapa_dia: pd.DataFrame, mejoras: dict[str, float]) -> dict:
    """
    mejoras: {etapa: reducción del tiempo de ciclo en fracción (0.10 = un 10 % más rápida)}

    Devuelve:
      por_dia   Dia, cuello antes / después, motores antes / después y ganancia
      resumen   ganancia media (motores/día), total en el periodo, días con ganancia,
                nuevo cuello más frecuente, etapas ignoradas (sin ciclo calculable)
    """
    cap = capacidades(etapa_dia)
    ignoradas = [e for e in mejoras if e not in cap.columns]
    for e, p in mejoras.items():
        if not 0 <= p < 1:
            raise ValueError(f"La reducción del ciclo de {e} debe estar en [0, 1): {p}")
    nueva = cap.copy()
    for e, p in mejoras.items():
        if e in nueva.columns:
            nueva[e] = nueva[e] / (1 - p)

    antes, despues = cap.min(axis=1), nueva.min(axis=1)
    por_dia = pd.DataFrame({
        "cuello_antes": cap.idxmin(axis=1), "motores_antes": antes,
        "cuello_despues": nueva.idxmin(axis=1), "motores_despues": despues,
    })
    por_dia["ganancia"] = por_dia["motores_despues"] - por_dia["motores_antes"]
    con_ganancia = por_dia["ganancia"] > 0.5
    resumen = {
        "ganancia_media_dia": float(por_dia["ganancia"].mean()),
        "ganancia_total": float(por_dia["ganancia"].sum()),
        "ganancia_pct": float(100 * por_dia["ganancia"].sum() / por_dia["motores_antes"].sum()),
        "dias_con_ganancia": int(con_ganancia.sum()),
        "dias": int(len(por_dia)),
        "nuevo_cuello_frecuente": por_dia["cuello_despues"].mode().iat[0] if len(por_dia) else None,
        "ignoradas": ignoradas,
    }
    return {"por_dia": por_dia.reset_index(), "resumen": resumen}


def potencial(etapa_dia: pd.DataFrame, reduccion: float = 0.10) -> pd.DataFrame:
    """
    Para cada etapa, ganancia de motores/día si SOLO ella mejorase su ciclo `reduccion`.
    Incluye el techo: lo máximo que ganaría con capacidad ilimitada (hasta el siguiente cuello).
    Sirve para decidir dónde actuar primero.
    """
    cap = capacidades(etapa_dia)
    base = cap.min(axis=1)
    filas = []
    for e in cap.columns:
        mejor = cap.copy()
        mejor[e] = mejor[e] / (1 - reduccion)
        techo = cap.drop(columns=e).min(axis=1)
        g, gt = mejor.min(axis=1) - base, techo - base
        filas.append({
            "Etapa": e,
            "dias_cuello": int((cap.idxmin(axis=1) == e).sum()),
            "ganancia_media_dia": float(g.mean()),
            "techo_media_dia": float(gt.clip(lower=0).mean()),
            "dias_con_ganancia": int((g > 0.5).sum()),
        })
    return (pd.DataFrame(filas).sort_values(["ganancia_media_dia", "techo_media_dia"], ascending=False)
            .reset_index(drop=True))


def _cargar_etapa_dia() -> pd.DataFrame:
    d, c, r = D.cargar()
    return D.por_etapa_dia(d, D.mapa_etapas(c, D.grupos_paralelo(c, r)))


def main(argv: list[str]) -> None:
    """
    Uso:
        python -m lossia.simulador                        potencial de cada etapa (Tcy -10 %)
        python -m lossia.simulador ST_1000=10 PM_2020=15  simula esas mejoras (% de Tcy)
    """
    ed = _cargar_etapa_dia()
    cal = calibracion(ed)
    print(f"Calibración: error medio {cal['error_pct'].abs().mean():.1f} % "
          f"(máx {cal['error_pct'].abs().max():.1f} %) frente a la producción real")
    if not argv:
        print("\nPotencial si cada etapa redujera su tiempo de ciclo un 10 % (motores/día):")
        print(potencial(ed).head(10).round(1).to_string(index=False))
        return
    mejoras = {}
    for arg in argv:
        etapa, pct = arg.split("=")
        mejoras[etapa] = float(pct) / 100
    res = simular(ed, mejoras)
    r = res["resumen"]
    texto = ", ".join(f"{e} −{p:.0%}" for e, p in mejoras.items())
    print(f"\nMejora del tiempo de ciclo: {texto}")
    print(f"  +{r['ganancia_media_dia']:.1f} motores/día ({r['ganancia_pct']:+.2f} %), "
          f"+{r['ganancia_total']:.0f} en los {r['dias']} días")
    print(f"  días con ganancia: {r['dias_con_ganancia']}/{r['dias']} · "
          f"nuevo cuello más frecuente: {r['nuevo_cuello_frecuente']}")
    if r["ignoradas"]:
        print(f"  sin ciclo calculable (contador no fiable o fuera de la cadena): {r['ignoradas']}")


if __name__ == "__main__":
    main(sys.argv[1:])
