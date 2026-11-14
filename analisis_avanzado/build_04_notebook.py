"""
Generador del notebook 04_analisis_cuellos_botella_generico.ipynb
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
cells.append(make_cell("markdown", """# 04 · Aplicación Genérica del Análisis de Cuellos de Botella
### Cómo aplicar `analisis_cuellos_botella.py` a cualquier dataset de fabricación

Este notebook demuestra cómo utilizar el módulo universal `analisis_cuellos_botella.py` sobre:
1. **El dataset real del Reto LOSSIA (HORSE Línea 5)**.
2. **Un dataset completamente nuevo y distinto** (con nombres de columna arbitrarios, diferentes turnos y umbrales).

---

### ¿Por qué este enfoque es genérico y extrapolable?
1. **Inferencia automática de columnas**: Detecta por sinónimos columnas como `TBF`/`uptime`, `TAP`/`downtime`, `DES`/`starvation`, `SAT`/`blocking`, etc.
2. **Detección automática de líneas en paralelo**: Identifica puestos contiguos que se reparten la cadencia (50% de volumen).
3. **Filtro de anomalías de sensor (chattering)**: Distingue averías mecánicas reales de falsos positivos en fotocélulas o finales de carrera.
4. **Parámetros de planta configurables**: Horas de turno (`t_abierto_dia`), disponibilidad objetivo (`dp_min_target`), tiempo de ciclo (`tcy_max_cmin`), y pesos del índice IPL."""))

# ==================== CELDA 2 ====================
cells.append(make_cell("code", """import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Importamos la clase principal de nuestro módulo genérico
from analisis_cuellos_botella import BottleneckAnalyzer

print("Módulo analisis_cuellos_botella importado correctamente.")"""))

# ==================== CELDA 3 ====================
cells.append(make_cell("markdown", """## Caso 1: Aplicación directa sobre los datos del Reto HORSE
Solo requerimos instanciar la clase y llamar a `fit_transform()`. El script resuelve automáticamente las columnas, agrupa los días y calcula el IPL."""))

# ==================== CELDA 4 ====================
cells.append(make_cell("code", """# 1. Cargar datos
df_horse = pd.read_csv("Datos_limpios/datos_limpios.csv")
cfg_horse = pd.read_csv("Datos_limpios/config_limpia.csv")

# 2. Inicializar analizador con los parámetros de la planta de Valladolid
analizador_horse = BottleneckAnalyzer(
    t_abierto_dia=22.0,      # 22 horas abiertas al día
    dp_min_target=90.0,      # Disponibilidad contractual ≥ 90%
    tcy_max_cmin=80.0,       # Tiempo de ciclo límite ≤ 80 cmin (48 s)
    auto_detect_parallel=True
)

# 3. Ejecutar análisis completo
resultados_horse = analizador_horse.fit_transform(df_horse, config_df=cfg_horse)

print(f"Análisis completado para {len(resultados_horse)} operaciones.")
display(analizador_horse.get_top_penalizantes(5))"""))

# ==================== CELDA 5 ====================
cells.append(make_cell("markdown", """### Visualización automática del informe HORSE y Cuello de Botella Medio"""))

# ==================== CELDA 6 ====================
cells.append(make_cell("code", """# Imprime el informe ejecutivo en texto plano listo para enviar a jefatura
print(analizador_horse.generar_informe_texto())

# 1. Panel general de tres cuadrantes
analizador_horse.plot_resumen()

# 2. Código autocontenido para graficar el Cuello de Botella Medio a lo largo de la cadena
df_plot = analizador_horse.results_df.sort_values("Orden_OP").reset_index(drop=True)
ordenes = df_plot["Orden_OP"].values
ipl_vals = df_plot["IPL"].values
tap = df_plot["TAP"].values
sat = df_plot["SAT"].values
des = df_plot["DES"].values

# Curva de cuello de botella medio (media móvil de 5 puestos)
ipl_para_tendencia = df_plot["IPL"].copy()
if df_plot["es_anomalia_sensor"].any():
    ipl_para_tendencia[df_plot["es_anomalia_sensor"]] = np.nan
ipl_media_movil = ipl_para_tendencia.rolling(window=5, center=True, min_periods=1).mean()

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), sharex=True, gridspec_kw={"height_ratios": [1.2, 1]})

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

ax1.set_title("A. Cuello de Botella Medio a lo largo de la Cadena de Montaje (Índice LOSSIA IPL)", fontsize=13, weight="bold")
ax1.set_ylabel("Índice LOSSIA (IPL)", fontsize=10, weight="bold")
ax1.set_ylim(-2, 105)
ax1.legend(loc="upper left", frameon=True, fontsize=8.5)

# Panel 2: Mecánica de Flujo (SAT vs TAP vs DES)
ax2.bar(ordenes, tap, width=0.8, color="#D62828", alpha=0.5, label="Parada Propia (TAP, h/día)", zorder=2)
ax2.plot(ordenes, sat, color="#1D3557", linewidth=2.2, label="Saturación (SAT, horas atascada)", zorder=3)
ax2.plot(ordenes, des, color="#E9C46A", linewidth=2.2, label="Desabastecimiento (DES, horas sin piezas)", zorder=3)
des_media = pd.Series(des).rolling(5, center=True, min_periods=1).mean()
ax2.plot(ordenes, des_media, color="#B08900", linestyle="--", linewidth=1.5, alpha=0.8, label="Desabastecimiento Medio del Tramo")

ax2.set_title("B. Mecánica del Atasco: Saturación aguas arriba (SAT) vs Desabastecimiento aguas abajo (DES)", fontsize=13, weight="bold")
ax2.set_xlabel("Orden Secuencial de Operación a lo largo de la Cadena de Montaje (1 a 91)", fontsize=10, weight="bold")
ax2.set_ylabel("Horas del Día Productivo (base 22 h)", fontsize=10, weight="bold")
ax2.set_xlim(ordenes.min() - 1, ordenes.max() + 1)
ax2.legend(loc="upper left", frameon=True, fontsize=8.5)

plt.tight_layout()
plt.savefig("cuello_botella_cadena_montaje.png", dpi=160, bbox_inches="tight")
plt.show()"""))

