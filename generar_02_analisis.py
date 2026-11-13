"""
Generador del notebook 02_analisis_penalizantes.ipynb para el Hackathon HORSE / Reto LOSSIA
"""
import json
from pathlib import Path

def make_cell(cell_type, source, outputs=None):
    c = {
        "cell_type": cell_type,
        "metadata": {},
        "source": [s + "\n" for s in source.split("\n")]
    }
    if cell_type == "code":
        c["execution_count"] = None
        c["outputs"] = outputs or []
    return c

cells = []

# ==================== CELDA 1 ====================
cells.append(make_cell("markdown", """# 02 · Identificación y Explicabilidad de Máquinas Penalizantes
### Reto LOSSIA · Línea 5 de Montaje de Motores (HORSE Valladolid)

En este notebook abordamos el **núcleo técnico del reto**: responder objetivamente a la pregunta:
> **¿Qué máquina es realmente penalizante para la línea y por qué?**

---

### 1. Contexto y Reglas de Negocio de HORSE
1. **No toda parada es igual**:
   - **TAP (Parada Propia / Temps d'Arrêt Propre)**: La máquina se para sola (avería mecánica, eléctrica, microparada o fallo en puesto manual).
   - **TAI (Parada Inducida = DES + SAT / Temps d'Arrêt Induit)**: La máquina se detiene por motivos ajenos a ella:
     - **DES (Desabastecimiento)**: La operación previa se ha detenido y no suministra piezas (línea vacía).
     - **SAT (Saturación)**: La operación posterior está detenida o saturada y no acepta piezas (línea atascada).
   - *Premisa clave de HORSE*: **Una máquina con mucho tiempo de parada no es necesariamente la culpable**. La máquina penalizante es aquella que genera paradas inducidas en las demás (alto TAP propio y bajo TAI inducido, provocando SAT aguas arriba y DES aguas abajo).

2. **Referencias Oficiales de Producción de HORSE**:
   - **Tiempo de Ciclo Máximo ($Tcy_{max}$)**: $\\le 80 \\text{ cmin}$ ($1 \\text{ cmin} = 0.6 \\text{ s} \\implies 80 \\text{ cmin} = 48 \\text{ s}$).
   - **Disponibilidad Propia Mínima ($Dp_{min}$)**: $\\ge 90\\%$. Representa la fracción de tiempo productivo del tiempo atribuible a la máquina:
     $$Dp = \\frac{TBF}{TBF + TAP} \\times 100\\%$$
   - **Frecuencia de Paradas ($Fpm$)**: Número de paradas propias por cada 1.000 piezas:
     $$Fpm = \\frac{NAP}{NPR} \\times 1000$$

3. **Arquitectura Especial y Peculiaridades de la Línea 5**:
   - **Puestos en paralelo**: `ST2376` (Orden 72) y `ST-2375` (Orden 74). Cada una produce ~la mitad de las piezas de la línea (~750 vs ~1500), por lo que su ritmo conjunto cumple el ciclo de la línea.
   - **Anomalías de sensor vs cuellos de botella mecánicos**: `ST2235` (Orden 61) acumula >22.000 paradas/día y 14 h de TAP registrado, pero la línea produce 1.500 motores con normalidad. Esto evidencia un sensor chattering (rebote de señal de microparadas), no un cuello de botella físico.
   - **Contador de piezas descalibrado**: `ST-0295` (Orden 25) con solo ~2.5 piezas/día mientras produce 19 h.

---
### Estructura de este Notebook:
1. **Preparación y Carga de Datos Limpios**
2. **Cálculo de Indicadores Oficiales (KPIs de HORSE: Dp, Tcy, Fpm, MTBF, MTTR)**
3. **Análisis de Cumplimiento (Semáforo de Producción)**
4. **Matriz de Culpabilidad LOSSIA: Parada Propia ($TAP$) vs Inducida ($TAI$)**
5. **Topología de Línea y Propagación de Ondas (Efecto SAT/DES)**
6. **Algoritmo del Índice de Penalización LOSSIA (IPL)**
7. **Fichas Explicables para Jefe de Unidad y Mantenimiento**
8. **Exportación de Resultados para la Solución Tecnológica**"""))

