"""
analisis_cuellos_botella.py
===========================
Módulo genérico y reutilizable para la detección, modelado y explicabilidad
de cuellos de botella y máquinas penalizantes en cualquier línea de producción industrial.

Autor: Equipo Hackathon LOSSIA / HORSE
Compatible con: Pandas, NumPy, Matplotlib, Seaborn.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


class BottleneckAnalyzer:
    """
    Analizador genérico de cuellos de botella para líneas de montaje y manufactura.

    Desacopla la Parada Propia (TAP) de las Paradas Inducidas (DES + SAT) y evalúa
    la propagación topológica de saturación aguas arriba y desabastecimiento aguas abajo.
    Calcula un Índice de Penalización LOSSIA (IPL) de 0 a 100 configurable y genera
    diagnósticos automáticos para responsables de producción y mantenimiento.
    """

    # Mapeo de sinónimos comunes en bases de datos industriales
    COLUMN_ALIASES = {
        "op": ["operacion", "operation", "op", "station", "station_id", "maquina", "machine", "equipo", "puesto"],
        "orden": ["orden_op", "orden", "order", "line_order", "sequence", "secuencia", "pos", "step"],
        "tbf": ["tbf", "uptime", "tiempo_marcha", "running_time", "operating_time", "tiempo_produccion", "t_marcha"],
        "tap": ["tap", "downtime", "parada_propia", "breakdown", "failure_time", "tiempo_averia", "t_parada_propia"],
        "des": ["des", "starvation", "desabastecimiento", "starving", "lack_of_parts", "espera_pieza", "t_des"],
        "sat": ["sat", "blocking", "saturacion", "blocked", "line_blocked", "bloqueo_salida", "t_sat"],
        "nap": ["nap", "stops", "num_paradas", "failures", "stop_count", "conteo_fallas", "n_paradas"],
        "npr": ["npr", "parts", "pieces", "piezas", "piezas_producidas", "production_count", "piezas_buenas", "output_count"]
    }

    def __init__(
        self,
        col_op: Optional[str] = None,
        col_orden: Optional[str] = None,
        col_tbf: Optional[str] = None,
        col_tap: Optional[str] = None,
        col_des: Optional[str] = None,
        col_sat: Optional[str] = None,
        col_nap: Optional[str] = None,
        col_npr: Optional[str] = None,
        t_abierto_dia: float = 22.0,
        dp_min_target: float = 90.0,
        tcy_max_cmin: float = 80.0,
        cmin_per_second: float = 1.0 / 0.6,  # 1 cmin = 0.6 s -> factor 6000 cmin/hora
        peso_tap: float = 0.35,
        peso_culpa: float = 0.25,
        peso_impacto: float = 0.25,
        peso_dp: float = 0.15,
        auto_detect_parallel: bool = True,
        sensor_anomaly_nap_threshold: float = 5000.0
    ):
        """
        Parámetros:
        -----------
        col_op: Nombre de la columna de identificación de operación/máquina.
        col_orden: Nombre de la columna con la posición/secuencia en la línea.
        col_tbf: Nombre de la columna de tiempo de buen funcionamiento (horas).
        col_tap: Nombre de la columna de parada propia (horas).
        col_des: Nombre de la columna de desabastecimiento (horas).
        col_sat: Nombre de la columna de saturación (horas).
        col_nap: Nombre de la columna con el conteo de paradas propias.
        col_npr: Nombre de la columna con el conteo de piezas producidas.
        t_abierto_dia: Horas abiertas de referencia por día o turno (por defecto 22 h).
        dp_min_target: Disponibilidad contractual mínima esperada en % (por defecto 90.0%).
        tcy_max_cmin: Tiempo de ciclo máximo admitido en cmin (por defecto 80.0 cmin = 48 s).
        cmin_per_second: Conversión a centésimas de minuto (por defecto 6000 cmin/hora).
        peso_tap: Ponderación en el IPL para la duración de averías propias directas (0.0 a 1.0).
        peso_culpa: Ponderación en el IPL para el ratio TAP / (TAP + TAI).
        peso_impacto: Ponderación en el IPL para la afección a puestos vecinos (SAT_ant + DES_sig).
        peso_dp: Ponderación en el IPL para la penalización por incumplir Dp_min.
        auto_detect_parallel: Si True, detecta automáticamente puestos en paralelo por reducción de volumen al 50%.
        sensor_anomaly_nap_threshold: Umbral de paradas/día para detectar rebote de sensor (chattering).
        """
        self.col_map = {
            "op": col_op,
            "orden": col_orden,
            "tbf": col_tbf,
            "tap": col_tap,
            "des": col_des,
            "sat": col_sat,
            "nap": col_nap,
            "npr": col_npr
        }
        self.t_abierto = float(t_abierto_dia)
        self.dp_min = float(dp_min_target)
        self.tcy_max = float(tcy_max_cmin)
        self.cmin_factor = 6000.0  # 1 hora = 60 min = 6000 cmin
        self.peso_tap = peso_tap
        self.peso_culpa = peso_culpa
        self.peso_impacto = peso_impacto
        self.peso_dp = peso_dp
        self.auto_detect_parallel = auto_detect_parallel
        self.sensor_nap_threshold = float(sensor_anomaly_nap_threshold)

        # Atributos de resultado
        self.results_df: Optional[pd.DataFrame] = None
        self.raw_data_summary: Dict[str, Union[int, float]] = {}

    def _infer_column(self, df_cols: List[str], key: str) -> str:
        """Infiere automáticamente el nombre de una columna según sus alias."""
        specified = self.col_map.get(key)
        if specified and specified in df_cols:
            return specified

        # Búsqueda insensible a mayúsculas
        cols_lower = {c.lower(): c for c in df_cols}
        for alias in self.COLUMN_ALIASES[key]:
            if alias.lower() in cols_lower:
                return cols_lower[alias.lower()]

        raise ValueError(
            f"No se pudo inferir la columna para '{key}'. Columnas disponibles en el dataset: {df_cols}. "
            f"Por favor especifícala manualmente con el parámetro col_{key}."
        )

    def _resolve_mappings(self, df: pd.DataFrame) -> Dict[str, str]:
        """Resuelve el diccionario completo de columnas."""
        resolved = {}
        for key in ["op", "orden", "tbf", "tap", "des", "sat", "nap", "npr"]:
            resolved[key] = self._infer_column(list(df.columns), key)
        return resolved

    def fit_transform(
        self,
        df: pd.DataFrame,
        config_df: Optional[pd.DataFrame] = None,
        filter_col: Optional[str] = "incluir_analisis"
    ) -> pd.DataFrame:
        """
        Ejecuta el pipeline completo de análisis sobre el dataset proporcionado.

        Retorna un DataFrame ordenado por el flujo de la línea con todos los KPIs,
        el Índice de Penalización LOSSIA (IPL) y los diagnósticos explicables.
        """
        data = df.copy()

        # Filtrar operaciones válidas si existe la columna de inclusión
        if filter_col and filter_col in data.columns:
            data = data[data[filter_col] == True].copy()
            if data.empty:
                raise ValueError(f"El dataset quedó vacío tras filtrar por {filter_col} == True.")

        # Resolver columnas
        cols = self._resolve_mappings(data)
        self.col_map = cols

        # Guardar resumen de partida
        self.raw_data_summary = {
            "num_registros": len(data),
            "num_operaciones": data[cols["op"]].nunique(),
        }

        # 1. Agregación a nivel de operación si hay múltiples registros por máquina (días, turnos, semanas)
        necesita_agregacion = len(data) > data[cols["op"]].nunique()

        if necesita_agregacion:
            # Agrupar por operación y orden
            agrupado = data.groupby([cols["orden"], cols["op"]]).agg({
                cols["tbf"]: "mean",
                cols["tap"]: "mean",
                cols["des"]: "mean",
                cols["sat"]: "mean",
                cols["nap"]: "mean",
                cols["npr"]: "mean"
            }).reset_index()
        else:
            agrupado = data[[cols["orden"], cols["op"], cols["tbf"], cols["tap"],
                             cols["des"], cols["sat"], cols["nap"], cols["npr"]]].copy()

        # Asegurar orden secuencial estricto
        agrupado = agrupado.sort_values(cols["orden"]).reset_index(drop=True)

        # 2. Renombrar columnas internas estandarizadas
        res = pd.DataFrame()
        res["Orden_OP"] = agrupado[cols["orden"]]
        res["Operacion"] = agrupado[cols["op"]]
        res["TBF"] = agrupado[cols["tbf"]].astype(float)
        res["TAP"] = agrupado[cols["tap"]].astype(float)
        res["DES"] = agrupado[cols["des"]].astype(float)
        res["SAT"] = agrupado[cols["sat"]].astype(float)
        res["NAP"] = agrupado[cols["nap"]].astype(float)
        res["NPR"] = agrupado[cols["npr"]].astype(float)

        # Añadir información de configuración externa si está disponible
        if config_df is not None and "Tipo" in config_df.columns and "Operacion" in config_df.columns:
            res = res.merge(config_df[["Operacion", "Tipo"]], on="Operacion", how="left")
            res["Tipo"] = res["Tipo"].fillna("Estándar")
        elif "Tipo" in data.columns:
            tipos = data[[cols["op"], "Tipo"]].drop_duplicates()
            res = res.merge(tipos, left_on="Operacion", right_on=cols["op"], how="left")
            if cols["op"] != "Operacion":
                res = res.drop(columns=[cols["op"]])
            res["Tipo"] = res["Tipo"].fillna("Estándar")
        else:
            res["Tipo"] = "Estación"

        # 3. Detección de paradas inducidas y culpabilidad
        res["TAI"] = res["DES"] + res["SAT"]
        res["Ratio_Culpa"] = res["TAP"] / (res["TAP"] + res["TAI"] + 1e-6)

        # 4. Detección automática de estaciones en paralelo
        # Si dos máquinas consecutivas producen ~50% de la mediana de la línea
        mediana_piezas = res["NPR"].replace(0, np.nan).median()
        res["es_paralelo"] = False

        if self.auto_detect_parallel and mediana_piezas > 0:
            ratio_piezas = res["NPR"] / mediana_piezas
            posibles = (ratio_piezas >= 0.35) & (ratio_piezas <= 0.65)
            # Marcar consecutivas que cumplan la condición
            for i in range(len(res) - 1):
                if posibles.iloc[i] and posibles.iloc[i+1]:
                    res.loc[i, "es_paralelo"] = True
                    res.loc[i+1, "es_paralelo"] = True

        # 5. Cálculo de KPIs contractuales
        # Dp: Disponibilidad propia intrínseca (%)
        res["Dp"] = 100.0 * res["TBF"] / (res["TBF"] + res["TAP"] + 1e-6)

        # Tcy: Tiempo de ciclo (cmin)
        # 1 hora = 6000 cmin
        npr_safe = res["NPR"].replace(0, np.nan)
        res["Tcy_unitario_cmin"] = (res["TBF"] * self.cmin_factor) / npr_safe
        res["Tcy_linea_cmin"] = np.where(
            res["es_paralelo"],
            res["Tcy_unitario_cmin"] / 2.0,
            res["Tcy_unitario_cmin"]
        )

        # Fpm: Frecuencia de averías por mil piezas
        res["Fpm"] = (res["NAP"] / npr_safe) * 1000.0

        # MTBF y MTTR
        nap_safe = res["NAP"].replace(0, np.nan)
        res["MTBF_h"] = res["TBF"] / nap_safe
        res["MTTR_min"] = (res["TAP"] * 60.0) / nap_safe

        # 6. Detección de anomalías de instrumentación / sensor
        # Muchísimas paradas (> umbral) con producción normal
        res["es_anomalia_sensor"] = (res["NAP"] >= self.sensor_nap_threshold) & (res["NPR"] > 0.5 * mediana_piezas)
        # Contador de piezas descalibrado (produciendo muchas horas pero 0 o casi 0 piezas)
        res["flag_contador_piezas_roto"] = (res["TBF"] > 2.0) & (res["NPR"] < 0.05 * mediana_piezas)

        # 7. Propagación topológica en vecinas
        # SAT de la anterior (aguas arriba) + DES de la posterior (aguas abajo)
        res["SAT_anterior"] = res["SAT"].shift(1).fillna(0.0)
        res["DES_siguiente"] = res["DES"].shift(-1).fillna(0.0)
        res["Impacto_Vecinas"] = res["SAT_anterior"] + res["DES_siguiente"]

        # 8. Cálculo del Índice de Penalización LOSSIA (IPL)
        res = self._compute_ipl(res)

        # 9. Generación de Diagnósticos Explicables
        res["Diagnostico_Tipo"] = res.apply(self._clasificar_operacion, axis=1)
        res["Diagnostico_Texto"] = res.apply(self._generar_diagnostico_texto, axis=1)

        self.results_df = res.sort_values("Orden_OP").reset_index(drop=True)
        return self.results_df

    def _compute_ipl(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula el Índice de Penalización LOSSIA normalizado (0 a 100)."""
        def norm(series: pd.Series) -> pd.Series:
            s_min, s_max = series.min(), series.max()
            return (series - s_min) / (s_max - s_min + 1e-6)

        # Penalización por Dp < Dp_min contractual
        gap_dp = np.maximum(0.0, (self.dp_min - df["Dp"]) / self.dp_min)

        # Score crudo ponderado
        score_crudo = (
            self.peso_tap * norm(df["TAP"]) +
            self.peso_culpa * df["Ratio_Culpa"] +
            self.peso_impacto * norm(df["Impacto_Vecinas"]) +
            self.peso_dp * gap_dp
        )

        df["IPL"] = 100.0 * norm(score_crudo)
        return df

    def _clasificar_operacion(self, row: pd.Series) -> str:
        """Asigna categoría cualitativa al puesto."""
        if row["es_anomalia_sensor"]:
            return "Anomalía de Instrumentación / Sensor"
        if row["IPL"] >= 60.0:
            return "Cuello de Botella Crítico (Penalizante Muy Alta)"
        if row["IPL"] >= 40.0:
            return "Penalizante Moderada"
        if row["TAI"] >= 3.0 and row["Ratio_Culpa"] < 0.4:
            return "Víctima de Línea (Parada Inducida)"
        return "Operación Estable / Equilibrada"

    def _generar_diagnostico_texto(self, r: pd.Series) -> str:
        """Genera explicación en lenguaje natural comprensible por jefes de unidad y mantenimiento."""
        op = r["Operacion"]
        orden = int(r["Orden_OP"])
        tipo = r["Tipo"]
        ipl = r["IPL"]
        dp = r["Dp"]
        tap = r["TAP"]
        tai = r["TAI"]
        fpm = r["Fpm"]
        tcy = r["Tcy_linea_cmin"]

        lineas = [
            f"Puesto #{orden} [{op} - {tipo}] | IPL: {ipl:.1f}/100",
            f"• Dp: {dp:.1f}% ({'INCUMPLE < ' + str(self.dp_min) + '%' if dp < self.dp_min else 'OK'}) | Tcy: {tcy:.1f} cmin ({'LENTO > ' + str(self.tcy_max) if tcy > self.tcy_max else 'OK'})",
            f"• Tiempos: TAP propia = {tap:.2f} h/día | TAI inducida = {tai:.2f} h/día (DES: {r['DES']:.2f}h, SAT: {r['SAT']:.2f}h)",
            f"• Frecuencia: {fpm:.1f} averías/1000 pz | MTTR: {r['MTTR_min']:.1f} min | MTBF: {r['MTBF_h']:.1f} h"
        ]

        if r["es_anomalia_sensor"]:
            lineas.append(
                "• VEREDICTO: ALERTA DE INSTRUMENTACIÓN. Registra un conteo masivo de paradas sin frenar la producción. "
                "No enviar mecánicos; revisar fotocélula/final de carrera por rebote de contacto (chattering)."
            )
        elif r["flag_contador_piezas_roto"]:
            lineas.append(
                "• VEREDICTO: CONTADOR DE PIEZAS DESCALIBRADO. La estación está en marcha pero no suma piezas al PLC."
            )
        elif ipl >= 60.0:
            lineas.append(
                f"• VEREDICTO: CUELLO DE BOTELLA CRÍTICO. Falla de forma autónoma ({tap:.2f} h) y contagia {r['Impacto_Vecinas']:.2f} h "
                f"de parada a las máquinas contiguas. PRIORIDAD MÁXIMA de mantenimiento correctivo/predictivo."
            )
        elif r["TAI"] >= 3.0 and r["Ratio_Culpa"] < 0.4:
            lineas.append(
                f"• VEREDICTO: VÍCTIMA DE LÍNEA. No falla por sí sola, pero pierde {tai:.2f} h/día esperando piezas o saturada por la siguiente. "
                f"No intervenir este puesto; actuar sobre la máquina penalizante contigua."
            )
        else:
            lineas.append("• VEREDICTO: Comportamiento operativo dentro de la tolerancia nominal de la línea.")

        return "\n".join(lineas)

    def get_top_penalizantes(self, n: int = 10, incluir_anomalias: bool = False) -> pd.DataFrame:
        """Devuelve el ranking de las N máquinas más penalizantes."""
        if self.results_df is None:
            raise ValueError("Primero debes ejecutar fit_transform().")

        df = self.results_df
        if not incluir_anomalias:
            df = df[~df["es_anomalia_sensor"]]

        cols_mostrar = [
            "Orden_OP", "Operacion", "Tipo", "IPL", "TAP", "TAI", "Dp",
            "Tcy_linea_cmin", "Fpm", "MTTR_min", "Impacto_Vecinas", "Diagnostico_Tipo"
        ]
        return df.sort_values("IPL", ascending=False).head(n)[cols_mostrar].reset_index(drop=True)

    def export_results(self, output_path: Union[str, Path]) -> None:
        """Exporta los resultados completos a un archivo CSV."""
        if self.results_df is None:
            raise ValueError("Primero debes ejecutar fit_transform().")
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.results_df.to_csv(path, index=False)
        print(f"Resultados exportados con éxito a: {path.resolve()}")

    def plot_resumen(self, save_path: Optional[Union[str, Path]] = None) -> None:
        """
        Genera un panel visual con tres gráficos clave:
        1. Matriz de Culpabilidad (TAP vs TAI).
        2. Perfil Longitudinal de Estados a lo largo del flujo.
        3. Top 10 Máquinas Penalizantes según el IPL.
        """
        if self.results_df is None:
            raise ValueError("Primero debes ejecutar fit_transform().")

        sns.set_theme(style="whitegrid", font_scale=0.95)
        fig = plt.figure(figsize=(18, 12))
        gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.2])

        ax_cuadrante = fig.add_subplot(gs[0, 0])
        ax_top = fig.add_subplot(gs[0, 1])
        ax_linea = fig.add_subplot(gs[1, :])

        df = self.results_df

        # 1. Matriz de Culpabilidad
        colores_cat = {
            "Cuello de Botella Crítico (Penalizante Muy Alta)": "#D62828",
            "Penalizante Moderada": "#E76F51",
            "Víctima de Línea (Parada Inducida)": "#F77F00",
            "Operación Estable / Equilibrada": "#2A9D8F",
            "Anomalía de Instrumentación / Sensor": "#9D4EDD"
        }

        sns.scatterplot(
            data=df,
            x="TAP", y="TAI",
            hue="Diagnostico_Tipo",
            palette=colores_cat,
            s=90, alpha=0.85,
            ax=ax_cuadrante
        )
        ax_cuadrante.set_title("1. Matriz de Culpabilidad: Parada Propia vs Inducida", weight="bold", fontsize=12)
        ax_cuadrante.set_xlabel("Parada Propia (TAP, horas/día) → CULPABILIDAD", weight="bold")
        ax_cuadrante.set_ylabel("Parada Inducida (TAI = DES + SAT, horas/día) → VÍCTIMA", weight="bold")
        ax_cuadrante.legend(fontsize=8, loc="upper right")

        # Anotar top 4 máquinas
        top4 = df[~df.es_anomalia_sensor].sort_values("IPL", ascending=False).head(4)
        for _, r in top4.iterrows():
            ax_cuadrante.annotate(
                r["Operacion"], (r["TAP"], r["TAI"]),
                xytext=(5, 5), textcoords="offset points",
                weight="bold", fontsize=9, color="#1D3557"
            )

        # 2. Top 10 Máquinas Penalizantes (IPL)
        top10 = self.get_top_penalizantes(10, incluir_anomalias=False)
        palette_bars = sns.color_palette("Reds_r", len(top10))
        sns.barplot(
            data=top10,
            x="IPL", y="Operacion",
            palette=palette_bars,
            ax=ax_top
        )
        ax_top.set_title("2. Top 10 Máquinas Penalizantes (Índice LOSSIA IPL)", weight="bold", fontsize=12)
        ax_top.set_xlabel("Índice de Penalización LOSSIA (0 a 100)", weight="bold")
        ax_top.set_ylabel("Operación", weight="bold")
        for i, val in enumerate(top10["IPL"]):
            ax_top.text(val + 1, i, f"{val:.1f} pts (Dp: {top10.iloc[i]['Dp']:.1f}%)", va="center", fontsize=8.5, weight="bold")
        ax_top.set_xlim(0, 115)

        # 3. Perfil de Línea a lo largo del flujo
        ordenes = df["Orden_OP"].values
        tbf = df["TBF"].values
        des = df["DES"].values
        sat = df["SAT"].values
        tap = df["TAP"].values

        ax_linea.bar(ordenes, tbf, label="TBF (Produciendo)", color="#2A9D8F", alpha=0.85, width=0.8)
        ax_linea.bar(ordenes, des, bottom=tbf, label="DES (Desabastecida)", color="#E9C46A", alpha=0.85, width=0.8)
        ax_linea.bar(ordenes, sat, bottom=tbf + des, label="SAT (Saturada)", color="#264653", alpha=0.85, width=0.8)
        ax_linea.bar(ordenes, tap, bottom=tbf + des + sat, label="TAP (Parada Propia)", color="#E76F51", alpha=0.85, width=0.8)

        ax_linea.set_title("3. Firma de Tiempos a lo largo del Flujo de la Línea (Orden Secuencial)", weight="bold", fontsize=12)
        ax_linea.set_xlabel("Orden de Operación en Línea", weight="bold")
        ax_linea.set_ylabel("Horas del Día Productivo", weight="bold")
        ax_linea.set_xlim(df["Orden_OP"].min() - 1, df["Orden_OP"].max() + 1)
        ax_linea.legend(loc="upper right", ncol=4)

        plt.tight_layout()
        if save_path:
            p = Path(save_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(p, dpi=150)
            print(f"Gráfico resumen guardado en: {p.resolve()}")
        plt.show()

    def plot_cuello_botella_cadena(self, save_path: Optional[Union[str, Path]] = None, ventana_suavizado: int = 5) -> None:
        """
        Genera el gráfico del cuello de botella medio a lo largo de toda la cadena de montaje.
        Muestra:
        1. Panel superior: Índice de Penalización (IPL) y la curva del Cuello de Botella Medio (Media Móvil).
        2. Panel inferior: Mecánica física del atasco (Cruce de Saturación SAT aguas arriba vs Desabastecimiento DES aguas abajo).
        """
        if self.results_df is None:
            raise ValueError("Primero debes ejecutar fit_transform().")

        df = self.results_df.sort_values("Orden_OP").reset_index(drop=True)
        sns.set_theme(style="whitegrid", font_scale=0.95)
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), sharex=True, gridspec_kw={"height_ratios": [1.2, 1]})

        ordenes = df["Orden_OP"].values
        ipl = df["IPL"].values
        tap = df["TAP"].values
        sat = df["SAT"].values
        des = df["DES"].values

        # Curva de cuello de botella medio (suavizado por tramos)
        ipl_clean = df["IPL"].copy()
        if "es_anomalia_sensor" in df.columns and df["es_anomalia_sensor"].any():
            ipl_clean[df["es_anomalia_sensor"]] = np.nan
        ipl_media = ipl_clean.rolling(window=ventana_suavizado, center=True, min_periods=1).mean()

        # Panel 1: Curva de Penalización e IPL medio
        ax1.fill_between(ordenes, 0, ipl, color="#E63946", alpha=0.18, label="IPL por Puesto de Montaje")
        ax1.plot(ordenes, ipl, color="#E63946", alpha=0.45, linewidth=1.2, linestyle=":")
        ax1.plot(ordenes, ipl_media, color="#9B2226", linewidth=2.8, label=f"Cuello de Botella Medio (Media Móvil {ventana_suavizado} puestos)")
        ax1.axhline(60, color="#D62828", linestyle="--", linewidth=1.5, alpha=0.7, label="Umbral Crítico (IPL ≥ 60)")
        ax1.axhline(40, color="#F77F00", linestyle="--", linewidth=1.5, alpha=0.7, label="Umbral Moderado (IPL ≥ 40)")

        # Anotación de los top cuellos de botella
        top_pts = df[~df.es_anomalia_sensor].sort_values("IPL", ascending=False).head(4)
        for _, r in top_pts.iterrows():
            x = r["Orden_OP"]
            y = r["IPL"]
            ax1.scatter(x, y, color="#9B2226", s=90, zorder=5, edgecolor="white", linewidth=1.5)
            offset = 12 if y < 70 else -18
            ax1.annotate(
                f"{r['Operacion']}\n[{y:.1f} pts]",
                xy=(x, y), xytext=(x, y + offset),
                ha="center", fontsize=8.5, weight="bold", color="#1B263B",
                arrowprops=dict(arrowstyle="->", color="#1B263B", lw=1.2),
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#FFF8E7", edgecolor="#D4A373", alpha=0.9)
            )

        ax1.set_title("A. Perfil del Cuello de Botella Medio a lo largo de la Cadena de Montaje (Índice LOSSIA IPL)", fontsize=13, weight="bold")
        ax1.set_ylabel("Índice de Penalización (0 a 100)", fontsize=10, weight="bold")
        ax1.set_ylim(-2, 105)
        ax1.legend(loc="upper left", frameon=True, fontsize=8.5)

        # Panel 2: Mecánica de flujo (SAT vs TAP vs DES)
        ax2.bar(ordenes, tap, width=0.8, color="#D62828", alpha=0.5, label="Parada Propia (TAP, h/día)", zorder=2)
        ax2.plot(ordenes, sat, color="#1D3557", linewidth=2.2, label="Saturación (SAT, horas atascada por la siguiente)", zorder=3)
        ax2.plot(ordenes, des, color="#E9C46A", linewidth=2.2, label="Desabastecimiento (DES, horas sin piezas)", zorder=3)
        des_media = pd.Series(des).rolling(ventana_suavizado, center=True, min_periods=1).mean()
        ax2.plot(ordenes, des_media, color="#B08900", linestyle="--", linewidth=1.5, alpha=0.8, label="Desabastecimiento Medio del Tramo")

        ax2.set_title("B. Mecánica del Atasco: Saturación aguas arriba (SAT) vs Desabastecimiento aguas abajo (DES)", fontsize=13, weight="bold")
        ax2.set_xlabel("Orden Secuencial de Operación a lo largo de la Cadena de Montaje", fontsize=10, weight="bold")
        ax2.set_ylabel("Horas del Día Productivo (base 22 h)", fontsize=10, weight="bold")
        ax2.set_xlim(ordenes.min() - 1, ordenes.max() + 1)
        ax2.legend(loc="upper left", frameon=True, fontsize=8.5)

        plt.tight_layout()
        if save_path:
            p = Path(save_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(p, dpi=160, bbox_inches="tight")
            print(f"Gráfico del cuello de botella medio guardado en: {p.resolve()}")
        plt.show()

    def generar_informe_texto(self) -> str:
        """Genera un resumen ejecutivo en texto plano listo para imprimir o enviar."""
        if self.results_df is None:
            raise ValueError("Primero debes ejecutar fit_transform().")

        df = self.results_df
        top = self.get_top_penalizantes(5, incluir_anomalias=False)
        anomalias = df[df.es_anomalia_sensor]

        lineas = [
            "=" * 75,
            "INFORME EJECUTIVO DE CUELLOS DE BOTELLA Y MÁQUINAS PENALIZANTES",
            "=" * 75,
            f"• Total operaciones analizadas: {len(df)}",
            f"• Referencias contractuales aplicadas: Dp ≥ {self.dp_min}% | Tcy ≤ {self.tcy_max} cmin",
            f"• Operaciones que incumplen Disponibilidad Propia (Dp < {self.dp_min}%): {(df.Dp < self.dp_min).sum()}",
            f"• Operaciones con Tiempo de Ciclo lento (Tcy > {self.tcy_max} cmin): {(df.Tcy_linea_cmin > self.tcy_max).sum()}",
            "-" * 75,
            "🏆 TOP 5 MÁQUINAS MÁS PENALIZANTES (Mantenimiento Prioritario):",
            "-" * 75
        ]

        for idx, row in top.iterrows():
            lineas.append(
                f"#{idx+1} | Puesto #{int(row['Orden_OP'])}: {row['Operacion']} ({row['Tipo']}) "
                f"→ IPL: {row['IPL']:.1f}/100 | TAP: {row['TAP']:.2f} h/d | Dp: {row['Dp']:.1f}% | Impacto Vecinas: {row['Impacto_Vecinas']:.2f} h"
            )

        if not anomalias.empty:
            lineas.extend([
                "-" * 75,
                "⚠️ ANOMALÍAS DE INSTRUMENTACIÓN (Intervención de Sensor/PLC, no mecánica):",
                "-" * 75
            ])
            for _, row in anomalias.iterrows():
                lineas.append(
                    f"• {row['Operacion']} (Puesto #{int(row['Orden_OP'])}): Registra {row['NAP']:.0f} paradas/día con {row['NPR']:.0f} piezas. Rebote de señal."
                )

        lineas.append("=" * 75)
        return "\n".join(lineas)


def main():
    """Interfaz de Línea de Comandos (CLI) para ejecutar el analizador sobre cualquier dataset."""
    parser = argparse.ArgumentParser(
        description="Analizador genérico de cuellos de botella industriales (Reto LOSSIA / HORSE)."
    )
    parser.add_argument("--data", required=True, help="Ruta al archivo CSV con los datos de paradas.")
    parser.add_argument("--config", default=None, help="Ruta opcional al CSV de configuración de línea.")
    parser.add_argument("--output", default="resultados_cuellos_botella.csv", help="Ruta para exportar el CSV resultante.")
    parser.add_argument("--plot", default=None, help="Ruta opcional para guardar la imagen del gráfico de resumen (.png).")
    parser.add_argument("--plot_cadena", default=None, help="Ruta opcional para guardar el gráfico del cuello de botella medio a lo largo de la cadena (.png).")
    parser.add_argument("--t_abierto", type=float, default=22.0, help="Horas abiertas por día (default: 22.0).")
    parser.add_argument("--dp_min", type=float, default=90.0, help="Disponibilidad propia mínima en % (default: 90.0).")
    parser.add_argument("--tcy_max", type=float, default=80.0, help="Tiempo de ciclo máximo en cmin (default: 80.0).")

    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Error: No se encontró el archivo de datos: {data_path}")
        sys.exit(1)

    print(f"Cargando dataset desde: {data_path.resolve()}...")
    df = pd.read_csv(data_path)

    cfg = None
    if args.config:
        cfg_path = Path(args.config)
        if cfg_path.exists():
            print(f"Cargando configuración desde: {cfg_path.resolve()}...")
            cfg = pd.read_csv(cfg_path)

    analyzer = BottleneckAnalyzer(
        t_abierto_dia=args.t_abierto,
        dp_min_target=args.dp_min,
        tcy_max_cmin=args.tcy_max
    )

    print("Ejecutando análisis de cuellos de botella...")
    res = analyzer.fit_transform(df, config_df=cfg)

    print("\n" + analyzer.generar_informe_texto() + "\n")

    analyzer.export_results(args.output)

    if args.plot:
        analyzer.plot_resumen(save_path=args.plot)

    if args.plot_cadena:
        analyzer.plot_cuello_botella_cadena(save_path=args.plot_cadena)


if __name__ == "__main__":
    main()
