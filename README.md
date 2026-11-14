# LOSSIA · Máquinas penalizantes en la Línea 5 de HORSE Valladolid

Proyecto del Hackathon LOSSIA (HORSE e ICAI, noviembre de 2026). El objetivo es identificar qué
máquinas de la Línea 5 de montaje de motores penalizan de verdad la producción, explicar por qué y
estimar qué se ganaría actuando sobre ellas.

El proyecto se compone de cuatro partes que comparten los mismos datos y el mismo motor de cálculo:

1. **Limpieza de datos** de los registros diarios de la línea.
2. **Motor de análisis** (`lossia/`): indicadores, método de flechas y prioridades.
3. **Cuadro de mandos web** (`Streamlit/`): resumen, visualizaciones, detalle por máquina,
   simulación de la línea y el asistente KAIROS.
4. **Simulador de la línea** (`simulador/`): réplica de eventos discretos para evaluar mejoras.

## Datos

- Línea 5 de montaje, 91 operaciones, del 29/09/2026 al 23/10/2026 (16 días con datos).
- Por cada operación y día: tiempo funcionando (TBF), parada propia (TAP), desabastecimiento (DES),
  saturación (SAT), número de paradas (NAP) y piezas producidas (NPR).
- Originales en `Datos/`; datos depurados, alertas y registro de la limpieza en `Datos_limpios/`.

## Metodología

### Indicadores

| Indicador | Definición | Objetivo |
|---|---|---|
| Dp (disponibilidad propia) | TBF / (TBF + TAP) | ≥ 90 % |
| Tcy (tiempo de ciclo) | TBF / NPR, en centiminutos por pieza | ≤ 80 cmin |
| Fpm (frecuencia de paro) | NAP / NPR × 1000 | — |
| TAI (parada inducida) | DES + SAT: tiempo parada por culpa de las vecinas | — |
| TAP / TAI | Parada propia frente a parada inducida | > 1 = el problema es de la propia máquina |

Las operaciones en paralelo se fusionan en una sola etapa. Los umbrales están en `lossia/config.py`.

### Cuellos de botella y máquinas penalizantes

- **Método de flechas** (`lossia/determinista.py`): compara cuánto se bloquea cada etapa con cuánto
  se queda sin piezas. Una etapa es cuello de botella cuando las flechas de sus vecinas convergen en
  ella; la **severidad** mide cuánto frena el flujo.
- **Criterio de HORSE**: un cuello es **penalizante** si su severidad supera el 5 % y su cociente
  TAP/TAI es mayor que 1. Si no, es una víctima de su entorno.
- En la web, el ranking de cuellos se ordena por **severidad × TAP/TAI**.

### Simulador

Réplica de eventos discretos de la línea (`simulador/simulador_linea.py`):

- Cada etapa trabaja a su tiempo de ciclo y sufre paradas con la frecuencia y la duración medias
  reales; las paradas se generan al azar con esas medias.
- Entre etapas hay buffers de capacidad limitada. Su tamaño no viene en los datos y se ha calibrado
  en 8 piezas para reproducir la producción real.
- Las cifras de producción son la media de 5 jornadas simuladas, con los mismos números aleatorios
  en todos los escenarios, de modo que las diferencias se deben solo a la mejora evaluada.
- La producción simulada (1.521 motores/día) queda a menos de un 1 % de la real (1.530).

El simulador no reproduce un día concreto: sirve para **comparar escenarios** (qué ocurre si se
reducen las paradas de una o varias etapas, o si cambia el tamaño de un buffer).

## Resultados principales

- **PM_2020** es la máquina más penalizante: cuello de botella con severidad del 18 % y TAP/TAI de
  2,4. Fue la penalizante principal 8 de los 16 días.
- **ST_0261** es la segunda penalizante (TAP/TAI 1,3).
- **ST_0260** es el cuello con mayor severidad (39 %), pero con TAP/TAI de 0,38: sus paradas vienen
  sobre todo de sus vecinas, así que actuar sobre ella no resolvería el problema.
- **ST_2235** registra unas 22.000 paradas al día y un 20 % de disponibilidad, pero su contador de
  piezas no es fiable ningún día y la línea produce con normalidad. Apunta a un fallo del sensor,
  no de la máquina.
- **Simulación**: eliminar las paradas de **PM_2250** es la mejora con más impacto (+29 motores/día),
  porque sus paradas son largas (unos 8 minutos de media) y vacían los buffers. Eliminar las paradas
  de los cuellos de botella del método de flechas apenas cambia la producción: sus paradas son cortas
  y los buffers las absorben.

Conclusión: el método de flechas sirve para **diagnosticar** (qué máquina frena el flujo y si la
culpa es suya o de su entorno) y el simulador para **decidir** (qué arreglar primero y cuánto se gana).

## Cuadro de mandos web

Pestañas de la cabecera:

| Pestaña | Contenido |
|---|---|
| Resumen | Alertas de calidad de datos, insights principales y cifras de la línea |
| Visualizaciones | Reparto del tiempo, top penalizantes, evolución de objetivos y parada propia frente a inducida |
| Simulación | Animación de una jornada, mejora de una o varias etapas y tamaño de buffer por tramo |
| Máquinas | Detalle de cada etapa: indicadores, categoría, motivo de prioridad y evolución diaria |
| Datos | Tabla completa con descarga en CSV |

La barra lateral filtra por centro, línea, periodo, días de la semana, tipo de operación, tramo y
máquinas. **KAIROS**, el botón flotante de abajo a la derecha, responde preguntas sobre la línea con
un modelo de lenguaje que consulta las herramientas de `chat/`: todas las cifras salen del motor
oficial y cada respuesta indica si sus cifras están verificadas.

## Estructura del repositorio

```text
Streamlit/            Cuadro de mandos web
  app.py              Aplicación principal
  graficos.py         Gráficos de las visualizaciones
  lossia.css          Estilos
  requirements.txt    Dependencias
lossia/               Motor de análisis oficial
  datos.py            Carga y agregación por etapa
  kpis.py             Dp, Tcy, Fpm y paradas
  determinista.py     Método de flechas, severidad y criterio TAP/TAI
  prioridades.py      Ranking de prioridades y de mantenimiento
  interfaz.py         Punto de entrada para la web y el chat
  config.py           Umbrales y rutas
simulador/            Simulador de eventos discretos y animación de la línea
chat/                 Herramientas y conexión del asistente KAIROS
analisis_avanzado/    Análisis complementarios: penalizantes, módulo genérico de cuellos de
                      botella y predicción diaria de averías
presentacion/         Presentaciones y guion para el jurado
Datos/                Datos originales del reto
Datos_limpios/        Datos depurados, alertas y registro de la limpieza
Resultados/           Indicadores y rankings calculados por analisis.py
tests/                Pruebas del motor y del chat
Informacion_RETO/     Presentación oficial del reto
docs/                 Documentación de apoyo (referencia de estilo de la web)
limpieza.py           Limpieza de los datos originales
analisis.py           Cálculo de todos los resultados
01_limpieza.ipynb     Limpieza paso a paso
02_eda.ipynb          Análisis exploratorio
03_llm_kaggle.ipynb   Servidor del modelo de lenguaje en Kaggle
04_demo_remota.ipynb  Demo remota del asistente
```

## Instalación y uso

Requisitos: Python 3.10 o superior.

```bash
pip install -r Streamlit/requirements.txt
```

Orden de ejecución desde la raíz del repositorio:

```bash
python limpieza.py                     # 1. Datos/ -> Datos_limpios/
python analisis.py                     # 2. Datos_limpios/ -> Resultados/
streamlit run Streamlit/app.py         # 3. Cuadro de mandos web
```

Los pasos 1 y 2 solo son necesarios si cambian los datos: `Datos_limpios/` y `Resultados/` ya están
en el repositorio.

Otros comandos:

```bash
python simulador/simulador_linea.py --buffer 8          # ranking de motores/día ganados por etapa
python simulador/animacion_linea.py --mejorar PM_2250   # animación HTML de una jornada
python analisis_avanzado/predictor_fallos_diario.py --dia S43-D4   # informe de riesgo de un día
python -m pytest tests                                  # pruebas
```

### Conexión del asistente KAIROS

El asistente necesita un servidor del modelo de lenguaje compatible con la API de OpenAI (por
ejemplo, el que levanta `03_llm_kaggle.ipynb`). La conexión se configura en
`.streamlit/secrets.toml`:

```toml
LLM_BASE_URL = "https://<servidor>/v1"
LLM_MODEL    = "<nombre del modelo>"
LLM_API_KEY  = "<clave>"
```

Sin conexión, el resto del cuadro de mandos funciona con normalidad y KAIROS lo indica. Más detalle
en `chat/README.md` y `chat/REMOTO.md`.

## Limitaciones

- 16 días de datos: los resultados son robustos para el periodo, pero no permiten estudiar
  tendencias largas.
- Tres operaciones (ST_0295, ST_2235 y ST_3300) tienen el contador de piezas no fiable, así que no
  tienen tiempo de ciclo ni frecuencia de paro.
- El simulador supone paradas independientes con duración exponencial y tiempo de ciclo constante;
  el tamaño de los buffers está calibrado, no medido, y las operaciones en paralelo se tratan como
  una sola etapa.
- La reproducción de las esperas por etapa (DES y SAT) es moderada, aunque la producción total
  coincide con la real.

## Equipo

- **Alonso**: limpieza de datos y motor de análisis.
- **Gonzalo**: cuadro de mandos web y simulador.
- **Miguel**: asistente KAIROS e integración.
- **Jorge**: análisis avanzado y presentación.