# ==================== CELDA 2 ====================
cells.append(make_cell("code", """from pathlib import Path
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

pd.set_option("display.max_columns", 40)
pd.set_option("display.width", 200)

ENTRADA = Path("Datos_limpios")
SALIDA = Path("Datos_limpios")

# Configuración estética profesional
sns.set_theme(style="whitegrid", font_scale=0.95)
plt.rcParams["figure.dpi"] = 110
plt.rcParams["font.sans-serif"] = "DejaVu Sans"

# Constantes de negocio oficiales de HORSE
DP_MIN_HORSE = 90.0        # Disponibilidad mínima (%)
TCY_MAX_HORSE = 80.0       # Tiempo de ciclo máximo (cmin)
T_ABIERTO_DIA = 22.0       # Horas abiertas por día productivo

COLORES = {
    "TBF": "#2A9D8F",             # Verde producción
    "TAP": "#E76F51",             # Rojo parada propia
    "DES": "#E9C46A",             # Amarillo desabastecimiento
    "SAT": "#264653",             # Azul petróleo saturación
    "Penalizante": "#D62828",     # Rojo intenso
    "Victima": "#F77F00",         # Naranja
    "Robusta": "#06D6A0",         # Verde agua
    "Sensor_Anomalo": "#9D4EDD"   # Morado
}
print("Configuración y librerías cargadas con éxito.")"""))

# ==================== CELDA 3 ====================
cells.append(make_cell("markdown", """## 1. Carga de Datos Limpios y Filtrado
Cargamos los datos generados en la fase de limpieza (`datos_limpios.csv` y `config_limpia.csv`). Seleccionamos las operaciones marcadas para análisis (`incluir_analisis == True`)."""))

# ==================== CELDA 4 ====================
cells.append(make_cell("code", """df = pd.read_csv(ENTRADA / "datos_limpios.csv")
cfg = pd.read_csv(ENTRADA / "config_limpia.csv")

print(f"Dataset limpio: {df.shape[0]} registros ({df[['Week', 'Jour']].drop_duplicates().shape[0]} días productivos)")
print(f"Total operaciones en línea: {len(cfg)} | Operaciones aptas para análisis: {cfg.incluir_analisis.sum()}")

# Filtrar operaciones válidas
df_valid = df[df.incluir_analisis == True].copy()
df_valid.head(3)"""))

# ==================== CELDA 5 ====================
cells.append(make_cell("markdown", """## 2. Cálculo de los Indicadores Oficiales de HORSE

Implementamos las definiciones de ingeniería de HORSE:
- **Disponibilidad Propia ($Dp$)**:
  $$Dp = \\frac{TBF}{TBF + TAP} \\times 100\\%$$
- **Tiempo de Ciclo Real ($Tcy$)**:
  $$Tcy = \\frac{TBF \\times 6000}{NPR} \\quad (\\text{en centésimas de minuto})$$
  *Ajuste para estaciones en paralelo*: `ST2376` y `ST-2375` trabajan en paralelo repartiéndose la producción. Para el flujo de la línea, su tiempo de ciclo equivalente es la mitad del individual.
- **Frecuencia de Averías ($Fpm$)**:
  $$Fpm = \\frac{NAP}{NPR} \\times 1000$$
- **MTBF (Tiempo Medio Entre Fallos)** y **MTTR (Tiempo Medio de Reparación)**:
  $$MTBF = \\frac{TBF}{NAP} \\quad [\\text{horas/fallo}], \\qquad MTTR = \\frac{TAP \\times 60}{NAP} \\quad [\\text{minutos/fallo}]$$"""))

