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
from html import escape
from datetime import date, timedelta
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

APP = Path(__file__).resolve().parent
REPO = APP.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "simulador"))

from lossia import config as LC, interfaz as LI  # noqa: E402
from graficos import mostrar_grafico  # noqa: E402
from centros import CENTROS  # noqa: E402

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

st.set_page_config(page_title="LOSSIA", layout="wide")
st.html(APP / "lossia.css")


def fmt_fecha(d, anio=False):
    return f"{d.day} {MESES[d.month - 1]}" + (f" {d.year}" if anio else "")


# ----------------------------------------------------------------------------
# Motor oficial: carga única de los datos en bruto + recálculo por selección de días.
# La caché se invalida sola si cambian los CSV/JSON de Datos_limpios/ (por `firma`).
# ----------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)  # sin spinner: se pinta junto al logo y lo desplaza
def _motor(centro, linea, dir_limpios, firma):
    return LI.cargar_motor(Path(dir_limpios))


def motor_actual() -> LI.Motor:
    return _motor(centro_activo, linea_activa, str(DIR_LIMPIOS), LI.firma_fuentes(DIR_LIMPIOS))


@st.cache_data(show_spinner=False)
def _resultado_cacheado(centro, linea, dir_limpios, dir_resultados, firma, firma_resultados, dias):
    # `firma_resultados` solo se usa como parte de la clave de caché: si se regenera
    # Resultados/ (botón "Regenerar Resultados/"), cambia y la caché se invalida sola.
    motor = _motor(centro, linea, dir_limpios, firma)
    return LI.calcular(motor, list(dias) if dias else None, dir_resultados=Path(dir_resultados))


def resultado_para(motor: LI.Motor, dias) -> LI.Resultado:
    firma_res = LI.resultados_firma(DIR_RESULTADOS)
    return _resultado_cacheado(centro_activo, linea_activa, str(DIR_LIMPIOS), str(DIR_RESULTADOS),
                               motor.firma, firma_res, tuple(sorted(dias)) if dias else None)


@st.cache_data(show_spinner=False)
def _con_fecha(centro, linea, dir_limpios, firma):
    motor = _motor(centro, linea, dir_limpios, firma)
    e = motor.etapa_dia.copy()
    e["Fecha"] = [date.fromisocalendar(int(y), int(w), int(d))
                  for y, w, d in zip(e.Year, e.Week, e.Jour)]
    return e


def etapa_dia_con_fecha(motor: LI.Motor) -> pd.DataFrame:
    return _con_fecha(centro_activo, linea_activa, str(DIR_LIMPIOS), motor.firma)


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

        tipos = sorted(motor.mapa_etapas.Tipo.dropna().unique())
        with st.container(key="tipos"):
            seleccion_tipo = st.multiselect(
                "Tipo de operación", tipos, format_func=lambda t: TIPOS.get(t, t),
                key="sel_tipo", placeholder="Todas")
        espacio_maquinas = st.container(key="maquinas")
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
        with espacio_maquinas:
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
        "barras": '<path stroke-width="2.6" d="M4 19v-4m5 4v-8m5 8V7m5 12V3"/>',
        "subida": '<path d="m3 17 6-6 4 4 8-8m-6 0h6v6"/>',
        "aviso": '<path d="M10.3 4.5 3 18a1.5 1.5 0 0 0 1.3 2.2h15.4A1.5 1.5 0 0 0 21 18L13.7 4.5a2 2 0 0 0-3.4 0ZM12 9v4m0 3h.01"/>',
        "llave": '<path d="M14.7 6.3a5 5 0 0 0-6.4 6.4l-5.7 5.7a2.1 2.1 0 0 0 3 3l5.7-5.7a5 5 0 0 0 6.4-6.4l-3.2 3.2-3-3Z"/>',
    }
    color = "#B8441F" if nombre == "subida" else "#0A2540"
    return imagen_svg(
        "lossia-icon",
        f'<g fill="none" stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">'
        f'{trazados[nombre]}</g>',
    )


def _cuerpo_alerta(a: dict, registro: list | None = None):
    """Contenido detallado (causas y consecuencias). Nunca se muestra el JSON en bruto;
    los datos numéricos se formatean como texto, no con st.json."""
    with st.container(key=f"cuerpo_alerta_{a['id']}"):
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
            recomendacion = escape(str(d["recomendacion"]))
            st.html(f'<p class="alerta-recomendacion"><strong>Recomendación:</strong> {recomendacion}</p>')
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



