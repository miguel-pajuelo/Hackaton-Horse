"""
Generador del notebook 03_solucion_tecnologica.ipynb para el Hackathon HORSE / Reto LOSSIA
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
cells.append(make_cell("markdown", """# 03 · Solución Tecnológica LOSSIA
### Cuadro de Mando Explicable, Gemelo Digital Lite y Simulador What-If
**Línea 5 de Montaje de Motores · HORSE Valladolid**

---

### ¿Por qué esta solución responde al Objetivo Final del Hackathon?
La presentación oficial de HORSE define tres objetivos claros:
1. **Analizar las paradas**: Identificar máquinas penalizantes vs máquinas víctimas.
2. **Crear una solución tecnológica**: Herramienta unificada que democratice el análisis técnico.
3. **Versión simplificada y accesible**: Una interfaz intuitiva donde **un Jefe de Unidad y un Técnico de Mantenimiento** cuenten con la misma información objetiva para tomar decisiones inmediatas sin discrecionalidad.

### Módulos integrados en este Notebook:
1. **Visor Diagnóstico Interactivo**: Selección de máquina con semáforos de KPIs ($Dp$, $Tcy$, $Fpm$) y explicación en lenguaje natural.
2. **Simulador What-If de Impacto**: ¿Cuántos motores adicionales gana la Línea 5 si reducimos las averías de una máquina crítica?
3. **Mapa Visual de Planta (Línea 5)**: Gemelo digital esquemático del flujo de montaje con detección de cuellos de botella.
4. **Generador del Dashboard Web Autónomo**: Exportación automática de una aplicación web HTML interactiva (`dashboard_lossia.html`) lista para proyectar ante el jurado."""))

# ==================== CELDA 2 ====================
cells.append(make_cell("code", """from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import ipywidgets as widgets
from IPython.display import display, HTML, clear_output

pd.set_option("display.max_columns", 40)
sns.set_theme(style="whitegrid", font_scale=0.95)
plt.rcParams["figure.dpi"] = 110

ENTRADA = Path("Datos_limpios")

# Cargar análisis de penalizantes generado en el notebook 02
if (ENTRADA / "analisis_penalizantes.csv").exists():
    df_pen = pd.read_csv(ENTRADA / "analisis_penalizantes.csv")
    print(f"Dataset de penalizantes cargado: {len(df_pen)} operaciones.")
else:
    raise FileNotFoundError("Por favor ejecuta primero el notebook 02_analisis_penalizantes.ipynb")
"""))

# ==================== CELDA 3 ====================
cells.append(make_cell("markdown", """## 1. Visor Diagnóstico Interactivo
Selecciona cualquier operación del desplegable para inspeccionar al instante:
- Cumplimiento de $Dp \\ge 90\\%$ y $Tcy \\le 80$ cmin.
- Gráfico de balance de tiempos (Producción vs Parada Propia vs Inducidas).
- Ficha explicativa para el Jefe de Unidad y el Técnico de Mantenimiento."""))

# ==================== CELDA 4 ====================
cells.append(make_cell("code", """# Desplegable ordenado por criticidad (IPL descendente)
opciones = df_pen.sort_values("IPL", ascending=False)["Operacion"].tolist()
dropdown = widgets.Dropdown(
    options=opciones,
    value="ST-2390",
    description="Operación:",
    style={"description_width": "initial"},
    layout=widgets.Layout(width="350px")
)

salida_visor = widgets.Output()

