from base64 import b64encode
from datetime import date, timedelta
import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from graficos import mostrar_grafico

APP = Path(__file__).resolve().parent
REPO = APP.parent
DEFAULT_DATOS = REPO / "Datos_limpios" / "datos_limpios.csv"
DEFAULT_CONFIG = REPO / "Datos_limpios" / "config_limpia.csv"
INFORME = REPO / "Datos_limpios" / "informe_limpieza.txt"
ALERTAS = REPO / "Datos_limpios" / "alertas.json"
REGISTRO = REPO / "Datos_limpios" / "registro_limpieza.json"

TCY_MAX = 80.0      # cmin
DP_MIN = 90.0       # %
CMIN_POR_HORA = 6000  # 1 h = 60 min = 6000 cmin  (los tiempos vienen en horas)

DIAS = {1: "Lun", 2: "Mar", 3: "Mié", 4: "Jue", 5: "Vie", 6: "Sáb", 7: "Dom"}
TIPOS = {"Estacion (ST)": "Estación (ST)", "Estación (ST)": "Estación (ST)",
         "Puesto manual (PM)": "Puestos manuales", "Manutencion / auxiliar": "Manutención / auxiliar"}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
PRESETS = {"7 días": 6, "30 días": 29, "Todo": None}
VISTAS = {
    "reparto": ("Reparto", "Reparto del tiempo"),
    "criticidad": ("Penalizantes", "Mapa de criticidad"),
    "ranking": ("Penalizantes", "Top penalizantes"),
    "paradas": ("Penalizantes", "Parada propia vs. inducida"),
    "disponibilidad": ("Objetivos", "Disponibilidad por operación"),
    "ciclo": ("Objetivos", "Tiempo de ciclo"),
    "frecuencia": ("Objetivos", "Frecuencia de paro"),
}
ACCESOS = {
    "reparto": "Reparto del tiempo",
    "criticidad": "Mapa de criticidad",
    "ranking": "Top penalizantes",
    "disponibilidad": "Evolución de objetivos",
    "paradas": "Parada propia vs. inducida",
}
COLUMNAS = ["Orden_OP", "Operacion", "Tipo", "TBF", "TAP", "DES", "SAT", "TAI", "TR",
            "%TAP", "%TAI", "Dp", "Tcy", "Fpm", "Induce_vecinos", "Indice"]

st.set_page_config(page_title="LOSSIA · Línea 5", layout="wide")
st.html(APP / "lossia.css")


def fmt_fecha(d, anio=False):
    return f"{d.day} {MESES[d.month - 1]}" + (f" {d.year}" if anio else "")


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
    # Fecha real a partir de semana ISO + día (Jour: 1 = lunes ... 7 = domingo)
    anio = df["Year"] if "Year" in df.columns else pd.Series(date.today().year, index=df.index)
    dia = df["Jour"] if "Jour" in df.columns else pd.Series(1, index=df.index)
    df["Fecha"] = [date.fromisocalendar(int(y), int(w), int(d))
                   for y, w, d in zip(anio, df["Week"], dia)]
    return df


@st.cache_data
def cargar_json(ruta: str) -> dict:
    p = Path(ruta)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _alertas_por_op() -> dict:
    """{operacion: [alertas]} de alertas.json."""
    out = {}
    for a in cargar_json(str(ALERTAS)).get("alertas", []):
        out.setdefault(a.get("operacion"), []).append(a)
    return out


def _registro_por_op() -> dict:
    """{operacion|None: [entradas]} de registro_limpieza.json."""
    out = {}
    for e in cargar_json(str(REGISTRO)).get("entradas", []):
        out.setdefault(e.get("operacion"), []).append(e)
    return out