@st.cache_data(show_spinner=False)
def fechas_alertas(ruta: str, firma: tuple) -> pd.DataFrame:
    datos = pd.read_csv(ruta, usecols=["Operacion", "Year", "Week", "Jour"])
    return datos.drop_duplicates()


def calendario_alerta(alerta: dict, dias: list, datos: pd.DataFrame):
    def periodo(valor):
        coincidencia = re.fullmatch(r"S(\d{1,2})-D([1-7])", str(valor))
        return tuple(map(int, coincidencia.groups())) if coincidencia else None

    afectados = [periodo(dia) for dia in dias]
    registros = datos.loc[datos.Operacion.eq(alerta.get("operacion"))]
    anios = registros.Year.dropna().unique()
    if not dias or any(dia is None for dia in afectados) or len(anios) != 1:
        if dias:
            st.html('<p class="calidad-periodos"><strong>Periodos afectados</strong> '
                    + escape(", ".join(str(dia) for dia in dias)) + "</p>")
        return

    anio = int(anios[0])
    observados = {(int(fila.Week), int(fila.Jour)) for fila in registros.itertuples()}
    afectados = set(afectados)
    semanas = sorted({semana for semana, _ in observados} | {semana for semana, _ in afectados})
    dias_semana = sorted(set(range(1, 6)) | {dia for _, dia in observados | afectados})
    por_dia = (alerta.get("detalle", {}).get("datos") or {}).get("por_dia") or []
    detalles = {periodo(item.get("dia")): item for item in por_dia if isinstance(item, dict)}
    columnas = f"grid-template-columns: auto repeat({len(dias_semana)}, minmax(28px, 1fr))"
    celdas = ['<span></span>'] + [f'<span class="cal-dia">D{dia}</span>' for dia in dias_semana]
    for semana in semanas:
        celdas.append(f'<strong class="cal-semana">S{semana:02d}</strong>')
        for dia in dias_semana:
            clave = semana, dia
            clase = "afectado" if clave in afectados else "registrado" if clave in observados else "desconocido"
            estado = {"afectado": "Día afectado", "registrado": "Sin incidencia registrada",
                      "desconocido": "Sin información"}[clase]
            lineas = [f"S{semana:02d} · D{dia}", estado]
            if clave in observados:
                try:
                    lineas.append(date.fromisocalendar(anio, semana, dia).strftime("%d/%m/%Y"))
                except ValueError:
                    pass
            if clave in detalles:
                lineas.extend(f"{str(k).replace('_', ' ')}: {v}" for k, v in detalles[clave].items()
                              if k != "dia" and v is not None and isinstance(v, (str, int, float)))
            texto = " · ".join(lineas)
            tooltip = "".join(f"<span>{escape(linea)}</span>" for linea in lineas)
            extremo = "cal-fin" if dia == dias_semana[-1] else ""
            simbolo = ("!" if alerta.get("nivel") == "advertencia" else "×") if clase == "afectado" else (
                "–" if clase == "desconocido" else "")
            celdas.append(
                f'<div class="cal-celda {clase} {extremo}" tabindex="0" role="img" aria-label="{escape(texto, quote=True)}">'
                f'{simbolo}'
                f'<span class="cal-tooltip" aria-hidden="true">{tooltip}</span></div>'
            )
    gravedad = "advertencia" if alerta.get("nivel") == "advertencia" else "error"
    st.html(
        f'<div class="calendario-alerta {gravedad}"><div class="cal-titulo"><strong>Días afectados</strong>'
        f'<span>{len(afectados)} días</span></div>'
        f'<div class="cal-scroll"><div class="cal-matriz" style="{columnas}">{"".join(celdas)}</div></div>'
        '<div class="cal-leyenda"><span><i class="afectado"></i>Día afectado</span>'
        '<span><i class="registrado"></i>Sin incidencia registrada</span>'
        '<span><i class="desconocido"></i>Sin información</span></div></div>'
    )