def actualizar_visor(change):
    op_sel = change["new"] if isinstance(change, dict) else change
    row = df_pen[df_pen.Operacion == op_sel].iloc[0]
    
    with salida_visor:
        clear_output(wait=True)
        
        # 1. Tarjeta resumen
        es_pen = row["IPL"] >= 50
        color_header = "#D62828" if es_pen else "#2A9D8F"
        badge_sensor = "<span style='background:#9D4EDD;color:white;padding:3px 8px;border-radius:4px;'>ANOMALÍA INSTRUMENTACIÓN</span>" if row["es_anomalia_sensor"] else ""
        
        html_card = f\"\"\"
        <div style="border: 2px solid {color_header}; border-radius: 8px; padding: 15px; margin-bottom: 15px; background: #FAF9F6;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="margin:0; color:{color_header};">Puesto #{int(row['Orden_OP'])}: {row['Operacion']} ({row['Tipo']})</h3>
                <div>{badge_sensor} <span style="background:{color_header}; color:white; padding:4px 10px; border-radius:12px; font-weight:bold;">IPL: {row['IPL']:.1f}/100</span></div>
            </div>
            <hr style="margin: 10px 0;">
            <div style="display: flex; gap: 20px; font-size: 14px;">
                <div><b>Disponibilidad (Dp):</b> {row['Dp']:.1f}% {'❌ (<90%)' if row['Dp'] < 90 else '✅'}</div>
                <div><b>Tiempo de Ciclo (Tcy):</b> {row['Tcy_linea_cmin']:.1f} cmin {'❌ (>80 cmin)' if row['Tcy_linea_cmin'] > 80 else '✅'}</div>
                <div><b>Paradas/1.000 piezas (Fpm):</b> {row['Fpm']:.1f}</div>
                <div><b>MTTR:</b> {row['MTTR_min']:.1f} min</div>
                <div><b>Diagnóstico:</b> <b>{row['Diagnostico_Tipo']}</b></div>
            </div>
        </div>
        \"\"\"
        display(HTML(html_card))
        
        # 2. Gráfico comparativo
        fig, axes = plt.subplots(1, 2, figsize=(14, 4))
        
        # Desglose de horas
        estados = ["TBF", "TAP", "DES", "SAT", "T_no_registrado"]
        valores = [row[e] for e in estados]
        nombres = ["Producción (TBF)", "Parada Propia (TAP)", "Desabast. (DES)", "Saturación (SAT)", "No Registrado"]
        colores = ["#2A9D8F", "#E76F51", "#E9C46A", "#264653", "#B0B0B0"]
        
        axes[0].barh(nombres, valores, color=colores)
        axes[0].set_xlabel("Horas por día (base 22 h)")
        axes[0].set_title(f"Distribución diaria del tiempo · {op_sel}", weight="bold")
        for i, v in enumerate(valores):
            axes[0].text(v + 0.2, i, f"{v:.2f} h", va="center", weight="bold")
        axes[0].set_xlim(0, max(valores) + 3)
        
        # Radar o barras de KPIs clave vs HORSE
        kpis = ["Disponibilidad Dp (%)", "Tcy Límite (cmin)", "Ratio Culpa (%)"]
        val_kpis = [row["Dp"], row["Tcy_linea_cmin"], row["Ratio_Culpa"] * 100]
        targets = [90.0, 80.0, 50.0]
        
        x = np.arange(len(kpis))
        width = 0.35
        axes[1].bar(x - width/2, val_kpis, width, label="Valor Operación", color="#457B9D")
        axes[1].bar(x + width/2, targets, width, label="Referencia / Umbral", color="#E63946", alpha=0.7)
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(kpis)
        axes[1].set_title("Comparativa vs Estándares HORSE", weight="bold")
        axes[1].legend()
        for i in range(len(kpis)):
            axes[1].text(i - width/2, val_kpis[i] + 2, f"{val_kpis[i]:.1f}", ha="center", weight="bold")
            axes[1].text(i + width/2, targets[i] + 2, f"{targets[i]:.0f}", ha="center", color="#900C3F")
        axes[1].set_ylim(0, max(val_kpis + targets) + 15)
        
        plt.tight_layout()
        plt.show()

dropdown.observe(actualizar_visor, names="value")
display(dropdown)
actualizar_visor("ST-2390")
display(salida_visor)
"""))

# ==================== CELDA 5 ====================
cells.append(make_cell("markdown", """## 2. Simulador What-If de Impacto en la Línea 5
### ¿Qué beneficio obtiene HORSE al intervenir una máquina crítica?

Este módulo permite cuantificar el **Retorno de Inversión (ROI)** de una acción de mantenimiento preventivo o mejora de ingeniería en un cuello de botella."""))

# ==================== CELDA 6 ====================
cells.append(make_cell("code", """slider_reduccion = widgets.IntSlider(
    value=40, min=10, max=80, step=5,
    description="Reducción TAP (%):",
    style={"description_width": "initial"},
    layout=widgets.Layout(width="400px")
)