def _cuerpo_alerta(a: dict, registro: list | None = None):
    """Contenido detallado (causas y consecuencias) dentro del panel flotante."""
    d = a.get("detalle", {})
    icono = "🔴" if a.get("nivel") == "error" else "🟠"
    st.markdown(f"#### {icono} {a.get('titulo', a.get('id'))}")
    st.caption(f"{a.get('id')} · {a.get('categoria', '').replace('_', ' ')} · "
               f"orden OP {a.get('orden_op', '—')}")
    st.markdown(f"**Problema:** {a.get('resumen', '')}")
    if d.get("efecto_observado"):
        st.markdown(f"**Qué se observa:** {d['efecto_observado']}")
    if d.get("causa_probable"):
        st.markdown(f"**Causa probable:** {d['causa_probable']}")
    if d.get("otras_causas_posibles"):
        st.markdown("**Otras causas posibles:**\n" +
                    "\n".join(f"- {c}" for c in d["otras_causas_posibles"]))
    if d.get("impacto_en_el_analisis"):
        st.markdown(f"**Consecuencia en el análisis:** {d['impacto_en_el_analisis']}")
    if d.get("recomendacion"):
        st.info(f"**Recomendación:** {d['recomendacion']}")
    if d.get("dias_afectados"):
        st.caption(f"Días afectados ({len(d['dias_afectados'])}): " + ", ".join(d["dias_afectados"]))
    if d.get("datos"):
        st.json(d["datos"], expanded=False)
    if registro:
        with st.expander("🧹 Tratamiento aplicado en la limpieza"):
            for e in registro:
                st.markdown(f"- **{e.get('id')}** · {e.get('descripcion', '')} "
                            f"→ *{str(e.get('accion', '')).replace('_', ' ')}*"
                            f" ({e.get('filas_afectadas', 0)} filas)")


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


def navegar(vista, op=None, *, cerrar_menu=False):
    st.session_state.vista = vista
    if op is not None:
        st.session_state.operacion_detalle = op
    if cerrar_menu:
        st.session_state.acciones = False


def abrir_detalle(op):
    navegar("detalle", op)
    st.rerun()


def restablecer_filtros():
    for key in ("preset", "rango_fechas", "sel_dia", "sel_tipo", "rango_op", "sel_operaciones"):
        st.session_state.pop(key, None)


def filtro_periodo(fecha_min, fecha_max):
    def aplicar_preset():
        preset = st.session_state.preset
        if preset is not None:
            dias_atras = PRESETS[preset]
            inicio = fecha_min if dias_atras is None else max(fecha_min, fecha_max - timedelta(days=dias_atras))
            st.session_state.rango_fechas = (inicio, fecha_max)

    if "rango_fechas" not in st.session_state:
        st.session_state.preset = "30 días"
        aplicar_preset()

    with st.container(key="periodo"):
        st.markdown("**Periodo**")
        st.segmented_control("Periodo", list(PRESETS), key="preset", on_change=aplicar_preset,
                             label_visibility="collapsed", width="stretch", wrap=False)
        fechas = st.date_input(
            "Rango de fechas", key="rango_fechas", min_value=fecha_min, max_value=fecha_max,
            format="DD/MM/YYYY", label_visibility="collapsed",
            on_change=lambda: st.session_state.update(preset=None))
    if not fechas:
        return fecha_min, fecha_max
    return fechas[0], fechas[-1]