# ==================== CELDA 6 ====================
cells.append(make_cell("code", """# Ajuste de estaciones en paralelo para el tiempo de ciclo
df_valid["es_paralelo"] = df_valid["Operacion"].isin(["ST2376", "ST-2375"])

# Tiempo de ciclo individual (cmin)
df_valid["Tcy_unitario_cmin"] = (df_valid["TBF"] * 6000.0) / df_valid["NPR"].replace(0, np.nan)

# Tiempo de ciclo equivalente para la línea
df_valid["Tcy_linea_cmin"] = np.where(
    df_valid["es_paralelo"],
    df_valid["Tcy_unitario_cmin"] / 2.0,
    df_valid["Tcy_unitario_cmin"]
)

# Resumen promedio por operación a lo largo de los días productivos
ops = df_valid.groupby(["Orden_OP", "Operacion", "Operacion_norm", "Tipo"]).agg({
    "TBF": "mean",
    "TAP": "mean",
    "DES": "mean",
    "SAT": "mean",
    "TAI": "mean",
    "T_no_registrado": "mean",
    "NAP": "mean",
    "NPR": "mean",
    "Tcy_linea_cmin": "mean",
    "flag_tap_sospechoso": "sum",
    "flag_npr_invalido": "sum"
}).reset_index().sort_values("Orden_OP")

# KPIs agregados
ops["Dp"] = 100.0 * ops["TBF"] / (ops["TBF"] + ops["TAP"])
ops["Fpm"] = (ops["NAP"] / ops["NPR"].replace(0, np.nan)) * 1000.0
ops["MTBF_h"] = ops["TBF"] / ops["NAP"].replace(0, np.nan)
ops["MTTR_min"] = (ops["TAP"] * 60.0) / ops["NAP"].replace(0, np.nan)

# Ratio de Culpabilidad Propia: qué fracción del tiempo de parada se debe a sí misma
ops["Ratio_Culpa"] = ops["TAP"] / (ops["TAP"] + ops["TAI"] + 1e-6)

# Detección de anomalías de instrumentación (señales erráticas / chattering)
ops["es_anomalia_sensor"] = ops["flag_tap_sospechoso"] >= 8

print("KPIs calculados para todas las operaciones.")
ops[["Orden_OP", "Operacion", "Tipo", "TAP", "TAI", "Dp", "Tcy_linea_cmin", "Fpm"]].head()"""))

# ==================== CELDA 7 ====================
cells.append(make_cell("markdown", """## 3. Semáforo de Cumplimiento de Estándares de HORSE

Comparamos las 85 operaciones analizadas contra los dos límites contractuales de HORSE:
1. $Dp \\ge 90\\%$
2. $Tcy \\le 80$ cmin"""))

# ==================== CELDA 8 ====================
cells.append(make_cell("code", """fig, axes = plt.subplots(1, 2, figsize=(15, 5))

# 1. Disponibilidad Propia (Dp)
sns.histplot(ops[~ops.es_anomalia_sensor]["Dp"], bins=25, kde=True, color="#2A9D8F", ax=axes[0])
axes[0].axvline(DP_MIN_HORSE, color="#D62828", linestyle="--", linewidth=2, label=f"Objetivo HORSE ({DP_MIN_HORSE}%)")
axes[0].set_title("Distribución de Disponibilidad Propia ($Dp$)", fontsize=13, weight="bold")
axes[0].set_xlabel("Disponibilidad Propia (%)")
axes[0].set_ylabel("Número de Operaciones")
axes[0].legend()

# 2. Tiempo de Ciclo de Línea (Tcy)
valid_tcy = ops[(ops.flag_npr_invalido == 0) & ops.Tcy_linea_cmin.notna()]["Tcy_linea_cmin"]
sns.histplot(valid_tcy, bins=25, kde=True, color="#264653", ax=axes[1])
axes[1].axvline(TCY_MAX_HORSE, color="#D62828", linestyle="--", linewidth=2, label=f"Límite HORSE ({TCY_MAX_HORSE} cmin)")
axes[1].set_title("Distribución de Tiempo de Ciclo ($Tcy$)", fontsize=13, weight="bold")
axes[1].set_xlabel("Tiempo de Ciclo Equivalente (cmin)")
axes[1].set_ylabel("Número de Operaciones")
axes[1].legend()

plt.tight_layout()
plt.show()

# Operaciones que incumplen Disponibilidad Propia (< 90%)
incumple_dp = ops[ops.Dp < DP_MIN_HORSE].sort_values("Dp")
print(f"\\n⚠️ Operaciones que INCUMPLEN Disponibilidad Propia (Dp < 90%): {len(incumple_dp)}")
display(incumple_dp[["Orden_OP", "Operacion", "Tipo", "Dp", "TAP", "TAI", "Fpm", "es_anomalia_sensor"]])"""))

