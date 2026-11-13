"""
LOSSIA · Línea 5, Montaje Valladolid.

Capa de PRESENTACIÓN únicamente. Todo el cálculo analítico (KPIs, método de
flechas, prioridades y mantenimiento) vive en `lossia/` y se ejecuta igual que
en `analisis.py`; esta app no recalcula nada por su cuenta — ver `lossia/interfaz.py`.

Unidad de análisis: la ETAPA (una o varias operaciones en paralelo fusionadas).
El tramo de línea, el tipo de operación y la selección de máquinas filtran solo
la PRESENTACIÓN (qué filas se muestran); nunca se usan para recortar la cadena
antes del método de flechas, que necesita la línea completa y consecutiva.
"""
from base64 import b64encode
from datetime import date, timedelta
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

APP = Path(__file__).resolve().parent
REPO = APP.parent
sys.path.insert(0, str(REPO))

from lossia import config as LC, interfaz as LI  # noqa: E402
from graficos import mostrar_grafico  # noqa: E402

DIR_LIMPIOS = LC.DIR_LIMPIOS
DIR_RESULTADOS = LC.DIR_RESULTADOS
ALERTAS = DIR_LIMPIOS / "alertas.json"
REGISTRO = DIR_LIMPIOS / "registro_limpieza.json"
INFORME = DIR_LIMPIOS / "informe_limpieza.txt"

TCY_MAX = LC.TCY_MAX_CMIN     # cmin — única fuente de verdad: lossia/config.py
DP_MIN = LC.DP_MIN * 100      # % — lossia/config.py guarda la fracción (0.90)

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
    "disponibilidad": ("Objetivos", "Disponibilidad por etapa"),
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
            "%TAP", "%TAI", "Dp", "Tcy", "Fpm", "Induce_vecinos", "Severidad", "Categoria"]

st.set_page_config(page_title="LOSSIA · Línea 5", layout="wide")
st.html(APP / "lossia.css")


def fmt_fecha(d, anio=False):
    return f"{d.day} {MESES[d.month - 1]}" + (f" {d.year}" if anio else "")


# ----------------------------------------------------------------------------
# Motor oficial: carga única de los datos en bruto + recálculo por selección de días.
# La caché se invalida sola si cambian los CSV/JSON de Datos_limpios/ (por `firma`).
# ----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Cargando datos de la línea…")
def _motor(firma):
    return LI.cargar_motor(DIR_LIMPIOS)


def motor_actual() -> LI.Motor:
    return _motor(LI.firma_fuentes(DIR_LIMPIOS))


@st.cache_data(show_spinner=False)
def _resultado_cacheado(firma, firma_resultados, dias):
    # `firma_resultados` solo se usa como parte de la clave de caché: si se regenera
    # Resultados/ (botón "Regenerar Resultados/"), cambia y la caché se invalida sola.
    motor = _motor(firma)
    return LI.calcular(motor, list(dias) if dias else None)


def resultado_para(motor: LI.Motor, dias) -> LI.Resultado:
    firma_res = LI.resultados_firma(DIR_RESULTADOS)
    return _resultado_cacheado(motor.firma, firma_res, tuple(sorted(dias)) if dias else None)


@st.cache_data(show_spinner=False)
def _con_fecha(firma):
    motor = _motor(firma)
    e = motor.etapa_dia.copy()
    e["Fecha"] = [date.fromisocalendar(int(y), int(w), int(d))
                  for y, w, d in zip(e.Year, e.Week, e.Jour)]
    return e


def etapa_dia_con_fecha(motor: LI.Motor) -> pd.DataFrame:
    return _con_fecha(motor.firma)


@st.cache_data(show_spinner=False)
def cargar_json(ruta: str) -> dict:
    p = Path(ruta)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _alertas() -> list[dict]:
    return cargar_json(str(ALERTAS)).get("alertas", [])


def _registro_por_operacion() -> dict:
    out = {}
    for e in cargar_json(str(REGISTRO)).get("entradas", []):
        out.setdefault(e.get("operacion"), []).append(e)
    return out