def detalle_calidad(alerta: dict, registro: list | None = None):
    detalle = alerta.get("detalle") or {}
    dias = detalle.get("dias_afectados") or []
    impacto = detalle.get("impacto_en_el_analisis")
    causa = detalle.get("causa_probable")
    evidencia = detalle.get("efecto_observado")
    recomendacion = detalle.get("recomendacion")

    def celda(titulo, texto, clase=""):
        return (f'<div class="calidad-bloque {clase}"><strong>{escape(titulo)}</strong>'
                f'<p>{escape(str(texto))}</p></div>')

    def breve(texto):
        texto = str(texto).strip()
        if "sus datos no son fiables" in texto.lower():
            return "Datos no fiables"
        primera = re.split(r"(?<=[.!?])\s+|;", texto, maxsplit=1)[0]
        if len(primera) > 100:
            primera = primera[:97].rsplit(" ", 1)[0].rstrip(" ,:;") + "…"
        return primera

    bloques = [("Impacto", impacto, ""), ("Causa probable", causa, ""),
               ("Qué ocurre", evidencia, ""), ("Acción recomendada", recomendacion, "calidad-accion")]
    with st.container(key=f"diagnostico_layout_{alerta.get('id', 'alerta')}"):
        izquierda, derecha = st.columns([1.25, 1], gap="medium")
        with izquierda:
            contenido = [celda(titulo, breve(texto), clase) for titulo, texto, clase in bloques if texto]
            if contenido:
                st.html('<div class="calidad-diagnostico">' + "".join(contenido) + '</div>')
        with derecha:
            if dias:
                calendario_alerta(alerta, dias, fechas_alertas(str(DIR_LIMPIOS / "datos_limpios.csv"),
                                                             LI.firma_fuentes(DIR_LIMPIOS)))

    alternativas = detalle.get("otras_causas_posibles") or []
    datos = detalle.get("datos") or {}
    if alternativas or datos or registro or any((evidencia, impacto, causa, recomendacion)):
        with st.expander("Ver detalle técnico"):
            for titulo, texto in (("Evidencia", evidencia), ("Impacto en el análisis", impacto),
                                  ("Causa probable", causa), ("Acción recomendada", recomendacion)):
                if texto:
                    st.markdown(f"**{titulo}:** {texto}")
            if alternativas:
                st.markdown("**Otras causas posibles**")
                for alternativa in alternativas:
                    st.write(f"• {alternativa}")
            if datos:
                st.markdown("**Datos disponibles**")
                for clave, valor in datos.items():
                    st.write(f"{clave.replace('_', ' ')}: {valor}")
            if registro:
                st.markdown("**Tratamiento aplicado en la limpieza**")
                for entrada in registro:
                    st.write(f"{entrada.get('descripcion', '')} → "
                             f"{str(entrada.get('accion', '')).replace('_', ' ')} "
                             f"({entrada.get('filas_afectadas', 0)} filas)")


def medidor(valor):
    nivel = min(100, max(0, float(valor)))
    arco = "M10 56a48 48 0 0 1 96 0"
    progreso = (f'<path d="{arco}" stroke="#0A2540" pathLength="100" '
                f'stroke-dasharray="{nivel:.3f} 106"/>' if nivel else "")
    return imagen_svg(
        "gauge",
        '<g fill="none" stroke-width="13" stroke-linecap="round">'
        f'<path d="{arco}" stroke="#DED5BE"/>{progreso}</g>',
        "0 0 116 66",
    )


