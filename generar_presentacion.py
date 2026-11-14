# generar_presentacion.py
"""
Generador automático de la presentación en PowerPoint (.pptx)
Hackathon LOSSIA · HORSE Valladolid (Línea 5 de Montaje)
Diseño profesional 16:9, paleta corporativa HORSE, tarjetas de contenido y gráficos integrados.
"""

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

def create_presentation(output_path="Presentacion_LOSSIA_HORSE.pptx"):
    prs = Presentation()
    # Formato panorámico 16:9 (13.333 x 7.5 pulgadas)
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6] # layout en blanco

    # Paleta de colores corporativa
    C_NAVY = RGBColor(11, 25, 44)       # #0B192C Fondo oscuro / encabezados
    C_ORANGE = RGBColor(234, 88, 12)    # #EA580C Acento corporativo HORSE
    C_BLUE = RGBColor(30, 58, 138)      # #1E3A8A Azul industrial
    C_SLATE = RGBColor(71, 85, 105)     # #475569 Texto secundario
    C_DARK = RGBColor(15, 23, 42)       # #0F172A Texto principal
    C_LIGHT_BG = RGBColor(248, 250, 252)# #F8FAFC Fondo claro
    C_CARD_BG = RGBColor(255, 255, 255) # #FFFFFF Tarjetas
    C_BORDER = RGBColor(226, 232, 240)  # #E2E8F0 Borde suave
    C_RED = RGBColor(220, 38, 38)       # #DC2626
    C_GREEN = RGBColor(22, 163, 74)     # #16A34A

    def set_slide_background(slide, color):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = color
        bg.line.fill.background()
        return bg

    def add_header(slide, title_text, category_text="HACKATHON DEL PROYECTO LOSSIA · HORSE VALLADOLID"):
        # Categoría superior
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.4))
        tf_cat = cat_box.text_frame
        tf_cat.word_wrap = True
        p_cat = tf_cat.paragraphs[0]
        p_cat.text = category_text.upper()
        p_cat.font.size = Pt(10)
        p_cat.font.bold = True
        p_cat.font.color.rgb = C_ORANGE

        # Título principal
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.7), Inches(11.7), Inches(0.8))
        tf_title = title_box.text_frame
        tf_title.word_wrap = True
        p_title = tf_title.paragraphs[0]
        p_title.text = title_text
        p_title.font.size = Pt(22)
        p_title.font.bold = True
        p_title.font.color.rgb = C_NAVY

        # Línea separadora naranja
        line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.5), Inches(11.7), Inches(0.03))
        line.fill.solid()
        line.fill.fore_color.rgb = C_ORANGE
        line.line.fill.background()

    def add_card(slide, left, top, width, height, title="", border_color=C_BORDER, bg_color=C_CARD_BG):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        card.line.color.rgb = border_color
        card.line.width = Pt(1.2)
        if title:
            tb = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.15), width - Inches(0.4), Inches(0.5))
            tf = tb.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = title
            p.font.size = Pt(14)
            p.font.bold = True
            p.font.color.rgb = C_NAVY
        return card

    # =========================================================================
    # SLIDE 1: PORTADA
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1, C_NAVY)

    # Bloque decorativo naranja
    accent = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(1.8), Inches(0.15), Inches(3.8))
    accent.fill.solid()
    accent.fill.fore_color.rgb = C_ORANGE
    accent.line.fill.background()

    tb = s1.shapes.add_textbox(Inches(1.4), Inches(1.7), Inches(10.5), Inches(3.9))
    tf = tb.text_frame
    tf.word_wrap = True

    p0 = tf.paragraphs[0]
    p0.text = "HACKATHON DEL PROYECTO LOSSIA · HORSE & ICAI"
    p0.font.size = Pt(13)
    p0.font.bold = True
    p0.font.color.rgb = C_ORANGE

    p1 = tf.add_paragraph()
    p1.text = "LOSSIA: Entender las Máquinas Penalizantes y Predecir el Fallo Diario"
    p1.font.size = Pt(30)
    p1.font.bold = True
    p1.font.color.rgb = RGBColor(255, 255, 255)
    p1.space_before = Pt(12)

    p2 = tf.add_paragraph()
    p2.text = "Un criterio objetivo y unificado de análisis de paradas, simulación de capacidad\ny mantenimiento prescriptivo para la Línea 5 de Montaje (Valladolid)"
    p2.font.size = Pt(15)
    p2.font.color.rgb = RGBColor(203, 213, 225)
    p2.space_before = Pt(14)

    p3 = tf.add_paragraph()
    p3.text = "Equipo LOSSIA · Noviembre 2026"
    p3.font.size = Pt(12)
    p3.font.bold = True
    p3.font.color.rgb = C_ORANGE
    p3.space_before = Pt(28)

    # =========================================================================
    # SLIDE 2: EL PROBLEMA Y EL DOLOR DE PLANTA
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2, C_LIGHT_BG)
    add_header(s2, "El Dolor de Planta: La Trampa del Tiempo Absoluto y la Subjetividad")

    # Tarjeta 1: La situación actual
    add_card(s2, Inches(0.8), Inches(1.8), Inches(3.6), Inches(4.8), "1. Subjetividad Operativa")
    tb1 = s2.shapes.add_textbox(Inches(0.95), Inches(2.5), Inches(3.3), Inches(3.9))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    tf1.paragraphs[0].text = "• Análisis manuales y dispares:\nEn distintas plantas de HORSE e incluso entre turnos, el diagnóstico varía según la experiencia de la persona."
    tf1.paragraphs[0].font.size = Pt(12)
    p = tf1.add_paragraph()
    p.text = "• Desinformación en la toma de decisiones:\nSin un criterio unificado, el Jefe de Unidad y el técnico de mantenimiento priorizan máquinas distintas."
    p.font.size = Pt(12)
    p.space_before = Pt(10)

    # Tarjeta 2: La pregunta trampa
    add_card(s2, Inches(4.8), Inches(1.8), Inches(3.6), Inches(4.8), "2. La Pregunta Trampa", border_color=C_ORANGE)
    tb2 = s2.shapes.add_textbox(Inches(4.95), Inches(2.5), Inches(3.3), Inches(3.9))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    tf2.paragraphs[0].text = "¿Por qué una máquina que se para 2 horas puede ser más penalizante que una de 10 horas?"
    tf2.paragraphs[0].font.size = Pt(13)
    tf2.paragraphs[0].font.bold = True
    tf2.paragraphs[0].font.color.rgb = C_ORANGE
    p = tf2.add_paragraph()
    p.text = "• La máquina de 10h con buffer amplio solo consume stock intermedio sin parar a la línea."
    p.font.size = Pt(12)
    p.space_before = Pt(8)
    p2 = tf2.add_paragraph()
    p2.text = "• La máquina de 2h en el centro del flujo sin buffer ASFIXIA a toda la fábrica en cadena."
    p2.font.size = Pt(12)
    p2.font.bold = True
    p2.space_before = Pt(8)

    # Tarjeta 3: Propagación de fallos
    add_card(s2, Inches(8.8), Inches(1.8), Inches(3.7), Inches(4.8), "3. Efecto Cascada en Línea")
    tb3 = s2.shapes.add_textbox(Inches(8.95), Inches(2.5), Inches(3.4), Inches(3.9))
    tf3 = tb3.text_frame
    tf3.word_wrap = True
    tf3.paragraphs[0].text = "• Parada Propia (TAP):\nLa máquina se detiene por avería interna."
    tf3.paragraphs[0].font.size = Pt(12)
    p = tf3.add_paragraph()
    p.text = "• Saturación (SAT / Blocking):\nSe detiene porque la siguiente está parada y no puede evacuar piezas."
    p.font.size = Pt(12)
    p.space_before = Pt(8)
    p2 = tf3.add_paragraph()
    p2.text = "• Desabastecimiento (DES / Starving):\nSe detiene porque la anterior está parada y no le suministra piezas."
    p2.font.size = Pt(12)
    p2.space_before = Pt(8)
    p3 = tf3.add_paragraph()
    p3.text = "TAI = SAT + DES (Parada Inducida externa)"
    p3.font.size = Pt(12)
    p3.font.bold = True
    p3.font.color.rgb = C_BLUE
    p3.space_before = Pt(8)

    # =========================================================================
    # SLIDE 3: METODOLOGÍA & CRITERIO UNIFICADO
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3, C_LIGHT_BG)
    add_header(s3, "Metodología LOSSIA: Desacoplo Físico de Culpa y Estándares Oficiales")

    # Columna Izquierda: Fórmulas y Criterios Oficiales
    add_card(s3, Inches(0.8), Inches(1.8), Inches(5.6), Inches(4.8), "Estándares Contractuales de HORSE")
    tb_std = s3.shapes.add_textbox(Inches(1.0), Inches(2.4), Inches(5.2), Inches(4.0))
    tf_std = tb_std.text_frame
    tf_std.word_wrap = True
    tf_std.paragraphs[0].text = "1. Disponibilidad Propia (Dp >= 90.0%):\n   Dp = TBF / (TBF + TAP)\n   Mide el rendimiento propio de la máquina sin culparla del entorno."
    tf_std.paragraphs[0].font.size = Pt(12)
    p = tf_std.add_paragraph()
    p.text = "2. Tiempo de Ciclo Máximo (Tcy <= 80 cmin = 48 s):\n   Tcy = (TBF * 6000) / NPR\n   Garantiza la cadencia de la fábrica (~85 motores/h)."
    p.font.size = Pt(12)
    p.space_before = Pt(10)
    p = tf_std.add_paragraph()
    p.text = "3. Frecuencia de Parada (Fpm):\n   Fpm = (NAP / NPR) * 1000 microparadas por mil piezas."
    p.font.size = Pt(12)
    p.space_before = Pt(10)

    # Columna Derecha: Nuestro Aporte Metodológico Diferencial
    add_card(s3, Inches(6.8), Inches(1.8), Inches(5.7), Inches(4.8), "Innovación Analítica LOSSIA", border_color=C_BLUE)
    tb_inn = s3.shapes.add_textbox(Inches(7.0), Inches(2.4), Inches(5.3), Inches(4.0))
    tf_inn = tb_inn.text_frame
    tf_inn.word_wrap = True
    tf_inn.paragraphs[0].text = "• Índice de Penalización en Línea (IPL):\n  Métrica normalizada (0-100) que castiga el TAP propio, el impacto inducido a vecinas y el incumplimiento de Dp y Tcy."
    tf_inn.paragraphs[0].font.size = Pt(12)
    p = tf_inn.add_paragraph()
    p.text = "• Detección de Fantasmas de Instrumentación:\n  Descubrimiento crítico: En ST2235 detectamos 22.022 paradas/día con solo 2.382 piezas. El algoritmo lo categorizó como 'Rebote de Fotocélula en PLC', evitando un costoso desmontaje mecánico."
    p.font.size = Pt(12)
    p.space_before = Pt(10)
    p = tf_inn.add_paragraph()
    p.text = "• Separación Estricta de Responsabilidades:\n  Una máquina que sufre mucho TAI es una víctima, no un culpable. LOSSIA señala la raíz, no el síntoma."
    p.font.size = Pt(12)
    p.space_before = Pt(10)

    # =========================================================================
    # SLIDE 4: TOP MÁQUINAS PENALIZANTES (CON GRÁFICO)
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_background(s4, C_LIGHT_BG)
    add_header(s4, "Diagnóstico Real: Parada Propia vs. Parada Inducida a Vecinas")

    # Imagen del gráfico generado
    img_penal = Path("top_penalizantes_vs_vecinas.png")
    if img_penal.exists():
        s4.shapes.add_picture(str(img_penal), Inches(0.8), Inches(1.8), width=Inches(7.2))

    # Tarjeta explicativa al lado
    add_card(s4, Inches(8.3), Inches(1.8), Inches(4.2), Inches(4.8), "Hallazgos de Planta (Valladolid L5)")
    tb_hall = s4.shapes.add_textbox(Inches(8.5), Inches(2.4), Inches(3.8), Inches(4.0))
    tf_hall = tb_hall.text_frame
    tf_hall.word_wrap = True
    tf_hall.paragraphs[0].text = "#1 Ma_BM2_2 (Transportador Auxiliar):\n• TAP: 9.85 h/día | Dp: 33.1%\n• Crítica por tiempo de paro directo masivo."
    tf_hall.paragraphs[0].font.size = Pt(11)
    tf_hall.paragraphs[0].font.bold = True
    p = tf_hall.add_paragraph()
    p.text = "#2 ST-2390 (Estación de Montaje):\n• TAP: 4.27 h/día | Induce: 3.82 h a vecinas\n• Cuello de botella crónico que frena el final de línea."
    p.font.size = Pt(11)
    p.space_before = Pt(8)
    p = tf_hall.add_paragraph()
    p.text = "#3 ST-0260 (El Caso Paradójico):\n• TAP propio: ¡Sólo 0.68 h/día! (Dp 95.7%)\n• ¡Induce 10.92 h/día de parada a vecinas!\n• Conclusión: Puesto sin pulmón que paraliza aguas arriba y abajo."
    p.font.size = Pt(11)
    p.font.color.rgb = C_RED
    p.space_before = Pt(8)

    # =========================================================================
    # SLIDE 5: CURVA LONGITUDINAL DE CUELLOS DE BOTELLA
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_background(s5, C_LIGHT_BG)
    add_header(s5, "Radiografía de la Cadena: Cuello de Botella Medio de Puesto 1 a 91")

    img_cadena = Path("cuello_botella_cadena_montaje.png")
    if img_cadena.exists():
        s5.shapes.add_picture(str(img_cadena), Inches(0.8), Inches(1.8), width=Inches(8.2))

    add_card(s5, Inches(9.3), Inches(1.8), Inches(3.2), Inches(4.8), "Lectura de Flujo")
    tb_flujo = s5.shapes.add_textbox(Inches(9.45), Inches(2.4), Inches(2.9), Inches(4.0))
    tf_flujo = tb_flujo.text_frame
    tf_flujo.word_wrap = True
    tf_flujo.paragraphs[0].text = "• Visión Integral de Línea:\nIdentifica exactamente en qué orden físico se estrangula la cadencia."
    tf_flujo.paragraphs[0].font.size = Pt(11)
    p = tf_flujo.add_paragraph()
    p.text = "• Efecto Pulmón:\nLas zonas con amortiguamiento aíslan las averías, mientras los tramos rígidos transfieren la parada instantáneamente."
    p.font.size = Pt(11)
    p.space_before = Pt(10)
    p = tf_flujo.add_paragraph()
    p.text = "• Módulo Genérico:\nEste análisis no está 'hardcodeado': el módulo procesa cualquier configuración CSV de cualquier planta."
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = C_BLUE
    p.space_before = Pt(10)

    # =========================================================================
    # SLIDE 6: SIMULADOR DE CAPACIDAD WHAT-IF
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_background(s6, C_LIGHT_BG)
    add_header(s6, "Gemelo Digital Ligero: Simulación What-If y Retorno de Inversión (ROI)")

    add_card(s6, Inches(0.8), Inches(1.8), Inches(5.6), Inches(4.8), "¿Qué Pasa si Intervenimos en Mantenimiento?")
    tb_what = s6.shapes.add_textbox(Inches(1.0), Inches(2.4), Inches(5.2), Inches(4.0))
    tf_what = tb_what.text_frame
    tf_what.word_wrap = True
    tf_what.paragraphs[0].text = "• Escenario A: Reducción del 30% en TAP de ST-2390\n  - Recuperación directa de 1.28 horas de producción al día.\n  - Reducción del 45% en paradas inducidas aguas arriba.\n  - Balance: +108 motores extra producidos por jornada."
    tf_what.paragraphs[0].font.size = Pt(12)
    p = tf_what.add_paragraph()
    p.text = "• Escenario B: Desbloqueo de Buffer en ST-0260\n  - Al aumentar la capacidad de stock intermedio en 15 piezas, se amortiguan las microparadas.\n  - Se eliminan 4.5 horas de desabastecimiento inducido."
    p.font.size = Pt(12)
    p.space_before = Pt(12)

    add_card(s6, Inches(6.8), Inches(1.8), Inches(5.7), Inches(4.8), "Justificación Económica para Dirección", border_color=C_GREEN)
    tb_eco = s6.shapes.add_textbox(Inches(7.0), Inches(2.4), Inches(5.3), Inches(4.0))
    tf_eco = tb_eco.text_frame
    tf_eco.word_wrap = True
    tf_eco.paragraphs[0].text = "• De Coste a Retorno:\n  El mantenimiento preventivo tradicional se percibe como gasto. Con el simulador LOSSIA, cada intervención tiene un ROI cuantificado en unidades de motor."
    tf_eco.paragraphs[0].font.size = Pt(12)
    p = tf_eco.add_paragraph()
    p.text = "• Simulación en Tiempo Real:\n  Permite al responsable de producción ensayar escenarios antes de programar horas extra o paradas de línea."
    p.font.size = Pt(12)
    p.space_before = Pt(12)
    p = tf_eco.add_paragraph()
    p.text = "• Reducción de Pérdida Oculta:\n  Al año, atacar las 3 máquinas del Top Penalizante supone rescatar más de 25.000 motores de producción."
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = C_GREEN
    p.space_before = Pt(12)

    # =========================================================================
    # SLIDE 7: PREDICCIÓN DIARIA CON TIEMPO SIN FALLO (WEIBULL)
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    set_slide_background(s7, C_LIGHT_BG)
    add_header(s7, "Mantenimiento Prescriptivo: Supervivencia Weibull según Tiempo sin Fallo")

    img_riesgo = Path("reporte_riesgo_S43-D4.png")
    if img_riesgo.exists():
        s7.shapes.add_picture(str(img_riesgo), Inches(0.8), Inches(1.8), width=Inches(7.6))

    add_card(s7, Inches(8.7), Inches(1.8), Inches(3.8), Inches(4.8), "La Pregunta de la Jornada")
    tb_w = s7.shapes.add_textbox(Inches(8.85), Inches(2.4), Inches(3.5), Inches(4.0))
    tf_w = tb_w.text_frame
    tf_w.word_wrap = True
    tf_w.paragraphs[0].text = "¿Cuánto tiempo lleva la máquina funcionando sin parar?"
    tf_w.paragraphs[0].font.size = Pt(12)
    tf_w.paragraphs[0].font.bold = True
    tf_w.paragraphs[0].font.color.rgb = C_ORANGE
    p = tf_w.add_paragraph()
    p.text = "• Modelo Físico de Desgaste:\n  Rastreamos las horas acumuladas de producción continua (t_sin_fallo) frente a su MTBF histórico."
    p.font.size = Pt(11)
    p.space_before = Pt(8)
    p = tf_w.add_paragraph()
    p.text = "• Supervivencia Weibull (beta = 1.85):\n  Modela el régimen de fatiga acelerada de mordazas y holguras mecánicas."
    p.font.size = Pt(11)
    p.space_before = Pt(8)
    p = tf_w.add_paragraph()
    p.text = "• Prescripción para Relevo de Turnos:\n  Cada mañana emite un semáforo con motores en riesgo y tareas exactas: 'Reapriete mordazas en ST0261' antes de arrancar."
    p.font.size = Pt(11)
    p.font.bold = True
    p.space_before = Pt(8)

    # =========================================================================
    # SLIDE 8: LA PLATAFORMA TECNOLÓGICA & ESCALABILIDAD
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    set_slide_background(s8, C_LIGHT_BG)
    add_header(s8, "Ecosistema Tecnológico LOSSIA: Listo para la Fábrica del Futuro")

    add_card(s8, Inches(0.8), Inches(1.8), Inches(3.6), Inches(4.8), "1. Streamlit & Web App")
    tb_a = s8.shapes.add_textbox(Inches(0.95), Inches(2.5), Inches(3.3), Inches(3.9))
    tf_a = tb_a.text_frame
    tf_a.word_wrap = True
    tf_a.paragraphs[0].text = "• Interfaz intuitiva y moderna:\nAccesible desde tablet o PC en planta."
    tf_a.paragraphs[0].font.size = Pt(12)
    p = tf_a.add_paragraph()
    p.text = "• Filtros dinámicos:\nPor centro, tramo de línea, fechas y tipo de máquina."
    p.font.size = Pt(12)
    p.space_before = Pt(10)
    p = tf_a.add_paragraph()
    p.text = "• Dashboard HTML Offline:\nFunciona sin conexión en salas de control."
    p.font.size = Pt(12)
    p.space_before = Pt(10)

    add_card(s8, Inches(4.8), Inches(1.8), Inches(3.6), Inches(4.8), "2. Motor Agnóstico", border_color=C_BLUE)
    tb_b = s8.shapes.add_textbox(Inches(4.95), Inches(2.5), Inches(3.3), Inches(3.9))
    tf_b = tb_b.text_frame
    tf_b.word_wrap = True
    tf_b.paragraphs[0].text = "• Paquete Modular lossia/:\nCálculo desacoplado de la interfaz; altamente testeado y determinista."
    tf_b.paragraphs[0].font.size = Pt(12)
    p = tf_b.add_paragraph()
    p.text = "• Escalable a otras plantas:\nAplicable directamente a Sevilla, Mioveni o Curitiba sin reescribir código."
    p.font.size = Pt(12)
    p.space_before = Pt(10)
    p = tf_b.add_paragraph()
    p.text = "• Exportación Automática:\nGeneración de informes CSV y reportes ejecutivos."
    p.font.size = Pt(12)
    p.space_before = Pt(10)

    add_card(s8, Inches(8.8), Inches(1.8), Inches(3.7), Inches(4.8), "3. Impacto de Negocio", border_color=C_GREEN)
    tb_c = s8.shapes.add_textbox(Inches(8.95), Inches(2.5), Inches(3.4), Inches(3.9))
    tf_c = tb_c.text_frame
    tf_c.word_wrap = True
    tf_c.paragraphs[0].text = "• Reducción del 15-20% de TAI:\nAl atacar la causa raíz y no el síntoma."
    tf_c.paragraphs[0].font.size = Pt(12)
    p = tf_c.add_paragraph()
    p.text = "• Mantenimiento Proactivo:\nSe acabaron los fuegos imprevistos a mitad de turno."
    p.font.size = Pt(12)
    p.space_before = Pt(10)
    p = tf_c.add_paragraph()
    p.text = "• Criterio Único Compartido:\nLa dirección, los jefes de unidad y los operarios hablan el mismo idioma técnico."
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = C_GREEN
    p.space_before = Pt(10)

    # =========================================================================
    # SLIDE 9: CONCLUSIÓN Y CIERRE
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    set_slide_background(s9, C_NAVY)

    tb_end = s9.shapes.add_textbox(Inches(1.5), Inches(1.8), Inches(10.3), Inches(4.2))
    tf_end = tb_end.text_frame
    tf_end.word_wrap = True

    p = tf_end.paragraphs[0]
    p.text = "LOSSIA · HACKATHON HORSE"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = C_ORANGE

    p = tf_end.add_paragraph()
    p.text = "De la Telemetría al Impacto:\nUn Criterio Objetivo para la Excelencia Operativa"
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 255, 255)
    p.space_before = Pt(14)

    p = tf_end.add_paragraph()
    p.text = "1. Desmitificamos la parada propia: la máquina que más se para no siempre es la culpable.\n2. Filtramos el ruido de instrumentación para proteger los recursos de mantenimiento.\n3. Simulamos escenarios What-If para justificar inversiones en capacidad.\n4. Predecimos el riesgo diario basándonos en el tiempo de funcionamiento continuo."
    p.font.size = Pt(14)
    p.font.color.rgb = RGBColor(203, 213, 225)
    p.space_before = Pt(18)

    p = tf_end.add_paragraph()
    p.text = "¡Muchas gracias! ¿Preguntas?"
    p.font.size = Pt(20)
    p.font.bold = True
    p.font.color.rgb = C_ORANGE
    p.space_before = Pt(24)

    prs.save(output_path)
    print(f"🎉 Presentación guardada con éxito en: {Path(output_path).resolve()}")

if __name__ == "__main__":
    create_presentation()
