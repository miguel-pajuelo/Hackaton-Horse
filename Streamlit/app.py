"""
LOSSIA · Visualización de máquinas penalizantes (Línea 5 Montaje Valladolid)

Ejecutar desde la raíz del repo:   streamlit run Streamlit/app.py
Entrada: Datos_limpios/datos_limpios.csv (salida de limpieza.py)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ----------------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------------
REPO = Path(__file__).resolve().parent.parent
DEFAULT_DATOS = REPO / "Datos_limpios" / "datos_limpios.csv"
DEFAULT_CONFIG = REPO / "Datos_limpios" / "config_limpia.csv"
INFORME = REPO / "Datos_limpios" / "informe_limpieza.txt"

TCY_MAX = 80.0      # cmin
DP_MIN = 90.0       # %
CMIN_POR_HORA = 6000  # 1 h = 60 min = 6000 cmin  (los tiempos vienen en horas)

COLORES = {"TBF": "#2E9E5B", "TAP": "#D64545", "DES": "#E8A33D", "SAT": "#4A7BD0"}
NOMBRES = {"TBF": "Funcionando (TBF)", "TAP": "Parada propia (TAP)",
           "DES": "Desabastecimiento (DES)", "SAT": "Saturación (SAT)"}

st.set_page_config(page_title="LOSSIA · Máquinas penalizantes", page_icon="🏭", layout="wide")


# ----------------------------------------------------------------------------
# Carga
# ----------------------------------------------------------------------------
@st.cache_data
def cargar(datos_src, config_src):
    df = pd.read_csv(datos_src)
    # Si los datos no traen el orden de la línea (p.ej. CSV original), se cruza con la config
    if "Orden_OP" not in df.columns:
        config = pd.read_csv(config_src)
        on = [c for c in ("Linea", "Operacion") if c in df.columns and c in config.columns]
        df = df.merge(config, on=on, how="inner")
    # Columnas opcionales que genera limpieza.py
    for col, default in {"incluir_analisis": True, "flag_npr_invalido": False,
                         "flag_tap_sospechoso": False, "Tipo": "—"}.items():
        if col not in df.columns:
            df[col] = default
    for col in ("incluir_analisis", "flag_npr_invalido", "flag_tap_sospechoso"):
        df[col] = df[col].astype(str).str.lower().isin(["true", "1"])
    return df


def kpis(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega por operación (suma de tiempos/contadores) y calcula indicadores."""
    df = df.copy()
    # Piezas no fiables (flag_npr_invalido): sus tiempos cuentan, pero no entran en Tcy/Fpm
    ok = ~df.flag_npr_invalido
    df["TBF_v"] = df.TBF.where(ok, 0)
    df["NAP_v"] = df.NAP.where(ok, 0)
    df["NPR_v"] = df.NPR.where(ok, 0)

    g = (df.groupby(["Operacion", "Orden_OP", "Tipo"], as_index=False)
           [["TBF", "TAP", "DES", "SAT", "NAP", "NPR", "TBF_v", "NAP_v", "NPR_v"]].sum()
           .sort_values("Orden_OP").reset_index(drop=True))
    g["TAI"] = g.DES + g.SAT
    g["TR"] = g.TBF + g.TAP + g.TAI
    tr = g.TR.replace(0, np.nan)
    for c in ("TBF", "TAP", "DES", "SAT", "TAI"):
        g[f"%{c}"] = 100 * g[c] / tr
    g["Dp"] = 100 * g.TBF / (g.TBF + g.TAP).replace(0, np.nan)
    npr = g.NPR_v.replace(0, np.nan)
    g["Tcy"] = g.TBF_v * CMIN_POR_HORA / npr
    g["Fpm"] = 1000 * g.NAP_v / npr

    # Evidencia de propagación en la línea (línea serie, por orden):
    #  - si i se para, la siguiente (i+1) se queda sin piezas  -> DES de i+1
    #  - si i se para, la anterior (i-1) no puede descargar    -> SAT de i-1
    g["DES_siguiente"] = g.DES.shift(-1).fillna(0)
    g["SAT_anterior"] = g.SAT.shift(1).fillna(0)
    g["Induce_vecinos"] = g.DES_siguiente + g.SAT_anterior

    # Índice de penalización: horas de parada propia ponderadas por lo "libre" que
    # está la máquina (poca parada inducida => la parada es suya y se propaga).
    g["Indice"] = g.TAP * (1 - g["%TAI"].fillna(0) / 100)
    g["Incumple_Dp"] = g.Dp < DP_MIN
    g["Incumple_Tcy"] = g.Tcy > TCY_MAX
    return g


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
st.sidebar.title("🏭 LOSSIA")
with st.sidebar.expander("Fuentes de datos", expanded=False):
    up_datos = st.file_uploader("CSV de datos (limpio)", type="csv")
    up_config = st.file_uploader("CSV de configuración (solo si los datos no traen Orden_OP)", type="csv")