# ==================== CELDA 9 ====================
cells.append(make_cell("markdown", """## 4. Desacoplamiento Clave: Parada Propia ($TAP$) vs Parada Inducida ($TAI$)
### Matriz de Culpabilidad LOSSIA

El reto de HORSE establece un principio fundamental:
> *No toda parada es igual. Una máquina que está parada muchas horas puede ser simplemente una víctima de que otra se paró antes (desabastecimiento) o después (saturación).*

Representamos en un plano bidimensional:
- **Eje X: Parada Propia ($TAP$)** en horas/día.
- **Eje Y: Parada Inducida ($TAI = DES + SAT$)** en horas/día.

Esto define cuatro cuadrantes claros:
1. **Penalizante Crítica (Zona Roja)**: Alto TAP, Bajo TAI. La máquina falla sola y arrastra a las demás.
2. **Víctima de Línea (Zona Naranja)**: Bajo TAP, Alto TAI. La máquina funciona bien, pero sufre por averías ajenas.
3. **Robusta / Equilibrada (Zona Verde)**: Bajo TAP, Bajo TAI. Máquinas estables.
4. **Anomalía de Señal / Mantenimiento Especial (Zona Morada)**: Registros atípicos (como ST2235)."""))

# ==================== CELDA 10 ====================
cells.append(make_cell("code", """plt.figure(figsize=(12, 7))

# Filtrar para visualización
ops_plot = ops.copy()

# Asignar categoría visual
def categorizar(row):
    if row["es_anomalia_sensor"]:
        return "Sensor Anómalo"
    elif row["TAP"] >= 1.5 and row["Ratio_Culpa"] >= 0.5:
        return "Penalizante Crítica"
    elif row["TAI"] >= 3.0 and row["Ratio_Culpa"] < 0.4:
        return "Víctima de Línea"
    else:
        return "Robusta / Normal"

ops_plot["Categoria"] = ops_plot.apply(categorizar, axis=1)
colores_cat = {
    "Penalizante Crítica": "#D62828",
    "Víctima de Línea": "#F77F00",
    "Robusta / Normal": "#2A9D8F",
    "Sensor Anómalo": "#9D4EDD"
}

# Scatter plot
sns.scatterplot(
    data=ops_plot,
    x="TAP", y="TAI",
    hue="Categoria",
    palette=colores_cat,
    s=120, alpha=0.85,
    style="Tipo"
)

# Líneas guía de cuadrante
plt.axvline(1.5, color="gray", linestyle=":", alpha=0.6)
plt.axhline(3.0, color="gray", linestyle=":", alpha=0.6)

# Etiquetas para máquinas clave
etiquetas = ["ST-2390", "PM2250", "ST_0100", "ST0259", "ST-0270", "ST-0260", "ManutPul", "ST_3300", "ST2235", "Ma_BM2_2"]
for _, r in ops_plot.iterrows():
    if r["Operacion"] in etiquetas:
        plt.annotate(
            r["Operacion"],
            (r["TAP"], r["TAI"]),
            textcoords="offset points",
            xytext=(6, 5),
            fontsize=9.5,
            weight="bold",
            color="#1D3557"
        )

plt.title("Matriz de Culpabilidad LOSSIA: Parada Propia (TAP) vs Parada Inducida (TAI)", fontsize=14, weight="bold")
plt.xlabel("Parada Propia Promedio (TAP, horas/día) → CULPABILIDAD INTRÍNSECA", fontsize=11, weight="bold")
plt.ylabel("Parada Inducida Promedio (TAI = DES + SAT, horas/día) → AFECTACIÓN AJENA", fontsize=11, weight="bold")
plt.xlim(-0.2, 15)
plt.ylim(-0.2, 9)
plt.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
plt.tight_layout()
plt.show()"""))