def filtros(df):
    with st.sidebar:
        st.html('<div class="lossia-brand"><i aria-hidden="true"><b></b><b></b><b></b><b></b></i>LOSSIA</div>')
        inicio, fin = filtro_periodo(df.Fecha.min(), df.Fecha.max())
        fechas = df.Fecha.between(inicio, fin)
        if "Jour" in df.columns:
            dias = sorted(int(d) for d in df.Jour.unique())

            def completar_dias():
                if not st.session_state.sel_dia:
                    st.session_state.sel_dia = dias

            with st.container(key="dias"):
                seleccion = st.pills("Días de la semana", dias, selection_mode="multi",
                                     default=dias, format_func=DIAS.__getitem__, key="sel_dia",
                                     on_change=completar_dias, wrap=len(dias) > 5)
            fechas &= df.Jour.isin(seleccion or dias)

        tipos = sorted(df.Tipo.dropna().unique())
        with st.container(key="tipos"):
            seleccion_tipo = st.multiselect(
                "Tipo de operación", tipos, format_func=lambda t: TIPOS.get(t, t),
                key="sel_tipo", placeholder="Todas")
        minimo, maximo = int(df.Orden_OP.min()), int(df.Orden_OP.max())
        with st.container(key="tramo"):
            if minimo == maximo:
                st.markdown(f"**Tramo de la línea** · OP {minimo}")
                rango = (minimo, maximo)
            else:
                rango = st.slider("Tramo de la línea", minimo, maximo, (minimo, maximo),
                                  key="rango_op", format="OP %d")
        alcance = df.Orden_OP.between(*rango) & df.Tipo.isin(seleccion_tipo or tipos)
        opciones = df.loc[alcance].sort_values(["Orden_OP", "Operacion"]).Operacion.unique().tolist()
        vigentes = [op for op in st.session_state.get("sel_operaciones", []) if op in opciones]
        if vigentes != st.session_state.get("sel_operaciones", []):
            st.session_state.sel_operaciones = vigentes
        with st.container(key="maquinas"):
            seleccion_op = st.multiselect(
                "Máquinas / Operaciones", opciones, key="sel_operaciones",
                placeholder="Todas", help="Busca por identificador. Vacía la selección para incluir todas.")
        if seleccion_op:
            alcance &= df.Operacion.isin(seleccion_op)
    return df.loc[fechas & alcance], df.loc[fechas, "Fecha"].unique(), inicio, fin, rango


def imagen_svg(clase, contenido, viewbox="0 0 24 24"):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}">{contenido}</svg>'
    datos = b64encode(svg.encode()).decode("ascii")
    return f'<img class="{clase}" src="data:image/svg+xml;base64,{datos}" alt="" aria-hidden="true">'


def icono(nombre):
    trazados = {
        "calendario": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4m8-4v4m-8 8h2m4 0h2"/>',
        "reloj": '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 3"/>',
        "objetivo": '<path d="M21 10a9 9 0 1 1-7-7m3 8a5 5 0 1 1-4-4m-1 5 8-8m-3 0h3V1m0 3h3"/>',
        "destellos": '<path d="M10 21C9 15 7 13 2 12c5-1 7-3 8-9 1 6 3 8 8 9-5 1-7 3-8 9Zm9-20c.5 3 1.5 4 4 4.5C20.5 6 19.5 7 19 10c-.5-3-1.5-4-4-4.5 2.5-.5 3.5-1.5 4-4.5Z"/>',
        "subida": '<path d="m3 17 6-6 4 4 8-8m-6 0h6v6"/>',
        "aviso": '<path d="M10.3 4.5 3 18a1.5 1.5 0 0 0 1.3 2.2h15.4A1.5 1.5 0 0 0 21 18L13.7 4.5a2 2 0 0 0-3.4 0ZM12 9v4m0 3h.01"/>',
    }
    color = "#0045a5" if nombre in ("destellos", "subida") else "#183958"
    return imagen_svg(
        "lossia-icon",
        f'<g fill="none" stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">'
        f'{trazados[nombre]}</g>',
    )


def indicador(grafico, valor, etiqueta, delta=""):
    return (f'<div class="kpi">{grafico}<div class="kpi-text"><strong>{valor}</strong>'
            f'<span>{etiqueta}</span></div>{delta}</div>')