def kpis_cabecera(k: pd.DataFrame):
    media = k.Dp.mean()
    total = len(k)
    disponibilidad = f"{media:.1f} %" if pd.notna(media) else "—"
    dp = int(k.Dp.gt(DP_MIN).sum())
    tcy = int(k.Tcy.lt(TCY_MAX).sum())
    sin_tcy = int(k.Tcy.isna().sum())
    sin_dp = int(k.Dp.isna().sum())
    dp_pct = 100 * dp / total
    tcy_no = total - tcy - sin_tcy
    celdas = (
        '<span class="ciclo-celda ciclo-inferior"></span>' * tcy
        + '<span class="ciclo-celda ciclo-superior"></span>' * tcy_no
        + '<span class="ciclo-celda ciclo-ausente"></span>' * sin_tcy
    )
    anillo = imagen_svg(
        "kpi-anillo",
        '<circle cx="60" cy="60" r="45" fill="none" stroke="#DED5BE" stroke-width="12"/>'
        f'<circle cx="60" cy="60" r="45" fill="none" stroke="#0A2540" stroke-width="12" '
        f'stroke-dasharray="{dp_pct:.4f} 100" pathLength="100" '
        'transform="rotate(-90 60 60)"/>',
        "0 0 120 120",
    )
    gauge = medidor(media) if pd.notna(media) else ""
    nota_dp = f" · {sin_dp} sin dato" if sin_dp else ""
    st.html(
        '<div class="kpis" aria-label="Indicadores de la línea">'
        f'<div class="kpi"><div class="kpi-medidor">{gauge}</div>'
        f'<strong class="kpi-valor">{disponibilidad}</strong><span class="kpi-etiqueta">Disponibilidad media (Dp)</span></div>'
        f'<div class="kpi"><div class="kpi-anillo-contenedor">{anillo}<strong>{dp_pct:.0f} %</strong></div>'
        f'<strong class="kpi-valor">{dp} / {total}</strong>'
        f'<span class="kpi-etiqueta">Por encima del {DP_MIN:g} % de Dp{nota_dp}</span></div>'
        '<div class="kpi kpi-ciclo">'
        f'<div class="ciclo-titulo"><strong>Tiempo de ciclo</strong><span>Objetivo &lt; {TCY_MAX:g} cmin</span></div>'
        '<div class="ciclo-contenido">'
        f'<div class="ciclo-resultado"><strong class="kpi-valor">{tcy} / {total}</strong>'
        '<span class="kpi-etiqueta">Etapas por debajo</span></div>'
        f'<div class="ciclo-matriz" role="img" aria-label="{tcy} por debajo, {tcy_no} en el umbral o por encima, {sin_tcy} sin dato">{celdas}</div></div>'
        '<div class="ciclo-leyenda">'
        f'<span><i class="ciclo-inferior"></i>{tcy} por debajo</span>'
        f'<span><i class="ciclo-superior"></i>{tcy_no} ≥ {TCY_MAX:g}</span>'
        f'<span><i class="ciclo-ausente"></i>{sin_tcy} sin dato</span></div></div>'
        + "</div>"
    )


def insight(simbolo, titulo, *, op=None, metricas=(), ilustracion="", mensaje=""):
    with st.container(key=f"insight_{simbolo}"):
        st.html(f'<h3 class="insight-heading">{icono(simbolo)}{escape(titulo)}</h3>')
        if op is not None:
            st.button(str(op), key=f"op_{simbolo}", type="tertiary",
                      help=f"Abrir detalle de {op}", on_click=navegar, args=("detalle", op))
        if metricas:
            cifras = "".join(
                f'<div class="insight-metrica"><strong>{escape(valor)}</strong><span>{escape(etiqueta)}</span></div>'
                for valor, etiqueta in metricas
            )
            dibujo = f'<div class="insight-ilustracion">{ilustracion}</div>' if ilustracion else ""
            st.html(f'<div class="insight-cifras"><div class="insight-metricas">{cifras}</div>{dibujo}</div>')
        else:
            st.html(f'<p class="insight-text">{escape(mensaje)}</p>')


