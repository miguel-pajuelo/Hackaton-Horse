# construir_presentacion_visual_lossia.py
"""
Generador de la presentación oficial LOSSIA (Hackathon HORSE Valladolid)
Estilo visual IDÉNTICO al dashboard de la foto:
- Fondo crema / papel cálido: #F6F3EB
- Barra superior de pestañas (tabs) idéntica al dashboard con subrayado terracota en la pestaña activa
- Tipografía display: Georgia (Serif elegante de planta)
- Cero muros de texto: diapositivas 100% visuales con KPIs gigantes, diagramas y capturas
- 5 Secciones requeridas:
  1. EDA
  2. DASHBOARD
  3. SIMULADOR
  4. INFORME DE POSIBLES FALLOS
  5. MEJORAS FUTURAS
"""

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

DIR_PRESENTACION = Path(__file__).resolve().parent

def get_asset(name: str) -> Path:
    p = DIR_PRESENTACION / name
    return p if p.exists() else Path(name)

def build_presentation(output_file: str | Path | None = None):
    if output_file is None:
        output_file = DIR_PRESENTACION / "Presentacion_LOSSIA_HORSE_Visual.pptx"
    else:
        output_file = Path(output_file)
        if not output_file.is_absolute() and not output_file.parent.name:
            output_file = DIR_PRESENTACION / output_file
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Paleta idéntica al dashboard
    C_BG = RGBColor(246, 243, 235)         # #F6F3EB Fondo crema
    C_CARD_BG = RGBColor(252, 250, 246)    # #FCFAF6 Fondo tarjetas marfil
    C_BORDER = RGBColor(223, 215, 199)     # #DFD7C7 Borde suave de tarjeta
    C_NAVY = RGBColor(14, 32, 56)          # #0E2038 Azul tinta oscuro (texto y gráficos)
    C_TERRACOTTA = RGBColor(200, 90, 50)   # #C85A32 Terracota / naranja quemado activo
    C_MUTED = RGBColor(140, 130, 117)      # #8C8275 Texto secundario
    C_PILL_BG = RGBColor(238, 232, 220)    # #EEE8DC Fondo de chips y píldoras
    C_WHITE = RGBColor(255, 255, 255)

    SECCIONES = [
        ("eda", "EDA"),
        ("dashboard", "DASHBOARD"),
        ("propagacion", "PROPAGACIÓN"),
        ("simulador", "SIMULADOR"),
        ("fallos", "INFORME DE FALLOS"),
        ("futuro", "MEJORAS FUTURAS")
    ]

    def set_slide_background(slide):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = C_BG
        bg.line.fill.background()
        return bg

    def add_navigation_header(slide, active_slug="eda", title_text="Informe de la línea 5 - Valladolid"):
        # 1. Pestañas de navegación superiores (idénticas a la foto)
        tab_start_x = Inches(0.8)
        tab_y = Inches(0.28)
        tab_spacing = Inches(1.78)

        for i, (slug, label) in enumerate(SECCIONES):
            is_active = (slug == active_slug)
            tb_tab = slide.shapes.add_textbox(tab_start_x + i * tab_spacing, tab_y, Inches(1.72), Inches(0.35))
            tf_tab = tb_tab.text_frame
            tf_tab.margin_left = tf_tab.margin_top = tf_tab.margin_right = tf_tab.margin_bottom = 0
            p = tf_tab.paragraphs[0]
            p.text = label.lower()
            p.font.name = "Georgia"
            p.font.size = Pt(11)
            p.font.bold = is_active
            p.font.color.rgb = C_NAVY if is_active else C_MUTED

            # Línea de pestaña activa terracota
            if is_active:
                underline = slide.shapes.add_shape(
                    MSO_SHAPE.RECTANGLE,
                    tab_start_x + i * tab_spacing,
                    tab_y + Inches(0.32),
                    Inches(1.2),
                    Inches(0.035)
                )
                underline.fill.solid()
                underline.fill.fore_color.rgb = C_TERRACOTTA
                underline.line.fill.background()

        # 2. Logo HORSE a la derecha
        logo_box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(11.4), Inches(0.25), Inches(1.15), Inches(0.45))
        logo_box.fill.solid()
        logo_box.fill.fore_color.rgb = C_CARD_BG
        logo_box.line.color.rgb = C_BORDER
        logo_box.line.width = Pt(1.0)
        tf_logo = logo_box.text_frame
        tf_logo.margin_top = Inches(0.08)
        p_logo = tf_logo.paragraphs[0]
        p_logo.text = "HORSE"
        p_logo.font.name = "Georgia"
        p_logo.font.size = Pt(12)
        p_logo.font.bold = True
        p_logo.font.color.rgb = C_NAVY
        p_logo.alignment = PP_ALIGN.CENTER

        # 3. Título principal de la diapositiva en Serif
        tb_title = slide.shapes.add_textbox(Inches(0.8), Inches(0.72), Inches(11.7), Inches(0.65))
        tf_title = tb_title.text_frame
        tf_title.margin_left = tf_title.margin_top = tf_title.margin_right = tf_title.margin_bottom = 0
        p_title = tf_title.paragraphs[0]
        p_title.text = title_text
        p_title.font.name = "Georgia"
        p_title.font.size = Pt(24)
        p_title.font.bold = True
        p_title.font.color.rgb = C_NAVY

    # =========================================================================
    # SLIDE 1: PORTADA (ESTILO DASHBOARD RETRO-CREMA)
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1)

    # Tarjeta central principal
    card_center = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.5), Inches(1.2), Inches(10.33), Inches(5.1))
    card_center.fill.solid()
    card_center.fill.fore_color.rgb = C_CARD_BG
    card_center.line.color.rgb = C_BORDER
    card_center.line.width = Pt(1.5)

    tb1 = s1.shapes.add_textbox(Inches(2.0), Inches(1.8), Inches(9.33), Inches(3.8))
    tf1 = tb1.text_frame
    tf1.word_wrap = True

    p_sub = tf1.paragraphs[0]
    p_sub.text = "HACKATHON · ICAI"
    p_sub.font.name = "Georgia"
    p_sub.font.size = Pt(14)
    p_sub.font.bold = True
    p_sub.font.color.rgb = C_MUTED
    p_sub.alignment = PP_ALIGN.CENTER

    p_logo = tf1.add_paragraph()
    p_logo.text = "L O S S I A"
    p_logo.font.name = "Georgia"
    p_logo.font.size = Pt(54)
    p_logo.font.bold = True
    p_logo.font.color.rgb = C_NAVY
    p_logo.alignment = PP_ALIGN.CENTER
    p_logo.space_before = Pt(8)

    p_tit = tf1.add_paragraph()
    p_tit.text = "Informe de la línea 5 — Valladolid"
    p_tit.font.name = "Georgia"
    p_tit.font.size = Pt(26)
    p_tit.font.bold = True
    p_tit.font.color.rgb = C_TERRACOTTA
    p_tit.alignment = PP_ALIGN.CENTER
    p_tit.space_before = Pt(10)

    p_desc = tf1.add_paragraph()
    p_desc.text = "Cuadro de Mandos · Cuellos de Botella · Simulación · Mantenimiento Prescriptivo"
    p_desc.font.name = "Georgia"
    p_desc.font.size = Pt(14)
    p_desc.font.color.rgb = C_NAVY
    p_desc.alignment = PP_ALIGN.CENTER
    p_desc.space_before = Pt(16)

    # Pills inferiores de secciones
    pills = ["01 EDA", "02 DASHBOARD", "03 PROPAGACIÓN", "04 SIMULADOR", "05 FALLOS", "06 FUTURO"]
    pill_w = Inches(1.75)
    pill_start_x = Inches(0.9)
    for i, pill in enumerate(pills):
        p_shape = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, pill_start_x + i * Inches(1.9), Inches(5.1), pill_w, Inches(0.42))
        p_shape.fill.solid()
        p_shape.fill.fore_color.rgb = C_PILL_BG
        p_shape.line.color.rgb = C_BORDER
        p_shape.line.width = Pt(1.0)
        tf_p = p_shape.text_frame
        tf_p.margin_top = Inches(0.08)
        pp = tf_p.paragraphs[0]
        pp.text = pill
        pp.font.name = "Georgia"
        pp.font.size = Pt(10)
        pp.font.bold = True
        pp.font.color.rgb = C_NAVY
        pp.alignment = PP_ALIGN.CENTER

    # =========================================================================
    # SLIDE 2: SECCIÓN 01 · EDA
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2)
    add_navigation_header(s2, active_slug="eda", title_text="01 · EDA — Exploración de Datos y Telemetría")

    # Tarjetas superiores con KPIs gigantes (sin texto en párrafo)
    kpis_eda = [
        ("16", "Días analizados", C_NAVY),
        ("85", "Etapas en línea", C_NAVY),
        ("91", "Operaciones totales", C_NAVY),
        ("2.382", "Motores / día", C_TERRACOTTA),
    ]
    card_w = Inches(2.7)
    for i, (val, label, col) in enumerate(kpis_eda):
        card = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8) + i * Inches(2.95), Inches(1.42), card_w, Inches(1.0))
        card.fill.solid()
        card.fill.fore_color.rgb = C_CARD_BG
        card.line.color.rgb = C_BORDER
        card.line.width = Pt(1.2)
        tf = card.text_frame
        tf.margin_top = Inches(0.12)
        p1 = tf.paragraphs[0]
        p1.text = val
        p1.font.name = "Georgia"
        p1.font.size = Pt(28)
        p1.font.bold = True
        p1.font.color.rgb = col
        p1.alignment = PP_ALIGN.CENTER
        p2 = tf.add_paragraph()
        p2.text = label
        p2.font.name = "Georgia"
        p2.font.size = Pt(11)
        p2.font.color.rgb = C_MUTED
        p2.alignment = PP_ALIGN.CENTER

    # Gráfico visual de EDA incrustado
    img_eda = get_asset("grafico_eda_lossia.png")
    if img_eda.exists():
        s2.shapes.add_picture(str(img_eda), Inches(0.8), Inches(2.55), width=Inches(11.7))

    # =========================================================================
    # SLIDE 3: SECCIÓN 02 · DASHBOARD
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3)
    add_navigation_header(s3, active_slug="dashboard", title_text="02 · DASHBOARD — Monitor Oficial de la Línea 5")

    # Incrustar la captura EXACTA del dashboard de la foto
    img_dash = get_asset("dashboard_screenshot.jpg")
    if img_dash.exists():
        # Captura centrada y nítida
        s3.shapes.add_picture(str(img_dash), Inches(0.8), Inches(1.45), width=Inches(11.73))

    # =========================================================================
    # SLIDE 4: SECCIÓN 03 · PROPAGACIÓN DE CUELLOS DE BOTELLA
    # =========================================================================
    s_prop = prs.slides.add_slide(blank_layout)
    set_slide_background(s_prop)
    add_navigation_header(s_prop, active_slug="propagacion", title_text="03 · PROPAGACIÓN — El Efecto Dominó en Cadena (SAT vs DES)")

    # Tarjetas superiores con KPIs de propagación
    kpis_prop = [
        ("ST_0260", "Puesto #20 · Cuello crítico", C_NAVY),
        ("0.68 h", "Parada propia (TAP)", C_TERRACOTTA),
        ("10.92 h", "Inducidas a vecinas", C_NAVY),
        ("x 16.1", "Multiplicador de asfixia", C_TERRACOTTA),
    ]
    for i, (val, label, col) in enumerate(kpis_prop):
        card = s_prop.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8) + i * Inches(2.95), Inches(1.42), card_w, Inches(1.0))
        card.fill.solid()
        card.fill.fore_color.rgb = C_CARD_BG
        card.line.color.rgb = C_BORDER
        card.line.width = Pt(1.2)
        tf = card.text_frame
        tf.margin_top = Inches(0.12)
        p1 = tf.paragraphs[0]
        p1.text = val
        p1.font.name = "Georgia"
        p1.font.size = Pt(24)
        p1.font.bold = True
        p1.font.color.rgb = col
        p1.alignment = PP_ALIGN.CENTER
        p2 = tf.add_paragraph()
        p2.text = label
        p2.font.name = "Georgia"
        p2.font.size = Pt(11)
        p2.font.color.rgb = C_MUTED
        p2.alignment = PP_ALIGN.CENTER

    # Gráfico de propagación incrustado
    img_prop = get_asset("grafico_propagacion_lossia.png")
    if img_prop.exists():
        s_prop.shapes.add_picture(str(img_prop), Inches(0.8), Inches(2.55), width=Inches(11.7))

    # =========================================================================
    # SLIDE 5: SECCIÓN 04 · SIMULADOR
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_background(s4)
    add_navigation_header(s4, active_slug="simulador", title_text="04 · SIMULADOR — Capacidad What-If y Retorno de Inversión")

    # Tarjetas superiores con KPIs de simulación
    kpis_sim = [
        ("ST-2390", "Estación objetivo (Puesto #75)", C_NAVY),
        ("- 30 %", "Reducción de TAP propio", C_TERRACOTTA),
        ("+ 1.28 h", "Tiempo ganado al día", C_NAVY),
        ("+ 108", "Motores extra / día", C_TERRACOTTA),
    ]
    for i, (val, label, col) in enumerate(kpis_sim):
        card = s4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8) + i * Inches(2.95), Inches(1.42), card_w, Inches(1.0))
        card.fill.solid()
        card.fill.fore_color.rgb = C_CARD_BG
        card.line.color.rgb = C_BORDER
        card.line.width = Pt(1.2)
        tf = card.text_frame
        tf.margin_top = Inches(0.12)
        p1 = tf.paragraphs[0]
        p1.text = val
        p1.font.name = "Georgia"
        p1.font.size = Pt(24)
        p1.font.bold = True
        p1.font.color.rgb = col
        p1.alignment = PP_ALIGN.CENTER
        p2 = tf.add_paragraph()
        p2.text = label
        p2.font.name = "Georgia"
        p2.font.size = Pt(11)
        p2.font.color.rgb = C_MUTED
        p2.alignment = PP_ALIGN.CENTER

    # Gráfico del simulador
    img_sim = get_asset("grafico_simulador_lossia.png")
    if img_sim.exists():
        s4.shapes.add_picture(str(img_sim), Inches(0.8), Inches(2.55), width=Inches(11.7))

    # =========================================================================
    # SLIDE 6: SECCIÓN 05 · INFORME DE POSIBLES FALLOS
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_background(s5)
    add_navigation_header(s5, active_slug="fallos", title_text="05 · INFORME DE POSIBLES FALLOS — Predicción Diaria por Desgaste (Weibull)")

    # Tarjetas superiores de estado diario
    kpis_fallos = [
        ("S43-D4", "Jornada analizada", C_NAVY),
        ("15", "Máquinas en alerta alta (P >= 45%)", C_TERRACOTTA),
        ("~1.986", "Motores en riesgo", C_NAVY),
        ("ST0261", "Máxima prioridad (65.6% P)", C_TERRACOTTA),
    ]
    for i, (val, label, col) in enumerate(kpis_fallos):
        card = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8) + i * Inches(2.95), Inches(1.42), card_w, Inches(1.0))
        card.fill.solid()
        card.fill.fore_color.rgb = C_CARD_BG
        card.line.color.rgb = C_BORDER
        card.line.width = Pt(1.2)
        tf = card.text_frame
        tf.margin_top = Inches(0.12)
        p1 = tf.paragraphs[0]
        p1.text = val
        p1.font.name = "Georgia"
        p1.font.size = Pt(24)
        p1.font.bold = True
        p1.font.color.rgb = col
        p1.alignment = PP_ALIGN.CENTER
        p2 = tf.add_paragraph()
        p2.text = label
        p2.font.name = "Georgia"
        p2.font.size = Pt(11)
        p2.font.color.rgb = C_MUTED
        p2.alignment = PP_ALIGN.CENTER

    # Gráfico de predicción
    img_pred = get_asset("grafico_prediccion_lossia.png")
    if img_pred.exists():
        s5.shapes.add_picture(str(img_pred), Inches(0.8), Inches(2.55), width=Inches(11.7))

    # =========================================================================
    # SLIDE 7: SECCIÓN 06 · MEJORAS FUTURAS
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_background(s6)
    add_navigation_header(s6, active_slug="futuro", title_text="06 · MEJORAS FUTURAS — Hoja de Ruta para HORSE")

    # Gráfico de mejoras futuras en formato cuadrícula visual
    img_futuro = get_asset("grafico_futuro_lossia.png")
    if img_futuro.exists():
        s6.shapes.add_picture(str(img_futuro), Inches(0.8), Inches(1.5), width=Inches(11.7))

    # =========================================================================
    # SLIDE 7: CIERRE
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    set_slide_background(s7)

    card_end = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.5), Inches(1.5), Inches(10.33), Inches(4.5))
    card_end.fill.solid()
    card_end.fill.fore_color.rgb = C_CARD_BG
    card_end.line.color.rgb = C_BORDER
    card_end.line.width = Pt(1.5)

    tb_e = s7.shapes.add_textbox(Inches(2.0), Inches(2.0), Inches(9.33), Inches(3.5))
    tf_e = tb_e.text_frame
    tf_e.word_wrap = True

    p_e0 = tf_e.paragraphs[0]
    p_e0.text = "L O S S I A · H O R S E"
    p_e0.font.name = "Georgia"
    p_e0.font.size = Pt(16)
    p_e0.font.bold = True
    p_e0.font.color.rgb = C_MUTED
    p_e0.alignment = PP_ALIGN.CENTER

    p_e1 = tf_e.add_paragraph()
    p_e1.text = "Excelencia Operativa en la Línea 5"
    p_e1.font.name = "Georgia"
    p_e1.font.size = Pt(36)
    p_e1.font.bold = True
    p_e1.font.color.rgb = C_NAVY
    p_e1.alignment = PP_ALIGN.CENTER
    p_e1.space_before = Pt(12)

    p_e2 = tf_e.add_paragraph()
    p_e2.text = "EDA  ·  DASHBOARD  ·  PROPAGACIÓN  ·  SIMULADOR  ·  PREDICCIÓN  ·  FUTURO"
    p_e2.font.name = "Georgia"
    p_e2.font.size = Pt(14)
    p_e2.font.bold = True
    p_e2.font.color.rgb = C_TERRACOTTA
    p_e2.alignment = PP_ALIGN.CENTER
    p_e2.space_before = Pt(16)

    p_e3 = tf_e.add_paragraph()
    p_e3.text = "¿Preguntas?"
    p_e3.font.name = "Georgia"
    p_e3.font.size = Pt(28)
    p_e3.font.bold = True
    p_e3.font.color.rgb = C_NAVY
    p_e3.alignment = PP_ALIGN.CENTER
    p_e3.space_before = Pt(24)

    prs.save(output_file)
    print(f"🎉 Presentación visual final guardada con éxito en: {Path(output_file).resolve()}")

if __name__ == '__main__':
    build_presentation()
