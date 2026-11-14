# 🎤 GUION DE PRESENTACIÓN — PROYECTO LOSSIA
### **Hackathon LOSSIA · HORSE Valladolid (Línea 5 de Montaje)**
*Duración estimada: 5 minutos | 9 Diapositivas | Enfoque: Técnico, Industrial y de Negocio*

---

## ⏱️ ESTRUCTURA Y TIEMPOS DEL PITCH

| Diapositiva | Título / Tema | Duración Sugerida |
| :---: | :--- | :---: |
| **Slide 1** | Portada: LOSSIA — La verdad objetiva en planta | 0:25 min |
| **Slide 2** | El Dolor: La trampa del tiempo absoluto y la subjetividad | 0:45 min |
| **Slide 3** | Metodología LOSSIA: Desacoplo físico de culpa y filtros de sensor | 0:45 min |
| **Slide 4** | Diagnóstico Real: Top penalizantes (¿Por qué 2h > 10h?) | 0:50 min |
| **Slide 5** | Radiografía Longitudinal: Cuello de botella medio de puesto 1 a 91 | 0:45 min |
| **Slide 6** | Gemelo Digital Ligero: Simulación de Capacidad What-If & ROI | 0:45 min |
| **Slide 7** | Capa Predictiva: Supervivencia Weibull según tiempo sin fallar ($t_{\text{sin\_fallo}}$) | 0:55 min |
| **Slide 8** | Plataforma Tecnológica: Streamlit, motor agnóstico y escalabilidad | 0:35 min |
| **Slide 9** | Conclusión y Cierre: De la telemetría al impacto | 0:20 min |
| **Total** | **Pitch Principal** | **~5:20 min** |

---

## 📑 DIAPOSITIVA A DIAPOSITIVA: QUÉ DECIR Y QUÉ DESTACAR

---

### Diapositiva 1: Portada
* **Visual:** Fondo azul marino HORSE con acento naranja. Título: *LOSSIA: Entender las Máquinas Penalizantes y Predecir el Fallo Diario*.
* **Guion del Presentador:**
  > *"Buenos días a todos. Somos el equipo LOSSIA. Hoy venimos a presentaros una solución integral diseñada específicamente para la Línea 5 de Montaje de Motores de Valladolid. Nuestro objetivo ha sido responder a una necesidad crítica de HORSE: transformar la telemetría masiva de paradas en un criterio objetivo, unificado y prescriptivo que permita a cualquier persona de planta —con o sin experiencia— tomar las decisiones correctas de mantenimiento y producción."*

---

### Diapositiva 2: El Dolor de Planta y la Pregunta Trampa
* **Visual:** 3 tarjetas: Subjetividad Operativa, La Pregunta Trampa (¿Por qué 2h > 10h?), Efecto Cascada en Línea.
* **Guion del Presentador:**
  > *"Actualmente en planta, el análisis de paradas se realiza de forma manual y varía drásticamente según la persona que lo interprete. Pero además, nos enfrentamos a una gran paradoja industrial:*  
  > *¿Por qué una máquina que se para 10 horas puede ser menos penalizante para la fábrica que una que se para sólo 2 horas?*  
  > *La respuesta está en la física del flujo: una máquina con 10 horas de parada pero con amplios pulmones intermedios solo consume stock intermedio sin asfixiar la línea. En cambio, una máquina en el corazón del flujo que se para 2 horas sin buffer provoca un efecto dominó devastador: desabastece aguas abajo (starving / DES) y satura aguas arriba (blocking / SAT), paralizando a decenas de compañeras. En LOSSIA no buscamos a la que más tiempo se para; buscamos a la que realmente estrangula la fábrica."*

---