# ==================== CELDA 11 ====================
cells.append(make_cell("markdown", """## 5. Topología de Línea: Propagación de Saturación y Desabastecimiento

En una línea de montaje secuencial:
- Cuando una máquina se detiene ($TAP$), **bloquea a las precedentes** $\\rightarrow$ La saturación ($SAT$) sube aguas arriba.
- Y **deja sin piezas a las siguientes** $\\rightarrow$ El desabastecimiento ($DES$) sube aguas abajo.

Por tanto, un cuello de botella sistémico deja una **firma geométrica inconfundible**:
$$\\text{Pico de } SAT \\implies [ \\text{CUELLO DE BOTELLA} ] \\implies \\text{Pico de } DES$$"""))

# ==================== CELDA 12 ====================
cells.append(make_cell("code", """fig, ax = plt.subplots(figsize=(17, 6))

ordenes = ops["Orden_OP"].values
tbf = ops["TBF"].values
tap = ops["TAP"].values
des = ops["DES"].values
sat = ops["SAT"].values

# Barras apiladas
ax.bar(ordenes, tbf, label="TBF (Produciendo)", color=COLORES["TBF"], alpha=0.85, width=0.8)
ax.bar(ordenes, des, bottom=tbf, label="DES (Desabastecida)", color=COLORES["DES"], alpha=0.85, width=0.8)
ax.bar(ordenes, sat, bottom=tbf + des, label="SAT (Saturada)", color=COLORES["SAT"], alpha=0.85, width=0.8)
ax.bar(ordenes, tap, bottom=tbf + des + sat, label="TAP (Parada Propia)", color=COLORES["TAP"], alpha=0.85, width=0.8)

# Marcar cuellos de botella destacados
ax.annotate("ST-0259/0260\\n(Gran Bloqueo SAT)", xy=(19, 21), xytext=(12, 23.5),
            arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=6),
            weight="bold", fontsize=9.5)

ax.annotate("ST-2390\\n(Mayor TAP de Línea)", xy=(75, 21), xytext=(68, 23.5),
            arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=6),
            weight="bold", fontsize=9.5)

ax.set_title("Firma de Estados a lo largo de la Línea 5 (Orden de Operación 1 a 91)", fontsize=14, weight="bold")
ax.set_xlabel("Orden de Operación en Línea 5", fontsize=11, weight="bold")
ax.set_ylabel("Horas del Día Productivo (base 22 h)", fontsize=11, weight="bold")
ax.set_xlim(0, 92)
ax.set_ylim(0, 25)
ax.legend(loc="upper right", ncol=4)
plt.tight_layout()
plt.show()"""))

# ==================== CELDA 13 ====================
cells.append(make_cell("markdown", """## 6. Algoritmo del Índice de Penalización LOSSIA (IPL)

Para unificar todos los factores en una métrica única (0 a 100) que una persona experta y una no experta puedan interpretar igual:

$$\\text{IPL} = 100 \\times \\left( w_1 \\cdot \\text{Norm}(TAP) + w_2 \\cdot \\text{RatioCulpa} + w_3 \\cdot \\text{Norm}(ImpactoVecinas) + w_4 \\cdot \\text{Penalización}_{Dp} \\right)$$

Donde:
1. **$TAP$**: Duración de las averías propias directas ($w_1 = 0.35$).
2. **$\\text{RatioCulpa} = \\frac{TAP}{TAP + TAI}$**: Responsabilidad intrínseca vs inducida ($w_2 = 0.25$).
3. **$ImpactoVecinas = SAT_{i-1} + DES_{i+1}$**: Grado de contagio hacia las máquinas adyacentes ($w_3 = 0.25$).
4. **$\\text{Penalización}_{Dp} = \\max(0, 1 - Dp / 90)$**: Grado de violación de la disponibilidad contractual ($w_4 = 0.15$).
5. **Aislamiento de Sensores**: Las operaciones con señales erráticas (como `ST2235`) se segregan a una categoría específica para evitar intervenciones mecánicas innecesarias."""))

