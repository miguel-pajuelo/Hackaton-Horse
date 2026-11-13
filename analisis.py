"""
Análisis de máquinas penalizantes - reto LOSSIA (Hackathon HORSE).

Uso:
    python analisis.py [carpeta_datos_limpios] [carpeta_resultados]
    (por defecto: Datos_limpios/ y Resultados/)

Requiere haber ejecutado antes limpieza.py.

Salidas en Resultados/ (todas con columna 'Periodo' = 'GLOBAL' o día 'S40-D2',
para que la interfaz filtre por granularidad):
    etapas.csv                 operaciones -> etapa (paralelos fusionados), orden, si entra en la cadena
    kpis_{global,dia}.csv      Dp, Tcy, Fpm, % de paradas y semáforo frente a las referencias
    determinista_{global,dia}.csv   flechas, cuello de botella, severidad y horas inducidas
    determinista_resumen_dias.csv   cuántos días fue cada máquina cuello / cuello principal
    ml_relaciones.csv          relaciones causa -> efecto aprendidas (coef., estabilidad, dirección)
    ml_calidad.csv             R² en validación cruzada de cada modelo
    ml_{global,dia}.csv        horas de parada inducida atribuidas a cada máquina
    comparacion_{global,dia}.csv    ambos rankings lado a lado con etiqueta de acuerdo
    comparacion_metricas.csv   Spearman, solape del top-K y máquina principal por periodo
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

from lossia import comparacion, config as C, datos, determinista, kpis, ml


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
    etapas = etapa_dia.drop_duplicates("Etapa")[["Etapa", "Orden_etapa"]]
    print(f"Etapas: {etapas.shape[0]} ({mapa['en_cadena'].sum()} operaciones en cadena) | "
          f"días: {etapa_dia['Dia'].nunique()} | paralelos fusionados: {grupos}")

    # 2. ML (se ajusta una vez con todos los días; luego se puntúa por nivel)
    print(f"Ajustando modelo ML ({C.ML_N_BOOTSTRAP} remuestreos)...")
    rel, cal = ml.ajustar(etapa_dia)
    guardar(rel, "ml_relaciones.csv")
    guardar(cal, "ml_calidad.csv")
    atrib = ml.horas_inducidas_dia(etapa_dia, rel)

    metricas = []
    for nivel in C.NIVELES:
        agg = datos.agregar(etapa_dia, nivel)
        guardar(kpis.calcular(agg), f"kpis_{nivel}.csv")
        det = determinista.analizar(agg)
        guardar(det, f"determinista_{nivel}.csv")
        if nivel == "dia":
            guardar(determinista.resumen_dias(det), "determinista_resumen_dias.csv")
        pml = ml.puntuar(atrib, nivel, etapas)
        guardar(pml, f"ml_{nivel}.csv")
        uni = comparacion.unir(det, pml)
        guardar(uni, f"comparacion_{nivel}.csv")
        metricas.append(comparacion.metricas(uni).assign(Nivel=nivel))
    met = pd.concat(metricas, ignore_index=True)
    guardar(met, "comparacion_metricas.csv")

    # 3. Resumen por consola
    g = met[met["Nivel"] == "global"].iloc[0]
    dia = met[met["Nivel"] == "dia"]
    est = rel[rel["estable"]]
    print("\n=== RESULTADO GLOBAL ===")
    uni_g = pd.read_csv(dir_res / "comparacion_global.csv")
    print(uni_g.head(C.TOP_K)[["Etapa", "es_cuello", "horas_inducidas", "rango_det",
                               "horas_inducidas_ml", "rango_ml", "acuerdo"]].round(1).to_string(index=False))
    print(f"\nPrincipal determinista: {g['principal_det']} | principal ML: {g['principal_ml']}")
    print(f"Spearman global: {g['spearman']:.2f} | solape top-{C.TOP_K}: {g[f'solape_top{C.TOP_K}']:.0%}")
    print(f"Por día: Spearman medio {dia['spearman'].mean():.2f}, "
          f"misma principal en {dia['misma_principal'].mean():.0%} de los días")
    print(f"ML: {len(est)} relaciones estables, {est['direccion_logica'].mean():.0%} con dirección "
          f"físicamente lógica | R² CV mediano {cal['r2_cv'].median():.2f}")
    print(f"\nResultados en {dir_res}  ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(Path(args[0]) if args else C.DIR_LIMPIOS,
         Path(args[1]) if len(args) > 1 else C.DIR_RESULTADOS)