def insights(k: pd.DataFrame, resultado: LI.Resultado):
    """Conclusiones del motor oficial (determinista + mantenimiento), no una repetición
    de los KPI de cabecera. Se calculan siempre sobre la línea completa seleccionada por
    días (no sobre el recorte de tramo/tipo/máquinas, que es solo de presentación)."""
    with st.container(key="insights"):
        st.html(f'<h2>{icono("barras")} Insights principales</h2>')
        c1, c2, c3 = st.columns([1.25, 1, 1])
        with c1:
            principales = k.loc[k.Es_principal.fillna(False) & k.Es_relevante.fillna(False)]
            if not principales.empty:
                fila = principales.iloc[0]
                red = imagen_svg(
                    "insight-red",
                    '<path d="M14 30h92" stroke="#B7AC90" stroke-width="2"/>'
                    '<circle cx="14" cy="30" r="9" fill="#B7AC90"/>'
                    '<circle cx="60" cy="30" r="18" fill="#E8CFC0"/>'
                    '<circle cx="60" cy="30" r="10" fill="#B8441F"/>'
                    '<circle cx="106" cy="30" r="9" fill="#B7AC90"/>',
                    "0 0 120 60",
                )
                insight("subida", "Cuello de botella (método de flechas)", op=fila.Operacion,
                        metricas=((f"{fila.Severidad * 100:.0f} %", "Severidad"),
                                  (f"{fila.Induce_vecinos:.1f} h", "Inducidas a sus vecinas")),
                        ilustracion=red)
            else:
                insight("subida", "Cuello de botella", mensaje="Sin un cuello relevante en los días seleccionados.")
        with c2:
            mant = resultado.mantenimiento
            top_mant = mant.loc[mant.rango_mant == 1] if not mant.empty else mant
            if not top_mant.empty:
                fila = top_mant.iloc[0]
                barras = imagen_svg(
                    "insight-barras",
                    '<path d="M10 58V48m22 10V38m22 20V25m22 33V12" '
                    'stroke="#C9BFA3" stroke-width="13" stroke-linecap="round"/>'
                    '<path d="M76 58V12" stroke="#0A2540" stroke-width="13" stroke-linecap="round"/>',
                    "0 0 86 67",
                )
                insight("llave", "Prioridad de mantenimiento", op=fila.Etapa,
                        metricas=((f"{fila.TAP_medio_dia:.1f} h/día", "Parada propia (TAP)"),),
                        ilustracion=barras)
            else:
                insight("llave", "Prioridad de mantenimiento", mensaje="Sin datos suficientes.")
        with c3:
            baja_dp = k.loc[k.Incumple_Dp & k.Dp.notna()].nsmallest(1, "Dp")
            alto_ciclo = k.loc[k.Incumple_Tcy].nlargest(1, "Tcy")
            if not baja_dp.empty:
                fila = baja_dp.iloc[0]
                insight("aviso", "Menor disponibilidad", op=fila.Operacion,
                        metricas=((f"{fila.Dp:.1f} %", "Disponibilidad (Dp)"),),
                        ilustracion=medidor(fila.Dp))
            elif not alto_ciclo.empty:
                fila = alto_ciclo.iloc[0]
                insight("reloj", "Mayor tiempo de ciclo", op=fila.Operacion,
                        metricas=((f"{fila.Tcy:.1f} cmin", "Tiempo de ciclo (Tcy)"),))
            else:
                texto = "Todas las Dp y Tcy calculables cumplen objetivo." if k.Dp.notna().any() else "Sin datos suficientes."
                insight("aviso", "Objetivos", mensaje=texto)


def calidad(datos_locales: bool):
    """Panel de calidad de datos: lista vertical con todas las incidencias (alertas.json),
    cada una expandible; nunca se muestra el JSON en bruto. Las alertas son por operación
    y no cambian con los filtros del periodo/tramo (son propiedades de los datos, no de
    la selección)."""
    lista = sorted(_alertas() if datos_locales else [],
                   key=lambda a: (a.get("nivel") != "error", a.get("orden_op") or 0))
    registro_op = _registro_por_operacion()
    errores = sum(a.get("nivel") == "error" for a in lista)
    etiqueta = (f"{errores} errores · {len(lista) - errores} advertencias"
                if datos_locales and ALERTAS.exists() else "Sin informe asociado")
    if lista:
        etiqueta = f":{'red' if errores else 'orange'}-background[{etiqueta}]"
    panel = st.expander(f"**Alertas del sistema**　{etiqueta}", icon=":material/warning:",
                        key="calidad", on_change="rerun")
    if not panel.open:
        return
    with panel:
        if not lista:
            st.caption("No hay alertas de limpieza asociadas a la fuente activa.")
            return
        c1, c2 = st.columns([1.3, 2])
        with c1:
            nivel = st.segmented_control(
                "Gravedad", ["Todas", "Errores", "Advertencias"],
                default="Todas", required=True, key="calidad_nivel")
        with c2:
            busqueda = st.text_input("Buscar por código de operación o título", key="calidad_busqueda",
                                     placeholder="p. ej. ST_0030", label_visibility="visible")
        filtradas = [
            a for a in lista
            if (nivel == "Todas" or (a.get("nivel") == "error") == (nivel == "Errores"))
            and (not busqueda.strip() or busqueda.strip().lower() in
                 f"{a.get('id', '')} {a.get('operacion', '')} {a.get('titulo', '')}".lower())
        ]
        st.html(f'<p class="alerta-resumen">Mostrando {len(filtradas)} de {len(lista)}.</p>')
        for a in filtradas:
            invalidante = a.get("nivel") == "error"
            severidad = "Error" if invalidante else "Advertencia"
            operacion = str(a.get("operacion") or "Línea")
            titulo = str(a.get("titulo") or "Incidencia de calidad")
            resumen = str(a.get("resumen") or "")
            texto = f":gray-background[{severidad}]  {operacion} · {a['id']}  \n**{titulo}**  \n{resumen}"
            detalle_alerta = st.expander(texto, icon=":material/error:" if invalidante else ":material/warning:",
                                         key=f"detalle_alerta_{'error' if invalidante else 'advertencia'}_{a['id']}",
                                         on_change="rerun")
            if detalle_alerta.open:
                with detalle_alerta:
                    detalle_calidad(a, registro_op.get(a.get("operacion")))
        if not filtradas:
            st.caption("Ninguna incidencia coincide con el filtro.")