def resumen(k, alertas_op, registro_op, datos_locales):
    media = k.Dp.mean()
    delta = media - DP_MIN
    delta_html = ""
    gauge = ""
    if pd.notna(delta):
        nivel = min(100, max(0, media))
        gauge = imagen_svg(
            "gauge",
            '<g fill="none" stroke-width="13" stroke-linecap="round">'
            '<path d="M10 56a48 48 0 0 1 96 0" stroke="#dce2ea"/>'
            f'<path d="M10 56a48 48 0 0 1 96 0" stroke="#163f65" '
            f'pathLength="100" stroke-dasharray="{nivel:.3f} 106"/></g>',
            "0 0 116 66",
        )
        color = "positive" if delta >= 0 else "negative"
        delta_html = f'<span class="delta {color}" title="Diferencia respecto al objetivo del {DP_MIN:g} %">{delta:+.1f} pp</span>'
    else:
        gauge = icono("objetivo")

    disponibilidad = f"{media:.1f} %" if pd.notna(media) else "—"
    dp = int(k.Incumple_Dp.sum())
    tcy = int(k.Incumple_Tcy.sum())
    aclaracion_dp = f" · {k.Dp.isna().sum()} sin Dp" if k.Dp.isna().any() else ""
    aclaracion_tcy = f" · {k.Tcy.isna().sum()} sin Tcy" if k.Tcy.isna().any() else ""
    st.html(
        '<div class="kpis" aria-label="Indicadores de la línea">'
        + indicador(gauge, disponibilidad, "Disponibilidad media", delta_html)
        + indicador(icono("objetivo"), f"{dp} / {len(k)}", f"Por debajo del {DP_MIN:g} % de Dp{aclaracion_dp}")
        + indicador(icono("reloj"), f"{tcy} / {len(k)}", f"Por encima de {TCY_MAX:g} cmin{aclaracion_tcy}")
        + "</div>"
    )

    top = k.loc[k.Indice.idxmax()]
    baja_dp = k.loc[k.Incumple_Dp].nsmallest(2, "Dp")
    alto_ciclo = k.loc[k.Incumple_Tcy].nlargest(1, "Tcy")
    with st.container(key="insights"):
        st.html(f'<h2>{icono("destellos")} Insights principales</h2>')
        c1, c2, c3 = st.columns(3)
        with c1:
            if top.Indice > 0:
                insight("subida", "Mayor índice de penalización", f"{top.TAP:.1f} h de parada propia.", top.Operacion)
            else:
                insight("subida", "Índice de penalización", "Sin un índice positivo en la selección.")
        with c2:
            if baja_dp.empty:
                texto = "Todas las Dp calculables cumplen." if k.Dp.notna().any() else "Sin datos suficientes."
                insight("aviso", "Disponibilidad", texto)
            else:
                repetida = len(baja_dp) > 1 and baja_dp.iloc[0].Operacion == top.Operacion
                fila = baja_dp.iloc[int(repetida)]
                titulo = "Otra prioridad de disponibilidad" if repetida else "Menor disponibilidad"
                insight("aviso", titulo, f"Dp de {fila.Dp:.1f} %.", fila.Operacion)
        with c3:
            if alto_ciclo.empty:
                texto = "Todos los ciclos calculables cumplen." if k.Tcy.notna().any() else "Sin datos suficientes."
                insight("reloj", "Tiempo de ciclo", texto)
            else:
                fila = alto_ciclo.iloc[0]
                insight("reloj", "Mayor tiempo de ciclo", f"{fila.Tcy:.1f} cmin.", fila.Operacion)
    calidad(alertas_op, registro_op, datos_locales)


def insight(simbolo, titulo, texto, op=None):
    with st.container(key=f"insight_{simbolo}"):
        st.html(f'<div class="insight-heading">{icono(simbolo)}<strong>{titulo}</strong></div>')
        if op is not None:
            with st.container(horizontal=True, gap="xsmall", vertical_alignment="center"):
                st.button(str(op), key=f"op_{simbolo}", type="tertiary",
                          help=f"Abrir detalle de {op}", on_click=navegar, args=("detalle", op))
                st.html(f'<span class="insight-text">{texto}</span>', width="content")
        else:
            st.html(f'<span class="insight-text">{texto}</span>')


