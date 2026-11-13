"""
Limpieza de datos - Hackathon HORSE (Linea 5 montaje, Valladolid)

Entrada : Datos/datos_hackaton.csv, Datos/config_hackaton.csv
Salida  : Datos_limpios/datos_limpios.csv      (una fila por operacion y dia productivo)
          Datos_limpios/config_limpia.csv      (operaciones + tipo + si entran al analisis)
          Datos_limpios/informe_limpieza.txt   (que se ha hecho y a cuantas filas afecta)

Supuestos de negocio:
- Tiempo abierto por dia = 22 h (3 turnos de 8 h = 24 h - 2 h de descanso para comer).
- Estados: TBF (produciendo), TAP (parada propia), DES (desabastecimiento), SAT (saturacion).
- NAP = numero de paradas propias, NPR = numero de piezas producidas.

No se borra informacion: las filas dudosas se marcan con flags y la columna
`incluir_analisis` dice si entran al calculo de cuellos de botella.
"""
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
ENTRADA = BASE / "Datos"
SALIDA = BASE / "Datos_limpios"

T_ABIERTO = 22.0          # horas abiertas por dia
TOL = 0.05                # tolerancia de redondeo (h)
ESTADOS = ["TBF", "TAP", "DES", "SAT"]
CLAVE = ["Year", "Week", "Jour", "Operacion"]

# Operaciones sin informacion util (revisadas a mano, ver informe):
EXCLUIR = {
    "ST_0030": "Sin datos: todos los estados a 0 en todos los dias productivos (estacion inactiva/puenteada)",
    "PM2130": "TAP = 22 h todos los dias y 0 piezas mientras la linea produce: fuera de servicio",
    "Ma_BM1_2": "Siempre TBF = 22 h, 0 piezas, sin DES/SAT: contador de manutencion no informativo",
    "Ma_VES_0": "Siempre TBF = 22 h, 0 piezas, sin DES/SAT: contador de manutencion no informativo",
    "Ma_VESRE": "Siempre TBF = 22 h, 0 piezas, sin DES/SAT: contador de manutencion no informativo",
    "ManBM2_1": "0 piezas, sin DES/SAT y TAP erratico (hasta 22 h con la linea produciendo)",
}


def tipo_operacion(op: str) -> str:
    if op.startswith("ST"):
        return "Estacion (ST)"
    if op.startswith("PM"):
        return "Puesto manual (PM)"
    if op.startswith("Ma") or op.startswith("MAN"):
        return "Manutencion / auxiliar"
    return "Otro"


def normalizar_nombre(op: str) -> str:
    """ST-0050, ST_0050 y ST0050 -> ST_0050 (solo para mostrar; la clave sigue siendo el original)."""
    import re
    m = re.fullmatch(r"(ST|PM)[-_]?(\d+)(_\d+)?", op)
    return f"{m.group(1)}_{m.group(2)}{m.group(3) or ''}" if m else op


