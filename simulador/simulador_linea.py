"""
Simulador de eventos discretos de la Línea 5 (reto LOSSIA, Hackathon HORSE).

Reproduce la línea como una cadena de etapas en serie con buffers finitos:
cada pieza pasa por todas las etapas; cada etapa tarda su tiempo de ciclo y,
de vez en cuando, sufre paradas propias (TAP). Las paradas se propagan solas:
la etapa siguiente se queda sin piezas (DES) y la anterior se bloquea (SAT).

Parámetros por etapa (de Datos_limpios/datos_limpios.csv y Resultados/etapas.csv):
    tiempo de ciclo     = TBF / NPR                 [s/pieza]
    paradas por pieza   = NAP / NPR                 (Poisson)
    duración de parada  = TAP / NAP                 [s/parada] (exponencial)

Uso (desde la raíz del repo):
    python simulador/simulador_linea.py                      # todo
    python simulador/simulador_linea.py --ignorar-tap ST_2235  # trata su TAP como no fiable

Salidas en simulador/salidas/:
    validacion_etapas.csv   DES y SAT simulados frente a los reales por etapa
    ranking_simulado.csv    motores/día ganados al eliminar las paradas de cada etapa
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

H = 3600.0  # segundos por hora


# ----------------------------------------------------------------------------
# 1. Parámetros
# ----------------------------------------------------------------------------
def cargar_parametros(raiz: Path) -> tuple[pd.DataFrame, float, float]:
    d = pd.read_csv(raiz / "Datos_limpios" / "datos_limpios.csv")
    e = pd.read_csv(raiz / "Resultados" / "etapas.csv")

    d = d[d["incluir_analisis"]].merge(
        e[["Operacion_norm", "Etapa", "Orden_etapa", "n_paralelo", "en_cadena"]],
        on="Operacion_norm",
    )
    d = d[d["en_cadena"]].copy()
    # Contador de piezas no fiable (ST_0295, ST_2235, ST_3300): se usa la
    # producción típica de la línea ese día (mediana de las máquinas fiables)
    npr_dia = (d[~d["flag_npr_invalido"]].groupby(["Week", "Jour"])["NPR"].median()
               .rename("NPR_linea").reset_index())
    d = d.merge(npr_dia, on=["Week", "Jour"])
    d["NPR"] = d["NPR"].astype(float)
    malo = d["flag_npr_invalido"]
    d.loc[malo, "NPR"] = d.loc[malo, "NPR_linea"] * d.loc[malo, "n_paralelo"].rdiv(1)
    n_dias = d[["Week", "Jour"]].drop_duplicates().shape[0]
    horas_dia = float((d["TBF"] + d["TAP"] + d["DES"] + d["SAT"]).groupby(
        [d["Week"], d["Jour"]]).median().median())

    g = (d.groupby("Etapa")
           .agg(Orden=("Orden_etapa", "first"), n_par=("n_paralelo", "first"),
                TBF=("TBF", "sum"), TAP=("TAP", "sum"), DES=("DES", "sum"),
                SAT=("SAT", "sum"), NAP=("NAP", "sum"), NPR=("NPR", "sum"))
           .sort_values("Orden").reset_index())

    # En etapas en paralelo, TBF y NPR son sumas de n máquinas que trabajan a la vez:
    # el tiempo efectivo por pieza de la etapa es (TBF/n) / NPR
    g["ciclo_s"] = g["TBF"] / g["n_par"] * H / g["NPR"]
    g["paradas_por_pieza"] = g["NAP"] / g["NPR"]
    g["dur_parada_s"] = np.where(g["NAP"] > 0, g["TAP"] * H / g["NAP"].clip(lower=1), 0.0)
    # Una parada en una de n máquinas en paralelo solo quita 1/n de la capacidad
    g["dur_parada_s"] /= g["n_par"]

    for c in ["TAP", "DES", "SAT"]:
        g[f"{c}_real_h_dia"] = g[c] / n_dias
    produccion_real = float(d.groupby(["Week", "Jour"])["NPR"].median().mean())
    return g, horas_dia, produccion_real


# ----------------------------------------------------------------------------
# 2. Motor de simulación (recursión de tiempos de salida, línea con bloqueo)
# ----------------------------------------------------------------------------
def tiempos_servicio(p: pd.DataFrame, n_piezas: int, rng: np.random.Generator) -> np.ndarray:
    """Matriz [etapa, pieza] con ciclo + paradas sufridas al procesar esa pieza."""
    n = len(p)
    ciclo = p["ciclo_s"].to_numpy()[:, None]
    lam = p["paradas_por_pieza"].to_numpy()[:, None]
    dur = p["dur_parada_s"].to_numpy()[:, None]
    k = rng.poisson(np.broadcast_to(lam, (n, n_piezas)))
    paradas = rng.gamma(shape=np.maximum(k, 1e-12), scale=np.broadcast_to(dur, (n, n_piezas)))
    paradas[k == 0] = 0.0
    return ciclo + paradas, paradas


def simular(t: np.ndarray, buffer, horizonte_s: float, guardar: bool = False) -> dict:
    """
    t[i, k]: tiempo de servicio de la pieza k en la etapa i.
    Bloqueo tras servicio: la pieza sale de i cuando hay hueco en el buffer de i+1.
    Mide en la ventana [horizonte, 2*horizonte) para quitar el arranque en vacío.
    """
    n, K = t.shape
    # buffer: un entero (mismo tamaño en todos los tramos) o una lista con el de cada tramo i -> i+1
    cap = [int(buffer)] * max(n - 1, 0) if np.isscalar(buffer) else [int(b) for b in buffer]
    if len(cap) != max(n - 1, 0):
        raise ValueError(f"Se esperaban {n - 1} buffers y llegaron {len(cap)}")
    S = np.zeros((n, K))  # inicio
    D = np.zeros((n, K))  # salida
    C = np.zeros((n, K))  # fin de proceso (antes de esperar hueco)
    des = np.zeros(n)
    sat = np.zeros(n)
    t0, t1 = horizonte_s, 2 * horizonte_s
    tl = t.tolist()
    for k in range(K):
        for i in range(n):
            llegada = D[i - 1, k] if i > 0 else 0.0
            libre = D[i, k - 1] if k > 0 else 0.0
            s = llegada if llegada > libre else libre
            c = s + tl[i][k]
            if i < n - 1 and k - cap[i] - 1 >= 0:
                hueco = S[i + 1, k - cap[i] - 1]
                d = c if c > hueco else hueco
            else:
                d = c
            S[i, k] = s
            D[i, k] = d
            C[i, k] = c
            if t0 <= d < t1:
                if i > 0 and llegada > libre:
                    des[i] += llegada - libre
                sat[i] += d - c
    salidas = D[-1]
    piezas = int(((salidas >= t0) & (salidas < t1)).sum())
    out = {"piezas": piezas, "DES_h": des / H, "SAT_h": sat / H}
    if guardar:
        out.update(S=S, C=C, D=D)
    return out


def piezas_necesarias(p: pd.DataFrame, horizonte_s: float) -> int:
    return int(2.3 * horizonte_s / p["ciclo_s"].max()) + 50


DIAS_MEDIDA = 5   # jornadas que se promedian para las cifras de producción


def produccion_media(p, factores, buffer, horizonte, semilla, dias=DIAS_MEDIDA):
    """Motores/día medios en `dias` jornadas seguidas tras una de calentamiento, con los mismos
    números aleatorios en todos los escenarios (así las diferencias se deben a la mejora)."""
    K = int((dias + 1.3) * horizonte / p["ciclo_s"].max()) + 50
    t, paradas = tiempos_servicio(p, K, np.random.default_rng(semilla + 1))
    for etapa, f in factores.items():
        i = int(p.index[p["Etapa"] == etapa][0])
        t[i] -= paradas[i] * (1 - f)
    salidas = np.sort(simular(t, buffer, horizonte, guardar=True)["D"][-1])
    medidos = np.searchsorted(salidas, (dias + 1) * horizonte) - np.searchsorted(salidas, horizonte)
    return medidos / dias


# ----------------------------------------------------------------------------
# 3. Experimentos
# ----------------------------------------------------------------------------
def ejecutar(p, horizonte_s, buffer, reps, semilla, quitar=None, factor=0.0):
    """Media de piezas/día. 'quitar' = índice de etapa cuyas paradas se multiplican por factor."""
    K = piezas_necesarias(p, horizonte_s)
    res = []
    for r in range(reps):
        rng = np.random.default_rng(semilla + r)  # números aleatorios comunes
        t, paradas = tiempos_servicio(p, K, rng)
        if quitar is not None:
            t[quitar] -= paradas[quitar] * (1 - factor)
        res.append(simular(t, buffer, horizonte_s))
    return {
        "piezas": float(np.mean([x["piezas"] for x in res])),
        "DES_h": np.mean([x["DES_h"] for x in res], axis=0),
        "SAT_h": np.mean([x["SAT_h"] for x in res], axis=0),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", type=Path, default=Path("."))
    ap.add_argument("--reps", type=int, default=3, help="réplicas por escenario")
    ap.add_argument("--buffer", type=int, default=None, help="tamaño de buffer; si no, se calibra")
    ap.add_argument("--ignorar-tap", nargs="*", default=[], help="etapas cuyo TAP se considera no fiable")
    ap.add_argument("--semilla", type=int, default=2026)
    a = ap.parse_args()

    p, horas_dia, real = cargar_parametros(a.raiz)
    horizonte = horas_dia * H
    for et in a.ignorar_tap:
        p.loc[p["Etapa"] == et, ["paradas_por_pieza", "dur_parada_s"]] = 0.0
    salida = a.raiz / "simulador" / "salidas"
    salida.mkdir(parents=True, exist_ok=True)

    print(f"Etapas en cadena: {len(p)} | jornada: {horas_dia:.1f} h | producción real: {real:.0f} motores/día")
    if a.ignorar_tap:
        print(f"TAP ignorado en: {', '.join(a.ignorar_tap)}")

    # 3.1 Calibración del buffer: el que mejor reproduce la producción real
    if a.buffer is None:
        print("\nCalibrando buffer entre etapas…")
        mejor = None
        for b in [0, 1, 2, 3, 5, 8, 10]:
            x = produccion_media(p, {}, b, horizonte, a.semilla)
            print(f"  buffer={b}: {x:7.0f} motores/día")
            if mejor is None or abs(x - real) < abs(mejor[1] - real):
                mejor = (b, x)
        a.buffer = mejor[0]
    base = ejecutar(p, horizonte, a.buffer, a.reps, a.semilla)
    base["piezas"] = produccion_media(p, {}, a.buffer, horizonte, a.semilla)
    err = (base["piezas"] - real) / real * 100
    print(f"\nEscenario base (buffer={a.buffer}, media de {DIAS_MEDIDA} jornadas): {base['piezas']:.0f} motores/día "
          f"frente a {real:.0f} reales ({err:+.1f} %)")

    # 3.2 Validación por etapa: DES y SAT simulados frente a reales
    val = p[["Etapa", "Orden", "TAP_real_h_dia", "DES_real_h_dia", "SAT_real_h_dia"]].copy()
    val["DES_sim_h_dia"] = base["DES_h"]
    val["SAT_sim_h_dia"] = base["SAT_h"]
    val.round(3).to_csv(salida / "validacion_etapas.csv", index=False)
    for c in ["DES", "SAT"]:
        r = val[f"{c}_real_h_dia"].corr(val[f"{c}_sim_h_dia"], method="spearman")
        print(f"  Correlación (Spearman) {c} real vs simulado por etapa: {r:.2f}")

    # 3.3 Ranking: ¿cuántos motores/día se ganan si una etapa no tuviera paradas?
    print(f"\nSimulando sin paradas cada una de las {len(p)} etapas…")
    filas = []
    for i, fila in p.iterrows():
        if fila["paradas_por_pieza"] == 0:
            ganancia = 0.0
        else:
            ganancia = produccion_media(p, {fila["Etapa"]: 0.0}, a.buffer, horizonte, a.semilla) - base["piezas"]
        filas.append({"Etapa": fila["Etapa"], "Orden": fila["Orden"],
                      "TAP_h_dia": round(fila["TAP_real_h_dia"], 2),
                      "motores_dia_ganados": round(ganancia, 1),
                      "ganancia_pct": round(ganancia / base["piezas"] * 100, 2)})
    rk = pd.DataFrame(filas).sort_values("motores_dia_ganados", ascending=False)
    rk.insert(0, "rango", range(1, len(rk) + 1))
    rk.to_csv(salida / "ranking_simulado.csv", index=False)
    print("\nTop 10 etapas por motores/día ganados al eliminar sus paradas:")
    print(rk.head(10).to_string(index=False))
    print(f"\nResultados en {salida}/")


if __name__ == "__main__":
    main()
