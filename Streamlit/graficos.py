"""Figuras de LOSSIA sobre los indicadores ya calculados y las filas filtradas."""

from math import ceil

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lossia import config as LC


COLORES = {"TBF": "#3C7A5E", "TAP": "#B8441F", "DES": "#C9973F", "SAT": "#8C9AAB"}
NOMBRES = {
    "TBF": "Funcionando (TBF)",
    "TAP": "Parada propia (TAP)",
    "DES": "Desabastecimiento (DES)",
    "SAT": "Saturación (SAT)",
}
AZUL = "#0A2540"
SECUNDARIO = "#3C5878"
GRIS_BARRA = "#B7AC90"


def _eje_operaciones(fig, operaciones):
    operaciones = list(operaciones)
    paso = max(1, ceil(len(operaciones) / 13))
    fig.update_xaxes(
        title="Operación", type="category", categoryorder="array",
        categoryarray=operaciones, tickvals=operaciones[::paso], tickangle=-35,
        showgrid=False,
    )


def _barras_estados(datos, eje_x, estados, *, porcentajes=False, divergente=False):
    fig = go.Figure()
    etiqueta = "%{x|%d/%m/%Y}" if eje_x == "Fecha" else "%{x} · OP %{customdata[2]:.0f}"
    for estado in estados:
        valores = datos[f"%{estado}"] if porcentajes else datos[estado]
        signo = -1 if divergente and estado != "TAP" else 1
        unidad = "%{customdata[0]:.2f} % del TR · " if porcentajes else ""
        detalle = [valores, datos[estado]]
        if eje_x == "Operacion":
            detalle.append(datos.Orden_OP)
        fig.add_bar(
            x=datos[eje_x], y=signo * valores, name=NOMBRES[estado],
            marker_color=COLORES[estado],
            customdata=np.column_stack(detalle),
            hovertemplate=(
                f"<b>{etiqueta}</b><br>{NOMBRES[estado]} · {unidad}"
                "%{customdata[1]:.2f} h<extra></extra>"
            ),
        )
    fig.update_layout(barmode="relative" if divergente else "stack", bargap=0.17)
    return fig


def _nota_sin_tr(k):
    sin_tr = int(k.TR.eq(0).sum())
    if sin_tr:
        st.caption(f"Operaciones sin tiempo de estados registrado en la selección: {sin_tr}.")


def _reparto(k):
    modo = st.radio("Escala", ["% del TR", "Horas"], horizontal=True, key="escala_reparto")
    pct = modo == "% del TR"
    fig = _barras_estados(k, "Operacion", COLORES, porcentajes=pct)
    _eje_operaciones(fig, k.Operacion)
    fig.update_yaxes(title="% del TR" if pct else "Horas", ticksuffix=" %" if pct else None)
    if pct:
        fig.update_yaxes(range=[0, 103])
    _nota_sin_tr(k)
    return fig


def _paradas(k):
    st.caption("Sobre cero, parada propia (TAP). Bajo cero, desabastecimiento (DES) y saturación (SAT).")
    fig = _barras_estados(k, "Operacion", ("TAP", "DES", "SAT"), porcentajes=True, divergente=True)
    _eje_operaciones(fig, k.Operacion)
    fig.update_yaxes(title="% del TR", ticksuffix=" %", zeroline=True, zerolinecolor=SECUNDARIO)
    _nota_sin_tr(k)
    return fig


