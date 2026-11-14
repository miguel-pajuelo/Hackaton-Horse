"""
generar_grafico_cuello_botella.py
=================================
Genera el gráfico longitudinal de cuellos de botella medios a lo largo de la cadena de montaje.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from pathlib import Path

# Cargar dataset de análisis
df = pd.read_csv("Datos_limpios/analisis_penalizantes.csv")
df = df.sort_values("Orden_OP").reset_index(drop=True)

# Configuración estética
sns.set_theme(style="whitegrid", font_scale=0.95)
plt.rcParams["figure.dpi"] = 140
plt.rcParams["font.sans-serif"] = "DejaVu Sans"

# Crear figura con 2 subplots verticales compartiendo eje X
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), sharex=True, gridspec_kw={"height_ratios": [1.2, 1]})

ordenes = df["Orden_OP"].values
ipl = df["IPL"].values
tap = df["TAP"].values
sat = df["SAT"].values
des = df["DES"].values

# Excluir anomalías extremas de sensor para la media móvil (como ST2235) para que no distorsione la curva media
ipl_para_tendencia = df["IPL"].copy()
if (df["es_anomalia_sensor"]).any():
    ipl_para_tendencia[df["es_anomalia_sensor"]] = np.nan

# Media móvil (ventana de 5 estaciones) para representar el "cuello de botella medio" por tramos de la cadena
ipl_media_movil = ipl_para_tendencia.rolling(window=5, center=True, min_periods=1).mean()

# =========================================================================
# PANEL 1: ÍNDICE DE PENALIZACIÓN LOSSIA (IPL) Y CUELLO DE BOTELLA MEDIO
# =========================================================================
# Área sombreada de criticidad
ax1.fill_between(ordenes, 0, ipl, color="#E63946", alpha=0.18, label="IPL por Estación (Criticidad)")
ax1.plot(ordenes, ipl, color="#E63946", alpha=0.45, linewidth=1.2, linestyle=":")

# Curva de Cuello de Botella Medio (Tendencia por sector)
ax1.plot(ordenes, ipl_media_movil, color="#9B2226", linewidth=2.8, label="Cuello de Botella Medio (Media Móvil 5 estaciones)")

# Líneas guía de umbrales
ax1.axhline(60, color="#D62828", linestyle="--", linewidth=1.5, alpha=0.7, label="Umbral Crítico (IPL ≥ 60)")
ax1.axhline(40, color="#F77F00", linestyle="--", linewidth=1.5, alpha=0.7, label="Umbral Moderado (IPL ≥ 40)")

# Puntos destacados
puntos_clave = {
    "ST-0260\n(Embudo SAT/DES)": (20, df.loc[df.Operacion == "ST-0260", "IPL"].values[0]),
    "PM2250\n(Cuello Manual)": (63, df.loc[df.Operacion == "PM2250", "IPL"].values[0]),
    "ST-2390\n(Cuello Mecánico Nº1)": (75, df.loc[df.Operacion == "ST-2390", "IPL"].values[0]),
    "Ma_BM2_2\n(Manutención final)": (88, df.loc[df.Operacion == "Ma_BM2_2", "IPL"].values[0])
}

for etiqueta, (x, y) in puntos_clave.items():
    ax1.scatter(x, y, color="#9B2226", s=90, zorder=5, edgecolor="white", linewidth=1.5)
    offset_y = 12 if y < 70 else -18
    ax1.annotate(
        f"{etiqueta}\n[{y:.1f} pts]",
        xy=(x, y),
        xytext=(x, y + offset_y),
        ha="center",
        fontsize=8.5,
        weight="bold",
        color="#1B263B",
        arrowprops=dict(arrowstyle="->", color="#1B263B", lw=1.2),
        bbox=dict(boxstyle="round,pad=0.2", facecolor="#FFF8E7", edgecolor="#D4A373", alpha=0.9)
    )

ax1.set_title("A. Perfil del Cuello de Botella Medio a lo largo de la Cadena de Montaje (Índice LOSSIA IPL)", fontsize=13, weight="bold")
ax1.set_ylabel("Índice de Penalización (0 a 100)", fontsize=10, weight="bold")
ax1.set_ylim(-2, 105)
ax1.legend(loc="upper left", frameon=True, fontsize=8.5)

# =========================================================================
# PANEL 2: MECÁNICA DE LÍNEA - CRUCE DE SATURACIÓN (SAT), DESABASTECIMIENTO (DES) Y TAP
# =========================================================================
# Barras de Parada Propia (TAP)
ax2.bar(ordenes, tap, width=0.8, color="#D62828", alpha=0.5, label="Parada Propia (TAP, h/día)", zorder=2)

# Curvas de SAT (aguas arriba) y DES (aguas abajo)
ax2.plot(ordenes, sat, color="#1D3557", linewidth=2.2, label="Saturación (SAT, horas bloqueada por la siguiente)", zorder=3)
ax2.plot(ordenes, des, color="#E9C46A", linewidth=2.2, label="Desabastecimiento (DES, horas sin piezas)", zorder=3)

# Suavizado de desabastecimiento medio
des_media = pd.Series(des).rolling(5, center=True, min_periods=1).mean()
ax2.plot(ordenes, des_media, color="#B08900", linestyle="--", linewidth=1.5, alpha=0.8, label="Desabastecimiento Medio del Tramo")

ax2.set_title("B. Mecánica del Atasco: Saturación aguas arriba (SAT) vs Desabastecimiento aguas abajo (DES)", fontsize=13, weight="bold")
ax2.set_xlabel("Orden Secuencial de Operación a lo largo de la Cadena de Montaje (1 a 91)", fontsize=10, weight="bold")
ax2.set_ylabel("Horas del Día Productivo (base 22 h)", fontsize=10, weight="bold")
ax2.set_xlim(0, 93)
ax2.set_ylim(0, 11)
ax2.legend(loc="upper left", frameon=True, fontsize=8.5)

# Marcar las 4 zonas industriales clave
zonas = [
    (1, 15, "Sector 1: Entrada y Subconjuntos", "#E0F2FE"),
    (16, 35, "Sector 2: Bloqueo Central (ST0259/0260)", "#FEE2E2"),
    (36, 70, "Sector 3: Montaje Intermedio y Manual", "#FEF3C7"),
    (71, 91, "Sector 4: Cuello Mecánico Crítico (ST-2390)", "#FEE2E2")
]

for x_ini, x_fin, nombre_zona, color_fondo in zonas:
    ax1.axvspan(x_ini - 0.5, x_fin + 0.5, color=color_fondo, alpha=0.25, zorder=0)
    ax2.axvspan(x_ini - 0.5, x_fin + 0.5, color=color_fondo, alpha=0.25, zorder=0)
    ax1.text((x_ini + x_fin)/2, 98, nombre_zona, ha="center", fontsize=8, style="italic", color="#475569")

plt.tight_layout()

# Guardar figura
salida_img = Path("cuello_botella_cadena_montaje.png")
plt.savefig(salida_img, dpi=180, bbox_inches="tight")
print(f"Gráfico guardado con éxito en: {salida_img.resolve()}")