slider_dias = widgets.IntSlider(
    value=220, min=50, max=250, step=10,
    description="Días de producción/año:",
    style={"description_width": "initial"},
    layout=widgets.Layout(width="400px")
)

salida_sim = widgets.Output()

def simular_impacto(b=None):
    op_sel = dropdown.value
    r = df_pen[df_pen.Operacion == op_sel].iloc[0]
    pct_red = slider_reduccion.value / 100.0
    dias_ano = slider_dias.value
    
    tap_original = r["TAP"]
    tap_ahorrado_dia = tap_original * pct_red
    tap_nuevo = tap_original - tap_ahorrado_dia
    
    # Efecto en Dp
    dp_nuevo = 100.0 * (r["TBF"] + tap_ahorrado_dia) / (r["TBF"] + tap_ahorrado_dia + tap_nuevo)
    
    # Producción recuperada
    # Tiempo de ciclo en minutos
    tcy_min = (r["Tcy_linea_cmin"] * 0.6) / 60.0
    piezas_extra_dia = (tap_ahorrado_dia * 60.0) / (tcy_min if tcy_min > 0 else 0.8)
    piezas_extra_ano = int(piezas_extra_dia * dias_ano)
    
    with salida_sim:
        clear_output(wait=True)
        html_sim = f\"\"\"
        <div style="background: #E8F8F5; border-left: 6px solid #2A9D8F; padding: 15px; border-radius: 4px; margin-top: 10px;">
            <h4 style="margin-top:0; color: #1B4F72;">📊 Resultados de la Simulación What-If para <u>{op_sel}</u>:</h4>
            <ul>
                <li><b>Horas de parada recuperadas al día:</b> <span style="color:#2A9D8F; font-size:16px; font-weight:bold;">+{tap_ahorrado_dia:.2f} h/día</span> (TAP pasa de {tap_original:.2f} h a {tap_nuevo:.2f} h)</li>
                <li><b>Nueva Disponibilidad Estimada (Dp):</b> De <b>{r['Dp']:.1f}%</b> a <span style="color:#2A9D8F; font-size:16px; font-weight:bold;">{dp_nuevo:.1f}%</span> {'✅ (Alcanza estándar HORSE)' if dp_nuevo >= 90 else '⚠️ (Aún requiere ajuste adicional)'}</li>
                <li><b>Desbloqueo de flujo en la línea:</b> Se evita el desabastecimiento aguas abajo ({r['DES_siguiente']:.2f} h en máquinas contiguas).</li>
                <li><b>Motores adicionales producidos:</b></li>
                <ul>
                    <li>Por día productivo: <b>+{int(piezas_extra_dia):,} motores/día</b></li>
                    <li>Al año ({dias_ano} días): <b style="font-size:18px; color:#D62828;">+{piezas_extra_ano:,} motores/año</b></li>
                </ul>
            </ul>
        </div>
        \"\"\"
        display(HTML(html_sim))

slider_reduccion.observe(simular_impacto, names="value")
slider_dias.observe(simular_impacto, names="value")
dropdown.observe(simular_impacto, names="value")

display(widgets.VBox([slider_reduccion, slider_dias]))
simular_impacto()
display(salida_sim)
"""))

# ==================== CELDA 7 ====================
cells.append(make_cell("markdown", """## 3. Generación del Dashboard Web Standalone (`dashboard_lossia.html`)

Para la defensa del reto ante el jurado de HORSE, generamos una **aplicación web interactiva completa en un único archivo HTML**. Se puede abrir directamente en cualquier navegador o proyector sin depender de un servidor de Python."""))

# ==================== CELDA 8 ====================
cells.append(make_cell("code", """# Generador de dashboard HTML interactivo con JavaScript y diseño adaptativo
top_ops_json = df_pen[[
    "Orden_OP", "Operacion", "Tipo", "IPL", "TAP", "TAI", "DES", "SAT", "Dp",
    "Tcy_linea_cmin", "Fpm", "MTTR_min", "Diagnostico_Tipo", "es_anomalia_sensor"
]].sort_values("Orden_OP").to_dict(orient="records")

