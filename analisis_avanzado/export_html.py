import json
import pandas as pd
from pathlib import Path

df_pen = pd.read_csv("Datos_limpios/analisis_penalizantes.csv")
top_ops_json = df_pen[[
    "Orden_OP", "Operacion", "Tipo", "IPL", "TAP", "TAI", "DES", "SAT", "Dp",
    "Tcy_linea_cmin", "Fpm", "MTTR_min", "Diagnostico_Tipo", "es_anomalia_sensor"
]].sort_values("Orden_OP").to_dict(orient="records")

json_str = json.dumps(top_ops_json)

template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>LOSSIA · Reto HORSE Valladolid Línea 5</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; background: #0f172a; color: #f8fafc; }
        header { background: #1e293b; color: white; padding: 20px 35px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; }
        .logo-title { display: flex; align-items: center; gap: 15px; }
        .logo-title h1 { margin: 0; font-size: 22px; color: #38bdf8; }
        .logo-title p { margin: 2px 0 0 0; font-size: 13px; color: #94a3b8; }
        .container { max-width: 1400px; margin: 25px auto; padding: 0 25px; }
        .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; margin-bottom: 25px; }
        .kpi-card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px; position: relative; overflow: hidden; }
        .kpi-card::before { content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%; }
        .card-red::before { background: #ef4444; }
        .card-orange::before { background: #f97316; }
        .card-blue::before { background: #38bdf8; }
        .card-purple::before { background: #a855f7; }
        .kpi-title { font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; }
        .kpi-val { font-size: 28px; font-weight: 800; margin: 6px 0; color: #f8fafc; }
        .kpi-sub { font-size: 12px; color: #cbd5e1; }
        .main-grid { display: grid; grid-template-columns: 420px 1fr; gap: 25px; }
        .panel { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; }
        .table-wrap { max-height: 580px; overflow-y: auto; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th { position: sticky; top: 0; background: #0f172a; color: #94a3b8; padding: 10px; text-align: left; }
        td { padding: 9px 10px; border-bottom: 1px solid #334155; }
        tr:hover { background: #334155; cursor: pointer; }
        .active-row { background: #1e3a8a !important; }
        .badge { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; }
        .badge-red { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
        .badge-green { background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.4); }
        .badge-purple { background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.4); }
        .diag-box { background: #0f172a; border-left: 4px solid #38bdf8; border-radius: 6px; padding: 15px; margin-top: 20px; }
        .diag-box h4 { margin: 0 0 8px 0; color: #38bdf8; font-size: 14px; }
        .diag-box p { margin: 0; font-size: 13px; line-height: 1.5; color: #cbd5e1; }
        .metric-box { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 15px; }
        .m-item { background: #0f172a; padding: 12px; border-radius: 8px; border: 1px solid #334155; }
        .m-lbl { font-size: 11px; color: #94a3b8; text-transform: uppercase; }
        .m-val { font-size: 18px; font-weight: 700; color: #f8fafc; margin-top: 3px; }
    </style>
</head>
<body>
    <header>
        <div class="logo-title">
            <div style="font-size: 28px;">⚙️</div>
            <div>
                <h1>HORSE · RETO LOSSIA (Línea 5 Valladolid)</h1>
                <p>Solución Tecnológica de Detección y Explicabilidad de Máquinas Penalizantes</p>
            </div>
        </div>
        <div>
            <span class="badge badge-green" style="font-size: 13px; padding: 6px 14px;">L5 Ensamblaje · 85 Estaciones</span>
        </div>
    </header>

    <div class="container">
        <!-- KPI SUMMARY CARDS -->
        <div class="kpi-grid">
            <div class="kpi-card card-red">
                <div class="kpi-title">Cuello de Botella Nº1</div>
                <div class="kpi-val" style="color: #f87171;">ST-2390</div>
                <div class="kpi-sub">TAP: <b>4.27 h/día</b> | Dp: <b>77.3%</b> (Objetivo 90%)</div>
            </div>
            <div class="kpi-card card-orange">
                <div class="kpi-title">Puesto Manual Crítico</div>
                <div class="kpi-val" style="color: #fb923c;">PM2250</div>
                <div class="kpi-sub">TAP: <b>2.91 h/día</b> | Dp: <b>85.0%</b> (MTTR: 7.4 min)</div>
            </div>
            <div class="kpi-card card-blue">
                <div class="kpi-title">Punto Mayor Saturación</div>
                <div class="kpi-val" style="color: #38bdf8;">ST0259</div>
                <div class="kpi-sub">SAT: <b>6.74 h/día</b> (Línea bloqueada aguas abajo)</div>
            </div>
            <div class="kpi-card card-purple">
                <div class="kpi-title">Alerta de Instrumentación</div>
                <div class="kpi-val" style="color: #c084fc;">ST2235</div>
                <div class="kpi-sub">22.000 microparadas falsas/día (Sensor chattering)</div>
            </div>
        </div>

        <!-- MAIN TWO-COLUMN VIEW -->
        <div class="main-grid">
            <!-- LEFT PANEL: TABLE -->
            <div class="panel">
                <h3 style="margin: 0 0 15px 0; font-size: 16px; color: #f8fafc;">Ranking de la Línea (Orden de Flujo)</h3>
                <div class="table-wrap">
                    <table id="tabla">
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Operación</th>
                                <th>Tipo</th>
                                <th>IPL</th>
                                <th>Dp (%)</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>

            <!-- RIGHT PANEL: DETAILED CARD -->
            <div class="panel" id="panel-detalle">
                <p>Cargando detalles...</p>
            </div>
        </div>
    </div>

    <script>
        const datos = __DATA_JSON__;
        const tbody = document.querySelector("#tabla tbody");
        const panel = document.getElementById("panel-detalle");

        function renderTabla() {
            tbody.innerHTML = "";
            datos.forEach((d) => {
                const tr = document.createElement("tr");
                const badgeClass = d.IPL >= 60 ? "badge-red" : d.es_anomalia_sensor ? "badge-purple" : "badge-green";
                tr.innerHTML = `
                    <td>${d.Orden_OP}</td>
                    <td><b>${d.Operacion}</b></td>
                    <td>${d.Tipo.replace("Estación (ST)", "ST").replace("Puesto manual (PM)", "PM").replace("Manutención / auxiliar", "Manut.")}</td>
                    <td><span class="badge ${badgeClass}">${d.IPL.toFixed(1)}</span></td>
                    <td>${d.Dp.toFixed(1)}%</td>
                `;
                tr.onclick = () => mostrarDetalle(d, tr);
                if (d.Operacion === "ST-2390") tr.classList.add("active-row");
                tbody.appendChild(tr);
            });
        }

        function mostrarDetalle(d, tr) {
            document.querySelectorAll("#tabla tr").forEach(r => r.classList.remove("active-row"));
            if (tr) tr.classList.add("active-row");

            const badgeDp = d.Dp < 90 ? `<span class="badge badge-red">INCUMPLE (&lt;90%)</span>` : `<span class="badge badge-green">CUMPLE</span>`;
            const badgeTcy = d.Tcy_linea_cmin > 80 ? `<span class="badge badge-red">LENTO (&gt;80 cmin)</span>` : `<span class="badge badge-green">CUMPLE</span>`;

            panel.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 15px;">
                    <div>
                        <h2 style="margin: 0; font-size: 24px; color: #38bdf8;">Puesto #${d.Orden_OP}: ${d.Operacion}</h2>
                        <div style="font-size: 13px; color: #94a3b8; margin-top: 4px;">Tipo: <b>${d.Tipo}</b> | Categoría: <b>${d.Diagnostico_Tipo}</b></div>
                    </div>
                    <div style="text-align: right;">
                        <span class="badge badge-red" style="font-size: 16px; padding: 8px 16px;">IPL: ${d.IPL.toFixed(1)} / 100</span>
                    </div>
                </div>

                <div class="metric-box">
                    <div class="m-item">
                        <div class="m-lbl">Disponibilidad Propia (Dp)</div>
                        <div class="m-val">${d.Dp.toFixed(1)}% ${badgeDp}</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 3px;">Objetivo contractual: ≥ 90.0%</div>
                    </div>
                    <div class="m-item">
                        <div class="m-lbl">Tiempo de Ciclo Línea (Tcy)</div>
                        <div class="m-val">${d.Tcy_linea_cmin.toFixed(1)} cmin ${badgeTcy}</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 3px;">Límite contractual: ≤ 80.0 cmin (48 s)</div>
                    </div>
                    <div class="m-item">
                        <div class="m-lbl">Parada Propia (TAP)</div>
                        <div class="m-val" style="color: #f87171;">${d.TAP.toFixed(2)} h / día</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 3px;">Averías cada 1.000 piezas (Fpm): ${d.Fpm.toFixed(1)}</div>
                    </div>
                    <div class="m-item">
                        <div class="m-lbl">Parada Inducida (TAI = DES + SAT)</div>
                        <div class="m-val" style="color: #fb923c;">${d.TAI.toFixed(2)} h / día</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 3px;">DES: ${d.DES.toFixed(2)} h | SAT: ${d.SAT.toFixed(2)} h</div>
                    </div>
                </div>

                <div class="diag-box">
                    <h4>💡 Diagnóstico Explicable para Jefe de Unidad y Mantenimiento:</h4>
                    <p>
                        ${d.es_anomalia_sensor ? 
                            '⚠️ <b>ANOMALÍA INSTRUMENTAL DETECTADA:</b> La operación acumula más de 20.000 paradas diarias registradas mientras la línea mantiene su cadencia. Se trata de un fallo de rebote de contacto o sensor (chattering). <b>Recomendación:</b> No intervenir mecánicamente la estación; enviar a instrumentación/PLC a revisar fotocélula y filtrado de señal.' :
                            d.Operacion === 'ST-2390' ?
                            '🚨 <b>CUELLO DE BOTELLA MECÁNICO NÚMERO 1:</b> Esta estación sufre 4.27 horas diarias de avería propia (Dp 77.3%), provocando un desabastecimiento inmediato de más de 3 horas en las máquinas posteriores (ST-2400 y ST_2410). <b>Recomendación:</b> Prioridad crítica de mantenimiento preventivo, revisión de elementos de desgaste y reducción del MTTR.' :
                            d.Operacion === 'PM2250' ?
                            '⚠️ <b>CUELLO DE BOTELLA MANUAL:</b> Operación manual con disponibilidad reducida (85.0%). Sus paradas son largas y asociadas a cadencia de operario o complejidad ergonómica. <b>Recomendación:</b> Equilibrado de cargas y ergonomía en puesto.' :
                            d.Operacion === 'ST0259' ?
                            '🔒 <b>MÁXIMO BLOQUEO POR SATURACIÓN:</b> La máquina acumula 6.74 horas de parada inducida por saturación debido a que las estaciones intermedias (ST-0260) no absorben el flujo. <b>Recomendación:</b> Revisar capacidad de pulmón intermedio.' :
                            'Operación con desempeño dentro de los parámetros esperados de la Línea 5.'
                        }
                    </p>
                </div>
            `;
        }

        renderTabla();
        const inicial = datos.find(d => d.Operacion === "ST-2390") || datos[0];
        mostrarDetalle(inicial, null);
    </script>
</body>
</html>
"""

final_html = template.replace("__DATA_JSON__", json_str)
Path("dashboard_lossia.html").write_text(final_html, encoding="utf-8")
print("dashboard_lossia.html written successfully!")