def _criticidad(k):
    puntos = k.dropna(subset=["%TAP", "%TAI"]).copy()
    _nota_sin_tr(k)
    if puntos.empty:
        st.info("Sin porcentajes de parada calculables para esta selección.")
        return None, puntos

    puntos["Tamaño"] = puntos.TAP.clip(lower=0.01)
    destacadas = puntos[puntos.Severidad.gt(0)].nlargest(3, "Severidad").Operacion
    puntos["Etiqueta"] = puntos.Operacion.where(puntos.Operacion.isin(destacadas), "")
    fig = go.Figure()
    con_dp = puntos[puntos.Dp.notna()]
    sin_dp = puntos[puntos.Dp.isna()]
    for grupo, tiene_dp in ((con_dp, True), (sin_dp, False)):
        if grupo.empty:
            continue
        marcador = dict(
            sizemode="area", sizeref=2 * puntos["Tamaño"].max() / 28**2, sizemin=4,
            size=grupo["Tamaño"], line=dict(width=.7, color="#F5F1E8"),
        )
        if tiene_dp:
            marcador.update(color=grupo.Dp, coloraxis="coloraxis")
        else:
            marcador.update(color=GRIS_BARRA, symbol="diamond")
        dp_hover = "%{customdata[3]:.2f} %" if tiene_dp else "sin dato"
        fig.add_scatter(
            x=grupo["%TAI"], y=grupo["%TAP"], mode="markers+text", text=grupo.Etiqueta,
            textposition="top center", marker=marcador, showlegend=False,
            customdata=grupo[["Operacion", "Orden_OP", "TAP", "Dp"]].to_numpy(),
            hovertemplate=(
                "<b>%{customdata[0]}</b> · OP %{customdata[1]}<br>"
                "Parada inducida: %{x:.2f} % del TR<br>Parada propia: %{y:.2f} % del TR<br>"
                "TAP: %{customdata[2]:.2f} h<br>"
                f"Dp: {dp_hover}<extra></extra>"
            ),
        )
    fig.update_layout(coloraxis=dict(
        colorscale=["#B8441F", "#DED5BE", "#3C7A5E"], cmin=70, cmax=100,
        showscale=not con_dp.empty,
        colorbar=dict(title="Dp", ticksuffix=" %", thickness=12,
                      tickvals=[70, 80, 90, 100], outlinewidth=0),
    ))
    fig.update_xaxes(title="Parada inducida (TAI / TR)", ticksuffix=" %", rangemode="tozero")
    fig.update_yaxes(title="Parada propia (TAP / TR)", ticksuffix=" %", rangemode="tozero")
    if not sin_dp.empty:
        st.caption("Los rombos indican disponibilidad sin dato.")
    fig.add_vline(x=puntos["%TAI"].median(), line_dash="dot", line_color=SECUNDARIO)
    fig.add_hline(y=puntos["%TAP"].median(), line_dash="dot", line_color=SECUNDARIO)
    st.caption("Las líneas punteadas marcan las medianas de la selección. El tamaño representa horas de TAP.")
    return fig, puntos


def _explicacion_ranking():
    with st.expander("¿Cómo se calcula?"):
        st.markdown(
            "**Severidad (método de flechas, Kuo-Lim-Meerkov):** compara cuánto se bloquea "
            "cada etapa (satura a la anterior) frente a cuánto pasa hambre (la desabastece la "
            "anterior). Una etapa es cuello de botella cuando las flechas de sus vecinas "
            "convergen en ella. Es **penalizante** si además su severidad supera "
            f"{LC.SEVERIDAD_MIN:.0%} y su cociente **TAP/TAI** (parada propia / parada inducida, "
            f"criterio de HORSE) es mayor que {LC.COCIENTE_TAP_TAI_MIN:g}: se para más por sí misma "
            "que por culpa de sus vecinas. Si no, es una víctima de su entorno.\n\n"
            "**TAP medio/día** y **Fpm** son indicadores de mantenimiento: una etapa puede "
            "pararse mucho sin ser cuello de botella (tiene capacidad sobrante o un buffer la "
            "protege) y seguir siendo prioritaria para mantenimiento.\n\n"
            "**Horas inducidas** suman la saturación/desabastecimiento que un cuello de botella "
            "provoca en su zona de influencia, calculadas por `lossia/determinista.py`."
        )