def construir_vista(resultado: LI.Resultado) -> pd.DataFrame:
    """Tabla única por etapa para presentación: KPIs oficiales + columnas del método
    de flechas y de prioridades, sin ningún cálculo propio. Solo renombra/escala para
    mostrar (Dp y los % eran fracciones 0–1 en el motor; aquí se expresan en %)."""
    if resultado.kpis.empty:
        return resultado.kpis.assign(**{c: [] for c in COLUMNAS if c not in resultado.kpis.columns})

    extra = resultado.prioridades[["Etapa", "categoria", "motivo", "orden_vista", "rango_mant",
                                    "es_cuello", "es_relevante", "severidad", "horas_inducidas",
                                    "rango_det"]]
    k = resultado.kpis.merge(extra, on="Etapa", how="left")
    k = k.rename(columns={
        "Etapa": "Operacion", "Orden_etapa": "Orden_OP", "Tcy_cmin": "Tcy",
        "horas_inducidas": "Induce_vecinos", "severidad": "Severidad",
        "es_cuello": "Es_cuello", "es_relevante": "Es_relevante", "rango_det": "Rango_det",
        "categoria": "Categoria", "motivo": "Motivo",
    })
    k["Es_principal"] = k["Rango_det"] == 1
    k["Dp"] = k["Dp"] * 100
    for c in ("TAP", "DES", "SAT", "TAI"):
        k[f"%{c}"] = k.pop(f"pct_{c}") * 100
    k["%TBF"] = 100 * k["TBF"] / k["TR"].replace(0, np.nan)  # no está en kpis.calcular (solo paradas)
    k["Incumple_Dp"] = ~k["cumple_Dp"]
    k["Incumple_Tcy"] = k["cumple_Tcy"].eq(False)  # NaN (sin dato) -> False, no cuenta como incumplimiento
    return k.sort_values("Orden_OP").reset_index(drop=True)


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


def filtros(motor: LI.Motor):
    """Filtros de la barra lateral.
    - Periodo + días de la semana seleccionan los DÍAS que entran en el recálculo oficial
      (kpis/método de flechas se recomputan sobre exactamente esos días, igual que haría
      `analisis.py` para ese rango — nunca se suman/promedian resultados ya agregados).
    - Tipo, tramo de línea y máquinas son filtros de PRESENTACIÓN: no tocan el cálculo,
      solo qué filas de la tabla ya calculada (sobre la línea completa) se muestran.
    """
    ed = etapa_dia_con_fecha(motor)
    with st.sidebar:
        st.html('<div class="lossia-brand"><i aria-hidden="true"><b></b><b></b><b></b><b></b></i>LOSSIA</div>')
        inicio, fin = filtro_periodo(ed.Fecha.min(), ed.Fecha.max())
        mascara_fecha = ed.Fecha.between(inicio, fin)
        dias_sem = sorted(int(d) for d in ed.Jour.unique())

        def completar_dias():
            if not st.session_state.sel_dia:
                st.session_state.sel_dia = dias_sem

        with st.container(key="dias"):
            seleccion_dia = st.pills("Días de la semana", dias_sem, selection_mode="multi",
                                     default=dias_sem, format_func=DIAS.__getitem__, key="sel_dia",
                                     on_change=completar_dias, wrap=len(dias_sem) > 5)
        mascara_fecha &= ed.Jour.isin(seleccion_dia or dias_sem)
        dias_seleccionados = sorted(ed.loc[mascara_fecha, "Dia"].unique().tolist())

        st.caption("Tipo, tramo y máquinas filtran solo lo que se muestra; el método de "
                   "flechas se calcula siempre sobre la línea completa.", help=None)
        tipos = sorted(motor.mapa_etapas.Tipo.dropna().unique())
        with st.container(key="tipos"):
            seleccion_tipo = st.multiselect(
                "Tipo de operación", tipos, format_func=lambda t: TIPOS.get(t, t),
                key="sel_tipo", placeholder="Todas")
        minimo, maximo = int(motor.mapa_etapas.Orden_etapa.min()), int(motor.mapa_etapas.Orden_etapa.max())
        with st.container(key="tramo"):
            if minimo == maximo:
                st.markdown(f"**Tramo de la línea** · OP {minimo}")
                rango = (minimo, maximo)
            else:
                rango = st.slider("Tramo de la línea", minimo, maximo, (minimo, maximo),
                                  key="rango_op", format="OP %d")
        alcance_etapas = motor.mapa_etapas[
            motor.mapa_etapas.Orden_etapa.between(*rango)
            & motor.mapa_etapas.Tipo.isin(seleccion_tipo or tipos)
        ]["Etapa"].unique().tolist()
        opciones = sorted(alcance_etapas, key=lambda e: motor.mapa_etapas.loc[
            motor.mapa_etapas.Etapa == e, "Orden_etapa"].iloc[0])
        vigentes = [op for op in st.session_state.get("sel_operaciones", []) if op in opciones]
        if vigentes != st.session_state.get("sel_operaciones", []):
            st.session_state.sel_operaciones = vigentes
        with st.container(key="maquinas"):
            seleccion_op = st.multiselect(
                "Máquinas / Operaciones", opciones, key="sel_operaciones",
                placeholder="Todas", help="Busca por identificador de etapa. Vacía la selección para incluir todas.")
        etapas_mostradas = seleccion_op or opciones
    return dias_seleccionados, etapas_mostradas, inicio, fin, rango


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
        "llave": '<path d="M14.5 6.5a4 4 0 1 0 0 5.66L17 14.5l1.5-1.5L17 11.5l1.5-1.5L17 8.5 18.5 7 17 5.5l-2.5 1Z"/>',
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