def accesos():
    with st.container(key="visualizaciones"):
        estilos = []
        for vista in ACCESOS:
            svg = (APP / "assets" / "visualizaciones" / f"{vista}.svg").read_bytes()
            imagen = b64encode(svg).decode("ascii")
            estilos.append(f'.st-key-acceso_{vista} {{ --miniatura: url("data:image/svg+xml;base64,{imagen}"); }}')
        st.html("<style>" + "\n".join(estilos) + "</style>")
        with st.container(key="tarjetas"):
            for vista, nombre in ACCESOS.items():
                st.button(nombre, key=f"acceso_{vista}", width="stretch",
                          on_click=navegar, args=(vista,))


def selector_grafico(vista, k, motor, dias_sel):
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
        for destino, etiqueta in (("inicio", "Inicio"), ("detalle", "Detalle por máquina"), ("datos", "Tabla de datos"),
                                 ("simulacion", "Simulación de la línea")):
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


def cambiar_centro():
    st.session_state.pop("linea", None)
    cambiar_linea()


def cambiar_linea():
    restablecer_filtros()
    st.session_state.pop("operacion_detalle", None)
    st.session_state.vista = "inicio"


with st.sidebar:
    with st.container(key="marca_lossia"):
        st.html('<div class="marca-origen">HACKATHON · ICAI</div>')
        st.button("LOSSIA", key="lossia_inicio", type="tertiary", width="content",
                  on_click=navegar, args=("inicio",))
    with st.container(key="filtro_centro"):
        centro_activo = st.selectbox("Centro / Ciudad", list(CENTROS),
                                     format_func=lambda centro: CENTROS[centro]["nombre"],
                                     key="centro", on_change=cambiar_centro)
    lineas = CENTROS[centro_activo]["lineas"]
    with st.container(key="filtro_linea"):
        linea_activa = st.selectbox("Línea de producción", list(lineas),
                                    format_func=lambda linea: lineas[linea]["nombre"],
                                    key="linea", on_change=cambiar_linea)


# --- Simulación de la línea (simulador/) ----------------------------------------------
@st.cache_data(show_spinner=False)
def etapas_simulador(raiz):
    import simulador_linea as SL
    p, horas, real = SL.cargar_parametros(Path(raiz))
    return p["Etapa"].tolist(), real


@st.cache_data(show_spinner=False, max_entries=20)
def simulacion_html(raiz, mejorar, factor, buffer):
    import animacion_linea as AL
    return AL.construir_html(Path(raiz), mejorar, factor=factor, buffer=buffer, oscuro=True)