def calidad(alertas_op, registro_op, datos_locales):
    lista = sorted(
        (a for grupo in alertas_op.values() for a in grupo),
        key=lambda a: (a.get("nivel") != "error", a.get("orden_op") or 0))
    errores = sum(a.get("nivel") == "error" for a in lista)
    etiqueta = (f"{errores} errores · {len(lista) - errores} advertencias"
                if datos_locales and ALERTAS.exists() else "Sin informe asociado")
    if lista:
        etiqueta = f":{'red' if errores else 'orange'}-background[{etiqueta}]"
    panel = st.expander(f"**Calidad de datos**　{etiqueta}", icon=":material/database:",
                        key="calidad", on_change="rerun")
    if not panel.open:
        return
    with panel:
        if not lista:
            st.caption("No hay alertas de limpieza asociadas a la fuente activa.")
            return
        st.caption("Alertas del informe de limpieza para la línea completa.")
        nivel = st.radio("Gravedad", ["Todas", "Errores", "Advertencias"], horizontal=True)
        disponibles = {
            a["id"]: a for a in lista
            if nivel == "Todas" or (a.get("nivel") == "error") == (nivel == "Errores")
        }
        if disponibles:
            def etiqueta_alerta(clave):
                alerta = disponibles[clave]
                return f"{alerta.get('operacion') or 'Línea'} · {alerta.get('titulo') or clave}"

            seleccion = st.selectbox("Buscar alerta por código de operación o título",
                                     list(disponibles), format_func=etiqueta_alerta)
            alerta = disponibles[seleccion]
            _cuerpo_alerta(alerta, registro_op.get(alerta.get("operacion")))
        else:
            st.caption("No hay alertas con esta gravedad.")


def accesos():
    with st.container(key="visualizaciones"):
        st.html("<h2>Visualizaciones</h2>")
        with st.container(key="tarjetas"):
            for vista, nombre in ACCESOS.items():
                st.button(nombre, key=f"acceso_{vista}", width="stretch",
                          on_click=navegar, args=(vista,))


def selector_grafico(vista):
    categorias = {}
    for clave, (grupo, _) in VISTAS.items():
        categorias.setdefault(grupo, clave)
    area = VISTAS[vista][0]
    with st.container(key="navegacion_graficos", horizontal=True, gap="small"):
        categoria = st.selectbox("Categoría", list(categorias), index=list(categorias).index(area),
                                 key=f"categoria_{vista}")
        if categoria != area:
            navegar(categorias[categoria])
            st.rerun()
        alternativas = [clave for clave, (grupo, _) in VISTAS.items() if grupo == area]
        if len(alternativas) > 1:
            opcion = st.selectbox("Visualización", alternativas, index=alternativas.index(vista),
                                   format_func=lambda v: VISTAS[v][1], key=f"grafico_{vista}_selector")
            if opcion != vista:
                navegar(opcion)
                st.rerun()


def detalle(k, f, fechas, alertas_op, registro_op):
    ops = k.Operacion.drop_duplicates().tolist()
    if st.session_state.get("operacion_detalle") not in ops:
        st.session_state.operacion_detalle = k.loc[k.Indice.idxmax(), "Operacion"]
    op = st.session_state.operacion_detalle
    i = ops.index(op)
    with st.container(key="selector_operacion", horizontal=True, vertical_alignment="bottom"):
        st.button("Anterior", icon=":material/chevron_left:", disabled=i == 0,
                  on_click=navegar, args=("detalle", ops[max(0, i - 1)]))
        st.selectbox("Operación", ops, key="operacion_detalle",
                     format_func=lambda valor: f"{valor} · OP {k.loc[k.Operacion == valor, 'Orden_OP'].iloc[0]}")
        st.button("Siguiente", icon=":material/chevron_right:", icon_position="right",
                  disabled=i == len(ops) - 1, on_click=navegar,
                  args=("detalle", ops[min(i + 1, len(ops) - 1)]))
    fila = k.loc[k.Operacion == op].iloc[0]
    posicion = k.Indice.rank(ascending=False).loc[fila.name]
    medidas = [
        ("Orden en línea", f"OP {int(fila.Orden_OP)}", None),
        ("Disponibilidad", f"{fila.Dp:.1f} %" if pd.notna(fila.Dp) else "—",
         f"{fila.Dp - DP_MIN:+.1f} pp" if pd.notna(fila.Dp) else None),
        ("Tiempo de ciclo", f"{fila.Tcy:.1f} cmin" if pd.notna(fila.Tcy) else "—",
         f"{fila.Tcy - TCY_MAX:+.1f} cmin" if pd.notna(fila.Tcy) else None),
        ("Fpm", f"{fila.Fpm:.1f}" if pd.notna(fila.Fpm) else "—", None),
        ("Puesto por penalización", str(int(posicion)), None),
    ]
    with st.container(key="metricas_detalle", horizontal=True, gap="small"):
        for etiqueta, valor, delta in medidas:
            st.metric(etiqueta, valor, delta, border=True,
                      delta_color="inverse" if etiqueta == "Tiempo de ciclo" else "normal")
    for alerta in alertas_op.get(op, []):
        with st.popover(alerta.get("titulo", alerta["id"]), icon=":material/warning:"):
            _cuerpo_alerta(alerta, registro_op.get(op))
    if not alertas_op.get(op) and registro_op.get(op):
        with st.expander("Tratamiento aplicado en la limpieza"):
            for entrada in registro_op[op]:
                st.write(entrada.get("descripcion", ""))
    grafico = st.segmented_control("Visualización de la operación", ["diaria", "vecinas"],
                                   default="diaria", key="detalle_grafico",
                                   format_func=lambda v: {"diaria": "Evolución diaria", "vecinas": "Operaciones vecinas"}[v],
                                   label_visibility="collapsed")
    mostrar_grafico(grafico or "diaria", k, f, op=op, dp_min=DP_MIN, tcy_max=TCY_MAX, fechas=fechas)