def _cuerpo_alerta(a: dict, registro: list | None = None):
    """Contenido detallado (causas y consecuencias). Nunca se muestra el JSON en bruto;
    los datos numéricos se formatean como texto, no con st.json."""
    d = a.get("detalle", {})
    if d.get("efecto_observado"):
        st.markdown(f"**Evidencia / qué se observa:** {d['efecto_observado']}")
    if d.get("causa_probable"):
        st.markdown(f"**Causa probable:** {d['causa_probable']}")
    if d.get("otras_causas_posibles"):
        st.markdown("**Otras causas posibles:**\n" +
                    "\n".join(f"- {c}" for c in d["otras_causas_posibles"]))
    if d.get("impacto_en_el_analisis"):
        st.markdown(f"**Consecuencia analítica:** {d['impacto_en_el_analisis']}")
    if d.get("recomendacion"):
        st.info(f"**Recomendación:** {d['recomendacion']}")
    if d.get("dias_afectados"):
        st.caption(f"Días afectados ({len(d['dias_afectados'])}): " + ", ".join(d["dias_afectados"]))
    if d.get("datos"):
        pares = " · ".join(f"**{k}**: {v}" for k, v in d["datos"].items())
        st.caption(pares)
    if registro:
        st.markdown("**Tratamiento aplicado en la limpieza:**")
        for e in registro:
            st.markdown(f"- {e.get('descripcion', '')} → *{str(e.get('accion', '')).replace('_', ' ')}* "
                        f"({e.get('filas_afectadas', 0)} filas)")


def kpis_cabecera(k: pd.DataFrame):
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
    sin_tcy = int(k.Tcy.isna().sum())
    aclaracion_tcy = f" · {sin_tcy} sin dato" if sin_tcy else ""
    st.html(
        '<div class="kpis" aria-label="Indicadores de la línea">'
        + indicador(gauge, disponibilidad, "Disponibilidad media (Dp)", delta_html)
        + indicador(icono("objetivo"), f"{dp} / {len(k)}", f"Por debajo del {DP_MIN:g} % de Dp")
        + indicador(icono("reloj"), f"{tcy} / {len(k)}", f"Por encima de {TCY_MAX:g} cmin{aclaracion_tcy}")
        + "</div>"
    )


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


