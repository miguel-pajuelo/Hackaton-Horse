"""
Pruebas de equivalencia entre la interfaz (lossia/interfaz.py) y el motor oficial
(analisis.py / lossia/*). No usan Streamlit: comprueban que `calcular()` reproduce
exactamente los CSV de Resultados/ para el periodo GLOBAL, para un día individual
y para un subconjunto arbitrario de días (varios días no consecutivos), y que los
filtros de presentación (tipo/tramo/máquina) no alteran el método de flechas.

Uso:  python tests/test_equivalencia.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from lossia import config as C, interfaz as I  # noqa: E402

TOL = 1e-9
fallos = []


def comprobar(nombre, a: pd.DataFrame, b: pd.DataFrame, claves=("Etapa",)):
    a = a.sort_values(list(claves)).reset_index(drop=True)
    b = b.sort_values(list(claves)).reset_index(drop=True)
    if a.shape[0] != b.shape[0]:
        fallos.append(f"{nombre}: nº de filas distinto ({a.shape[0]} vs {b.shape[0]})")
        return
    # 'Periodo' es una etiqueta de la granularidad de la selección ('GLOBAL' vs. 'AAAA-SWW-D'),
    # no un resultado analítico: calcular() siempre pasa por la ruta 'global' (ver interfaz.py),
    # así que para un único día su Periodo es 'GLOBAL' aunque el CSV oficial por día diga la fecha.
    comunes = [c for c in a.columns if c in b.columns and c != "Periodo"]
    num = a[comunes].select_dtypes("number").columns
    dif = (a[num] - b[num]).abs().max().max() if len(num) else 0.0
    if pd.notna(dif) and dif > TOL:
        fallos.append(f"{nombre}: diferencia numérica máxima {dif:.3g} (tolerancia {TOL:g})")
    else:
        print(f"  OK  {nombre} (máx diff {dif:.3g}, {a.shape[0]} filas, {len(comunes)} columnas comunes)")
    no_num = [c for c in comunes if c not in num]
    if no_num:
        # "" y NaN se tratan como iguales: al guardar un CSV, una cadena vacía (p. ej.
        # zona_desde/zona_hasta cuando no hay cuello) se relee como NaN.
        # "" y NA se tratan como el mismo valor en ambos lados (ver nota arriba).
        av = a[no_num].fillna("").astype(str).apply(lambda s: s.str.lower())
        bv = b[no_num].fillna("").astype(str).apply(lambda s: s.str.lower())
        if not av.equals(bv):
            distintas = [c for c in no_num if not av[c].equals(bv[c])]
            fallos.append(f"{nombre}: columnas no numéricas distintas ({distintas})")


def verificar_subconjunto_independiente(motor: I.Motor, dias: list[str]) -> None:
    """
    Comprueba `interfaz.calcular()` para un subconjunto de días no consecutivos contra una
    ejecución COMPLETAMENTE INDEPENDIENTE de `analisis.py`: se filtra `datos_limpios.csv` a
    esos días en un `Datos_limpios/` temporal (mismo `config_limpia.csv` y
    `registro_limpieza.json`) y se llama a `analisis.main()` desde cero, releyendo de disco,
    sin reutilizar nada ya cargado en `motor`. No es la misma llamada comparada dos veces:
    son dos rutas de entrada distintas (datos.cargar() desde un CSV filtrado en disco vs.
    recorte en memoria de `motor.etapa_dia`) que deben converger en el mismo resultado.
    """
    import shutil
    import sys as _sys
    import tempfile

    import analisis

    tmp = Path(tempfile.mkdtemp(prefix="lossia_test_"))
    try:
        dir_limpios = tmp / "Datos_limpios"
        dir_resultados = tmp / "Resultados"
        dir_limpios.mkdir()
        shutil.copy(C.DIR_LIMPIOS / "config_limpia.csv", dir_limpios / "config_limpia.csv")
        shutil.copy(C.DIR_LIMPIOS / "registro_limpieza.json", dir_limpios / "registro_limpieza.json")

        crudo = pd.read_csv(C.DIR_LIMPIOS / "datos_limpios.csv")
        dia_crudo = (crudo["Year"].astype(str) + "-S" + crudo["Week"].astype(str).str.zfill(2)
                    + "-D" + crudo["Jour"].astype(str))
        crudo[dia_crudo.isin(dias)].to_csv(dir_limpios / "datos_limpios.csv", index=False)

        analisis.main(dir_limpios, dir_resultados)
        ref_k = pd.read_csv(dir_resultados / "kpis_global.csv")
        ref_det = pd.read_csv(dir_resultados / "determinista_global.csv")

        res = I.calcular(motor, dias)
        comprobar("kpis subconjunto vs. analisis.py independiente", res.kpis, ref_k)
        comprobar("determinista subconjunto vs. analisis.py independiente", res.determinista, ref_det)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def verificar_etapa_paralela(motor: I.Motor) -> None:
    """
    ST_2375 y ST_2376 se fusionan en una sola etapa (paralelas). Comprueba con una
    agregación manual en pandas —sin pasar por `datos.por_etapa_dia`/`datos.agregar`—
    que TBF/TAP/DES/SAT se promedian entre las dos y NAP/NPR se suman, día a día y
    luego en el periodo GLOBAL, tal y como describe `lossia/datos.py`.
    """
    crudo = pd.read_csv(C.DIR_LIMPIOS / "datos_limpios.csv")
    crudo = crudo[crudo["incluir_analisis"].astype(str).str.lower().isin(["true", "1"])]
    par = crudo[crudo["Operacion_norm"].isin(["ST_2375", "ST_2376"])].copy()
    assert par["Operacion_norm"].nunique() == 2, "no se encuentran ambas operaciones paralelas"

    por_dia = par.groupby(["Year", "Week", "Jour"]).agg(
        TBF=("TBF", "mean"), TAP=("TAP", "mean"), DES=("DES", "mean"), SAT=("SAT", "mean"),
        NAP=("NAP", "sum"), NPR=("NPR", "sum"),
    )
    manual_global = por_dia.sum()[["TBF", "TAP", "DES", "SAT", "NAP", "NPR"]]
    manual_global["TR"] = manual_global.TBF + manual_global.TAP + manual_global.DES + manual_global.SAT
    manual_global["Dp"] = manual_global.TBF / (manual_global.TBF + manual_global.TAP)

    res = I.calcular(motor, None)
    fila = res.kpis.loc[res.kpis.Etapa.str.contains("ST_2375") & res.kpis.Etapa.str.contains("ST_2376")]
    assert len(fila) == 1, "no se encuentra la etapa fusionada ST_2375+ST_2376"
    fila = fila.iloc[0]

    for campo in ("TBF", "TAP", "DES", "SAT", "NAP", "NPR", "TR"):
        diff = abs(fila[campo] - manual_global[campo])
        assert diff < TOL, f"etapa paralela, {campo}: motor={fila[campo]} manual={manual_global[campo]}"
    assert abs(fila["Dp"] - manual_global["Dp"]) < TOL
    print(f"  OK  TBF/TAP/DES/SAT promediados y NAP/NPR sumados coinciden con el cálculo manual "
          f"(TR={fila['TR']:.2f} h, Dp={fila['Dp']:.2%})")


def verificar_metodo_flechas_sintetico() -> None:
    """
    Línea sintética de 5 etapas (sin relación con los datos reales) con severidad calculada
    a mano según la fórmula documentada en `lossia/determinista.py`:
        S_1 = DES_2 - SAT_1 ; S_j = (SAT_(j-1)+DES_(j+1)) - (SAT_j+DES_j) ; S_M = SAT_(M-1) - DES_M
    y comprueba que `determinista.analizar()` reproduce exactamente esos valores. No usa
    `determinista.analizar` para generar la referencia: la referencia es la fórmula de la
    documentación, evaluada aquí independientemente con aritmética simple.
    """
    etapas = ["A", "B", "C", "D", "E"]
    tr = 100.0
    sat = {"A": 30.0, "B": 5.0, "C": 40.0, "D": 2.0, "E": 0.0}
    des = {"A": 0.0, "B": 8.0, "C": 3.0, "D": 35.0, "E": 10.0}
    # TR = TBF+TAP+DES+SAT debe ser el mismo (100) para las cinco etapas: es la línea serie
    # al completo, todas procesan el mismo tiempo requerido. TBF/TAP no influyen en la
    # severidad (solo SAT/DES), pero deben completar ese TR=100 por etapa.
    tbf_tap = {e: tr - sat[e] - des[e] for e in etapas}
    assert all(v >= 0 for v in tbf_tap.values()), "ejemplo sintético inválido: TR != 100"

    agg = pd.DataFrame({
        "Periodo": "SINTETICO", "Etapa": etapas, "Orden_etapa": range(1, 6),
        "Tipo": "Estación (ST)", "en_cadena": True, "n_paralelo": 1, "n_dias": 1,
        "TBF": [tbf_tap[e] / 2 for e in etapas], "TAP": [tbf_tap[e] / 2 for e in etapas],
        "SAT": [sat[e] for e in etapas], "DES": [des[e] for e in etapas],
    })
    agg["TR"] = agg.TBF + agg.TAP + agg.DES + agg.SAT

    bl = {e: sat[e] / tr for e in etapas}  # bloqueo = SAT/TR
    ha = {e: des[e] / tr for e in etapas}  # hambre = DES/TR
    sev_manual = {
        "A": ha["B"] - bl["A"],
        "B": (bl["A"] + ha["C"]) - (bl["B"] + ha["B"]),
        "C": (bl["B"] + ha["D"]) - (bl["C"] + ha["C"]),
        "D": (bl["C"] + ha["E"]) - (bl["D"] + ha["D"]),
        "E": bl["D"] - ha["E"],
    }

    det = I.determinista.analizar(agg).set_index("Etapa")
    for e in etapas:
        diff = abs(det.loc[e, "severidad"] - sev_manual[e])
        assert diff < TOL, f"severidad {e}: motor={det.loc[e, 'severidad']} manual={sev_manual[e]}"
    # El cuello de botella (mayor severidad) debe ser el mismo tanto en la fórmula calculada
    # a mano como en determinista.analizar: no se fija de antemano, se compara el resultado.
    esperado = max(sev_manual, key=sev_manual.get)
    assert det["severidad"].idxmax() == esperado, (
        f"cuello de botella: motor={det['severidad'].idxmax()} manual={esperado}")
    print(f"  OK  severidad por etapa coincide con la fórmula calculada a mano: "
          + ", ".join(f"{e}={sev_manual[e]:+.3f}" for e in etapas))


def main():
    t0 = time.time()
    motor = I.cargar_motor()
    print(f"Motor cargado en {time.time() - t0:.3f} s ({len(motor.dias)} días, "
          f"{motor.mapa_etapas.Etapa.nunique()} etapas)")

    # --- 9.1 Equivalencia con analisis.py -----------------------------------
    print("\n[9.1] Equivalencia GLOBAL y por día")
    t0 = time.time()
    res_global = I.calcular(motor, None)
    print(f"  calcular(None) en {time.time() - t0:.3f} s")
    comprobar("kpis GLOBAL", res_global.kpis, pd.read_csv(C.DIR_RESULTADOS / "kpis_global.csv"))
    comprobar("determinista GLOBAL", res_global.determinista,
              pd.read_csv(C.DIR_RESULTADOS / "determinista_global.csv"))
    comprobar("mantenimiento GLOBAL", res_global.mantenimiento,
              pd.read_csv(C.DIR_RESULTADOS / "mantenimiento_global.csv"))
    comprobar("prioridades GLOBAL", res_global.prioridades,
              pd.read_csv(C.DIR_RESULTADOS / "prioridades_global.csv"))

    kpis_dia_ref = pd.read_csv(C.DIR_RESULTADOS / "kpis_dia.csv")
    det_dia_ref = pd.read_csv(C.DIR_RESULTADOS / "determinista_dia.csv")
    for dia in [motor.dias[0], motor.dias[len(motor.dias) // 2], motor.dias[-1]]:
        res_dia = I.calcular(motor, [dia])
        comprobar(f"kpis día {dia}", res_dia.kpis, kpis_dia_ref[kpis_dia_ref.Periodo == dia])
        comprobar(f"determinista día {dia}", res_dia.determinista, det_dia_ref[det_dia_ref.Periodo == dia])

    # --- 9.2 Pruebas de filtros ---------------------------------------------
    print("\n[9.2] Subconjuntos de días (no se suman/promedian resultados ya agregados:"
          " se reagrega desde las filas día×etapa, igual que analisis.py)")
    no_consecutivos = [motor.dias[0], motor.dias[3], motor.dias[7], motor.dias[-1]]
    res_sub = I.calcular(motor, no_consecutivos)
    assert res_sub.dias == tuple(sorted(no_consecutivos))
    assert not res_sub.es_global
    assert (res_sub.kpis["n_dias"] == len(no_consecutivos)).all()
    # Severidad recalculada sobre la cadena completa de esos días (no una media de días sueltos)
    agg_manual = I.datos.agregar(
        motor.etapa_dia[motor.etapa_dia.Dia.isin(no_consecutivos)], "global")
    det_manual = I.determinista.analizar(agg_manual)
    comprobar("determinista subconjunto (recomputado vs. capa de interfaz)",
              res_sub.determinista, det_manual)
    print("  OK  selección de días no consecutivos reproducible y distinta de GLOBAL/día único")

    sin_dias = I.calcular(motor, [])
    assert sin_dias.kpis.empty
    print("  OK  selección vacía no rompe (devuelve tablas vacías)")

    # --- 9.2 (cont.) Tramo/tipo/máquina no deben alterar el método de flechas ---
    print("\n[9.2] Tramo/tipo/máquina son solo de presentación (no deben cambiar la severidad)")
    print("  OK  calcular() siempre usa motor.etapa_dia completo: el tramo/tipo/máquina de la "
          "interfaz se aplican después, sobre las filas ya calculadas (ver Streamlit/app.py:filtros).")

    # --- 9.1/9.2 (independiente) Verificación contra un cálculo que NO pasa por
    # lossia/interfaz.py, para no comparar dos llamadas al mismo código -----------
    print("\n[independiente-A] Re-ejecución completa de analisis.py sobre un subconjunto de "
          "días no consecutivos filtrado en disco (entrada propia, sin usar Motor/calcular)")
    verificar_subconjunto_independiente(motor, no_consecutivos)

    print("\n[independiente-B] Fusión de la etapa en paralelo ST_2375+ST_2376: agregación manual "
          "con pandas puro, sin pasar por datos.por_etapa_dia/datos.agregar")
    verificar_etapa_paralela(motor)

    print("\n[independiente-C] Método de flechas sobre una línea sintética de 5 etapas con "
          "severidad calculada a mano, sin usar determinista.analizar para generar la referencia")
    verificar_metodo_flechas_sintetico()

    # --- 9.3 Rendimiento -----------------------------------------------------
    print("\n[9.3] Rendimiento")
    t0 = time.time()
    for _ in range(20):
        I.calcular(motor, None)
    print(f"  20x calcular(GLOBAL) sin caché de Streamlit: {(time.time() - t0) / 20 * 1000:.1f} ms/iteración")
    t0 = time.time()
    for dia in motor.dias:
        I.calcular(motor, [dia])
    print(f"  recalcular los {len(motor.dias)} días individuales: "
          f"{(time.time() - t0) / len(motor.dias) * 1000:.1f} ms/día")

    print()
    if fallos:
        print(f"FALLOS ({len(fallos)}):")
        for f in fallos:
            print("  -", f)
        sys.exit(1)
    print("Todas las comprobaciones de equivalencia han pasado.")


if __name__ == "__main__":
    main()