# ==================== CELDA 14 ====================
cells.append(make_cell("code", """# Cálculo de propagación en vecinas (ordenadas estrictamente por Orden_OP)
ops = ops.sort_values("Orden_OP").reset_index(drop=True)
ops["SAT_anterior"] = ops["SAT"].shift(1).fillna(0)
ops["DES_siguiente"] = ops["DES"].shift(-1).fillna(0)
ops["Impacto_Vecinas"] = ops["SAT_anterior"] + ops["DES_siguiente"]

# Función de normalización min-max
def min_max(s):
    return (s - s.min()) / (s.max() - s.min() + 1e-6)

# Cálculo del IPL
res = ops.copy()
res["penalizacion_dp"] = np.maximum(0, (DP_MIN_HORSE - res["Dp"]) / DP_MIN_HORSE)

# Ponderación
res["IPL_crudo"] = (
    0.35 * min_max(res["TAP"]) +
    0.25 * res["Ratio_Culpa"] +
    0.25 * min_max(res["Impacto_Vecinas"]) +
    0.15 * res["penalizacion_dp"]
)

# Normalizar de 0 a 100
res["IPL"] = 100.0 * min_max(res["IPL_crudo"])

# Clasificación final
def clasificar_final(r):
    if r["es_anomalia_sensor"]:
        return "Anomalía Eléctrica / Sensor"
    elif r["IPL"] >= 60.0:
        return "Penalizante Muy Alta"
    elif r["IPL"] >= 40.0:
        return "Penalizante Moderada"
    elif r["TAI"] >= 3.0:
        return "Víctima de Línea"
    else:
        return "Operación Estable"

res["Diagnostico_Tipo"] = res.apply(clasificar_final, axis=1)

# Ranking oficial (excluyendo anomalías de sensor para la lista mecánica principal)
ranking_mecanico = res[~res.es_anomalia_sensor].sort_values("IPL", ascending=False).reset_index(drop=True)

print("🏆 TOP 10 MÁQUINAS PENALIZANTES SEGÚN EL ÍNDICE LOSSIA (IPL):")
display(ranking_mecanico[[
    "Orden_OP", "Operacion", "Tipo", "IPL", "TAP", "TAI", "Dp", "Tcy_linea_cmin", "Fpm", "Impacto_Vecinas", "Diagnostico_Tipo"
]].head(10).round(2))"""))

# ==================== CELDA 14B: GRÁFICO DEL CUELLO DE BOTELLA MEDIO ====================
cells.append(make_cell("markdown", """### Perfil del Cuello de Botella Medio a lo largo de la Cadena de Montaje
Visualizamos la distribución longitudinal de la criticidad a lo largo del flujo (Orden 1 a 91):
1. **Curva superior**: Índice de Penalización LOSSIA (IPL) de cada puesto y la **curva del Cuello de Botella Medio** (media móvil ponderada por tramos de la cadena).
2. **Curva inferior**: Mecánica física del atasco, mostrando el cruce entre **Saturación aguas arriba ($SAT$)**, **Desabastecimiento aguas abajo ($DES$)** y **Parada Propia ($TAP$)**."""))

