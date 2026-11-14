"""
Análisis de máquinas penalizantes - reto LOSSIA (Hackathon HORSE).

Uso:
    python analisis.py [carpeta_datos_limpios] [carpeta_resultados]
    (por defecto: Datos_limpios/ y Resultados/)

Requiere haber ejecutado antes limpieza.py.

Salidas en Resultados/ (todas con columna 'Periodo' = 'GLOBAL' o día '2026-S40-D2',
para que la interfaz filtre por granularidad):
    etapas.csv                      operaciones -> etapa (paralelos fusionados), orden, si entra en la cadena
    kpis_{global,dia}.csv           Dp, Tcy, Fpm, % de paradas y semáforo frente a las referencias
    determinista_{global,dia}.csv   flechas, cuello de botella, severidad y horas inducidas
    determinista_resumen_dias.csv   cuántos días fue cada máquina cuello / cuello principal
    mantenimiento_{global,dia}.csv  ranking por parada propia (TAP) con Dp, Tcy y datos dudosos
    prioridades_{global,dia}.csv    vista unificada para la interfaz: categoría, motivo y orden
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

from lossia import config as C, datos, determinista, kpis, prioridades


def main(dir_limpios: Path, dir_res: Path) -> None:
    t0 = time.time()
    dir_res.mkdir(parents=True, exist_ok=True)

    def guardar(df: pd.DataFrame, nombre: str) -> None:
        df.to_csv(dir_res / nombre, index=False, encoding="utf-8")

    # 1. Datos y etapas
    d, cfg, reg = datos.cargar(dir_limpios)
    grupos = datos.grupos_paralelo(cfg, reg)
    mapa = datos.mapa_etapas(cfg, grupos)
    etapa_dia = datos.por_etapa_dia(d, mapa)
    guardar(mapa, "etapas.csv")
    print(f"Etapas: {etapa_dia['Etapa'].nunique()} ({mapa['en_cadena'].sum()} operaciones en cadena) | "
          f"días: {etapa_dia['Dia'].nunique()} | paralelos fusionados: {grupos}")

    # 2. KPIs, método determinista y prioridades por granularidad
    for nivel in C.NIVELES:
        agg = datos.agregar(etapa_dia, nivel)
        k = kpis.calcular(agg)
        det = determinista.analizar(agg, etapa_dia if nivel == "global" else None)
        guardar(k, f"kpis_{nivel}.csv")
        guardar(det, f"determinista_{nivel}.csv")
        guardar(prioridades.mantenimiento(k), f"mantenimiento_{nivel}.csv")
        guardar(prioridades.vista(k, det), f"prioridades_{nivel}.csv")
        if nivel == "dia":
            guardar(determinista.resumen_dias(det), "determinista_resumen_dias.csv")

    # 3. Resumen por consola
    pri = pd.read_csv(dir_res / "prioridades_global.csv", keep_default_na=False)
    print("\n=== PRIORIDADES (GLOBAL) ===")
    print(pri[pri["categoria"] != ""][["orden_vista", "Etapa", "categoria", "motivo"]].to_string(index=False))
    res = pd.read_csv(dir_res / "determinista_resumen_dias.csv")
    n = etapa_dia["Dia"].nunique()
    print("\n=== ESTABILIDAD DIARIA DEL CUELLO DE BOTELLA ===")
    for _, f in res[res["dias_relevante"] > 0].head(5).iterrows():
        print(f"  {f['Etapa']:<10} principal {int(f['dias_principal']):>2}/{n} días | "
              f"cuello relevante {int(f['dias_relevante']):>2}/{n} días")
    print(f"\nResultados en {dir_res}  ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(Path(args[0]) if args else C.DIR_LIMPIOS,
         Path(args[1]) if len(args) > 1 else C.DIR_RESULTADOS)
