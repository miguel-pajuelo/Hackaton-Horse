"""
predictor_fallos_diario.py
==========================
Generador de reportes diarios de predicción de fallos para la Línea 5 (HORSE Valladolid).
Proof of Concept (PoC) que combina:
1. Modelo de Desgaste Temporal / Supervivencia (Weibull Hazard Rate según tiempo acumulado sin fallo vs MTBF).
2. Señales Precursoras de Línea (tendencia de microparadas NAP, degradación de Tcy y Dp en días previos).
3. Clasificador Predictivo diario calibrado para prescribir acciones preventivas en el relevo de turnos.

Autor: Equipo Hackathon LOSSIA / HORSE
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier


class DailyFailurePredictor:
    """
    Predictor diario de averías para líneas de ensamble.
    Modela la probabilidad de fallo en función de:
    - El tiempo acumulado que lleva cada máquina funcionando sin tener error (t_sin_fallo).
    - Su tiempo medio entre fallos (MTBF).
    - El aumento de microparadas y degradación del tiempo de ciclo en las 24 horas previas.
    """

    def __init__(
        self,
        datos_path: Union[str, Path] = "Datos_limpios/datos_limpios.csv",
        config_path: Union[str, Path] = "Datos_limpios/config_limpia.csv",
        umbral_fallo_tap: float = 0.60,      # Consideramos fallo relevante si TAP > 36 minutos
        beta_weibull: float = 1.85           # Factor de fatiga/envejecimiento (>1 = desgaste progresivo)
    ):
        self.datos_path = Path(datos_path)
        self.config_path = Path(config_path)
        self.umbral_fallo_tap = float(umbral_fallo_tap)
        self.beta_weibull = float(beta_weibull)

        self.df_base: Optional[pd.DataFrame] = None
        self.df_fechas: Optional[pd.DataFrame] = None
        self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        self.features_cols: List[str] = []

        self._cargar_y_entrenar()

    def _cargar_y_entrenar(self) -> None:
        """Carga datos, calcula variables temporales de supervivencia y ajusta el modelo PoC."""
        if not self.datos_path.exists():
            fallback = Path(__file__).resolve().parent.parent / self.datos_path
            if fallback.exists():
                self.datos_path = fallback
            else:
                raise FileNotFoundError(f"No se encontró el archivo: {self.datos_path}")

        raw = pd.read_csv(self.datos_path)
        df = raw[raw["incluir_analisis"] == True].copy()

        # Ordenar cronológicamente
        df["Dia_Cod"] = "S" + df["Week"].astype(str) + "-D" + df["Jour"].astype(str)
        fechas = df[["Week", "Jour", "Dia_Cod"]].drop_duplicates().sort_values(["Week", "Jour"]).reset_index(drop=True)
        fechas["Dia_Num"] = range(len(fechas))
        self.df_fechas = fechas

        df = df.merge(fechas[["Dia_Cod", "Dia_Num"]], on="Dia_Cod")
        df = df.sort_values(["Operacion", "Dia_Num"]).reset_index(drop=True)

        # Identificar anomalías de instrumentación
        if "flag_tap_sospechoso" in df.columns:
            df["es_anomalia_sensor"] = df["flag_tap_sospechoso"].astype(bool) | (df["NAP"] > 5000)
        else:
            df["es_anomalia_sensor"] = df["NAP"] > 5000

        # 1. Definir etiqueta objetivo: fallo significativo hoy (TAP > umbral)
        df["es_fallo_hoy"] = df["TAP"] >= self.umbral_fallo_tap

        # 2. MTBF histórico de fallos significativos por máquina
        mtbf_map = {}
        tap_medio_map = {}
        for op, grp in df.groupby("Operacion"):
            n_fallos = max(1, grp["es_fallo_hoy"].sum())
            tbf_total = grp["TBF"].sum()
            mtbf_map[op] = tbf_total / n_fallos
            tap_medio_map[op] = grp.loc[grp["es_fallo_hoy"], "TAP"].mean()
            if np.isnan(tap_medio_map[op]):
                tap_medio_map[op] = grp["TAP"].mean()

        df["MTBF_historico_h"] = df["Operacion"].map(mtbf_map)
        df["TAP_medio_cuando_falla"] = df["Operacion"].map(tap_medio_map)

        # 3. Calcular tiempo acumulado funcionando sin fallo antes de arrancar cada día
        df["horas_sin_fallo_acum"] = 0.0
        df["dias_sin_fallo_acum"] = 0

        for op, grp in df.groupby("Operacion"):
            cum_tbf = 0.0
            cum_dias = 0
            for idx, row in grp.iterrows():
                df.loc[idx, "horas_sin_fallo_acum"] = cum_tbf
                df.loc[idx, "dias_sin_fallo_acum"] = cum_dias
                # Actualizar acumulador al final del día
                if row["es_fallo_hoy"]:
                    cum_tbf = 0.0
                    cum_dias = 0
                else:
                    cum_tbf += row["TBF"]
                    cum_dias += 1

        # 4. Probabilidad analítica por modelo de Desgaste (Weibull Hazard)
        # Ratio de desgaste = horas acumuladas sin fallo / MTBF esperado
        df["ratio_desgaste_mtbf"] = df["horas_sin_fallo_acum"] / (df["MTBF_historico_h"] + 1e-6)

        # Supervivencia Weibull: P(fallo) = 1 - exp( - (t/eta)^beta )
        eta = df["MTBF_historico_h"] / 0.89  # Gamma(1 + 1/1.85) ≈ 0.89
        df["prob_weibull_desgaste"] = 1.0 - np.exp(-1.0 * np.power(df["horas_sin_fallo_acum"] / (eta + 1e-6), self.beta_weibull))
        df["prob_weibull_desgaste"] = df["prob_weibull_desgaste"].clip(0.02, 0.98)

        # 5. Variables de tendencia en el día previo (t-1)
        df["nap_ayer"] = df.groupby("Operacion")["NAP"].shift(1).fillna(df["NAP"].median())
        df["tap_ayer"] = df.groupby("Operacion")["TAP"].shift(1).fillna(0.0)
        df["tcy_ayer"] = (df.groupby("Operacion")["TBF"].shift(1) * 6000.0) / df.groupby("Operacion")["NPR"].shift(1).replace(0, np.nan)
        df["tcy_ayer"] = df["tcy_ayer"].fillna(75.0)

        # Desviación de microparadas ayer vs media
        nap_media_op = df.groupby("Operacion")["NAP"].transform("median")
        df["ratio_nap_vs_media"] = df["nap_ayer"] / (nap_media_op + 1.0)

        self.features_cols = [
            "horas_sin_fallo_acum",
            "dias_sin_fallo_acum",
            "ratio_desgaste_mtbf",
            "prob_weibull_desgaste",
            "nap_ayer",
            "tap_ayer",
            "tcy_ayer",
            "ratio_nap_vs_media"
        ]

        # Ajuste del modelo predictivo (Proof of Concept supervisado)
        X = df[self.features_cols].fillna(0)
        y = df["es_fallo_hoy"].astype(int)

        self.model.fit(X, y)
        df["prob_modelo_ml"] = self.model.predict_proba(X)[:, 1]

        # Probabilidad combinada calibrada: 50% componente físico de desgaste (Weibull) + 50% patrón ML
        df["Probabilidad_Fallo"] = (0.50 * df["prob_weibull_desgaste"] + 0.50 * df["prob_modelo_ml"]).clip(0.02, 0.98)

        self.df_base = df

    def get_dias_disponibles(self) -> List[str]:
        """Devuelve la lista de códigos de días disponibles ordenados cronológicamente."""
        return self.df_fechas["Dia_Cod"].tolist()

    def predecir_dia(self, dia_codigo: Optional[str] = None) -> pd.DataFrame:
        """
        Genera la predicción de fallos para todas las operaciones en un día determinado
        (por defecto el último día registrado, o simulación del día siguiente).
        """
        if self.df_base is None:
            raise ValueError("El modelo no está inicializado.")

        dias = self.get_dias_disponibles()
        if dia_codigo is None or dia_codigo not in dias:
            dia_codigo = dias[-1]

        sub = self.df_base[self.df_base["Dia_Cod"] == dia_codigo].copy()

        # Determinar nivel de riesgo y semáforo
        def nivel_riesgo(p: float) -> str:
            if p >= 0.70:
                return "CRÍTICO (ROJO)"
            elif p >= 0.45:
                return "ALTO (NARANJA)"
            elif p >= 0.25:
                return "MEDIO (AMARILLO)"
            else:
                return "BAJO (VERDE)"

        sub["Nivel_Riesgo"] = sub["Probabilidad_Fallo"].map(nivel_riesgo)

        # Horas esperadas de parada si ocurre el fallo y piezas en riesgo
        sub["TAP_Previsto_h"] = np.where(
            sub["Probabilidad_Fallo"] >= 0.40,
            sub["TAP_medio_cuando_falla"].fillna(1.2),
            0.0
        )
        # Cadencia aproximada de la línea: 85 motores/hora
        sub["Piezas_En_Riesgo"] = (sub["TAP_Previsto_h"] * 84.7).astype(int)

        # Causa principal identificada
        def causa_diagnostico(r: pd.Series) -> str:
            if r["es_anomalia_sensor"]:
                return "Rebote de señal en instrumentación/PLC (No mecánica)"
            elif r["ratio_desgaste_mtbf"] >= 1.2:
                return f"Desgaste inminente (acumula {r['horas_sin_fallo_acum']:.1f} h continuas sin avería vs MTBF)"
            elif r["ratio_nap_vs_media"] >= 1.5:
                return "Alerta precursora: repunte de microparadas en las últimas 24h"
            elif r["Operacion"] == "ST-2390":
                return "Frecuencia crítica constante de avería propia (cuello de botella crónico)"
            elif r["Operacion"].startswith("PM"):
                return "Fatiga operativa o desfase de cadencia manual"
            else:
                return "Probabilidad basal nominal del proceso"

        sub["Causa_Principal"] = sub.apply(causa_diagnostico, axis=1)

        # Acción preventiva prescrita
        def accion_preventiva(r: pd.Series) -> str:
            if r["es_anomalia_sensor"]:
                return "Revisar fotocélula/final de carrera para filtrar rebotes en tarjeta PLC."
            elif r["Probabilidad_Fallo"] >= 0.70:
                return f"PARADA PREVENTIVA OBLIGATORIA: Inspeccionar mordazas, reapriete y engrase antes del turno."
            elif r["Probabilidad_Fallo"] >= 0.45:
                return f"MONITORIZACIÓN ACTIVA: Vigilancia reforzada durante el relevo de turnos; preparar repuesto."
            else:
                return "Operación en régimen normal; mantenimiento estándar."

        sub["Accion_Recomendada"] = sub.apply(accion_preventiva, axis=1)

        cols_finales = [
            "Orden_OP", "Operacion", "Tipo", "Probabilidad_Fallo", "Nivel_Riesgo",
            "horas_sin_fallo_acum", "dias_sin_fallo_acum", "MTBF_historico_h",
            "ratio_desgaste_mtbf", "TAP_Previsto_h", "Piezas_En_Riesgo",
            "Causa_Principal", "Accion_Recomendada"
        ]

        return sub[cols_finales].sort_values("Probabilidad_Fallo", ascending=False).reset_index(drop=True)

    def generar_reporte_texto(self, dia_codigo: Optional[str] = None) -> str:
        """Genera el informe ejecutivo diario en texto plano para los jefes de unidad y mantenimiento."""
        if dia_codigo is None:
            dia_codigo = self.get_dias_disponibles()[-1]

        preds = self.predecir_dia(dia_codigo)
        top5 = preds.head(5)

        # KPIs globales del día
        n_criticos = (preds["Nivel_Riesgo"] == "CRÍTICO (ROJO)").sum()
        n_altos = (preds["Nivel_Riesgo"] == "ALTO (NARANJA)").sum()
        piezas_riesgo_total = preds.head(10)["Piezas_En_Riesgo"].sum()

        semaforo_global = "🚨 ALTO RIESGO" if n_criticos >= 2 else "⚠️ RIESGO MODERADO" if (n_criticos + n_altos) >= 3 else "✅ RIESGO CONTROLADO"

        lineas = [
            "=" * 82,
            f"HORSE VALLADOLID · LÍNEA 5 DE MONTAJE | REPORTE DIARIO DE PREDICCIÓN DE AVERÍAS",
            "=" * 82,
            f"• Periodo analizado: JORNADA {dia_codigo} | Estado General de la Línea: {semaforo_global}",
            f"• Máquinas en Riesgo Crítico (P > 70%): {n_criticos} | En Riesgo Alto (P > 45%): {n_altos}",
            f"• Estimación de Producción en Riesgo (Top 10): ~{piezas_riesgo_total:,} motores",
            "-" * 82,
            "📋 TOP 5 MÁQUINAS CON MAYOR PROBABILIDAD DE AVERÍA HOY (Prioridad Relevo Turnos):",
            "-" * 82
        ]

        for i, r in top5.iterrows():
            lineas.extend([
                f"#{i+1} | Puesto #{int(r['Orden_OP'])}: {r['Operacion']} ({r['Tipo']}) → PROBABILIDAD: {r['Probabilidad_Fallo']*100:.1f}% [{r['Nivel_Riesgo']}]",
                f"    - Tiempo Acumulado sin Fallo: {r['horas_sin_fallo_acum']:.1f} h ({int(r['dias_sin_fallo_acum'])} días) | MTBF Esperado: {r['MTBF_historico_h']:.1f} h",
                f"    - Desgaste Estimado: {r['ratio_desgaste_mtbf']*100:.0f}% del ciclo de vida agotado",
                f"    - Impacto Previsto si Falla: ~{r['TAP_Previsto_h']:.2f} h de parada ({r['Piezas_En_Riesgo']} motores)",
                f"    - Diagnóstico: {r['Causa_Principal']}",
                f"    - Prescripción: {r['Accion_Recomendada']}",
                ""
            ])

        lineas.extend([
            "-" * 82,
            "💡 PLAN DE ACCIÓN PARA EL JEFE DE MANTENIMIENTO ANTES DE ARRANCAR EL TURNO:",
            "1. Revisión prioritaria en 'ST-2390' e inspección de mordazas y lubricación.",
            "2. Verificar que las estaciones con más de 120% de su MTBF agotado no acumulen holguras.",
            "3. Asegurar que los pulmones intermedios (buffers) de la zona ST-0260 estén libres.",
            "=" * 82
        ])

        return "\n".join(lineas)

    def plot_reporte_diario(self, dia_codigo: Optional[str] = None, save_path: Optional[Union[str, Path]] = None) -> None:
        """Genera el cuadro de mando gráfico de predicción diaria del riesgo."""
        if dia_codigo is None:
            dia_codigo = self.get_dias_disponibles()[-1]

        preds = self.predecir_dia(dia_codigo)
        top10 = preds.head(10).copy()

        sns.set_theme(style="whitegrid", font_scale=0.95)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

        # Panel 1: Top 10 Probabilidades de Fallo
        colores = []
        for p in top10["Probabilidad_Fallo"]:
            if p >= 0.70:
                colores.append("#D62828")  # Rojo
            elif p >= 0.45:
                colores.append("#F77F00")  # Naranja
            elif p >= 0.25:
                colores.append("#E9C46A")  # Amarillo
            else:
                colores.append("#2A9D8F")  # Verde

        ax1.barh(top10["Operacion"][::-1], top10["Probabilidad_Fallo"][::-1] * 100, color=colores[::-1])
        ax1.set_xlabel("Probabilidad de Fallo Hoy (%)", weight="bold")
        ax1.set_title(f"A. Top 10 Máquinas con Mayor Riesgo de Avería · Jornada {dia_codigo}", weight="bold", fontsize=12)
        ax1.axvline(70, color="#D62828", linestyle="--", alpha=0.7, label="Umbral Crítico (70%)")
        ax1.axvline(45, color="#F77F00", linestyle="--", alpha=0.7, label="Umbral Alto (45%)")
        ax1.set_xlim(0, 105)
        ax1.legend(loc="lower right")

        for i, val in enumerate(top10["Probabilidad_Fallo"][::-1] * 100):
            ax1.text(val + 1.5, i, f"{val:.1f}%", va="center", weight="bold", fontsize=9)

        # Panel 2: Horas Acumuladas sin Fallo vs MTBF (Envejecimiento)
        ax2.scatter(
            preds["horas_sin_fallo_acum"],
            preds["Probabilidad_Fallo"] * 100,
            c=preds["Probabilidad_Fallo"] * 100,
            cmap="YlOrRd",
            s=70, alpha=0.85, edgecolor="black", linewidth=0.6
        )
        ax2.set_xlabel("Horas de Producción Acumuladas sin Avería (t_sin_fallo)", weight="bold")
        ax2.set_ylabel("Probabilidad de Fallo Estimada (%)", weight="bold")
        ax2.set_title("B. Curva de Desgaste: Riesgo en función del Tiempo sin Paradas", weight="bold", fontsize=12)
        ax2.set_ylim(-2, 105)

        # Anotar las 3 máquinas más extremas
        for _, r in top10.head(3).iterrows():
            ax2.annotate(
                f"{r['Operacion']}\n({r['horas_sin_fallo_acum']:.0f}h)",
                (r["horas_sin_fallo_acum"], r["Probabilidad_Fallo"] * 100),
                xytext=(6, 6), textcoords="offset points",
                fontsize=8.5, weight="bold", color="#1B263B"
            )

        plt.tight_layout()
        if save_path:
            p = Path(save_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(p, dpi=160, bbox_inches="tight")
            print(f"Gráfico de reporte guardado en: {p.resolve()}")
            plt.close(fig)
        else:
            plt.show()


def main():
    parser = argparse.ArgumentParser(description="Predictor Diario de Fallos y Averías (HORSE Valladolid L5)")
    parser.add_argument("--dia", default=None, help="Código del día a predecir (ej. S42-D3). Por defecto el último día.")
    parser.add_argument("--datos", default="Datos_limpios/datos_limpios.csv", help="Ruta a datos_limpios.csv")
    parser.add_argument("--plot", default=None, help="Ruta para guardar imagen PNG del reporte diario.")
    parser.add_argument("--output_csv", default=None, help="Ruta opcional para guardar el ranking en CSV.")

    args = parser.parse_args()

    predictor = DailyFailurePredictor(datos_path=args.datos)
    dia = args.dia if args.dia else predictor.get_dias_disponibles()[-1]

    print(predictor.generar_reporte_texto(dia))

    if args.output_csv:
        preds = predictor.predecir_dia(dia)
        preds.to_csv(args.output_csv, index=False)
        print(f"Predicciones guardadas en CSV: {args.output_csv}")

    if args.plot:
        predictor.plot_reporte_diario(dia, save_path=args.plot)


if __name__ == "__main__":
    main()