def _ranking_cuellos(ranking, titulo):
    """Cuellos de botella coloreados según el criterio de HORSE: penalizante (se para más por sí
    misma, TAP/TAI > 1) o víctima de su entorno (sus paradas vienen de las vecinas)."""
    fig = go.Figure()
    penal = ranking.Es_relevante.fillna(False).astype(bool)
    for filtro, nombre, color in ((penal, "Penalizante · TAP/TAI > 1", COLORES["TAP"]),
                                  (~penal, "Cuello víctima del entorno · TAP/TAI ≤ 1", GRIS_BARRA)):
        g = ranking[filtro]
        if g.empty:
            continue
        cociente = g.TAP_TAI.map(lambda v: f"{v:.2f}" if pd.notna(v) else "—")
        dias = g.Dias_principal.map(lambda v: f"{int(v)}" if pd.notna(v) else "—")
        fig.add_bar(
            x=g.Severidad * 100, y=g.Operacion, orientation="h", name=nombre, marker_color=color,
            customdata=np.column_stack((g.Orden_OP, cociente, g.Induce_vecinos.round(1), dias)),
            text=[f"{s * 100:.1f} %  ·  TAP/TAI {c}" for s, c in zip(g.Severidad, cociente)],
            textposition="outside", cliponaxis=False,
            hovertemplate=("<b>%{y}</b> · OP %{customdata[0]}<br>Severidad: %{x:.1f} %<br>"
                           "TAP/TAI: %{customdata[1]}<br>Horas inducidas a la línea: %{customdata[2]} h<br>"
                           "Días como penalizante principal: %{customdata[3]}<extra></extra>"),
        )
    fig.update_layout(height=max(320, 120 + len(ranking) * 34), barmode="overlay", bargap=.35,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    maximo = float((ranking.Severidad * 100).max())
    fig.update_xaxes(title="Severidad (%)", rangemode="tozero", range=[0, maximo * 1.35])
    fig.update_yaxes(type="category", categoryorder="array", categoryarray=list(ranking.Operacion),
                     autorange="reversed", showgrid=False)
    return fig


def _ranking(k, dp_min):
    criterios = {
        "Severidad": "Cuellos de botella (método de flechas)",
        "TAP_medio_dia": "Parada propia media por día (mantenimiento)",
        "Induce_vecinos": "Horas inducidas a las vecinas",
        "Fpm": "Frecuencia de paro (paros / 1000 piezas)",
    }
    col_a, col_b = st.columns([3, 1])
    criterio = col_a.selectbox("Ordenar por", criterios, format_func=criterios.get, key="criterio_ranking")
    top_n = col_b.selectbox("Operaciones", range(5, 31), index=5, key="top_ranking")
    if criterio == "Severidad":
        # Todos los cuellos de botella, en el orden oficial del método (penalizantes primero,
        # desempatadas por días como principal y severidad); no solo los que cumplen TAP/TAI > 1
        ranking = (k[k.Es_cuello.fillna(False)].dropna(subset=["Severidad"])
                   .sort_values(["Rango_det", "Severidad"], ascending=[True, False]).head(top_n))
        if ranking.empty:
            st.info("Sin cuellos de botella en la selección.")
            return None, ranking
        fig = _ranking_cuellos(ranking, criterios[criterio])
        _explicacion_ranking()
        return fig, ranking
    ranking = k.dropna(subset=[criterio]).nlargest(top_n, criterio)
    if ranking.empty:
        st.info("Sin valores calculables para este criterio en la selección.")
        return None, ranking

    es_pct = criterio == "Severidad"
    escala = 100 if es_pct else 1
    sufijo = " %" if es_pct else ""
    fig = go.Figure()
    grupos = (
        (ranking.Dp.lt(dp_min), f"Dp < {dp_min:g} %", COLORES["TAP"], ""),
        (ranking.Dp.ge(dp_min), f"Dp ≥ {dp_min:g} %", GRIS_BARRA, ""),
        (ranking.Dp.isna(), "Dp sin dato", GRIS_BARRA, "/"),
    )
    for filtro, etiqueta, color, trama in grupos:
        grupo = ranking[filtro]
        if grupo.empty:
            continue
        disp = grupo.Dp.map(lambda v: f"{v:.2f} %" if pd.notna(v) else "Sin dato")
        fig.add_bar(
            x=grupo[criterio] * escala, y=grupo.Operacion, orientation="h", name=etiqueta,
            marker=dict(color=color, pattern_shape=trama),
            customdata=np.column_stack((grupo.Operacion, grupo.Orden_OP, disp)),
            texttemplate=f"%{{x:.1f}}{sufijo}", textposition="outside", cliponaxis=False,
            hovertemplate=(
                "<b>%{y}</b> · OP %{customdata[1]}<br>"
                + criterios[criterio] + f": %{{x:.2f}}{sufijo}<br>Dp: %{{customdata[2]}}<extra></extra>"
            ),
        )
    fig.update_layout(height=max(445, 118 + len(ranking) * 26), barmode="overlay")
    fig.update_xaxes(title=criterios[criterio], rangemode="tozero")
    fig.update_yaxes(
        type="category", categoryorder="array", categoryarray=list(ranking.Operacion),
        autorange="reversed", showgrid=False,
    )
    _explicacion_ranking()
    return fig, ranking


def _objetivo(k, campo, etiqueta, unidad, umbral, fallo, ascendente):
    todas = st.checkbox("Ver todas las operaciones con dato", key=f"todas_{campo}")
    datos = k.dropna(subset=[campo])
    faltan = len(k) - len(datos)
    if faltan:
        st.caption(f"Operaciones sin {etiqueta.lower()} calculable: {faltan}.")
    if datos.empty:
        st.info(f"Sin valores de {etiqueta.lower()} para esta selección.")
        return None

    datos = datos.sort_values([fallo, campo], ascending=[False, ascendente])
    if not todas:
        datos = datos[datos[fallo]]
    if datos.empty:
        st.info("Todas las operaciones con dato cumplen el objetivo.")
        return None

    fig = go.Figure()
    horizontal = len(datos) <= 20
    eje_op, eje_valor = ("y", "x") if horizontal else ("x", "y")
    for incumple, nombre, color in (
        (True, "Fuera de objetivo", COLORES["TAP"]),
        (False, "En objetivo", COLORES["TBF"]),
    ):
        grupo = datos[datos[fallo].eq(incumple)]
        if grupo.empty:
            continue
        fig.add_bar(
            **{eje_op: grupo.Operacion, eje_valor: grupo[campo]},
            orientation="h" if horizontal else "v", name=nombre, marker_color=color,
            customdata=grupo.Orden_OP,
            texttemplate=f"%{{x:.1f}} {unidad}" if horizontal else None,
            textposition="outside" if horizontal else None,
            cliponaxis=False,
            hovertemplate=(
                f"<b>%{{{eje_op}}}</b> · OP %{{customdata}}<br>{etiqueta}: "
                f"%{{{eje_valor}:.2f}} {unidad}<br>{nombre}<extra></extra>"
            ),
        )
    fig.update_layout(barmode="overlay")
    estilo_umbral = dict(line_dash="dash", line_color=AZUL, line_width=1.4,
                         annotation_text=f"Objetivo {umbral:g} {unidad}",
                         annotation_font_color=AZUL, annotation_bgcolor="#F5F1E8")
    escala = dict(title=f"{etiqueta} ({unidad})", range=[0, max(umbral, datos[campo].max()) * 1.15])
    if horizontal:
        fig.update_layout(height=max(360, 130 + 26 * len(datos)))
        fig.add_vline(x=umbral, annotation_position="top left", **estilo_umbral)
        fig.update_xaxes(**escala)
        fig.update_yaxes(type="category", categoryorder="array", categoryarray=list(datos.Operacion),
                         autorange="reversed", showgrid=False)
    else:
        fig.add_hline(y=umbral, annotation_position="top right", **estilo_umbral)
        fig.update_yaxes(**escala)
        _eje_operaciones(fig, datos.Operacion)
    return fig


def _frecuencia(k):
    positivos = k[k.Fpm.gt(0)]
    ceros = int(k.Fpm.eq(0).sum())
    faltan = int(k.Fpm.isna().sum())
    st.caption("Fpm = NAP / NPR × 1000, sobre registros con contador de piezas válido.")
    if ceros or faltan:
        st.caption(
            f"Fpm igual a cero: {ceros} operaciones. Sin valor calculable: {faltan}. "
            "La escala logarítmica representa valores positivos."
        )
    if positivos.empty:
        st.info("Sin valores positivos de Fpm para esta selección.")
        return None

    top = positivos.nlargest(3, "Fpm")
    fig = go.Figure(go.Bar(
        x=positivos.Operacion, y=positivos.Fpm,
        marker_color=np.where(positivos.Operacion.isin(top.Operacion), AZUL, GRIS_BARRA),
        customdata=positivos.Orden_OP,
        hovertemplate=(
            "<b>%{x}</b> · OP %{customdata}<br>Fpm: %{y:.3f} paros / 1000 piezas<extra></extra>"
        ),
    ))
    _eje_operaciones(fig, k.Operacion)
    fig.update_yaxes(type="log", title="Paros / 1000 piezas (escala logarítmica)")
    st.caption("Mayores valores: " + " · ".join(f"{fila.Operacion}: {fila.Fpm:.2f}"
                                              for fila in top.itertuples()))
    return fig


def _diaria(ed, op, fechas):
    """`ed`: etapa_dia con columna Fecha (ver app.etapa_dia_con_fecha). `fechas`: lista de
    'Dia' (AAAA-SWW-D) seleccionados en la barra lateral, no fechas de calendario."""
    dias_etapa = ed[ed.Etapa.eq(op)]
    eje = (pd.to_datetime(dias_etapa.Fecha.unique()) if fechas is None
           else pd.to_datetime(dias_etapa.loc[dias_etapa.Dia.isin(fechas), "Fecha"].unique()))
    eje = eje.sort_values().unique()
    datos = dias_etapa.groupby("Fecha")[list(COLORES)].sum(min_count=1)
    datos.index = pd.to_datetime(datos.index)
    datos = datos.reindex(eje).rename_axis("Fecha").reset_index()
    fig = _barras_estados(datos, "Fecha", COLORES)
    sin_filas = datos[list(COLORES)].isna().all(axis=1)
    ceros = datos[list(COLORES)].notna().all(axis=1) & datos[list(COLORES)].eq(0).all(axis=1)
    for seleccion, nombre, simbolo in (
        (sin_filas, "Sin registro en la selección", "x"),
        (ceros, "Registro con 0 h en los cuatro estados", "circle-open"),
    ):
        dias_marcados = datos.loc[seleccion, "Fecha"]
        if dias_marcados.empty:
            continue
        fig.add_scatter(
            x=dias_marcados, y=np.zeros(len(dias_marcados)), mode="markers", name=nombre,
            marker=dict(size=9, symbol=simbolo, color=SECUNDARIO),
            hovertemplate=f"<b>%{{x|%d/%m/%Y}}</b><br>{nombre}<extra></extra>",
        )
    fig.update_xaxes(title="Fecha", tickformat="%d/%m", nticks=12)
    fig.update_yaxes(title="Horas", rangemode="tozero")
    return fig


def _vecinas(k, op):
    posicion = list(k.Operacion).index(op)
    inicio = max(0, posicion - 3)
    datos = k.iloc[inicio:posicion + 4]
    fig = _barras_estados(datos, "Operacion", COLORES, porcentajes=True)
    foco = posicion - inicio
    fig.add_vrect(
        x0=foco - .46, x1=foco + .46, fillcolor="#E8CFC0",
        opacity=1, line_width=0, layer="below",
    )
    _eje_operaciones(fig, datos.Operacion)
    fig.update_xaxes(ticktext=[f"<b>{v}</b>" if v == op else v for v in datos.Operacion])
    fig.update_yaxes(title="% del TR", ticksuffix=" %", range=[0, 103])
    _nota_sin_tr(datos)
    st.caption(f"{op} y hasta tres operaciones a cada lado en el conjunto filtrado, según el orden de línea.")
    return fig


def mostrar_grafico(vista, k, f, op=None, abrir_detalle=None, *, dp_min, tcy_max, fechas=None):
    """Presenta únicamente la figura solicitada junto con sus controles locales."""
    seleccionables = None
    if vista == "reparto":
        fig = _reparto(k)
    elif vista == "paradas":
        fig = _paradas(k)
    elif vista == "criticidad":
        fig, seleccionables = _criticidad(k)
    elif vista == "ranking":
        fig, seleccionables = _ranking(k, dp_min)
    elif vista == "disponibilidad":
        fig = _objetivo(k, "Dp", "Disponibilidad", "%", dp_min, "Incumple_Dp", True)
    elif vista == "ciclo":
        fig = _objetivo(k, "Tcy", "Tiempo de ciclo", "cmin", tcy_max, "Incumple_Tcy", False)
    elif vista == "frecuencia":
        fig = _frecuencia(k)
    elif vista == "diaria":
        fig = _diaria(f, op, fechas)
    elif vista == "vecinas":
        fig = _vecinas(k, op)
    else:
        raise ValueError(f"Vista de gráfico desconocida: {vista}")

    if fig is None:
        return
    fig.update_layout(
        template="plotly_white", height=fig.layout.height or 490,
        paper_bgcolor="#FBF8F1", plot_bgcolor="#FBF8F1",
        font=dict(family="Inter, Segoe UI, sans-serif", size=13, color="#0A2540"),
        margin=dict(l=24, r=36, t=62, b=28),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hoverlabel=dict(bgcolor="#0A2540", font_color="#F5F1E8"),
    )
    fig.update_xaxes(automargin=True, gridcolor="#E4DCC8", linecolor="#C9BFA3", title_standoff=12)
    fig.update_yaxes(automargin=True, gridcolor="#E4DCC8", linecolor="#C9BFA3", title_standoff=12)
    opciones = dict(
        width="stretch", theme=None, key=f"grafico_{vista}",
        config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
    )
    if seleccionables is None or abrir_detalle is None:
        st.plotly_chart(fig, **opciones)
        return

    operaciones = seleccionables.Operacion.drop_duplicates().tolist()
    fig.update_layout(clickmode="event+select", dragmode="zoom")
    seleccion = st.plotly_chart(fig, on_select="rerun", selection_mode="points", **opciones)
    puntos = seleccion.selection.points
    if len(puntos) == 1:
        dato = puntos[0].get("customdata") or []
        if dato and dato[0] in operaciones:
            abrir_detalle(dato[0])
            return

    operacion = st.selectbox(
        "Abrir detalle de una operación", operaciones, index=None,
        placeholder="Buscar por código de operación", key=f"detalle_{vista}",
    )
    if operacion is not None:
        abrir_detalle(operacion)