df = cargar(up_datos or DEFAULT_DATOS, up_config or DEFAULT_CONFIG)

semanas = sorted(df.Week.unique())
sel_sem = st.sidebar.multiselect("Semanas", semanas, default=semanas)
if "Jour" in df.columns:
    dias = sorted(df.Jour.unique())
    sel_dia = st.sidebar.multiselect("Día de la semana", dias, default=dias)
else:
    sel_dia = None

tipos = sorted(df.Tipo.dropna().unique())
sel_tipo = st.sidebar.multiselect("Tipo de operación", tipos, default=tipos)

orden_min, orden_max = int(df.Orden_OP.min()), int(df.Orden_OP.max())
rango = st.sidebar.slider("Tramo de la línea (orden OP)", orden_min, orden_max, (orden_min, orden_max))
top_n = st.sidebar.slider("Top N en rankings", 5, 30, 10)

st.sidebar.markdown("**Criterios de limpieza**")
solo_incluidas = st.sidebar.checkbox(
    "Solo operaciones incluidas en el análisis", value=True,
    help="Excluye las operaciones marcadas con incluir_analisis = False "
         "(fuera de servicio, contadores de manutención…).")
excl_tap = st.sidebar.checkbox(
    "Excluir días con TAP sospechoso", value=False,
    help="flag_tap_sospechoso: TAP de día completo con la línea produciendo o >5000 paradas/día "
         "(p.ej. ST2235). Actívalo para ver el ranking sin esas señales erráticas.")

f = df[df.Week.isin(sel_sem) & df.Orden_OP.between(*rango) & df.Tipo.isin(sel_tipo)]
if sel_dia is not None:
    f = f[f.Jour.isin(sel_dia)]
if solo_incluidas:
    f = f[f.incluir_analisis]
if excl_tap:
    f = f[~f.flag_tap_sospechoso]
if f.empty:
    st.warning("No hay datos con los filtros seleccionados.")
    st.stop()

k = kpis(f)

# ----------------------------------------------------------------------------
# Cabecera + KPIs
# ----------------------------------------------------------------------------
st.title("Máquinas penalizantes · Línea 5 Montaje Valladolid")
st.caption(f"Semanas {', '.join(map(str, sel_sem))} · operaciones {rango[0]}–{rango[1]} · "
           f"{k.Operacion.nunique()} operaciones")

top = k.sort_values("Indice", ascending=False).iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Máquina más penalizante", top.Operacion, f"{top.TAP:.1f} h parada propia", delta_color="off")
c2.metric("Disponibilidad media", f"{k.Dp.mean():.1f} %", f"{k.Dp.mean() - DP_MIN:+.1f} pp vs objetivo")
c3.metric("Incumplen Dp ≥ 90 %", f"{int(k.Incumple_Dp.sum())} / {len(k)}")
c4.metric("Incumplen Tcy ≤ 80 cmin", f"{int(k.Incumple_Tcy.sum())} / {len(k)}")

tab_linea, tab_rank, tab_obj, tab_maq, tab_tabla = st.tabs(
    ["🗺️ Mapa de la línea", "🎯 Penalizantes", "📏 Objetivos", "🔍 Detalle máquina", "📋 Tabla"])

# ----------------------------------------------------------------------------
# 1. Mapa de la línea
# ----------------------------------------------------------------------------
with tab_linea:
    st.subheader("Reparto del tiempo requerido por operación, en orden de la línea")
    st.caption("Una máquina penalizante suele verse como un pico rojo (TAP) con "
               "**naranja (DES) justo después** y **azul (SAT) justo antes**: su parada se propaga.")
    modo = st.radio("Escala", ["% del TR", "Horas"], horizontal=True)
    larga = k.melt(id_vars=["Operacion", "Orden_OP"],
                   value_vars=[("%" if modo == "% del TR" else "") + c for c in COLORES],
                   var_name="Tipo", value_name="Valor")
    larga["Tipo"] = larga.Tipo.str.lstrip("%").map(NOMBRES)
    fig = px.bar(larga, x="Operacion", y="Valor", color="Tipo",
                 color_discrete_map={NOMBRES[c]: COLORES[c] for c in COLORES},
                 category_orders={"Operacion": list(k.Operacion), "Tipo": list(NOMBRES.values())})
    fig.update_layout(barmode="stack", height=480, xaxis_tickangle=-60, legend_title=None,
                      yaxis_title=modo, xaxis_title="Operación (orden de línea →)")
    st.plotly_chart(fig, width="stretch")

    st.subheader("Parada propia vs. parada inducida a lo largo de la línea")
    fig2 = go.Figure()
    fig2.add_scatter(x=k.Operacion, y=k["%TAP"], name="% TAP", mode="lines+markers",
                     line=dict(color=COLORES["TAP"]))
    fig2.add_scatter(x=k.Operacion, y=k["%DES"], name="% DES", mode="lines",
                     line=dict(color=COLORES["DES"]))
    fig2.add_scatter(x=k.Operacion, y=k["%SAT"], name="% SAT", mode="lines",
                     line=dict(color=COLORES["SAT"]))
    fig2.update_layout(height=380, xaxis_tickangle=-60, yaxis_title="% del TR")
    st.plotly_chart(fig2, width="stretch")