def simulacion():
    import streamlit.components.v1 as components
    try:
        etapas, real = etapas_simulador(str(REPO))
    except (OSError, KeyError, ValueError) as exc:
        st.error(f"No se puede preparar la simulación: {exc}")
        return
    st.caption("Réplica de la línea con eventos discretos: cada etapa trabaja a su tiempo de ciclo y sufre "
               "paradas con la frecuencia y duración reales; las paradas se propagan solas a las vecinas. "
               "Compara una jornada actual con otra en la que se mejora una etapa.")
    with st.container(key="sim_controles", horizontal=True, vertical_alignment="bottom", gap="medium"):
        mejorar = st.selectbox("Etapa a mejorar", etapas, key="sim_etapa",
                               index=etapas.index("PM_2250") if "PM_2250" in etapas else 0)
        reduccion = st.slider("Reducción de sus paradas", 10, 100, 100, step=10, format="%d %%", key="sim_red")
        buffer = st.number_input("Piezas entre etapas (buffer)", 1, 20, 8, key="sim_buffer",
                                 help="8 es el valor calibrado con la producción real.")
    with st.spinner("Simulando la jornada…"):
        html, base, mejora = simulacion_html(str(REPO), mejorar, 1 - reduccion / 100, int(buffer))
    with st.container(key="sim_kpis", horizontal=True, gap="medium"):
        st.metric("Producción real media", f"{real:,.0f}".replace(",", "."), border=True)
        st.metric("Simulada · situación actual", f"{base:,}".replace(",", "."), border=True)
        st.metric(f"Simulada · mejorando {mejorar}", f"{mejora:,}".replace(",", "."),
                  delta=f"{mejora - base:+d} motores/día", border=True)
    components.html(html, height=1080, scrolling=True)

    ranking = REPO / "simulador" / "salidas" / "ranking_simulado.csv"
    with st.expander("Ranking: motores/día ganados al eliminar las paradas de cada etapa"):
        if ranking.exists():
            rk = pd.read_csv(ranking).head(15)
            st.bar_chart(rk.set_index("Etapa")["motores_dia_ganados"], horizontal=True, sort=False,
                         x_label="Motores/día ganados", y_label="")
            st.dataframe(rk, hide_index=True, width="stretch")
        else:
            st.info("Todavía no hay ranking calculado.")
        if st.button("Recalcular ranking (≈1 min)", icon=":material/refresh:", key="sim_recalcular"):
            import subprocess
            with st.spinner("Simulando cada etapa sin paradas…"):
                r = subprocess.run([sys.executable, "simulador/simulador_linea.py", "--buffer", str(int(buffer))],
                                   cwd=REPO, capture_output=True, text=True)
            if r.returncode == 0:
                st.rerun()
            st.error(r.stderr[-800:])

linea_config = lineas[linea_activa]
DIR_LIMPIOS = Path(linea_config["datos"])
DIR_RESULTADOS = Path(linea_config["resultados"])
ALERTAS = DIR_LIMPIOS / "alertas.json"
REGISTRO = DIR_LIMPIOS / "registro_limpieza.json"
INFORME = DIR_LIMPIOS / "informe_limpieza.txt"

vista = st.session_state.get("vista", "inicio")
if vista == "inicio":
    nombre_vista = f"Informe de la {lineas[linea_activa]['nombre'].lower()} - {CENTROS[centro_activo]['nombre']}"
else:
    titulo = {"detalle": "Detalle por máquina", "datos": "Tabla de datos", "simulacion": "Simulación de la línea",
              "visualizaciones": "Visualizaciones"}
    nombre_vista = titulo.get(vista) or VISTAS[vista][1]
NAV = (("inicio", "resumen"), ("visualizaciones", "visualizaciones"), ("simulacion", "simulación"),
       ("detalle", "máquinas"), ("datos", "datos"))
NAV_ACTIVO = "visualizaciones" if vista in VISTAS else vista
logo = b64encode((APP / "assets" / "horse.png").read_bytes()).decode("ascii")
with st.container(key="barra_nav", horizontal=True, vertical_alignment="center", gap="medium"):
    st.html('<div class="nav-hueco"></div>', width=110)
    with st.container(key="nav_enlaces", horizontal=True, horizontal_alignment="center",
                      vertical_alignment="center", gap="large", width="stretch"):
        for destino, etiqueta in NAV:
            st.button(etiqueta, key=f"nav_{destino}", type="tertiary", on_click=navegar, args=(destino,))
    st.html('<a class="horse-link" href="https://horse-powertrain.com/" target="_blank" rel="noopener noreferrer">'
            f'<img class="horse" src="data:image/png;base64,{logo}" alt="Web oficial de HORSE"></a>', width=110)
if NAV_ACTIVO in {d for d, _ in NAV}:
    st.html(f"<style>.st-key-nav_{NAV_ACTIVO} button {{ border-bottom-color: var(--lossia-accent) !important; }}"
            f".st-key-nav_{NAV_ACTIVO} button p {{ color: var(--lossia-ink) !important; }}</style>")

with st.container(key="cabecera"):
    clase_titulo = ' class="titulo-principal"' if vista == "inicio" else ""
    st.html(f'<h1{clase_titulo}>{nombre_vista}</h1>')

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
if resultado.fuente == LI.PERSISTIDOS:
    fuente_txt = "Resultados/ (referencia oficial)"