def main() -> None:
    SALIDA.mkdir(exist_ok=True)
    log: list[str] = []
    d = pd.read_csv(ENTRADA / "datos_hackaton.csv")
    c = pd.read_csv(ENTRADA / "config_hackaton.csv")
    log.append(f"Filas originales: {len(d)}  | operaciones: {d.Operacion.nunique()}  | dias: {d[['Week','Jour']].drop_duplicates().shape[0]}")

    # 0. Integridad basica
    assert d.duplicated(CLAVE).sum() == 0, "Hay claves duplicadas"
    assert set(d.Operacion) == set(c.Operacion), "Operaciones distintas entre datos y config"
    assert (d[ESTADOS + ["NAP", "NPR"]] >= 0).all().all(), "Hay valores negativos"
    log.append("Integridad: sin duplicados, sin negativos, sin nulos, datos y config con las mismas 91 operaciones.")

    # 1. Dias no productivos: TODA la linea con TAP = 22 h y 0 piezas -> linea cerrada, no es parada propia
    dia = d.groupby(["Year", "Week", "Jour"]).agg(npr=("NPR", "sum"), tap_min=("TAP", "min")).reset_index()
    cerrados = dia[(dia.npr == 0) & (dia.tap_min >= T_ABIERTO - TOL)]
    log.append(f"Dias no productivos eliminados ({len(cerrados)}): " +
               ", ".join(f"S{w}-D{j}" for w, j in zip(cerrados.Week, cerrados.Jour)) +
               ". Toda la linea marcaba 22 h de TAP y 0 piezas: es linea cerrada (festivo/sin programa), no averia.")
    d = d.merge(cerrados[["Year", "Week", "Jour"]], how="left", indicator=True)
    d = d[d._merge == "left_only"].drop(columns="_merge").reset_index(drop=True)

    # 2. Configuracion enriquecida
    c["Operacion_norm"] = c.Operacion.map(normalizar_nombre)
    c["Tipo"] = c.Operacion.map(tipo_operacion)
    c["incluir_analisis"] = ~c.Operacion.isin(EXCLUIR)
    c["motivo_exclusion"] = c.Operacion.map(EXCLUIR).fillna("")
    d = d.merge(c[["Operacion", "Orden_OP", "Operacion_norm", "Tipo", "incluir_analisis"]], on="Operacion")
    log.append(f"Operaciones excluidas del analisis ({len(EXCLUIR)}):")
    log += [f"   - {k}: {v}" for k, v in EXCLUIR.items()]

    # 3. Cuadre de horas contra las 22 h abiertas
    for col in ESTADOS:
        d[f"{col}_raw"] = d[col]
    d["T_total_raw"] = d[ESTADOS].sum(axis=1)

    exceso = d.T_total_raw > T_ABIERTO + TOL
    d["flag_exceso_horas"] = exceso
    factor = (T_ABIERTO / d.T_total_raw).where(exceso, 1.0)
    d[ESTADOS] = d[ESTADOS].mul(factor, axis=0)
    log.append(f"Filas con mas de 22 h registradas: {exceso.sum()} (max {d.T_total_raw.max():.2f} h). "
               "Se reescalan proporcionalmente a 22 h (estados solapados).")
    top = d[exceso].groupby("Operacion").size().sort_values(ascending=False).head(8)
    log.append("   Operaciones con mas excesos: " + ", ".join(f"{k} ({v})" for k, v in top.items()))

    d["T_no_registrado"] = (T_ABIERTO - d[ESTADOS].sum(axis=1)).clip(lower=0)
    d["flag_defecto_horas"] = d.T_no_registrado > TOL
    log.append(f"Filas con menos de 22 h registradas: {d.flag_defecto_horas.sum()} "
               f"(media que falta {d.loc[d.flag_defecto_horas,'T_no_registrado'].mean():.2f} h). "
               "Se guarda la diferencia como T_no_registrado (tiempo sin estado conocido).")

    # 4. Paradas propias sospechosas
    tap_dia = d.TAP_raw >= T_ABIERTO - TOL
    nap_absurdo = d.NAP > 5000
    d["flag_tap_sospechoso"] = tap_dia | nap_absurdo
    log.append(f"TAP sospechoso: {tap_dia.sum()} filas con TAP de dia completo mientras la linea produce; "
               f"{nap_absurdo.sum()} filas con mas de 5000 paradas/dia (ST2235: ~22.000 paradas y ~15 h TAP, "
               "imposible con la linea sacando ~1500 piezas -> microparadas o senal erratica).")

    # 5. Contador de piezas no fiable
    npr_mediana_linea = d[d.incluir_analisis].groupby(["Week", "Jour"]).NPR.transform("median")
    d["flag_npr_invalido"] = False
    d.loc[d.incluir_analisis, "flag_npr_invalido"] = (d.loc[d.incluir_analisis, "TBF"] > 1) & (
        d.loc[d.incluir_analisis, "NPR"] < 0.1 * npr_mediana_linea)
    log.append(f"NPR (piezas) no fiable: {d.flag_npr_invalido.sum()} filas con la maquina produciendo pero <10% "
               "de las piezas de la linea (p.ej. ST-0295). Sus tiempos se mantienen; sus piezas no se usan.")

    # 6. Porcentajes sobre el tiempo abierto
    for col in ESTADOS + ["T_no_registrado"]:
        d[f"pct_{col}"] = 100 * d[col] / T_ABIERTO
    d["TAI"] = d.DES + d.SAT
    d["pct_TAI"] = 100 * d.TAI / T_ABIERTO

    columnas = (["Linea", "Year", "Week", "Jour", "Orden_OP", "Operacion", "Operacion_norm", "Tipo",
                 "incluir_analisis"] + ESTADOS + ["TAI", "T_no_registrado", "NAP", "NPR"]
                + [f"pct_{c}" for c in ESTADOS + ["TAI", "T_no_registrado"]]
                + [f"{c}_raw" for c in ESTADOS] + ["T_total_raw", "flag_exceso_horas", "flag_defecto_horas",
                                                    "flag_tap_sospechoso", "flag_npr_invalido"])
    d = d[columnas].sort_values(["Week", "Jour", "Orden_OP"]).round(4)
    d.to_csv(SALIDA / "datos_limpios.csv", index=False)
    c.to_csv(SALIDA / "config_limpia.csv", index=False)

    log.append(f"\nResultado: {len(d)} filas ({d[['Week','Jour']].drop_duplicates().shape[0]} dias productivos x "
               f"{d.Operacion.nunique()} operaciones); {d.incluir_analisis.sum()} filas entran al analisis "
               f"({c.incluir_analisis.sum()} operaciones).")

    log.append("\nPuntos pendientes de confirmar con HORSE:")
    log += [
        "   - Orden de la config con saltos de numeracion: ST0261 antes de ST0259, ST-2002 antes de ST-2001, "
        "ST-2380 entre ST2376 y ST-2375, ST_0820-0850 despues de ST_2410. Se respeta Orden_OP tal cual.",
        "   - ST2376 y ST-2375 producen ~la mitad de piezas cada una (~750 vs ~1500): parecen puestos en PARALELO.",
        "   - ST_3300 produce 2000-3300 piezas/dia (mas que la linea): posible doble conteo o operacion por subconjunto.",
        "   - Varias operaciones (PM_0090, ST2135, ST2376, PM_0110...) suman ~23-24 h: podrian no parar en el "
        "descanso de comida (24 h) en vez de 22 h.",
        "   - Limites de la linea: aun no recibidos (afectan a DES de la primera y SAT de la ultima operacion).",
    ]
    texto = "\n".join(log)
    (SALIDA / "informe_limpieza.txt").write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