# ----------------------------------------------------------------------------
# 2. Penalizantes
# ----------------------------------------------------------------------------
with tab_rank:
    col_a, col_b = st.columns([3, 2])
    with col_a:
        st.subheader("Mapa de criticidad")
        st.caption("Arriba a la izquierda = **penalizante**: se para mucho por sí misma y casi "
                   "nunca la paran otras. Abajo a la derecha = **víctima**: sufre paradas ajenas.")
        sc = k.dropna(subset=["%TAP", "%TAI"]).copy()
        sc["Tamaño"] = sc.TAP.clip(lower=0.01)
        fig = px.scatter(sc, x="%TAI", y="%TAP", size="Tamaño", color="Dp",
                         color_continuous_scale="RdYlGn", range_color=(70, 100),
                         hover_name="Operacion",
                         hover_data={"Orden_OP": True, "TAP": ":.1f", "Dp": ":.1f", "Tamaño": False},
                         text=sc.Operacion.where(sc.Operacion.isin(
                             k.nlargest(top_n, "Indice").Operacion), ""))
        fig.add_vline(x=sc["%TAI"].median(), line_dash="dot", line_color="grey")
        fig.add_hline(y=sc["%TAP"].median(), line_dash="dot", line_color="grey")
        fig.update_traces(textposition="top center")
        fig.update_layout(height=520, xaxis_title="% parada inducida (TAI / TR)",
                          yaxis_title="% parada propia (TAP / TR)", coloraxis_colorbar_title="Dp %")
        st.plotly_chart(fig, width="stretch")

    with col_b:
        st.subheader(f"Top {top_n} penalizantes")
        criterio = st.selectbox("Ordenar por", {
            "Indice": "Índice de penalización",
            "TAP": "Horas de parada propia",
            "Induce_vecinos": "Paradas inducidas a vecinos",
            "Fpm": "Frecuencia de paro (Fpm)",
        }.keys(), format_func=lambda x: {
            "Indice": "Índice de penalización", "TAP": "Horas de parada propia",
            "Induce_vecinos": "DES siguiente + SAT anterior", "Fpm": "Fpm (paros / 1000 piezas)"}[x])
        r = k.nlargest(top_n, criterio).iloc[::-1]
        fig = px.bar(r, x=criterio, y="Operacion", orientation="h",
                     color="Incumple_Dp", color_discrete_map={True: COLORES["TAP"], False: "#9AA5B1"},
                     hover_data={"Orden_OP": True, "Dp": ":.1f", "%TAI": ":.1f"})
        fig.update_layout(height=520, legend_title="Dp < 90 %", yaxis_title=None)
        st.plotly_chart(fig, width="stretch")

    with st.expander("ℹ️ ¿Cómo se calcula el índice?"):
        st.markdown(
            "- **Índice = TAP × (1 − %TAI)**. Pondera las horas de parada propia por lo poco que "
            "otras máquinas paran a ésta: si casi no tiene parada inducida, sus paradas son suyas "
            "y las transmite al resto.\n"
            "- **DES siguiente + SAT anterior**: horas en que sus vecinas inmediatas estuvieron "
            "desabastecidas/saturadas, evidencia directa de propagación.\n"
            "- No se usa solo \"la que más se para\": como indica el reto, eso no tiene por qué "
            "ser lo correcto.")