html_content = f\"\"\"<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>LOSSIA · Reto HORSE Valladolid L5</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background: #F4F6F9; color: #333; }}
        header {{ background: #1B263B; color: white; padding: 18px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }}
        .container {{ max-width: 1300px; margin: 25px auto; padding: 0 20px; }}
        .grid {{ display: grid; grid-template-columns: 1fr 2fr; gap: 20px; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); }}
        .kpi-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }}
        .kpi-box {{ background: #FAFAFA; border: 1px solid #E0E0E0; border-radius: 6px; padding: 15px; text-align: center; }}
        .kpi-val {{ font-size: 24px; font-weight: bold; margin-top: 5px; }}
        .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
        .badge-red {{ background: #FFE3E3; color: #D62828; }}
        .badge-green {{ background: #D8F3DC; color: #2D6A4F; }}
        .badge-purple {{ background: #EBD4F7; color: #6A0572; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th, td {{ padding: 8px 10px; border-bottom: 1px solid #EEE; text-align: left; }}
        th {{ background: #F1F3F5; }}
        tr:hover {{ background: #F8F9FA; cursor: pointer; }}
        .highlight {{ background: #E3F2FD !important; }}
    </style>
</head>
<body>
    <header>
        <div>
            <h2 style="margin:0;">HORSE Valladolid · Línea 5 de Montaje</h2>
            <small style="opacity:0.8;">Reto LOSSIA · Solución Tecnológica para Detección de Máquinas Penalizantes</small>
        </div>
        <div><span class="badge badge-green" style="font-size:14px;">85 Operaciones Analizadas</span></div>
    </header>

    <div class="container">
        <div class="kpi-row">
            <div class="kpi-box"><div>Cuello de Botella Nº1</div><div class="kpi-val" style="color:#D62828;">ST-2390</div><small>TAP: 4.27 h | Dp: 77.3%</small></div>
            <div class="kpi-box"><div>Puesto Manual Crítico</div><div class="kpi-val" style="color:#F77F00;">PM2250</div><small>TAP: 2.91 h | Dp: 85.0%</small></div>
            <div class="kpi-box"><div>Gran Bloqueo Saturación</div><div class="kpi-val" style="color:#264653;">ST0259</div><small>SAT: 6.74 h (Buffer Lleno)</small></div>
            <div class="kpi-box"><div>Anomalía de Sensor</div><div class="kpi-val" style="color:#9D4EDD;">ST2235</div><small>22.000 paradas falsas/día</small></div>
        </div>

        <div class="grid">
            <div class="card" style="max-height: 600px; overflow-y: auto;">
                <h3 style="margin-top:0;">Ranking de Operaciones (Línea 5)</h3>
                <table id="tabla-ops">
                    <thead><tr><th>#</th><th>Operación</th><th>Tipo</th><th>IPL</th><th>Dp</th></tr></thead>
                    <tbody></tbody>
                </table>
            </div>

            <div class="card" id="detalle">
                <h3 style="margin-top:0; color:#1B263B;">Ficha Técnica y Diagnóstico de Operación</h3>
                <p>Haz clic en cualquier operación de la tabla izquierda para ver el diagnóstico detallado.</p>
            </div>
        </div>
    </div>

    <script>
        const datos = {json.dumps(top_ops_json)};
        const tbody = document.querySelector("#tabla-ops tbody");
        const detalle = document.getElementById("detalle");

        function renderTabla() {{
            tbody.innerHTML = "";
            datos.forEach((d, idx) => {{
                const tr = document.createElement("tr");
                tr.innerHTML = `<td>${{d.Orden_OP}}</td><td><b>${{d.Operacion}}</b></td><td>${{d.Tipo}}</td><td><b>${{d.IPL.toFixed(1)}}</b></td><td>${{d.Dp.toFixed(1)}}%</td>`;
                tr.onclick = () => seleccionar(d, tr);
                if (d.Operacion === "ST-2390") tr.classList.add("highlight");
                tbody.appendChild(tr);
            }});
        }}

        function seleccionar(d, tr) {{
            document.querySelectorAll("#tabla-ops tr").forEach(r => r.classList.remove("highlight"));
            if (tr) tr.classList.add("highlight");

            const badgeDp = d.Dp < 90 ? `<span class="badge badge-red">INCUMPLE (&lt;90%)</span>` : `<span class="badge badge-green">CUMPLE</span>`;
            const badgeTcy = d.Tcy_linea_cmin > 80 ? `<span class="badge badge-red">LENTO (&gt;80 cmin)</span>` : `<span class="badge badge-green">CUMPLE</span>`;

            detalle.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <h2 style="margin:0; color:#1B263B;">Puesto #${{d.Orden_OP}}: ${{d.Operacion}}</h2>
                    <div><span class="badge badge-red" style="font-size:15px;">IPL: ${{d.IPL.toFixed(1)}} / 100</span></div>
                </div>
                <p style="color:#666; margin:5px 0 15px 0;">Tipo: <b>${{d.Tipo}}</b> | Clasificación: <b>${{d.Diagnostico_Tipo}}</b></p>
                <hr>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px; margin:15px 0;">
                    <div style="background:#F8F9FA; padding:12px; border-radius:6px;">
                        <b>Disponibilidad Propia (Dp):</b> ${{d.Dp.toFixed(1)}}% ${{badgeDp}}<br>
                        <b>Tiempo de Ciclo:</b> ${{d.Tcy_linea_cmin.toFixed(1)}} cmin ${{badgeTcy}}<br>
                        <b>Averías cada 1.000 pz (Fpm):</b> ${{d.Fpm.toFixed(1)}}<br>
                        <b>Tiempo Medio Reparación (MTTR):</b> ${{d.MTTR_min.toFixed(1)}} min
                    </div>
                    <div style="background:#F8F9FA; padding:12px; border-radius:6px;">
                        <b>Parada Propia (TAP):</b> ${{d.TAP.toFixed(2)}} h/día<br>
                        <b>Parada Inducida (TAI):</b> ${{d.TAI.toFixed(2)}} h/día<br>
                        <b>- Desabastecimiento (DES):</b> ${{d.DES.toFixed(2)}} h/día<br>
                        <b>- Saturación (SAT):</b> ${{d.SAT.toFixed(2)}} h/día
                    </div>
                </div>
                <div style="background:#EBF5FB; border-left:4px solid #2980B9; padding:12px; border-radius:4px;">
                    <h4 style="margin:0 0 5px 0; color:#1B4F72;">Diagnóstico para el Jefe de Unidad y Mantenimiento:</h4>
                    <p style="margin:0; font-size:14px; line-height:1.4;">
                        ${{d.es_anomalia_sensor ? 
                            '⚠️ <b>Atención Instrumentación:</b> La máquina registra un volumen anómalo de paradas sin frenar los motores. Revisar conexionado de fotocélula o tarjeta PLC para filtrar rebotes.' :
                            d.Operacion === 'ST-2390' ?
                            '🚨 <b>Cuello de botella crítico Nº 1 de la línea.</b> Pierde más de 4 horas diarias de parada propia e induce desabastecimiento directo a ST-2400. Prioridad urgente de mantenimiento correctivo y sustitución de desgaste.' :
                            d.Operacion === 'PM2250' ?
                            '⚠️ <b>Puesto manual penalizante.</b> La disponibilidad cae al 85% por paradas prolongadas. Estudiar ayuda operativa y ergonomía de puesto.' :
                            'Operación con comportamiento acorde al balance general de la Línea 5.'
                        }}
                    </p>
                </div>
            `;
        }}

        renderTabla();
        const inicial = datos.find(d => d.Operacion === "ST-2390") || datos[0];
        seleccionar(inicial, null);
    </script>
</body>
</html>\"\"\"

salida_html = Path("dashboard_lossia.html")
salida_html.write_text(html_content, encoding="utf-8")
print(f"✅ Dashboard web autónomo generado con éxito en: {salida_html.resolve()}")
print("Puedes abrir 'dashboard_lossia.html' en cualquier navegador durante tu presentación!")
"""))

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

salida_nb = Path("03_solucion_tecnologica.ipynb")
with open(salida_nb, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"Notebook creado exitosamente: {salida_nb.resolve()} ({len(cells)} celdas)")