# ==================== CELDA 7 ====================
cells.append(make_cell("markdown", """---
## Caso 2: Aplicación sobre un Dataset Externo Arbitrario (Otra Línea / Otra Fábrica)

Imaginemos una línea de ensamblaje en otra planta con:
* **Turno de 8 horas** (`t_abierto_dia = 8.0`).
* **Columnas en inglés o con nombres no estándar**: `station_name`, `seq_order`, `uptime_hours`, `fault_hours`, `starve_hours`, `block_hours`, `fault_count`, `parts_produced`.
* **Objetivos más estrictos**: $Dp \ge 95\%$, $Tcy \le 60$ cmin.

Creamos un dataset sintético para verificar la adaptabilidad del script:"""))

# ==================== CELDA 8 ====================
cells.append(make_cell("code", """# Generamos datos sintéticos de una línea de 10 estaciones con nombres completamente distintos
np.random.seed(42)
estaciones = [f"EST_{i:02d}" for i in range(1, 11)]

datos_otra_planta = pd.DataFrame({
    "seq_order": range(1, 11),
    "station_name": estaciones,
    "uptime_hours": [6.8, 6.5, 6.2, 5.0, 6.7, 6.9, 4.2, 6.6, 6.8, 7.0],
    "fault_hours":  [0.2, 0.3, 0.4, 2.1, 0.2, 0.1, 2.9, 0.3, 0.2, 0.1],  # EST_04 y EST_07 fallan mucho
    "starve_hours": [0.1, 0.2, 0.3, 0.2, 0.6, 0.7, 0.3, 0.8, 0.7, 0.6],
    "block_hours":  [0.9, 1.0, 1.1, 0.7, 0.5, 0.3, 0.6, 0.3, 0.3, 0.3],  # Saturación acumulada antes de EST_04
    "fault_count":  [3, 5, 6, 25, 4, 2, 40, 5, 3, 2],
    "parts_produced": [480, 475, 470, 460, 465, 470, 450, 460, 465, 470]
})

print("Dataset de ejemplo de otra planta:")
display(datos_otra_planta.head(5))"""))

# ==================== CELDA 9 ====================
cells.append(make_cell("markdown", """### Ejecución del análisis sobre el nuevo dataset
Observa que **no cambiamos nada del código interno**: el analizador infiere automáticamente los nombres de columna o se le pasan explícitamente."""))

# ==================== CELDA 10 ====================
cells.append(make_cell("code", """# Inicializamos el analizador para el turno de 8 h y target de 95%
analizador_externo = BottleneckAnalyzer(
    col_op="station_name",
    col_orden="seq_order",
    col_tbf="uptime_hours",
    col_tap="fault_hours",
    col_des="starve_hours",
    col_sat="block_hours",
    col_nap="fault_count",
    col_npr="parts_produced",
    t_abierto_dia=8.0,       # Turno de 8 horas
    dp_min_target=95.0,      # Objetivo 95%
    tcy_max_cmin=65.0
)

# Ejecutar pipeline
resultados_externo = analizador_externo.fit_transform(datos_otra_planta)

print("Top cuellos de botella detectados en la nueva planta:")
display(analizador_externo.get_top_penalizantes(3))

# Generar informe textual
print(analizador_externo.generar_informe_texto())"""))

# ==================== CELDA 11 ====================
cells.append(make_cell("markdown", """### Visualización de la nueva planta"""))

# ==================== CELDA 12 ====================
cells.append(make_cell("code", """analizador_externo.plot_resumen()"""))

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

salida_nb = Path("04_analisis_cuellos_botella_generico.ipynb")
with open(salida_nb, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"Notebook creado exitosamente: {salida_nb.resolve()} ({len(cells)} celdas)")