def tabla(k, datos_locales):
    consulta = st.text_input("Buscar operación", placeholder="Código, tipo u orden OP")
    filas = k[COLUMNAS]
    if consulta.strip():
        filtro = consulta.strip().removeprefix("OP ").removeprefix("op ")
        coincide = (filas.Operacion.str.contains(filtro, case=False, regex=False)
                    | filas.Tipo.str.contains(filtro, case=False, regex=False)
                    | filas.Orden_OP.astype(str).str.contains(filtro, regex=False))
        filas = filas.loc[coincide]
    columnas = {c: st.column_config.NumberColumn(f"{c} (h)", format="%.1f")
                for c in ("TBF", "TAP", "DES", "SAT", "TAI", "TR", "Induce_vecinos")}
    columnas.update({
        "Orden_OP": "Orden OP", "Operacion": "Operación",
        "Dp": st.column_config.NumberColumn("Dp (%)", format="%.1f"),
        "Tcy": st.column_config.NumberColumn("Tcy (cmin)", format="%.1f"),
        "Fpm": st.column_config.NumberColumn("Fpm (paros / 1000 piezas)", format="%.1f"),
        "Indice": st.column_config.NumberColumn("Índice", format="%.1f"),
        "%TAP": st.column_config.NumberColumn("TAP / TR (%)", format="%.1f"),
        "%TAI": st.column_config.NumberColumn("TAI / TR (%)", format="%.1f"),
    })
    st.dataframe(filas, column_config=columnas, width="stretch", height=540, hide_index=True)
    if filas.empty:
        st.caption("Ninguna operación coincide con la búsqueda.")
    st.caption("TBF: funcionamiento. TAP: parada propia. DES: desabastecimiento. SAT: saturación. "
               "TAI: DES + SAT. TR: TBF + TAP + TAI. Dp: disponibilidad. Tcy: tiempo de ciclo.")
    if datos_locales and INFORME.exists():
        with st.expander("Informe de limpieza de datos"):
            st.text(INFORME.read_text(encoding="utf-8"))


def menu():
    with st.popover("Opciones", icon=":material/more_horiz:", key="acciones", on_change="rerun"):
        for destino, etiqueta in (("inicio", "Inicio"), ("detalle", "Detalle por máquina"), ("datos", "Tabla de datos")):
            st.button(etiqueta, on_click=navegar, args=(destino,), kwargs={"cerrar_menu": True}, width="stretch")
        st.button("Restablecer filtros", on_click=restablecer_filtros, width="stretch")
        with st.expander("Configuración de datos"):
            st.caption("Fuente predeterminada: CSV de Datos_limpios generados por limpieza.py.")
            datos = st.file_uploader("CSV de datos (limpio)", type="csv")
            config = st.file_uploader("CSV de configuración (si falta Orden_OP)", type="csv")
            incluidas = st.toggle("Solo operaciones incluidas", value=True,
                                  help="Aplica el indicador incluir_analisis del CSV.")
            excluir_tap = st.toggle("Excluir días con TAP sospechoso", value=False,
                                    help="Excluye las filas con flag_tap_sospechoso de todos los indicadores.")
    return datos, config, incluidas, excluir_tap