### Diapositiva 3: Metodología LOSSIA y Desacoplo de Culpa
* **Visual:** Estándares contractuales de HORSE ($Dp \ge 90\%$, $Tcy \le 80\text{ cmin}$, $Fpm$) frente a las innovaciones analíticas de LOSSIA (Índice IPL y filtrado de anomalías de sensor).
* **Guion del Presentador:**
  > *"Para resolver esto, implementamos los estándares contractuales de HORSE: Disponibilidad Propia ($Dp \ge 90\%$) y Tiempo de Ciclo ($Tcy \le 80\text{ cmin}$). Pero dimos dos pasos clave más allá:*  
  > *Primero, creamos el Índice de Penalización en Línea (IPL), que normaliza la culpa real combinando parada propia con impacto inducido en vecinas.*  
  > *Segundo, realizamos una higiene industrial profunda de los datos: en la estación `ST2235` detectamos 22.000 microparadas diarias con apenas 2.300 motores fabricados. Cualquier algoritmo estándar habría enviado al equipo mecánico a desmontarla. Nuestro modelo detectó inmediatamente que se trataba de un rebote de señal en la fotocélula hacia la tarjeta del PLC. Solucionamos el problema en software antes de gastar recursos mecánicos en balde."*

---

### Diapositiva 4: Diagnóstico Real — Parada Propia vs Inducida a Vecinas
* **Visual:** Gráfico de barras comparando Parada Propia ($TAP$) en rojo vs Paradas Inducidas a Vecinas ($TAI_{\text{inducido}}$) en azul.
* **Guion del Presentador:**
  > *"Aquí tenéis la evidencia empírica de la Línea 5:*  
  > *En el puesto #88 (`Ma_BM2_2`), tenemos una parada masiva directa (9.85 h/d) que destroza su disponibilidad propia ($33\%$).*  
  > *Pero mirad la estación #20 (`ST-0260`): su parada propia es de apenas 40 minutos al día (0.68 h/d), con una disponibilidad excelente del 95.7%. Cualquiera diría que está sana. Sin embargo, genera más de 10.9 horas de parada inducida a sus compañeras cada jornada. Es el cuello de botella invisible que asfixia a la línea. Gracias a LOSSIA, el equipo de mantenimiento sabe que debe intervenir en ST-0260 antes que en muchas máquinas que aparentemente fallan más."*

---

### Diapositiva 5: Radiografía Longitudinal de la Cadena
* **Visual:** Curva completa del cuello de botella medio a lo largo de las 91 estaciones y 85 etapas de montaje.
* **Guion del Presentador:**
  > *"Esta es la radiografía longitudinal completa de la Línea 5 de Valladolid. A diferencia de un análisis estático por puesto, este gráfico permite ver el comportamiento dinámico del flujo: cómo los pulmones intermedios absorben perturbaciones en ciertos tramos y cómo se propagan las ondas de choque en otros.*  
  > *Y lo más importante: este motor no está hecho a medida para Valladolid; es un módulo genérico que puede conectarse a las líneas de Sevilla, Mioveni o Curitiba simplemente cambiando el archivo de configuración."*

---

### Diapositiva 6: Gemelo Digital Ligero — Simulación What-If & ROI
* **Visual:** Escenarios de intervención: reducción del $TAP$ en `ST-2390` (+108 motores/día) y amortiguamiento de buffers.
* **Guion del Presentador:**
  > *"Un buen diagnóstico debe llevar a la acción. Por eso integramos un simulador de capacidad interactivo. Si el director de planta nos pregunta: '¿Qué gano si invierto en mejorar un 30% la estación crítica ST-2390?', el simulador responde de inmediato: recuperamos 1.28 horas efectivas y ganamos 108 motores adicionales al día.*  
  > *Convertimos el mantenimiento de ser un centro de coste a ser un motor de rentabilidad con ROI medible en unidades producidas."*

---

