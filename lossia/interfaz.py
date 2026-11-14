"""
Capa de acceso a los resultados oficiales para la interfaz (Streamlit u otra).

Arquitectura (revisión 2):
- `Resultados/*_global.csv` y `Resultados/*_dia.csv`, generados por `analisis.py`, son
  la REFERENCIA ANALÍTICA: cuando la selección de la interfaz es "todos los días" o un
  único día y esos ficheros están actualizados respecto a `Datos_limpios/`, `calcular()`
  los LEE directamente — no repite ningún cálculo.
- Cualquier otra selección (un subconjunto de días que no coincide con GLOBAL ni con un
  único día) no tiene archivo persistido equivalente: se resuelve EXCLUSIVAMENTE a través
  del motor oficial (`datos.agregar`, `kpis.calcular`, `determinista.analizar`,
  `prioridades.*`), ejecutado sobre las filas día×etapa de `Datos_limpios/`. Nunca se suma
  ni se promedia un resultado ya agregado (el método de flechas no es lineal en los días).
- Si `Resultados/` está desactualizado respecto a `Datos_limpios/`, se ignora y se recalcula
  siempre en vivo, para no mostrar nunca datos obsoletos como si fueran la referencia.
- `Resultado.fuente` deja constancia de cuál de las dos rutas se usó (trazabilidad).

Unidad de análisis: la ETAPA (`datos.mapa_etapas`), no la máquina — una etapa puede
agrupar varias operaciones en paralelo. `Motor.mapa_operaciones` resuelve la
correspondencia Operacion (código crudo, el que usan alertas.json/registro_limpieza.json)
-> Operacion_norm -> Etapa, para poder cruzar alertas de calidad con etapas.

Restricción deliberada: el tramo de línea, el tipo de operación y la selección de
máquinas NUNCA se usan para recortar las etapas antes de `determinista.analizar`,
porque el método de flechas necesita la cadena completa y consecutiva para que la
adyacencia entre etapas siga siendo válida. Esos filtros son solo de PRESENTACIÓN:
se aplican después, sobre las tablas/gráficos ya calculados sobre la línea entera.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config as C
from . import datos, determinista, kpis, prioridades

PERSISTIDOS = "resultados_persistidos"
BAJO_DEMANDA = "calculo_bajo_demanda"


@dataclass(frozen=True)
class Motor:
    """Datos crudos cargados una vez. A partir de aquí se recalcula cualquier selección de días."""
    etapa_dia: pd.DataFrame
    mapa_etapas: pd.DataFrame       # Operacion_norm -> Etapa, Orden_etapa, Tipo, en_cadena, n_paralelo
    mapa_operaciones: pd.DataFrame  # Operacion (crudo) -> Operacion_norm -> Etapa
    dias: list[str]                 # todos los 'Dia' disponibles (AAAA-SWW-DD), ordenados
    dir_limpios: Path               # origen, para comprobar si Resultados/ está al día
    firma: tuple                    # (ruta, tamaño, mtime) de las fuentes, para invalidar la caché


def firma_fuentes(dir_limpios: Path) -> tuple:
    archivos = ("datos_limpios.csv", "config_limpia.csv", "registro_limpieza.json")
    partes = []
    for nombre in archivos:
        p = dir_limpios / nombre
        st = p.stat()
        partes.append((nombre, st.st_size, st.st_mtime_ns))
    return tuple(partes)


def cargar_motor(dir_limpios: Path = C.DIR_LIMPIOS) -> Motor:
    """Carga y prepara los datos en bruto (equivalente al paso 1 de analisis.main)."""
    d, cfg, reg = datos.cargar(dir_limpios)
    grupos = datos.grupos_paralelo(cfg, reg)
    mapa = datos.mapa_etapas(cfg, grupos)
    etapa_dia = datos.por_etapa_dia(d, mapa)
    mapa_ops = (cfg[["Operacion", "Operacion_norm"]]
                .merge(mapa[["Operacion_norm", "Etapa"]], on="Operacion_norm", how="left"))
    dias = sorted(etapa_dia["Dia"].unique().tolist())
    return Motor(etapa_dia=etapa_dia, mapa_etapas=mapa, mapa_operaciones=mapa_ops,
                 dias=dias, dir_limpios=dir_limpios, firma=firma_fuentes(dir_limpios))


@dataclass(frozen=True)
class Resultado:
    """Salida para una selección de días. Todas las tablas son a nivel de ETAPA."""
    kpis: pd.DataFrame
    determinista: pd.DataFrame
    mantenimiento: pd.DataFrame
    prioridades: pd.DataFrame
    dias: tuple[str, ...]
    es_global: bool    # True si la selección cubre todos los días (periodo GLOBAL oficial)
    fuente: str        # PERSISTIDOS (leído de Resultados/) o BAJO_DEMANDA (motor oficial en vivo)


def resultados_firma(dir_resultados: Path) -> tuple:
    """(existe, mtime) de Resultados/kpis_global.csv, para invalidar cachés externas
    (p. ej. la de Streamlit) cuando se regeneran los ficheros oficiales."""
    p = dir_resultados / "kpis_global.csv"
    return (p.exists(), p.stat().st_mtime_ns if p.exists() else 0)


def resultados_desactualizados(dir_limpios: Path, dir_resultados: Path) -> bool:
    """True si Resultados/*_global.csv es más antiguo que las fuentes de Datos_limpios/,
    o si no existe. En ese caso nunca se usa como referencia: se recalcula en vivo."""
    salida = dir_resultados / "kpis_global.csv"
    if not salida.exists():
        return True
    fuente = dir_limpios / "datos_limpios.csv"
    if not fuente.exists():
        return False
    return fuente.stat().st_mtime_ns > salida.stat().st_mtime_ns


def _leer_persistidos(dir_resultados: Path) -> dict[str, pd.DataFrame]:
    """Lee los nueve CSV oficiales de Resultados/ tal cual, sin recalcular nada."""
    leer = lambda nombre: pd.read_csv(dir_resultados / nombre)  # noqa: E731

    def leer_prioridades(nombre):
        # categoria/motivo son "" (no "sin dato") cuando no aplican; el resto de columnas
        # (severidad, TAP_medio_dia...) deben seguir siendo numéricas con NaN, así que no se
        # puede usar keep_default_na=False para todo el fichero (convertiría esas columnas
        # numéricas a texto en cuanto una celda estuviera vacía).
        df = leer(nombre)
        for col in ("categoria", "motivo"):
            df[col] = df[col].fillna("")
        return df

    return {
        "kpis_global": leer("kpis_global.csv"),
        "kpis_dia": leer("kpis_dia.csv"),
        "determinista_global": leer("determinista_global.csv"),
        "determinista_dia": leer("determinista_dia.csv"),
        "mantenimiento_global": leer("mantenimiento_global.csv"),
        "mantenimiento_dia": leer("mantenimiento_dia.csv"),
        "prioridades_global": leer_prioridades("prioridades_global.csv"),
        "prioridades_dia": leer_prioridades("prioridades_dia.csv"),
    }


def _resultado_persistido(persistidos: dict, dia: str | None, es_global: bool) -> Resultado:
    if es_global:
        k, det = persistidos["kpis_global"], persistidos["determinista_global"]
        mant, pri = persistidos["mantenimiento_global"], persistidos["prioridades_global"]
        dias = tuple()  # el propio Periodo="GLOBAL" ya lo identifica
    else:
        k = persistidos["kpis_dia"].query("Periodo == @dia").reset_index(drop=True)
        det = persistidos["determinista_dia"].query("Periodo == @dia").reset_index(drop=True)
        mant = persistidos["mantenimiento_dia"].query("Periodo == @dia").reset_index(drop=True)
        pri = persistidos["prioridades_dia"].query("Periodo == @dia").reset_index(drop=True)
        dias = (dia,)
    return Resultado(k, det, mant, pri, dias, es_global, PERSISTIDOS)


def _resultado_en_vivo(motor: Motor, dias: list[str] | None, es_global: bool) -> Resultado:
    base = motor.etapa_dia if es_global else motor.etapa_dia[motor.etapa_dia["Dia"].isin(dias)]
    seleccion = tuple(sorted(base["Dia"].unique().tolist()))
    if base.empty:
        vacio = base.assign(Periodo="GLOBAL")
        return Resultado(vacio, vacio, vacio, vacio, seleccion, es_global, BAJO_DEMANDA)
    agg = datos.agregar(base, "global")
    k = kpis.calcular(agg)
    det = determinista.analizar(agg, base)  # desempate por días como principal
    mant = prioridades.mantenimiento(k)
    pri = prioridades.vista(k, det)
    return Resultado(k, det, mant, pri, seleccion, es_global, BAJO_DEMANDA)


def calcular(motor: Motor, dias: list[str] | None = None,
             dir_resultados: Path = C.DIR_RESULTADOS) -> Resultado:
    """
    `dias=None` o con todos los días -> periodo GLOBAL.
    Un único día -> ese día.
    Cualquier otro subconjunto -> recalculado en vivo, sin equivalente persistido.

    Si la selección es GLOBAL o un único día y `Resultados/` está actualizado respecto a
    `Datos_limpios/`, se LEE de los CSV oficiales (no se recalcula nada). En caso contrario
    —selección personalizada, o `Resultados/` desactualizado o ausente— se recalcula en vivo
    reutilizando exactamente las mismas funciones que `analisis.py` (`Resultado.fuente` indica
    cuál de las dos rutas se tomó).
    """
    es_global = dias is None or set(dias) >= set(motor.dias)
    dia_unico = None if es_global else (dias[0] if dias and len(set(dias)) == 1 else None)
    usa_persistidos = (es_global or dia_unico) and not resultados_desactualizados(
        motor.dir_limpios, dir_resultados)
    if usa_persistidos:
        try:
            persistidos = _leer_persistidos(dir_resultados)
            return _resultado_persistido(persistidos, dia_unico, es_global)
        except (FileNotFoundError, OSError, KeyError, pd.errors.ParserError):
            pass  # cualquier problema leyendo Resultados/ -> recalcular en vivo, nunca romper
    return _resultado_en_vivo(motor, dias, es_global)


def maquinas_de(motor: Motor, etapa: str) -> list[str]:
    """Operaciones (Operacion_norm) que componen una etapa, en orden."""
    filas = motor.mapa_etapas[motor.mapa_etapas["Etapa"] == etapa].sort_values("Orden_OP")
    return filas["Operacion_norm"].tolist()


def etapa_de_operacion(motor: Motor, operacion: str) -> str | None:
    """Etapa a la que pertenece una Operación cruda (código tal y como aparece en alertas.json)."""
    fila = motor.mapa_operaciones.loc[motor.mapa_operaciones["Operacion"] == operacion, "Etapa"]
    return fila.iloc[0] if not fila.empty else None


def operaciones_de_etapa(motor: Motor, etapa: str) -> list[str]:
    """Códigos crudos de Operación (los que usan alertas.json/registro_limpieza.json) de una etapa."""
    return motor.mapa_operaciones.loc[motor.mapa_operaciones["Etapa"] == etapa, "Operacion"].tolist()
