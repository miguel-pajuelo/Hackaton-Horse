# 🏭 LOSSIA · Plataforma de Inteligencia Operativa y Mantenimiento Prescriptivo
### **Hackathon Proyecto LOSSIA · HORSE Valladolid (Línea 5 de Montaje de Motores)**
*Organizado por HORSE & ICAI · Noviembre 2026*

---

## 🎯 Objetivo del Proyecto
Proporcionar a los responsables de producción y mantenimiento de **HORSE** una solución tecnológica integral que elimine la subjetividad en planta:
1. **Unificar el criterio analítico de paradas** diferenciando con rigor físico la **parada propia ($TAP$)** de la **parada inducida ($TAI = DES + SAT$)**, respondiendo objetivamente a por qué una máquina que se para poco puede ser la más penalizante.
2. **Filtrar anomalías de telemetría** (ej. rebote de fotocélula en `ST2235` con 22.022 paradas/día) para evitar intervenciones mecánicas innecesarias.
3. **Simular escenarios What-If** para evaluar el retorno de inversión (ROI) al intervenir cuellos de botella o insertar buffers intermedios con el gemelo digital de `simulador/` (p. ej. +29 motores/día eliminando las paradas de `PM_2250`).
4. **Predecir averías imprevistas** basándose en el **tiempo acumulado de marcha continua sin fallos ($t_{\text{sin\_fallo}}$ vs $MTBF$)** mediante un modelo de desgaste de Weibull ($\beta = 1.85$).
5. **Cerrar el ciclo agéntico (Agentic Closed-Loop)** mediante un copiloto con *Tool Calling* determinista (sin alucinaciones) capaz de generar borradores de órdenes de trabajo para SAP PM / GMAO.

---

## 📂 Estructura del Repositorio

El proyecto se encuentra organizado en módulos desacoplados y reproducibles:

```text
├── Streamlit/             # Cuadro de mandos web oficial (interfaz corporativa HORSE)
│   ├── app.py             # Aplicación principal Streamlit
│   ├── lossia.css         # Estilo visual editorial y retro-crema
│   └── graficos.py        # Visualizaciones de criticidad, reparto y objetivos
│
├── presentacion/          # Materiales de defensa y Pitch ante el Jurado
│   ├── Presentacion_LOSSIA_HORSE_Visual.pptx    # Presentación visual 16:9 (sin texto, diseño dashboard)
│   ├── GUION_PRESENTACION_LOSSIA.md             # Guion palabra por palabra para el pitch (5 min)
│   ├── construir_presentacion_visual_lossia.py  # Generador programático de las diapositivas
│   └── *.png                                    # Gráficos vectoriales de apoyo (SAT/DES, EDA, Simulador)
│
├── analisis_avanzado/     # Suite de Data Science, Fiabilidad y Módulos Autónomos
│   ├── 02_analisis_penalizantes.ipynb           # Análisis de máquinas penalizantes e IPL
│   ├── 04_analisis_cuellos_botella_generico.ipynb # Módulo agnóstico aplicable a cualquier fábrica
│   ├── 05_prediccion_fallos_diaria.ipynb        # Predictor diario por desgaste temporal (Weibull)
│   ├── predictor_fallos_diario.py               # Motor CLI de predicción y prescripción diaria
│   ├── analisis_cuellos_botella.py              # Clase universal BottleneckAnalyzer
│
├── chat/                  # Copiloto Agéntico "Pregunta a la Línea"
│   ├── herramientas.py    # Catálogo de herramientas deterministas (Zero-Hallucination)
│   ├── conexion.py        # Cliente de inferencia local / remoto
│   ├── kaggle_remoto.py   # Despliegue con Mistral Small 24B Q8 on-premise/Kaggle
│   └── README.md          # Documentación del agente y guía de conexión
│
├── simulador/             # Gemelo Digital y Simulación de Eventos Discretos
│   ├── simulador_linea.py # Cadena en serie con calibración de buffers por tramo
│   └── animacion_linea.py # Visualización dinámica del flujo de piezas
│
├── lossia/                # Motor de cálculo oficial determinista
│   ├── interfaz.py        # Fachada de carga y recálculo
│   ├── determinista.py    # Método de flechas y cálculo de severidad
│   ├── prioridades.py     # Criterio de ordenación de máquinas penalizantes
│   └── config.py          # Umbrales contractuales (Dp >= 90%, Tcy <= 80 cmin)
│
├── Datos_limpios/         # Telemetría depurada de la Línea 5 (Valladolid)
├── Resultados/            # KPIs y clasificaciones persistidas
└── tests/                 # Suite de pruebas unitarias y de equivalencia
```

---

## 🚀 Puesta en Marcha Rápida

### 1. Cuadro de Mandos Web (Streamlit)
```bash
streamlit run Streamlit/app.py
```

### 2. Predictor Diario de Averías (CLI)
Para emitir el informe ejecutivo de riesgo y prescripciones antes de arrancar el turno:
```bash
python analisis_avanzado/predictor_fallos_diario.py --dia S43-D4
```

### 3. Simulador de Capacidad y Buffers
```bash
python -m lossia.simulador ST_2390=30
python simulador/simulador_linea.py --buffer 10
```

### 4. Consultar la Presentación y el Guion
* La presentación visual para el jurado se encuentra en:  
  [`presentacion/Presentacion_LOSSIA_HORSE_Visual.pptx`](presentacion/Presentacion_LOSSIA_HORSE_Visual.pptx)
* El guion estructurado con notas de orador y defensa de Q&A se encuentra en:  
  [`presentacion/GUION_PRESENTACION_LOSSIA.md`](presentacion/GUION_PRESENTACION_LOSSIA.md)

---

## 🏆 Fortalezas Diferenciales ante el Jurado
* **Zero Hallucination:** El agente LLM razona mediante *Function Calling*; todas las cifras provienen del motor determinista oficial `lossia`.
* **Física de Fiabilidad:** Supervivencia modelada con Weibull ($\beta = 1.85$) en función del tiempo acumulado sin avería ($t_{\text{sin\_fallo}}$ vs $MTBF$).
* **Closed-Loop Action:** De la detección y el diagnóstico causal a la simulación What-If y la generación de órdenes de trabajo para SAP PM / GMAO.
* **Escalabilidad Global:** Algoritmos agnósticos preparados para desplegarse en cualquier centro de HORSE (Sevilla, Curitiba, Mioveni o Bursa).