### Diapositiva 7: Capa Predictiva — Tiempo sin Fallo y Supervivencia Weibull
* **Visual:** Reporte diario de averías con semáforos, scatter plot de horas acumuladas sin fallo vs probabilidad y Top 10 en riesgo.
* **Guion del Presentador:**
  > *"El último eslabón de LOSSIA es la anticipación: ¿qué va a pasar hoy?*  
  > *Para predecir averías no usamos una caja negra teórica; implementamos un modelo de supervivencia y desgaste de Weibull con parámetro $\beta = 1.85$. El sistema rastrea cuántas horas continuas de producción lleva cada máquina funcionando sin averiarse ($t_{\text{sin\_fallo}}$) frente a su vida media ($MTBF$).*  
  > *Si una estación como ST0261 supera el 120% de su ciclo de vida esperado sin revisión y sus microparadas previas repuntan, el sistema emite una alerta naranja antes del relevo de turnos con una prescripción concreta: 'Inspeccionar holgura y lubricar mordazas antes del arranque'. Evitamos la avería antes de que detenga la producción."*

---

### Diapositiva 8: Plataforma Tecnológica y Usabilidad
* **Visual:** Capturas de la App Streamlit (vistas de reparto, criticidad, objetivos) y arquitectura modular del paquete `lossia/`.
* **Guion del Presentador:**
  > *"Toda esta inteligencia está desplegada en una interfaz web ágil y visual desarrollada en Streamlit, con diseño corporativo HORSE. Dispone de filtros temporales, navegación por etapas y selección de centros. Además, generamos un cuadro de mandos HTML autónomo que funciona offline sin requerir servidores.*  
  > *El código está desacoplado, documentado y listo para producción."*

---

### Diapositiva 9: Conclusión y Cierre
* **Visual:** Resumen de valor: Desmitificación de paradas, higiene de datos, simulación de capacidad y predicción prescriptiva.
* **Guion del Presentador:**
  > *"En conclusión: con LOSSIA hemos transformado datos brutos en una herramienta operativa que unifica criterios, filtra el ruido, revela los verdaderos cuellos de botella y prescribe acciones preventivas antes del arranque de cada jornada.*  
  > *Muchísimas gracias por vuestro tiempo y quedamos a vuestra disposición para cualquier pregunta."*

---

# 🛡️ CHEAT SHEET DE PREGUNTAS DIFÍCILES DEL JURADO (Q&A)

### P1 (Alberto de los Ojos - AI Director): *"¿Por qué habéis usado un modelo Weibull y no una red neuronal o un XGBoost puro para predecir paradas?"*
* **Respuesta ganadora:**  
  *"Con 16 días de histórico en una línea industrial, un modelo puramente de Deep Learning o un ensemble complejo sufriría un sobreajuste severo sin base física. La distribución de Weibull con $\beta = 1.85$ incorpora la física de la degradación y el desgaste acumulativo de la maquinaria industrial (curva de la bañera), garantizando que el tiempo transcurrido sin averías incremente la probabilidad condicional de fallo de forma coherente con la realidad mecánica de planta."*

### P2 (Marcos Recio - Head of Agentic AI): *"¿Cómo interactúa un operario o jefe de unidad con este sistema en el día a día?"*
* **Respuesta ganadora:**  
  *"Al inicio de cada turno (6:00, 14:00, 22:00), el jefe de unidad abre la vista del día en Streamlit o recibe el reporte prescriptivo diario. En 30 segundos ve el semáforo global, las 3 máquinas en riesgo alto y la acción exacta prescrita (ej. 'revisar apriete en ST0261'). Pasa de apagar fuegos imprevistos a realizar mantenimiento preventivo dirigido antes de dar la orden de arranque."*

### P3 (Emma Llamas / Martin Gallardo - Digital Twins & Process): *"¿Cómo calculáis las paradas inducidas a vecinas si no tenéis una simulación física por eventos discretos milisegundo a milisegundo?"*
* **Respuesta ganadora:**  
  *"Utilizamos el principio de propagación de línea acoplada de HORSE: correlacionamos el $TAP$ de cada estación con la saturación ($SAT$) de la estación inmediatamente anterior y el desabastecimiento ($DES$) de la posterior, ponderado por la presencia y capacidad de los pulmones intermedios. Esto nos da un gemelo digital ligero analítico que no consume computación pesada pero captura con exactitud del 95% el efecto dominó."*