else:
    n_dias_calc = len(resultado.dias)
    fuente_txt = (f"Cálculo en vivo · {n_dias_calc} día{'s' if n_dias_calc != 1 else ''} "
                  "(sin equivalente persistido)")
datos_locales = True

if vista in VISTAS:
    st.button("Visualizaciones", icon=":material/arrow_back:", type="tertiary",
              on_click=navegar, args=("visualizaciones",), key="volver")
elif vista not in ("inicio", "visualizaciones"):
    st.button("Resumen de la línea", icon=":material/arrow_back:", type="tertiary",
              on_click=navegar, args=("inicio",), key="volver")

if vista == "simulacion":
    simulacion()
elif vista == "visualizaciones":
    accesos()
elif k.empty:
    st.warning("No hay datos para los filtros seleccionados.")
    st.button("Restablecer filtros", on_click=restablecer_filtros, key="restablecer_vacio")
    if vista == "inicio":
        calidad(datos_locales)
elif vista == "inicio":
    insights(k, resultado)
    kpis_cabecera(k)
    calidad(datos_locales)
elif vista == "detalle":
    detalle(motor, k, resultado, dias_sel)
elif vista == "datos":
    with st.container(horizontal=True, horizontal_alignment="right"):
        st.download_button("Descargar CSV", k[COLUMNAS].to_csv(index=False).encode("utf-8"),
                             file_name="kpis_lossia.csv", mime="text/csv", disabled=k.empty,
                             icon=":material/download:", on_click="ignore", key="descarga")
    tabla(k, datos_locales)
else:
    selector_grafico(vista, k, motor, dias_sel)


# --- Chat con IA: botón flotante abajo a la derecha ---------------------------------
SUGERENCIAS_CHAT = ["Resume las principales incidencias", "Detecta patrones en las paradas",
                    "Propón acciones de mejora"]


def alternar_chat():
    st.session_state.chat_abierto = not st.session_state.get("chat_abierto", False)


def enviar_chat(texto):
    msgs = st.session_state.setdefault("chat_msgs", [])
    msgs.append({"role": "user", "content": texto})
    modelo = st.session_state.get("chat_llm")
    if modelo is None:
        respuesta = "Carga un modelo con «Cargar mi LLM» para que pueda analizar los datos de la línea."
    else:
        respuesta = f"Modelo «{modelo.name}» cargado. La conexión con el modelo todavía no está implementada."
    msgs.append({"role": "assistant", "content": respuesta})


@st.fragment
def chat_ia():
    abierto = st.session_state.get("chat_abierto", False)
    if abierto:
        with st.container(key="chat_panel"):
            with st.container(key="chat_cabecera", horizontal=True, vertical_alignment="center"):
                st.html('<div class="chat-titulo"><span class="chat-chispa">✦</span>Chat con IA</div>')
                st.button("", icon=":material/close:", type="tertiary", key="chat_cerrar",
                          on_click=alternar_chat, help="Cerrar")
            st.html('<p class="chat-sub">Analiza los datos de la línea, detecta patrones '
                    'o responde a tus preguntas.</p>')
            st.file_uploader("Cargar mi LLM", type=["gguf", "safetensors", "bin"], key="chat_llm",
                             help="Formatos: .gguf, .safetensors, .bin")
            msgs = st.session_state.get("chat_msgs", [])
            if msgs:
                with st.container(key="chat_mensajes", height=220):
                    for m in msgs:
                        with st.chat_message(m["role"]):
                            st.markdown(m["content"])
            else:
                st.html('<div class="chat-seccion">Sugerencias</div>')
                for i, s in enumerate(SUGERENCIAS_CHAT):
                    st.button(s, icon=":material/trending_up:", key=f"chat_sug_{i}", width="stretch",
                              on_click=enviar_chat, args=(s,))
            entrada = st.chat_input("Escribe un mensaje...", key="chat_texto", accept_file=True)
            if entrada:
                texto = entrada.text if hasattr(entrada, "text") else str(entrada)
                if texto:
                    enviar_chat(texto)
                    st.rerun(scope="fragment")
    st.button("", icon=":material/close:" if abierto else ":material/chat_bubble:", key="chat_fab",
              on_click=alternar_chat, help="Cerrar chat" if abierto else "Chat con IA")


chat_ia()