cells.append(make_cell("code", """fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 9), sharex=True, gridspec_kw={"height_ratios": [1.2, 1]})

df_plot = res.sort_values("Orden_OP").reset_index(drop=True)
ordenes = df_plot["Orden_OP"].values
ipl_vals = df_plot["IPL"].values

# Excluir anomalías extremas de sensor para la media móvil
ipl_para_tendencia = df_plot["IPL"].copy()
if df_plot["es_anomalia_sensor"].any():
    ipl_para_tendencia[df_plot["es_anomalia_sensor"]] = np.nan
ipl_media_movil = ipl_para_tendencia.rolling(window=5, center=True, min_periods=1).mean()

# Panel 1: IPL y Cuello de Botella Medio
ax1.fill_between(ordenes, 0, ipl_vals, color="#E63946", alpha=0.18, label="IPL por Puesto (Criticidad)")
ax1.plot(ordenes, ipl_vals, color="#E63946", alpha=0.45, linewidth=1.2, linestyle=":")
ax1.plot(ordenes, ipl_media_movil, color="#9B2226", linewidth=2.8, label="Cuello de Botella Medio (Media Móvil 5 puestos)")
ax1.axhline(60, color="#D62828", linestyle="--", linewidth=1.5, alpha=0.7, label="Umbral Crítico (IPL ≥ 60)")
ax1.axhline(40, color="#F77F00", linestyle="--", linewidth=1.5, alpha=0.7, label="Umbral Moderado (IPL ≥ 40)")

# Puntos destacados
puntos_destacados = ["ST-0260", "PM2250", "ST-2390", "Ma_BM2_2"]
for op_name in puntos_destacados:
    r_pt = df_plot[df_plot.Operacion == op_name]
    if not r_pt.empty:
        x_pt = r_pt["Orden_OP"].values[0]
        y_pt = r_pt["IPL"].values[0]
        ax1.scatter(x_pt, y_pt, color="#9B2226", s=90, zorder=5, edgecolor="white", linewidth=1.5)
        offset_y = 12 if y_pt < 70 else -18
        ax1.annotate(
            f"{op_name}\\n[{y_pt:.1f} pts]",
            xy=(x_pt, y_pt), xytext=(x_pt, y_pt + offset_y),
            ha="center", fontsize=8.5, weight="bold", color="#1B263B",
            arrowprops=dict(arrowstyle="->", color="#1B263B", lw=1.2),
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#FFF8E7", edgecolor="#D4A373", alpha=0.9)
        )

ax1.set_title("A. Cuello de Botella Medio y Criticidad a lo largo de la Cadena de Montaje (Línea 5)", fontsize=13, weight="bold")
ax1.set_ylabel("Índice LOSSIA (IPL)", fontsize=10, weight="bold")
ax1.set_ylim(-2, 105)
ax1.legend(loc="upper left", frameon=True, fontsize=8.5)

# Panel 2: Mecánica de flujo (SAT vs TAP vs DES)
ax2.bar(ordenes, df_plot["TAP"], width=0.8, color="#D62828", alpha=0.5, label="Parada Propia (TAP, h/día)", zorder=2)
ax2.plot(ordenes, df_plot["SAT"], color="#1D3557", linewidth=2.2, label="Saturación (SAT, horas atascada)", zorder=3)
ax2.plot(ordenes, df_plot["DES"], color="#E9C46A", linewidth=2.2, label="Desabastecimiento (DES, horas sin piezas)", zorder=3)

ax2.set_title("B. Mecánica del Atasco: Saturación aguas arriba (SAT) vs Desabastecimiento aguas abajo (DES)", fontsize=13, weight="bold")
ax2.set_xlabel("Orden Secuencial de Operación a lo largo de la Cadena de Montaje", fontsize=10, weight="bold")
ax2.set_ylabel("Horas del Día Productivo (base 22 h)", fontsize=10, weight="bold")
ax2.set_xlim(ordenes.min() - 1, ordenes.max() + 1)
ax2.legend(loc="upper left", frameon=True, fontsize=8.5)

plt.tight_layout()
plt.show()"""))

# ==================== CELDA 15 ====================
cells.append(make_cell("markdown", """## 7. Fichas de Diagnóstico Explicable para el Jefe de Unidad y Mantenimiento

La clave del hackathon es que la solución sea **fácilmente interpretable** tanto por ingenieros veteranos como por personal de planta sin conocimientos estadísticos. Generamos diagnósticos automatizados en lenguaje natural."""))