def insights(k: pd.DataFrame, resultado: LI.Resultado):
    """Conclusiones del motor oficial (determinista + mantenimiento), no una repetición
    de los KPI de cabecera. Se calculan siempre sobre la línea completa seleccionada por
    días (no sobre el recorte de tramo/tipo/máquinas, que es solo de presentación)."""
    with st.container(key="insights"):
        st.html(f'<h2>{icono("destellos")} Insights principales</h2>')
        c1, c2, c3 = st.columns(3)
        with c1:
            principales = k.loc[k.Es_principal.fillna(False) & k.Es_relevante.fillna(False)]
            if not principales.empty:
                fila = principales.iloc[0]
                insight("subida", "Cuello de botella (método de flechas)",
                        f"Severidad {fila.Severidad:.0%} · {fila.Induce_vecinos:.1f} h inducidas "
                        "a sus vecinas en el periodo.", fila.Operacion)
            else:
                insight("subida", "Cuello de botella", "Sin un cuello relevante en los días seleccionados.")
        with c2:
            mant = resultado.mantenimiento
            top_mant = mant.loc[mant.rango_mant == 1] if not mant.empty else mant
            if not top_mant.empty:
                fila = top_mant.iloc[0]
                insight("llave", "Prioridad de mantenimiento",
                        f"{fila.TAP_medio_dia:.1f} h/día de parada propia (TAP).", fila.Etapa)
            else:
                insight("llave", "Prioridad de mantenimiento", "Sin datos suficientes.")
        with c3:
            baja_dp = k.loc[k.Incumple_Dp].nsmallest(1, "Dp")
            alto_ciclo = k.loc[k.Incumple_Tcy].nlargest(1, "Tcy")
            if not baja_dp.empty:
                fila = baja_dp.iloc[0]
                insight("aviso", "Menor disponibilidad", f"Dp de {fila.Dp:.1f} %.", fila.Operacion)
            elif not alto_ciclo.empty:
                fila = alto_ciclo.iloc[0]
                insight("reloj", "Mayor tiempo de ciclo", f"{fila.Tcy:.1f} cmin.", fila.Operacion)
            else:
                texto = "Todas las Dp y Tcy calculables cumplen objetivo." if k.Dp.notna().any() else "Sin datos suficientes."
                insight("aviso", "Objetivos", texto)


def calidad(datos_locales: bool):
    """Panel de calidad de datos: lista vertical con todas las incidencias (alertas.json),
    cada una expandible; nunca se muestra el JSON en bruto. Las alertas son por operación
    y no cambian con los filtros del periodo/tramo (son propiedades de los datos, no de
    la selección)."""
    lista = sorted(_alertas(), key=lambda a: (a.get("nivel") != "error", a.get("orden_op") or 0))
    registro_op = _registro_por_operacion()
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
        st.caption(f"{len(lista)} incidencias para la línea completa (no cambian con los filtros "
                   "del periodo, el tramo ni las máquinas).")
        c1, c2 = st.columns([1.3, 2])
        with c1:
            nivel = st.radio("Gravedad", ["Todas", "Errores", "Advertencias"], horizontal=True, key="calidad_nivel")
        with c2:
            busqueda = st.text_input("Buscar por código de operación o título", key="calidad_busqueda",
                                     placeholder="p. ej. ST_0030", label_visibility="visible")
        filtradas = [
            a for a in lista
            if (nivel == "Todas" or (a.get("nivel") == "error") == (nivel == "Errores"))
            and (not busqueda.strip() or busqueda.strip().lower() in
                 f"{a.get('id', '')} {a.get('operacion', '')} {a.get('titulo', '')}".lower())
        ]
        st.caption(f"Mostrando {len(filtradas)} de {len(lista)}.")
        for a in filtradas:
            invalidante = a.get("nivel") == "error"
            icono_sev = "🔴" if invalidante else "🟠"
            with st.container(key=f"alerta_{a['id']}", border=True):
                st.markdown(f"{icono_sev} **{a.get('operacion') or 'Línea'}** · `{a['id']}` — {a.get('titulo', '')}")
                resumen_corto = (a.get("resumen") or "")
                st.caption(resumen_corto[:160] + ("…" if len(resumen_corto) > 160 else ""))
                st.caption("Invalidante: excluye la operación del análisis." if invalidante
                           else "Advertencia: no invalida la operación, pero conviene revisarla.")
                with st.expander("Ver detalle"):
                    _cuerpo_alerta(a, registro_op.get(a.get("operacion")))
        if not filtradas:
            st.caption("Ninguna incidencia coincide con el filtro.")


def accesos():
    with st.container(key="visualizaciones"):
        st.html("<h2>Visualizaciones</h2>")
        with st.container(key="tarjetas"):
            for vista, nombre in ACCESOS.items():
                st.button(nombre, key=f"acceso_{vista}", width="stretch",
                          on_click=navegar, args=(vista,))


def selector_grafico(vista, k, motor, dias_sel):
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
    if k.empty:
        st.info("No hay etapas en la selección para dibujar esta visualización.")
        return
    mostrar_grafico(vista, k, etapa_dia_con_fecha(motor), abrir_detalle=abrir_detalle,
                    dp_min=DP_MIN, tcy_max=TCY_MAX, fechas=dias_sel)


