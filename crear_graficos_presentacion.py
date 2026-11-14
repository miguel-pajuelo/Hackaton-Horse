# crear_graficos_presentacion.py
"""
Genera gráficos de alta resolución con la estética exacta del dashboard de LOSSIA:
- Fondo crema / papel cálido: #F6F3EB
- Tarjetas redondeadas color marfil: #FCFAF6
- Tipografía serif: Georgia
- Azul tinta oscuro: #0A192F / #0E2038
- Terracota / naranja quemado: #C85A32 / #D9532F
- Tono arena / gris cálido: #D8CEBD
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Configuración global
plt.rcParams['font.family'] = 'Georgia'
BG_COLOR = '#F6F3EB'
CARD_BG = '#FCFAF6'
BORDER_COLOR = '#DFD7C7'
INK_NAVY = '#0E2038'
TERRACOTTA = '#C85A32'
ACCENT_BLUE = '#1E3A8A'
MUTED_SAND = '#D8CEBD'
SUCCESS_GREEN = '#2D6A4F'


def generar_grafico_eda():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.8), facecolor=BG_COLOR, dpi=180)
    
    # Panel 1: Detección de Anomalía de Sensor ST2235
    ax1.set_facecolor(CARD_BG)
    for spine in ax1.spines.values():
        spine.set_color(BORDER_COLOR)
        spine.set_linewidth(1.2)
        
    categorias = ['Piezas Reales\n(NPR)', 'Paradas Registradas\n(NAP en ST2235)']
    valores = [2382, 22022]
    colores = [INK_NAVY, TERRACOTTA]
    
    bars = ax1.bar(categorias, valores, color=colores, width=0.48, edgecolor=BORDER_COLOR, linewidth=1.5, zorder=3)
    ax1.set_ylabel('Unidades / día', fontsize=12, fontweight='bold', color=INK_NAVY)
    ax1.set_title('Anomalía de Telemetría: Rebote de Señal vs. Realidad\nST2235 registra 9.2 paradas por cada pieza fabricada', 
                  fontsize=13, fontweight='bold', color=INK_NAVY, pad=14)
    ax1.grid(axis='y', linestyle='--', alpha=0.5, color=MUTED_SAND, zorder=0)
    ax1.set_ylim(0, 25500)
    
    for bar in bars:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, h + 600, f'{h:,}', ha='center', va='bottom', 
                 fontsize=14, fontweight='bold', color=bar.get_facecolor())
        
    ax1.text(0.5, 0.45, 'REBOTE DE SEÑAL PLC\n(Filtro de Software, No Mecánica)', transform=ax1.transAxes,
             ha='center', va='center', fontsize=11, fontweight='bold', color=TERRACOTTA,
             bbox=dict(boxstyle='round,pad=0.6', facecolor='#FDF0EC', edgecolor=TERRACOTTA, linewidth=1.5))

    # Panel 2: Descomposición de Tiempos de Línea
    ax2.set_facecolor(CARD_BG)
    for spine in ax2.spines.values():
        spine.set_color(BORDER_COLOR)
        spine.set_linewidth(1.2)
        
    tiempos = [81.8, 8.4, 5.8, 4.0]
    etiquetas = ['TBF\n(Buen Funcionamiento)\n81.8%', 
                 'TAP\n(Parada Propia)\n8.4%', 
                 'DES\n(Desabastecimiento)\n5.8%', 
                 'SAT\n(Saturación)\n4.0%']
    colores_pie = [INK_NAVY, TERRACOTTA, MUTED_SAND, '#7E8B9B']
    
    wedges, texts = ax2.pie(tiempos, labels=etiquetas, colors=colores_pie, startangle=140,
                            wedgeprops=dict(width=0.45, edgecolor=BORDER_COLOR, linewidth=1.5))
    for t in texts:
        t.set_fontsize(10)
        t.set_fontweight('bold')
        t.set_color(INK_NAVY)
        
    ax2.set_title('Reparto Global del Tiempo Requerido (TR)\nTAI = DES + SAT = 9.8% de Parada Inducida Externa', 
                  fontsize=13, fontweight='bold', color=INK_NAVY, pad=14)
    
    plt.tight_layout()
    plt.savefig('grafico_eda_lossia.png', facecolor=BG_COLOR, dpi=180)
    plt.close()
    print("✅ Generado: grafico_eda_lossia.png")


def generar_grafico_simulador():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.8), facecolor=BG_COLOR, dpi=180)
    
    # Panel 1: Impacto de Reducción de TAP en ST-2390
    ax1.set_facecolor(CARD_BG)
    for spine in ax1.spines.values():
        spine.set_color(BORDER_COLOR)
        spine.set_linewidth(1.2)
        
    escenarios = ['Situación Actual', 'Escenario What-If\n(TAP -30%)']
    tap_horas = [4.27, 2.99]
    vecinas_horas = [3.82, 2.10]
    
    x = np.arange(len(escenarios))
    w = 0.35
    
    b1 = ax1.bar(x - w/2, tap_horas, w, label='TAP Propio (h/d)', color=TERRACOTTA, edgecolor=BORDER_COLOR, linewidth=1.2, zorder=3)
    b2 = ax1.bar(x + w/2, vecinas_horas, w, label='Parada Inducida Vecinas (h/d)', color=INK_NAVY, edgecolor=BORDER_COLOR, linewidth=1.2, zorder=3)
    
    ax1.set_ylabel('Horas / día', fontsize=12, fontweight='bold', color=INK_NAVY)
    ax1.set_title('Simulador What-If: Intervención en ST-2390\nReducción del 30% en parada propia desacopla la línea', 
                  fontsize=13, fontweight='bold', color=INK_NAVY, pad=14)
    ax1.set_xticks(x)
    ax1.set_xticklabels(escenarios, fontsize=11, fontweight='bold', color=INK_NAVY)
    ax1.legend(frameon=True, facecolor=BG_COLOR, edgecolor=BORDER_COLOR, fontsize=10)
    ax1.grid(axis='y', linestyle='--', alpha=0.5, color=MUTED_SAND, zorder=0)
    ax1.set_ylim(0, 5.2)
    
    for bar in list(b1) + list(b2):
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, h + 0.12, f'{h:.2f}h', ha='center', va='bottom', 
                 fontsize=11, fontweight='bold', color=bar.get_facecolor())

    # Panel 2: Producción Neta Ganada (Motores Extra)
    ax2.set_facecolor(CARD_BG)
    for spine in ax2.spines.values():
        spine.set_color(BORDER_COLOR)
        spine.set_linewidth(1.2)
        
    kpis = ['+1.28 h / día\nTiempo Recuperado', '+108 motores / día\nGanancia Neta', '+25.000 motores / año\nImpacto Fábrica']
    valores_kpi = [1.28, 108, 25000]
    
    ax2.axis('off')
    
    # Dibujar 3 tarjetas visuales dentro del panel
    y_positions = [0.72, 0.40, 0.08]
    textos_sup = ['+ 1.28 h / día', '+ 108 motores / día', '+ 25.000 motores / año']
    textos_inf = ['Tiempo productivo neto recuperado', 'Producción diaria adicional neta', 'Impacto anual estimado en Valladolid L5']
    colores_borde = [INK_NAVY, TERRACOTTA, SUCCESS_GREEN]
    
    for y, t_sup, t_inf, col in zip(y_positions, textos_sup, textos_inf, colores_borde):
        rect = plt.Rectangle((0.08, y), 0.84, 0.24, facecolor='#FAF7F0', edgecolor=col, linewidth=1.8, 
                             transform=ax2.transAxes, zorder=2)
        ax2.add_patch(rect)
        ax2.text(0.5, y + 0.14, t_sup, transform=ax2.transAxes, ha='center', va='center',
                 fontsize=18, fontweight='bold', color=col, zorder=3)
        ax2.text(0.5, y + 0.05, t_inf, transform=ax2.transAxes, ha='center', va='center',
                 fontsize=10.5, fontweight='bold', color='#4A5568', zorder=3)
        
    ax2.set_title('Retorno de Inversión de Mantenimiento (ROI)\nDe centro de coste a palanca de producción', 
                  fontsize=13, fontweight='bold', color=INK_NAVY, pad=14)
    
    plt.tight_layout()
    plt.savefig('grafico_simulador_lossia.png', facecolor=BG_COLOR, dpi=180)
    plt.close()
    print("✅ Generado: grafico_simulador_lossia.png")


def generar_grafico_prediccion():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.8), facecolor=BG_COLOR, dpi=180)
    
    # Panel 1: Top Máquinas en Riesgo Hoy
    ax1.set_facecolor(CARD_BG)
    for spine in ax1.spines.values():
        spine.set_color(BORDER_COLOR)
        spine.set_linewidth(1.2)
        
    maquinas = ['ST0261\n(Puesto #18)', 'ST-2380\n(Puesto #73)', 'PM_0110\n(Puesto #9)', 'ST-0385\n(Puesto #31)', 'ST-2215\n(Puesto #57)']
    probabilidades = [65.6, 56.9, 55.2, 54.8, 54.0]
    
    y = np.arange(len(maquinas))
    bars = ax1.barh(y[::-1], probabilidades[::-1], color=TERRACOTTA, height=0.52, edgecolor=BORDER_COLOR, linewidth=1.2, zorder=3)
    
    ax1.set_xlabel('Probabilidad de Avería Hoy (%)', fontsize=12, fontweight='bold', color=INK_NAVY)
    ax1.set_title('Top Máquinas con Riesgo Hoy · Jornada S43-D4\nPrioridad absoluta antes de arrancar el turno', 
                  fontsize=13, fontweight='bold', color=INK_NAVY, pad=14)
    ax1.set_yticks(y)
    ax1.set_yticklabels(maquinas[::-1], fontsize=10, fontweight='bold', color=INK_NAVY)
    ax1.grid(axis='x', linestyle='--', alpha=0.5, color=MUTED_SAND, zorder=0)
    ax1.set_xlim(0, 100)
    ax1.axvline(70, color='#D62828', linestyle='--', linewidth=1.5, label='Umbral Crítico (70%)')
    ax1.axvline(45, color=TERRACOTTA, linestyle='--', linewidth=1.5, label='Umbral Alerta (45%)')
    ax1.legend(loc='lower right', frameon=True, facecolor=BG_COLOR, edgecolor=BORDER_COLOR, fontsize=9.5)
    
    for bar in bars:
        w = bar.get_width()
        ax1.text(w + 1.8, bar.get_y() + bar.get_height()/2, f'{w:.1f}%', ha='left', va='center', 
                 fontsize=11, fontweight='bold', color=INK_NAVY)

    # Panel 2: Curva de Desgaste Weibull (Horas sin fallo vs MTBF)
    ax2.set_facecolor(CARD_BG)
    for spine in ax2.spines.values():
        spine.set_color(BORDER_COLOR)
        spine.set_linewidth(1.2)
        
    t = np.linspace(0, 250, 100)
    eta = 100.0 / 0.89  # MTBF = 100h
    beta = 1.85
    p_weibull = (1.0 - np.exp(-1.0 * np.power(t / eta, beta))) * 100
    
    ax2.plot(t, p_weibull, color=INK_NAVY, linewidth=2.8, label=r'Curva de Desgaste $\beta=1.85$ (Weibull)', zorder=3)
    ax2.axvline(100, color=TERRACOTTA, linestyle=':', linewidth=1.8, label='MTBF Medio (100h acumuladas)')
    ax2.scatter([216.3], [65.6], color=TERRACOTTA, s=140, zorder=4, edgecolor=INK_NAVY, linewidth=1.5)
    ax2.annotate('ST0261\n(216h sin fallo)\n275% MTBF agotado', (216.3, 65.6), xytext=(-65, 12), textcoords='offset points',
                 fontsize=9.5, fontweight='bold', color=TERRACOTTA,
                 bbox=dict(boxstyle='round,pad=0.4', facecolor='#FDF0EC', edgecolor=TERRACOTTA, linewidth=1.2))
    
    ax2.set_xlabel('Horas de Marcha Continua sin Avería (t_sin_fallo)', fontsize=12, fontweight='bold', color=INK_NAVY)
    ax2.set_ylabel('Probabilidad Condicional de Fallo (%)', fontsize=12, fontweight='bold', color=INK_NAVY)
    ax2.set_title('Modelo Físico de Supervivencia: Tasa Creciente\nA más horas sin parada, mayor probabilidad de fatiga mecánica', 
                  fontsize=13, fontweight='bold', color=INK_NAVY, pad=14)
    ax2.grid(True, linestyle='--', alpha=0.5, color=MUTED_SAND, zorder=0)
    ax2.legend(loc='lower right', frameon=True, facecolor=BG_COLOR, edgecolor=BORDER_COLOR, fontsize=9.5)
    ax2.set_ylim(-2, 102)
    
    plt.tight_layout()
    plt.savefig('grafico_prediccion_lossia.png', facecolor=BG_COLOR, dpi=180)
    plt.close()
    print("✅ Generado: grafico_prediccion_lossia.png")


def generar_grafico_futuro():
    fig, ax = plt.subplots(figsize=(14, 5.8), facecolor=BG_COLOR, dpi=180)
    ax.set_facecolor(BG_COLOR)
    ax.axis('off')
    
    # 4 Bloques visuales para mejoras futuras (2x2 grid)
    bloques = [
        ("01 · Streaming IoT en Tiempo Real", "Conexión directa PLC vía OPC-UA / MQTT", "< 1s Latencia", INK_NAVY, 0.04, 0.52),
        ("02 · Gemelo Digital 3D & Eventos Discretos", "Simulación AnyLogic / Simio con dinámica de AGVs", "Fidelidad 99%", TERRACOTTA, 0.52, 0.52),
        ("03 · Despliegue Multi-Planta HORSE", "Valladolid L5 → Sevilla → Mioveni → Curitiba → Bursa", "5 Factorías", INK_NAVY, 0.04, 0.04),
        ("04 · Prescripción Autónoma con GMAO", "Disparo automático de órdenes de trabajo en SAP PM", "100% Automático", SUCCESS_GREEN, 0.52, 0.04)
    ]
    
    for tit, subtit, pill, col, x, y in bloques:
        # Tarjeta
        rect = plt.Rectangle((x, y), 0.44, 0.42, facecolor=CARD_BG, edgecolor=BORDER_COLOR, 
                             linewidth=1.5, transform=ax.transAxes, zorder=2)
        ax.add_patch(rect)
        
        # Barra superior decorativa
        bar = plt.Rectangle((x, y + 0.395), 0.44, 0.025, facecolor=col, edgecolor='none', 
                            transform=ax.transAxes, zorder=3)
        ax.add_patch(bar)
        
        # Título
        ax.text(x + 0.03, y + 0.31, tit, transform=ax.transAxes, fontsize=13, fontweight='bold', color=INK_NAVY, zorder=4)
        
        # Subtítulo
        ax.text(x + 0.03, y + 0.20, subtit, transform=ax.transAxes, fontsize=10.5, color='#4A5568', zorder=4)
        
        # Pill badge
        pill_rect = plt.Rectangle((x + 0.03, y + 0.07), 0.20, 0.08, facecolor='#F3EDE2', edgecolor=col, 
                                  linewidth=1.2, transform=ax.transAxes, zorder=3)
        ax.add_patch(pill_rect)
        ax.text(x + 0.13, y + 0.11, pill, transform=ax.transAxes, ha='center', va='center', 
                fontsize=9.5, fontweight='bold', color=col, zorder=4)
        
    plt.tight_layout()
    plt.savefig('grafico_futuro_lossia.png', facecolor=BG_COLOR, dpi=180)
    plt.close()
    print("✅ Generado: grafico_futuro_lossia.png")


if __name__ == '__main__':
    generar_grafico_eda()
    generar_grafico_simulador()
    generar_grafico_prediccion()
    generar_grafico_futuro()