# ==================== CELDA 16 ====================
cells.append(make_cell("code", """def generar_ficha(row):
    op = row["Operacion"]
    orden = int(row["Orden_OP"])
    tipo = row["Tipo"]
    ipl = row["IPL"]
    dp = row["Dp"]
    tap = row["TAP"]
    tai = row["TAI"]
    fpm = row["Fpm"]
    tcy = row["Tcy_linea_cmin"]
    diag = row["Diagnostico_Tipo"]
    
    texto = [
        f"=======================================================================",
        f"FICHA DIAGNÓSTICA · OPERACIÓN: {op} (Puesto #{orden} - {tipo})",
        f"=======================================================================",
        f"• Índice de Penalización LOSSIA (IPL): {ipl:.1f}/100 → Clasificación: {diag.upper()}",
        f"• Disponibilidad Propia (Dp): {dp:.1f}% {'❌ [INCUMPLE < 90%]' if dp < 90 else '✅ [CUMPLE]'}",
        f"• Tiempo de Ciclo Línea (Tcy): {tcy:.1f} cmin {'❌ [INCUMPLE > 80 cmin]' if tcy > 80 else '✅ [CUMPLE]'}",
        f"• Balance de Parada: TAP Propia = {tap:.2f} h/día | TAI Inducida = {tai:.2f} h/día",
        f"• Frecuencia de Averías: {fpm:.1f} paradas cada 1.000 piezas (MTTR: {row['MTTR_min']:.1f} min)",
        f"-----------------------------------------------------------------------",
        f"EXPLICACIÓN PARA EL JEFE DE UNIDAD Y MANTENIMIENTO:"
    ]
    
    if row["es_anomalia_sensor"]:
        texto.append("⚠️ DIAGNÓSTICO: ANOMALÍA INSTRUMENTAL. Registra un número exorbitante de paradas (>20.000/día)")
        texto.append("   sin que la producción de motores se detenga. NO enviar mecánicos a desmontar la máquina;")
        texto.append("   revisar contacto del final de carrera, fotocélula o tarjeta PLC por rebote de señal (chattering).")
    elif op == "ST-2390":
        texto.append("🚨 DIAGNÓSTICO: CUELLO DE BOTELLA MECÁNICO NÚMERO 1 DE LA PLANTA.")
        texto.append("   Pierde más de 4.2 horas diarias en parada propia (Dp de solo 77.3%), sufriendo 600 microparadas.")
        texto.append("   Esto provoca más de 3.2 horas de desabastecimiento inmediato a ST-2400 y ST_2410.")
        texto.append("   ACCIÓN RECOMENDADA: Prioridad máxima en mantenimiento preventivo y revisión de utillaje.")
    elif op == "PM2250":
        texto.append("⚠️ DIAGNÓSTICO: CUELLO DE BOTELLA EN PUESTO MANUAL.")
        texto.append("   Disponibilidad de 85.0% (<90%). No tiene muchas paradas (NAP bajo), pero son de larga duración.")
        texto.append("   ACCIÓN RECOMENDADA: Revisión ergonómica del puesto, equilibrado de tiempos o apoyo temporal.")
    elif op in ["ST0259", "ST-0260", "ST-0270"]:
        texto.append("⚠️ DIAGNÓSTICO: PUNTO CRÍTICO DE BALANCEO DE FLUJO.")
        texto.append(f"   La zona sufre un gradiente extremo de saturación aguas arriba ({row['SAT']:.1f} h) y desabastecimiento.")
        texto.append("   ACCIÓN RECOMENDADA: Revisar capacidad de pulmones (buffers) intermedios y transfer.")
    else:
        texto.append(f"ℹ️ DIAGNÓSTICO: {diag}. Impacto moderado en la línea.")
        
    texto.append("=======================================================================\\n")
    return "\\n".join(texto)

# Imprimir fichas de las 4 operaciones más representativas
casos = ["ST-2390", "PM2250", "ST-0260", "ST2235"]
for c in casos:
    r = res[res.Operacion == c].iloc[0]
    print(generar_ficha(r))"""))

# ==================== CELDA 17 ====================
cells.append(make_cell("markdown", """## 8. Exportación de Resultados
Guardamos la tabla completa con todos los KPIs, el IPL y los diagnósticos en `Datos_limpios/analisis_penalizantes.csv`. Este fichero alimentará la herramienta interactiva de visualización (Solución Tecnológica de HORSE)."""))

# ==================== CELDA 18 ====================
cells.append(make_cell("code", """res.to_csv(SALIDA / "analisis_penalizantes.csv", index=False)
print(f"Resultados exportados con éxito a: {(SALIDA / 'analisis_penalizantes.csv').resolve()}")
print("Total de operaciones analizadas y clasificadas:", len(res))"""))

# Crear notebook
nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.11.5"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

salida_nb = Path("02_analisis_penalizantes.ipynb")
with open(salida_nb, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"Notebook creado exitosamente: {salida_nb.resolve()} ({len(cells)} celdas)")