def detalle(motor, k, resultado, fechas):
    ops = k.Operacion.drop_duplicates().tolist()
    if not ops:
        st.warning("No hay etapas en la selección actual.")
        return
    if st.session_state.get("operacion_detalle") not in ops:
        candidatas = k.loc[k.Es_principal.fillna(False)]
        st.session_state.operacion_detalle = (candidatas.iloc[0].Operacion if not candidatas.empty
                                              else k.iloc[0].Operacion)
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
    maquinas = LI.maquinas_de(motor, op)
    if len(maquinas) > 1:
        st.caption(f"Etapa con {len(maquinas)} operaciones en paralelo: {', '.join(maquinas)} "
                   "(tiempos promediados, piezas y paradas sumadas).")
    posicion = fila.Rango_det if pd.notna(fila.Rango_det) else None
    medidas = [
        ("Orden en línea", f"OP {int(fila.Orden_OP)}", None),
        ("Disponibilidad", f"{fila.Dp:.1f} %" if pd.notna(fila.Dp) else "—",
         f"{fila.Dp - DP_MIN:+.1f} pp" if pd.notna(fila.Dp) else None),
        ("Tiempo de ciclo", f"{fila.Tcy:.1f} cmin" if pd.notna(fila.Tcy) else "—",
         f"{fila.Tcy - TCY_MAX:+.1f} cmin" if pd.notna(fila.Tcy) else None),
        ("Fpm", f"{fila.Fpm:.1f}" if pd.notna(fila.Fpm) else "—", None),
        ("Puesto · método de flechas", str(int(posicion)) if posicion is not None else "fuera de cadena", None),
    ]
    with st.container(key="metricas_detalle", horizontal=True, gap="small"):
        for etiqueta, valor, delta in medidas:
            st.metric(etiqueta, valor, delta, border=True,
                      delta_color="inverse" if etiqueta == "Tiempo de ciclo" else "normal")
    if pd.notna(fila.Motivo) and fila.Motivo:
        st.info(f"**Motivo de prioridad:** {fila.Motivo}")

    alertas_op = [a for a in _alertas() if a.get("operacion") in maquinas]
    registro_op_todo = _registro_por_operacion()
    for alerta in alertas_op:
        with st.popover(alerta.get("titulo", alerta["id"]), icon=":material/warning:"):
            _cuerpo_alerta(alerta, registro_op_todo.get(alerta.get("operacion")))
    if not alertas_op and any(registro_op_todo.get(m) for m in maquinas):
        with st.expander("Tratamiento aplicado en la limpieza"):
            for m in maquinas:
                for entrada in registro_op_todo.get(m, []):
                    st.write(entrada.get("descripcion", ""))
    grafico = st.segmented_control("Visualización de la operación", ["diaria", "vecinas"],
                                   default="diaria", key="detalle_grafico",
                                   format_func=lambda v: {"diaria": "Evolución diaria", "vecinas": "Operaciones vecinas"}[v],
                                   label_visibility="collapsed")
    ed = etapa_dia_con_fecha(motor)
    mostrar_grafico(grafico or "diaria", k, ed, op=op, dp_min=DP_MIN, tcy_max=TCY_MAX, fechas=fechas)


def tabla(k: pd.DataFrame, datos_locales: bool):
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
        "Orden_OP": "Orden OP", "Operacion": "Etapa",
        "Dp": st.column_config.NumberColumn("Dp (%)", format="%.1f"),
        "Tcy": st.column_config.NumberColumn("Tcy (cmin)", format="%.1f"),
        "Fpm": st.column_config.NumberColumn("Fpm (paros / 1000 piezas)", format="%.1f"),
        "Severidad": st.column_config.NumberColumn("Severidad (flechas)", format="%.2f"),
        "%TAP": st.column_config.NumberColumn("TAP / TR (%)", format="%.1f"),
        "%TAI": st.column_config.NumberColumn("TAI / TR (%)", format="%.1f"),
    })
    st.dataframe(filas, column_config=columnas, width="stretch", height=540, hide_index=True)
    if filas.empty:
        st.caption("Ninguna operación coincide con la búsqueda.")
    st.caption("TBF: funcionamiento. TAP: parada propia. DES: desabastecimiento. SAT: saturación. "
               "TAI: DES + SAT. TR: TBF + TAP + TAI. Dp: disponibilidad. Tcy: tiempo de ciclo. "
               "Severidad y Categoría: método de flechas / prioridades oficiales (lossia/).")
    if datos_locales and INFORME.exists():
        with st.expander("Informe de limpieza de datos"):
            st.text(INFORME.read_text(encoding="utf-8"))


