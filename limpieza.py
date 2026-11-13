"""
Limpieza de datos - Hackathon HORSE (líneas de montaje)

Uso:
    py -3.13 limpieza.py [datos.csv] [config.csv] [carpeta_salida]
    (por defecto: Datos/datos_hackaton.csv, Datos/config_hackaton.csv, Datos_limpios/)

Salidas:
    datos_limpios.csv        una fila por operación y día productivo, con flags y columna `avisos`
                             (ids de alertas AL-xxx y entradas técnicas LT-xxx que afectan a la fila)
    config_limpia.csv        operaciones + tipo + si entran al análisis
    alertas.json             SOLO lo importante para el jefe de línea: problemas de proceso/sensores
                             detectados en este dataset, con causa -> efecto y detalle ampliable
    registro_limpieza.json   todo lo demás (días festivos eliminados, reescalados, huecos de tiempo,
                             orden de configuración...) por si se necesita en otros análisis

Las reglas son genéricas (umbrales en UMBRALES): no hay ninguna máquina escrita a mano,
así que el script sirve para otros periodos o líneas.

Supuestos de negocio:
- Tiempo abierto por día = 22 h (3 turnos de 8 h - 2 h de descanso para comer en montaje).
- Estados: TBF (produciendo), TAP (parada propia), DES (desabastecimiento), SAT (saturación).
- NAP = número de paradas propias, NPR = número de piezas producidas.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
ESTADOS = ["TBF", "TAP", "DES", "SAT"]
NUMERICAS = ESTADOS + ["NAP", "NPR"]
CLAVE = ["Year", "Week", "Jour", "Operacion"]
DIA = ["Year", "Week", "Jour"]

UMBRALES = {
    "t_abierto": 22.0,            # h abiertas por día
    "t_max_fisico": 24.0,         # por encima es imposible aunque no se pare a comer
    "tol": 0.05,                  # tolerancia de redondeo (h)
    "dia_cerrado_pct_ops": 0.9,   # % de operaciones con TAP de día completo para dar el día por cerrado
    "pct_dias_persistente": 0.8,  # % de días para considerar un comportamiento "de la máquina" y no puntual
    "pct_dias_sistematico": 0.5,  # % de días para considerar un problema sistemático
    "no_registrado_medio": 1.0,   # h medias sin estado para registrarlo
    "no_registrado_dia": 4.0,     # h sin estado en un solo día para registrarlo
    "nap_min": 2000,              # NAP mínimo para considerarlo anómalo...
    "nap_factor": 100,            # ...y además > factor x mediana de NAP de la línea
    "tap_outlier_mad": 5,         # TAP > mediana + k*MAD de la propia operación...
    "tap_outlier_min_h": 2.0,     # ...y al menos estas horas
    "npr_roto": 0.10,             # piezas < 10% de la línea con la máquina produciendo
    "npr_exceso": 1.30,           # piezas > 130% de la línea
    "npr_paralelo": (0.35, 0.65), # piezas ~ mitad de la línea
}

NIVEL_ORDEN = {"error": 0, "advertencia": 1, "info": 2}


# --------------------------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------------------------
def etiqueta_dia(week, jour) -> str:
    return f"S{int(week)}-D{int(jour)}"


def orden_dia(s: str):
    w, j = s[1:].split("-D")
    return int(w), int(j)


def dias_de(filas: pd.DataFrame | None) -> list[str]:
    if filas is None or filas.empty:
        return []
    return sorted({etiqueta_dia(w, j) for w, j in zip(filas.Week, filas.Jour)}, key=orden_dia)


def jsonable(v):
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return round(float(v), 2)
    return v


def tipo_operacion(op: str) -> str:
    if op.startswith("ST"):
        return "Estación (ST)"
    if op.startswith("PM"):
        return "Puesto manual (PM)"
    if op.upper().startswith("MA"):
        return "Manutención / auxiliar"
    return "Otro"


def normalizar_nombre(op: str) -> str:
    """ST-0050, ST_0050 y ST0050 -> ST_0050 (solo para mostrar; la clave sigue siendo el original)."""
    m = re.fullmatch(r"(ST|PM)[-_]?(\d+)(_\d+)?", op)
    return f"{m.group(1)}_{m.group(2)}{m.group(3) or ''}" if m else op


def codigo_numerico(op: str):
    m = re.fullmatch(r"(?:ST|PM)[-_]?(\d+)(?:_\d+)?", op)
    return int(m.group(1)) if m else None


def por_dia(filas: pd.DataFrame, columnas: dict[str, str]) -> list[dict]:
    """[{dia, <nombre>: valor, ...}] para el detalle ampliable del frontend."""
    out = []
    for _, r in filas.sort_values(["Week", "Jour"]).iterrows():
        fila = {"dia": etiqueta_dia(r.Week, r.Jour)}
        fila.update({nombre: r[col] for col, nombre in columnas.items()})
        out.append(fila)
    return out


# --------------------------------------------------------------------------------------------
# Registro de alertas (importantes) y entradas técnicas (resto)
# --------------------------------------------------------------------------------------------
class Registro:
    def __init__(self, orden_op: dict[str, int]) -> None:
        self.alertas: list[dict] = []
        self.tecnico: list[dict] = []
        self.orden_op = orden_op

    def alerta(self, *, nivel, categoria, operacion, problema, resumen, efecto, causa, otras_causas,
               impacto, recomendacion, filas=None, datos=None) -> str:
        aid = f"_AL{len(self.alertas)}"
        etiqueta = "Error" if nivel == "error" else "Advertencia"
        self.alertas.append({
            "id": aid,
            "nivel": nivel,
            "categoria": categoria,
            "operacion": operacion,
            "orden_op": self.orden_op.get(operacion),
            "titulo": f"{etiqueta} proceso {operacion}: {problema}",
            "resumen": resumen,
            "detalle": {
                "efecto_observado": efecto,
                "causa_probable": causa,
                "otras_causas_posibles": otras_causas,
                "impacto_en_el_analisis": impacto,
                "recomendacion": recomendacion,
                "dias_afectados": dias_de(filas),
                "datos": jsonable(datos or {}),
            },
        })
        return aid

    def tec(self, *, categoria, descripcion, accion, operacion=None, filas=None, n_filas=None, valores=None) -> str:
        tid = f"_LT{len(self.tecnico)}"
        self.tecnico.append({
            "id": tid, "categoria": categoria, "operacion": operacion, "descripcion": descripcion,
            "accion": accion, "dias": dias_de(filas),
            "filas_afectadas": int(n_filas if n_filas is not None else (0 if filas is None else len(filas))),
            "valores": jsonable(valores or {}),
        })
        return tid

    def renumerar(self) -> dict[str, str]:
        """Ordena (gravedad, posición en línea) y asigna ids definitivos AL-001 / LT-001."""
        self.alertas.sort(key=lambda a: (NIVEL_ORDEN[a["nivel"]], a["orden_op"] or 0, a["categoria"]))
        self.tecnico.sort(key=lambda t: (t["categoria"], self.orden_op.get(t["operacion"], 0)))
        mapa = {}
        for i, a in enumerate(self.alertas, 1):
            mapa[a["id"]] = a["id"] = f"AL-{i:03d}"
        for i, t in enumerate(self.tecnico, 1):
            mapa[t["id"]] = t["id"] = f"LT-{i:03d}"
        return mapa


def marcar(d: pd.DataFrame, mask, aid: str) -> None:
    d.loc[mask, "avisos"] = d.loc[mask, "avisos"].map(lambda s: f"{s};{aid}" if s else aid)


# --------------------------------------------------------------------------------------------
# Limpieza
# --------------------------------------------------------------------------------------------
def limpiar(ruta_datos: Path, ruta_config: Path, salida: Path) -> None:
    U = UMBRALES
    T, TOL, P, S = U["t_abierto"], U["tol"], U["pct_dias_persistente"], U["pct_dias_sistematico"]
    salida.mkdir(parents=True, exist_ok=True)

    d = pd.read_csv(ruta_datos)
    c = pd.read_csv(ruta_config).sort_values("Orden_OP").reset_index(drop=True)
    R = Registro(dict(zip(c.Operacion, c.Orden_OP)))
    n_orig, n_dias_orig = len(d), d[DIA].drop_duplicates().shape[0]

    # ---------- 1. Integridad (técnico) ----------
    for col in NUMERICAS:
        d[col] = pd.to_numeric(d[col], errors="coerce")
    nulos = d[NUMERICAS].isna().any(axis=1)
    for op, g in d[nulos].groupby("Operacion"):
        R.tec(categoria="valores_nulos", operacion=op, filas=g, accion="rellenado_con_0",
              descripcion="Valores vacíos (registro incompleto o fallo de exportación).",
              valores={"columnas": [x for x in NUMERICAS if g[x].isna().any()]})
    d[NUMERICAS] = d[NUMERICAS].fillna(0)

    neg = (d[NUMERICAS] < 0).any(axis=1)
    for op, g in d[neg].groupby("Operacion"):
        R.tec(categoria="valores_negativos", operacion=op, filas=g, accion="puesto_a_0",
              descripcion="Horas o contadores negativos (error de cálculo de duraciones o de exportación).",
              valores={"minimo": g[NUMERICAS].min().min()})
    d[NUMERICAS] = d[NUMERICAS].clip(lower=0)

    dup = d.duplicated(CLAVE, keep="first")
    for op, g in d[dup].groupby("Operacion"):
        R.tec(categoria="duplicados", operacion=op, filas=g, accion="eliminado",
              descripcion="Misma operación y día repetidos: se conserva el primer registro.")
    d = d[~dup]

    desconocidas = sorted(set(d.Operacion) - set(c.Operacion))
    for op in desconocidas:
        R.tec(categoria="operacion_desconocida", operacion=op, filas=d[d.Operacion == op], accion="eliminado",
              descripcion="Operación que no está en la configuración: sin posición en la línea no se puede analizar.")
    d = d[~d.Operacion.isin(desconocidas)]
    for op in sorted(set(c.Operacion) - set(d.Operacion)):
        R.tec(categoria="operacion_sin_registros", operacion=op, accion="sin_cambios",
              descripcion="Está en la configuración pero no tiene datos en el periodo.")

    previo = None
    for op in c.Operacion:
        n = codigo_numerico(op)
        if n is None:
            continue
        if previo is not None and n < previo[1]:
            R.tec(categoria="orden_config", operacion=op, accion="sin_cambios",
                  descripcion=f"Va después de {previo[0]} en la configuración aunque su número es menor. "
                              "Se respeta el orden de la configuración.",
                  valores={"anterior": previo[0]})
        previo = (op, n)

    # ---------- 2. Días no productivos (técnico) ----------
    dia = d.groupby(DIA).agg(npr=("NPR", "sum"),
                             pct_tap=("TAP", lambda s: (s >= T - TOL).mean())).reset_index()
    cerrados = dia[(dia.npr == 0) & (dia.pct_tap >= U["dia_cerrado_pct_ops"])]
    if len(cerrados):
        R.tec(categoria="dia_no_productivo", filas=d.merge(cerrados[DIA]), accion="eliminado",
              descripcion="Días con 0 piezas y casi toda la línea con TAP de día completo: línea cerrada "
                          "(festivo o sin programa), no averías.",
              valores={"n_dias": len(cerrados)})
        d = d.merge(cerrados[DIA], how="left", indicator=True)
        d = d[d._merge == "left_only"].drop(columns="_merge")
    d = d.reset_index(drop=True)
    d["avisos"] = ""

    # ---------- 3. Configuración enriquecida ----------
    c["Operacion_norm"] = c.Operacion.map(normalizar_nombre)
    c["Tipo"] = c.Operacion.map(tipo_operacion)
    d = d.merge(c[["Operacion", "Orden_OP", "Operacion_norm", "Tipo"]], on="Operacion")
    d["T_total_raw"] = d[ESTADOS].sum(axis=1)
    for e in ESTADOS:
        d[f"{e}_raw"] = d[e]
    n_dias = d[DIA].drop_duplicates().shape[0]
    npr_linea_dia = d.groupby(DIA).NPR.median()  # referencia provisional (se recalcula sin excluidas)
    npr_linea_ref = float(npr_linea_dia.median())

    # ---------- 4. Máquinas sin información útil (ALERTA + excluidas) ----------
    excluidas: dict[str, str] = {}
    for op, g in d.groupby("Operacion"):
        pct_tap_full = (g.TAP >= T - TOL).mean()
        base = {"dias_analizados": len(g), "piezas_totales": g.NPR.sum(),
                "horas_produccion_media": g.TBF.mean(), "horas_parada_propia_media": g.TAP.mean(),
                "piezas_linea_dia": npr_linea_ref}
        kw = None
        if (g.T_total_raw <= TOL).mean() >= P:
            kw = dict(nivel="error", categoria="maquina_sin_datos", problema="máquina sin datos",
                      resumen=f"No registra ningún estado en {(g.T_total_raw <= TOL).mean():.0%} de los días productivos",
                      efecto="Producción, paradas y esperas a 0 h todos los días mientras el resto de la línea trabaja.",
                      causa="Sin comunicación entre la máquina y el sistema de captura.",
                      otras_causas=["Estación inactiva o puenteada (bypass) en el flujo",
                                    "Operación dada de alta en la configuración pero no instalada"])
        elif pct_tap_full >= P and g.NPR.sum() == 0:
            kw = dict(nivel="advertencia", categoria="maquina_siempre_parada", problema="máquina siempre en parada",
                      resumen=f"Parada propia de 22 h en el {pct_tap_full:.0%} de los días y 0 piezas",
                      efecto=f"Marca parada propia todo el día mientras la línea produce ~{npr_linea_ref:.0f} "
                             "piezas/día. En una línea en serie esto solo es posible si las piezas no pasan por ella.",
                      causa="Máquina fuera de servicio o puenteada.",
                      otras_causas=["Señal de parada bloqueada (sensor roto o fallo permanente)",
                                    "Operación sustituida por otra y no dada de baja en la configuración"])
        elif (g.TBF >= T - TOL).mean() >= P and g.NPR.sum() == 0 and (g.DES + g.SAT).sum() == 0:
            kw = dict(nivel="error", categoria="senal_estado_bloqueada", problema="señal de estado bloqueada",
                      resumen="Marca 'produciendo' las 22 h todos los días sin contar ninguna pieza",
                      efecto="Nunca para, nunca espera y nunca cuenta piezas: la señal no cambia.",
                      causa="Señal de marcha forzada o sensor de estado roto.",
                      otras_causas=["Elemento de manutención (transportador) que no procesa piezas"])
        elif g.NPR.sum() == 0 and (g.DES + g.SAT).sum() == 0:
            kw = dict(nivel="advertencia", categoria="maquina_sin_trazabilidad",
                      problema="sin señal de piezas ni de esperas",
                      resumen=f"0 piezas y ninguna espera, con {g.TAP.mean():.1f} h/día de parada propia de media",
                      efecto="No cuenta piezas ni registra desabastecimiento o saturación; solo alterna "
                             "entre producción y parada propia de forma irregular.",
                      causa="Elemento auxiliar sin contador de piezas y con estados inducidos sin configurar.",
                      otras_causas=["Sensor de piezas roto", "Señal de parada errática"])
        if kw:
            aid = R.alerta(operacion=op, filas=g, datos=base,
                           impacto="Excluida del análisis de máquinas críticas: sus datos no son fiables.",
                           recomendacion="Confirmar con mantenimiento si la máquina está en el flujo y revisar "
                                         "su señal en el sistema de captura.", **kw)
            excluidas[op] = kw["problema"]
            marcar(d, d.Operacion == op, aid)

    c["incluir_analisis"] = ~c.Operacion.isin(excluidas)
    c["motivo_exclusion"] = c.Operacion.map(excluidas).fillna("")
    d["incluir_analisis"] = ~d.Operacion.isin(excluidas)
    activas = d.incluir_analisis
    npr_linea_dia = d[activas].groupby(DIA).NPR.median().rename("npr_linea")
    d = d.merge(npr_linea_dia, on=DIA, how="left")
    activas = d.incluir_analisis
    npr_linea_ref = float(npr_linea_dia.median())

    # ---------- 5. Cuadre de horas ----------
    exceso = d.T_total_raw > T + TOL
    imposible = d.T_total_raw > U["t_max_fisico"] + TOL

    for op, g in d[imposible].groupby("Operacion"):
        aid = R.alerta(
            nivel="error", categoria="tiempos_duplicados", operacion=op, filas=g,
            problema="registro de tiempos duplicado",
            resumen=f"Registra más de 24 h de actividad en {len(g)} día(s) (máx. {g.T_total_raw.max():.2f} h)",
            efecto=f"Producción + paradas + esperas suman hasta {g.T_total_raw.max():.2f} h en un día, "
                   "cuando un día no puede tener más de 24 h.",
            causa="El mismo intervalo se registra en dos estados a la vez (medida duplicada).",
            otras_causas=["Registro doble en el cambio de turno o al reiniciar el PLC/SCADA",
                          "Error de reloj de la máquina al agregar por día"],
            impacto="Los tiempos de esos días se han reescalado a 22 h manteniendo la proporción entre estados.",
            recomendacion="Revisar la configuración de estados de la máquina en el sistema de captura.",
            datos={"horas_maximas_posibles": U["t_max_fisico"], "horas_abiertas": T,
                   "por_dia": por_dia(g, {"T_total_raw": "horas_registradas", "TBF_raw": "produccion_h",
                                          "TAP_raw": "parada_propia_h", "DES_raw": "desabastecimiento_h",
                                          "SAT_raw": "saturacion_h"})})
        marcar(d, d.index.isin(g.index), aid)

    for op, g in d[exceso & ~imposible].groupby("Operacion"):
        sistematico = len(g) / n_dias >= S
        tid = R.tec(categoria="exceso_horas", operacion=op, filas=g, accion="reescalado_a_22h",
                    descripcion=(f"Supera 22 h en {len(g)} de {n_dias} días (media {g.T_total_raw.mean():.2f} h). "
                                 + ("Sistemático: probablemente no para en el descanso de comida."
                                    if sistematico else "Puntual: solape de estados.")),
                    valores={"media_h": g.T_total_raw.mean(), "max_h": g.T_total_raw.max(),
                             "sistematico": sistematico})
        marcar(d, d.index.isin(g.index), tid)

    d["flag_exceso_horas"] = exceso
    factor = (T / d.T_total_raw).where(exceso, 1.0)
    d[ESTADOS] = d[ESTADOS].mul(factor, axis=0)
    d["T_no_registrado"] = (T - d[ESTADOS].sum(axis=1)).clip(lower=0)
    d["flag_defecto_horas"] = d.T_no_registrado > TOL

    for op, g in d[activas].groupby("Operacion"):
        media, maximo = g.T_no_registrado.mean(), g.T_no_registrado.max()
        if media >= U["no_registrado_medio"] or maximo >= U["no_registrado_dia"]:
            g_def = g[g.T_no_registrado > TOL]
            tid = R.tec(categoria="tiempo_no_registrado", operacion=op, filas=g_def,
                        accion="guardado_en_T_no_registrado",
                        descripcion=f"Faltan de media {media:.2f} h/día sin estado (máx. {maximo:.2f} h).",
                        valores={"media_h": media, "max_h": maximo})
            marcar(d, d.index.isin(g_def.index), tid)

    # ---------- 6. Paradas propias (ALERTAS) ----------
    d["flag_tap_sospechoso"] = False
    d["flag_tap_outlier"] = False
    nap_linea = float(d.loc[activas, "NAP"].median())
    lim_nap = max(U["nap_min"], U["nap_factor"] * max(nap_linea, 1))
    tap_linea = float(d.loc[activas, "TAP_raw"].median())

    for op, g in d[activas].groupby("Operacion"):
        g_nap = g[g.NAP > lim_nap]
        if len(g_nap):
            seg = T * 3600 / g_nap.NAP.max()
            aid = R.alerta(
                nivel="error", categoria="sensor_paradas_defectuoso", operacion=op, filas=g_nap,
                problema="sensor de paradas defectuoso",
                resumen=f"Registra hasta {int(g_nap.NAP.max()):,} paradas al día (una cada {seg:.0f} s)".replace(",", "."),
                efecto=f"Cuenta de media {g_nap.NAP.mean():,.0f} paradas/día frente a {nap_linea:.0f} de mediana en la "
                       f"línea, y aun así produce {g_nap.NPR.mean():,.0f} piezas/día con {g_nap.TAP_raw.mean():.1f} h/día "
                       "de parada propia. Una máquina tan parada no podría producir eso.".replace(",", "."),
                causa="Sensor que parpadea (rebotes de señal) y genera microparadas falsas.",
                otras_causas=["Umbral de microparada mal configurado (cuenta como parada cualquier hueco de ciclo)"],
                impacto="Su parada propia está inflada: no se tiene en cuenta para señalarla como máquina crítica.",
                recomendacion="Revisar el sensor de estado y el umbral de microparada de la máquina.",
                datos={"paradas_dia_media": g_nap.NAP.mean(), "paradas_dia_max": g_nap.NAP.max(),
                       "paradas_dia_mediana_linea": nap_linea, "parada_propia_h_media": g_nap.TAP_raw.mean(),
                       "parada_propia_h_mediana_linea": tap_linea, "piezas_dia_media": g_nap.NPR.mean(),
                       "por_dia": por_dia(g_nap, {"NAP": "paradas", "TAP_raw": "parada_propia_h", "NPR": "piezas"})})
            d.loc[g_nap.index, "flag_tap_sospechoso"] = True
            marcar(d, d.index.isin(g_nap.index), aid)

        g_full = g[(g.TAP_raw >= T - TOL) & ~g.index.isin(g_nap.index)]
        if len(g_full):
            aid = R.alerta(
                nivel="advertencia", categoria="parada_dia_completo", operacion=op, filas=g_full,
                problema="parada de día completo sospechosa",
                resumen=f"Marca 22 h de parada propia en {len(g_full)} día(s) mientras la línea produce",
                efecto=f"Esos días la línea produjo ~{g_full.npr_linea.mean():.0f} piezas, pero esta máquina figura "
                       "parada las 22 h. En una línea en serie no es posible.",
                causa="Sensor atascado en estado de parada o máquina puenteada ese día.",
                otras_causas=["Avería real de larga duración con la línea desviada por otro camino"],
                impacto="La parada propia de esos días no es fiable y se marca como sospechosa.",
                recomendacion="Contrastar esos días con los partes de mantenimiento.",
                datos={"por_dia": por_dia(g_full, {"TAP_raw": "parada_propia_h", "NPR": "piezas_maquina",
                                                   "npr_linea": "piezas_linea"})})
            d.loc[g_full.index, "flag_tap_sospechoso"] = True
            marcar(d, d.index.isin(g_full.index), aid)

        resto = g.drop(index=g_full.index.union(g_nap.index))
        if len(resto) >= 5:
            med = resto.TAP_raw.median()
            lim = med + U["tap_outlier_mad"] * max((resto.TAP_raw - med).abs().median(), 0.05)
            g_out = resto[(resto.TAP_raw > lim) & (resto.TAP_raw >= U["tap_outlier_min_h"])]
            if len(g_out):
                peor = g_out.loc[g_out.TAP_raw.idxmax()]
                aid = R.alerta(
                    nivel="advertencia", categoria="averia_atipica", operacion=op, filas=g_out,
                    problema="parada propia anormalmente larga",
                    resumen=f"{peor.TAP_raw:.1f} h de parada propia el {etiqueta_dia(peor.Week, peor.Jour)} "
                            f"(lo normal en esta máquina: {med:.1f} h/día)",
                    efecto=f"En {len(g_out)} día(s) la parada propia multiplica por "
                           f"{g_out.TAP_raw.max() / max(med, 0.01):.0f} su valor habitual.",
                    causa="Avería grave puntual.",
                    otras_causas=["Parada de línea atribuida a esta máquina",
                                  "Estado de parada que no se cerró en el sistema"],
                    impacto="Se mantiene en el análisis: si fuera un error de registro, inflaría la parada propia "
                            "de esta máquina.",
                    recomendacion="Verificar con el parte de mantenimiento de ese día.",
                    datos={"parada_propia_habitual_h": med, "limite_atipico_h": lim,
                           "por_dia": por_dia(g_out, {"TAP_raw": "parada_propia_h", "NAP": "paradas",
                                                      "NPR": "piezas"})})
                d.loc[g_out.index, "flag_tap_outlier"] = True
                marcar(d, d.index.isin(g_out.index), aid)

    # ---------- 7. Contador de piezas (ALERTAS) ----------
    ratio = d.NPR / d.npr_linea.replace(0, np.nan)
    d["flag_npr_invalido"] = False
    lo, hi = U["npr_paralelo"]
    for op, g in d[activas].groupby("Operacion"):
        r = ratio[g.index]
        roto = g[(g.TBF > 1) & (r < U["npr_roto"])]
        if len(roto) / len(g) >= S:
            aid = R.alerta(
                nivel="error", categoria="contador_piezas_defectuoso", operacion=op, filas=roto,
                problema="contador de piezas defectuoso",
                resumen=f"Cuenta {roto.NPR.mean():.0f} piezas/día estando {roto.TBF.mean():.1f} h/día en producción",
                efecto=f"La línea produce ~{roto.npr_linea.mean():.0f} piezas/día y todas pasan por esta máquina, "
                       f"pero su contador solo registra {roto.NPR.mean():.0f}.",
                causa="Contador de piezas roto o desconectado.",
                otras_causas=["El contador registra otro evento (p.ej. rechazos) en vez de piezas buenas"],
                impacto="Sus piezas no se usan; sus tiempos de producción y paradas sí.",
                recomendacion="Revisar o sustituir el contador de piezas.",
                datos={"piezas_dia_media": roto.NPR.mean(), "piezas_linea_dia": roto.npr_linea.mean(),
                       "por_dia": por_dia(roto, {"NPR": "piezas_maquina", "npr_linea": "piezas_linea",
                                                 "TBF_raw": "produccion_h"})})
            d.loc[roto.index, "flag_npr_invalido"] = True
            marcar(d, d.index.isin(roto.index), aid)

        alto = g[r > U["npr_exceso"]]
        if len(alto) / len(g) >= S:
            exceso_pct = 100 * (g.NPR.median() / g.npr_linea.median() - 1)
            aid = R.alerta(
                nivel="error", categoria="contador_piezas_excesivo", operacion=op, filas=alto,
                problema="sensor de piezas defectuoso (cuenta de más)",
                resumen=f"Cuenta {g.NPR.median():.0f} piezas/día, un {exceso_pct:.0f} % más que la línea "
                        f"(~{g.npr_linea.median():.0f})",
                efecto=f"Ninguna máquina de una línea en serie puede producir más que la propia línea; esta llega a "
                       f"{alto.NPR.max():.0f} piezas en un día.",
                causa="Medida duplicada: el sensor cuenta cada pieza más de una vez.",
                otras_causas=["La operación cuenta subconjuntos o componentes y no motores",
                              "Piezas retrabajadas que vuelven a pasar y se recuentan"],
                impacto="Sus piezas no se usan para calcular la producción; sus tiempos sí.",
                recomendacion="Confirmar qué cuenta el sensor y revisar si hay doble conteo.",
                datos={"piezas_dia_mediana": g.NPR.median(), "piezas_linea_dia": g.npr_linea.median(),
                       "exceso_pct": exceso_pct,
                       "por_dia": por_dia(alto, {"NPR": "piezas_maquina", "npr_linea": "piezas_linea"})})
            d.loc[alto.index, "flag_npr_invalido"] = True
            marcar(d, d.index.isin(alto.index), aid)
        elif r.between(lo, hi).mean() >= P:
            R.tec(categoria="posible_paralelo", operacion=op, filas=g, accion="sin_cambios",
                  descripcion=f"Hace ~{g.NPR.median():.0f} piezas/día, la mitad que la línea "
                              f"(~{g.npr_linea.median():.0f}): probablemente es un puesto en paralelo.",
                  valores={"piezas_mediana": g.NPR.median(), "ratio": r.median()})
    d = d.drop(columns="npr_linea")

    # ---------- 8. Resumen técnico de exclusiones ----------
    R.tec(categoria="reescalado", accion="reescalado_a_22h", n_filas=int(exceso.sum()),
          descripcion="Filas que superaban 22 h: estados reescalados proporcionalmente (originales en *_raw).",
          valores={"filas": int(exceso.sum())})

    # ---------- 9. Derivadas, ids y guardado ----------
    mapa = R.renumerar()
    d["avisos"] = d.avisos.map(lambda s: ";".join(mapa[x] for x in s.split(";")) if s else "")
    d["TAI"] = d.DES + d.SAT
    for col in ESTADOS + ["TAI", "T_no_registrado"]:
        d[f"pct_{col}"] = 100 * d[col] / T

    columnas = (["Linea", "Year", "Week", "Jour", "Orden_OP", "Operacion", "Operacion_norm", "Tipo",
                 "incluir_analisis"] + ESTADOS + ["TAI", "T_no_registrado", "NAP", "NPR"]
                + [f"pct_{x}" for x in ESTADOS + ["TAI", "T_no_registrado"]]
                + [f"{x}_raw" for x in ESTADOS] + ["T_total_raw", "flag_exceso_horas", "flag_defecto_horas",
                                                    "flag_tap_sospechoso", "flag_tap_outlier", "flag_npr_invalido",
                                                    "avisos"])
    d = d[columnas].sort_values(["Week", "Jour", "Orden_OP"]).round(4)
    suma = d[ESTADOS + ["T_no_registrado"]].sum(axis=1)
    assert suma.between(T - TOL, T + TOL).all(), "Alguna fila no suma el tiempo abierto"

    d.to_csv(salida / "datos_limpios.csv", index=False)
    c.to_csv(salida / "config_limpia.csv", index=False)

    dias = sorted({etiqueta_dia(w, j) for w, j in zip(d.Week, d.Jour)}, key=orden_dia)
    generado = datetime.now().isoformat(timespec="seconds")
    alertas = {
        "generado": generado,
        "linea": str(d.Linea.iloc[0]) if len(d) else None,
        "periodo": {"desde": dias[0] if dias else None, "hasta": dias[-1] if dias else None,
                    "dias_productivos": len(dias)},
        "resumen": {
            "errores": sum(a["nivel"] == "error" for a in R.alertas),
            "advertencias": sum(a["nivel"] == "advertencia" for a in R.alertas),
            "maquinas_afectadas": len({a["operacion"] for a in R.alertas}),
            "maquinas_excluidas_del_analisis": sorted(excluidas),
        },
        "alertas": R.alertas,
    }
    tecnico = {
        "generado": generado,
        "fuente": {"datos": ruta_datos.name, "config": ruta_config.name},
        "umbrales": jsonable(UMBRALES),
        "resumen": {"filas_originales": n_orig, "dias_originales": n_dias_orig, "filas_limpias": len(d),
                    "dias_productivos": len(dias), "operaciones": int(len(c)),
                    "operaciones_en_analisis": int(c.incluir_analisis.sum())},
        "entradas": R.tecnico,
    }
    (salida / "alertas.json").write_text(json.dumps(alertas, ensure_ascii=False, indent=2), encoding="utf-8")
    (salida / "registro_limpieza.json").write_text(json.dumps(tecnico, ensure_ascii=False, indent=2),
                                                   encoding="utf-8")

    print(f"Filas {n_orig} -> {len(d)} | días productivos {len(dias)}/{n_dias_orig} | "
          f"operaciones en análisis {c.incluir_analisis.sum()}/{len(c)}")
    print(f"alertas.json: {alertas['resumen']['errores']} errores, {alertas['resumen']['advertencias']} advertencias")
    for a in R.alertas:
        print(f"  {a['id']}  {a['titulo']}  ->  {a['resumen']}")
    print(f"registro_limpieza.json: {len(R.tecnico)} entradas técnicas")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = sys.argv[1:]
    limpiar(Path(args[0]) if len(args) > 0 else BASE / "Datos" / "datos_hackaton.csv",
            Path(args[1]) if len(args) > 1 else BASE / "Datos" / "config_hackaton.csv",
            Path(args[2]) if len(args) > 2 else BASE / "Datos_limpios")