# ----------------------------------------------------------------------------
# 3. Objetivos
# ----------------------------------------------------------------------------
with tab_obj:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Disponibilidad (objetivo ≥ 90 %)")
        fig = px.bar(k, x="Operacion", y="Dp", color="Incumple_Dp",
                     color_discrete_map={True: COLORES["TAP"], False: COLORES["TBF"]},
                     category_orders={"Operacion": list(k.Operacion)})
        fig.add_hline(y=DP_MIN, line_dash="dash", annotation_text="90 %")
        fig.update_layout(height=420, showlegend=False, xaxis_tickangle=-60, yaxis_title="Dp %")
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.subheader("Tiempo de ciclo (objetivo ≤ 80 cmin)")
        tcy = k.dropna(subset=["Tcy"])
        fig = px.bar(tcy, x="Operacion", y="Tcy", color="Incumple_Tcy",
                     color_discrete_map={True: COLORES["TAP"], False: COLORES["TBF"]},
                     category_orders={"Operacion": list(k.Operacion)})
        fig.add_hline(y=TCY_MAX, line_dash="dash", annotation_text="80 cmin")
        fig.update_layout(height=420, showlegend=False, xaxis_tickangle=-60, yaxis_title="cmin")
        fig.update_yaxes(range=[0, max(TCY_MAX * 1.5, min(tcy.Tcy.quantile(.95) * 1.2, 300))])
        st.plotly_chart(fig, width="stretch")
    st.subheader("Frecuencia de paro · Fpm = NAP / NPR × 1000")
    fig = px.bar(k, x="Operacion", y="Fpm", category_orders={"Operacion": list(k.Operacion)},
                 color_discrete_sequence=[COLORES["SAT"]])
    fig.update_layout(height=360, xaxis_tickangle=-60, yaxis_type="log",
                      yaxis_title="paros / 1000 piezas (log)")
    st.plotly_chart(fig, width="stretch")

# ----------------------------------------------------------------------------
# 4. Detalle por máquina
# ----------------------------------------------------------------------------
with tab_maq:
    ops = list(k.Operacion)
    op = st.selectbox("Operación", ops, index=ops.index(top.Operacion))
    fila = k[k.Operacion == op].iloc[0]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Orden en línea", int(fila.Orden_OP))
    c2.metric("Disponibilidad", f"{fila.Dp:.1f} %", f"{fila.Dp - DP_MIN:+.1f} pp")
    c3.metric("Tiempo de ciclo", f"{fila.Tcy:.1f} cmin" if pd.notna(fila.Tcy) else "—",
              f"{fila.Tcy - TCY_MAX:+.1f}" if pd.notna(fila.Tcy) else None, delta_color="inverse")
    c4.metric("Fpm", f"{fila.Fpm:.1f}" if pd.notna(fila.Fpm) else "—")
    c5.metric("Rank penalización", int(k.Indice.rank(ascending=False)[k.Operacion == op].iloc[0]))

    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown("**Evolución diaria del tiempo**")
        ev = f[f.Operacion == op].copy()
        eje = ["Week", "Jour"] if "Jour" in ev.columns else ["Week"]
        ev = ev.groupby(eje, as_index=False)[list(COLORES)].sum()
        ev["Periodo"] = ev[eje].astype(str).agg("-".join, axis=1).radd("S")
        larga = ev.melt(id_vars="Periodo", value_vars=list(COLORES), var_name="Tipo", value_name="h")
        fig = px.bar(larga, x="Periodo", y="h", color="Tipo", color_discrete_map=COLORES)
        fig.update_layout(height=380, barmode="stack", yaxis_title="horas")
        st.plotly_chart(fig, width="stretch")
    with cc2:
        st.markdown("**Vecinas en la línea (±3 operaciones)**")
        i = ops.index(op)
        vec = k.iloc[max(0, i - 3): i + 4]
        larga = vec.melt(id_vars="Operacion", value_vars=[f"%{c}" for c in COLORES],
                         var_name="Tipo", value_name="%")
        larga["Tipo"] = larga.Tipo.str.lstrip("%")
        fig = px.bar(larga, x="Operacion", y="%", color="Tipo", color_discrete_map=COLORES,
                     category_orders={"Operacion": list(vec.Operacion)})
        fig.add_vrect(x0=i - max(0, i - 3) - 0.5, x1=i - max(0, i - 3) + 0.5,
                      fillcolor="black", opacity=0.08, line_width=0)
        fig.update_layout(height=380, barmode="stack", yaxis_title="% del TR")
        st.plotly_chart(fig, width="stretch")

# ----------------------------------------------------------------------------
# 5. Tabla
# ----------------------------------------------------------------------------
with tab_tabla:
    cols = ["Orden_OP", "Operacion", "Tipo", "TBF", "TAP", "DES", "SAT", "TAI", "TR",
            "%TAP", "%TAI", "Dp", "Tcy", "Fpm", "Induce_vecinos", "Indice"]
    st.dataframe(
        k[cols].style.format(precision=1)
        .background_gradient(subset=["Indice"], cmap="Reds")
        .map(lambda v: "color:#D64545;font-weight:600" if pd.notna(v) and v < DP_MIN else "",
             subset=["Dp"])
        .map(lambda v: "color:#D64545;font-weight:600" if pd.notna(v) and v > TCY_MAX else "",
             subset=["Tcy"]),
        width="stretch", height=600, hide_index=True)
    st.download_button("⬇️ Descargar CSV", k[cols].to_csv(index=False).encode("utf-8"),
                       "kpis_lossia.csv", "text/csv")

    if INFORME.exists():
        with st.expander("🧹 Informe de limpieza de datos"):
            st.text(INFORME.read_text(encoding="utf-8"))