def menu():
    with st.popover("Opciones", icon=":material/more_horiz:", key="acciones", on_change="rerun"):
        for destino, etiqueta in (("inicio", "Inicio"), ("detalle", "Detalle por máquina"), ("datos", "Tabla de datos")):
            st.button(etiqueta, on_click=navegar, args=(destino,), kwargs={"cerrar_menu": True}, width="stretch")
        st.button("Restablecer filtros", on_click=restablecer_filtros, width="stretch")
        desactualizado = LI.resultados_desactualizados(DIR_LIMPIOS, DIR_RESULTADOS)
        if desactualizado:
            st.caption(":orange[Resultados/ en disco está desactualizado respecto a Datos_limpios/. "
                       "La interfaz no se ve afectada (recalcula siempre en vivo desde Datos_limpios/), "
                       "pero conviene regenerarlo para otros consumidores (CLI, exportaciones).]")
            if st.button("Regenerar Resultados/", width="stretch"):
                import analisis
                with st.spinner("Ejecutando analisis.py…"):
                    analisis.main(DIR_LIMPIOS, DIR_RESULTADOS)
                st.cache_data.clear()
                st.success("Resultados/ actualizado.")


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
        menu()

try:
    motor = motor_actual()
except (OSError, KeyError, ValueError, TypeError) as exc:
    st.error(f"No se pueden cargar los datos oficiales de {DIR_LIMPIOS}. {exc}")
    st.stop()

dias_sel, etapas_mostradas, inicio, fin, rango = filtros(motor)
resultado = resultado_para(motor, dias_sel)
k_completa = construir_vista(resultado)
k = k_completa[k_completa.Operacion.isin(etapas_mostradas)].reset_index(drop=True)

n_ops = int(motor.mapa_etapas.loc[motor.mapa_etapas.Etapa.isin(k.Operacion), "Operacion_norm"].nunique()) if len(k) else 0
unidades = "operación" if n_ops == 1 else "operaciones"
periodo = f"{fmt_fecha(inicio, inicio.year != fin.year)} – {fmt_fecha(fin, anio=True)}"
nombre_vista = titulo.get(vista) or VISTAS[vista][1]
if resultado.fuente == LI.PERSISTIDOS:
    fuente_txt = "Resultados/ (referencia oficial)"
else:
    n_dias_calc = len(resultado.dias)
    fuente_txt = (f"Cálculo en vivo · {n_dias_calc} día{'s' if n_dias_calc != 1 else ''} "
                  "(sin equivalente persistido)")
contexto.html(
    f'<div class="header-line">Línea 5 · Montaje Valladolid</div><h1>{nombre_vista}</h1>'
    f'<div class="header-context"><span>{icono("calendario")}{periodo}</span>'
    f'<span>OP {rango[0]} – {rango[1]}</span><span>{len(k)} etapas · {n_ops} {unidades}</span>'
    f'<span title="Trazabilidad: de dónde vienen los KPI y el método de flechas de esta selección">'
    f'{fuente_txt}</span></div>'
)
descarga.download_button("Descargar CSV", k[COLUMNAS].to_csv(index=False).encode("utf-8"),
                         file_name="kpis_lossia.csv", mime="text/csv", disabled=k.empty,
                         icon=":material/download:", on_click="ignore", key="descarga")
datos_locales = True

if vista != "inicio":
    st.button("Resumen de la línea", icon=":material/arrow_back:", type="tertiary",
              on_click=navegar, args=("inicio",), key="volver")

if k.empty:
    st.warning("No hay datos para los filtros seleccionados.")
    st.button("Restablecer filtros", on_click=restablecer_filtros, key="restablecer_vacio")
    if vista == "inicio":
        calidad(datos_locales)
        accesos()
elif vista == "inicio":
    kpis_cabecera(k)
    insights(k, resultado)
    calidad(datos_locales)
    accesos()
elif vista == "detalle":
    detalle(motor, k, resultado, dias_sel)
elif vista == "datos":
    tabla(k, datos_locales)
else:
    selector_grafico(vista, k, motor, dias_sel)