vista = st.session_state.get("vista", "inicio")
titulo = {"inicio": "Resumen de la línea", "detalle": "Detalle por máquina", "datos": "Tabla de datos"}
with st.container(key="cabecera"):
    cabecera, acciones = st.columns([1, 0.38], vertical_alignment="top")
    with cabecera:
        contexto = st.empty()
    with acciones, st.container(key="cabecera_acciones", horizontal=True,
                               horizontal_alignment="right", vertical_alignment="center",
                               gap="small", wrap=False):
        logo = b64encode((APP / "assets" / "horse.png").read_bytes()).decode("ascii")
        st.html(f'<img class="horse" src="data:image/png;base64,{logo}" alt="HORSE">', width="content")
        descarga = st.empty()
        up_datos, up_config, solo_incluidas, excl_tap = menu()

fuente = (up_datos.file_id if up_datos else None, up_config.file_id if up_config else None)
if fuente != st.session_state.get("fuente"):
    restablecer_filtros()
    st.session_state.fuente = fuente
try:
    df = cargar(up_datos if up_datos is not None else DEFAULT_DATOS,
                up_config if up_config is not None else DEFAULT_CONFIG)
    if df.empty:
        raise ValueError("El CSV no contiene filas válidas tras cruzar la configuración.")
except (OSError, KeyError, ValueError, TypeError) as exc:
    st.error(f"No se puede cargar la fuente. Revisa los CSV en Opciones → Configuración de datos. {exc}")
    st.stop()

f, fechas, inicio, fin, rango = filtros(df)
if solo_incluidas:
    f = f[f.incluir_analisis]
if excl_tap:
    f = f[~f.flag_tap_sospechoso]

k = kpis(f)
n_ops = k.Operacion.nunique()
unidades = "operación" if n_ops == 1 else "operaciones"
periodo = f"{fmt_fecha(inicio, inicio.year != fin.year)} – {fmt_fecha(fin, anio=True)}"
nombre_vista = titulo.get(vista) or VISTAS[vista][1]
contexto.html(
    f'<div class="header-line">Línea 5 · Montaje Valladolid</div><h1>{nombre_vista}</h1>'
    f'<div class="header-context"><span>{icono("calendario")}{periodo}</span>'
    f'<span>OP {rango[0]} – {rango[1]}</span><span>{n_ops} {unidades}</span></div>'
)
descarga.download_button("Descargar CSV", k[COLUMNAS].to_csv(index=False).encode("utf-8"),
                         file_name="kpis_lossia.csv", mime="text/csv", disabled=k.empty,
                         icon=":material/download:", on_click="ignore", key="descarga")
datos_locales = up_datos is None and up_config is None
alertas_op = _alertas_por_op() if datos_locales else {}
registro_op = _registro_por_op() if datos_locales else {}

if vista != "inicio":
    st.button("Resumen de la línea", icon=":material/arrow_back:", type="tertiary",
              on_click=navegar, args=("inicio",), key="volver")

if k.empty:
    st.warning("No hay datos para los filtros seleccionados.")
    st.button("Restablecer filtros", on_click=restablecer_filtros, key="restablecer_vacio")
    if vista == "inicio":
        calidad(alertas_op, registro_op, datos_locales)
        accesos()
elif vista == "inicio":
    resumen(k, alertas_op, registro_op, datos_locales)
    accesos()
elif vista == "detalle":
    detalle(k, f, fechas, alertas_op, registro_op)
elif vista == "datos":
    tabla(k, datos_locales)
else:
    selector_grafico(vista)
    mostrar_grafico(vista, k, f, abrir_detalle=abrir_detalle, dp_min=DP_MIN, tcy_max=TCY_MAX)
