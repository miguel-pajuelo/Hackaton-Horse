# 🎤 GUION DE PRESENTACIÓN — PROYECTO LOSSIA (EDICIÓN VISUAL)
### **Hackathon LOSSIA · HORSE Valladolid (Línea 5 de Montaje)**
*Alineado 100% con el diseño visual del Dashboard de Alonso (Fondo crema, tipografía Georgia, sin muros de texto)*
*Duración recomendada: 4:30 a 5:00 minutos*

---

## ⏱️ ESTRUCTURA Y TIEMPOS

| Slide | Sección | Visual en Pantalla | Tiempo |
| :---: | :--- | :--- | :---: |
| **01** | **PORTADA** | Estilo editorial LOSSIA (ICAI · HORSE) | 0:20 min |
| **02** | **EDA** | 16 días · 85 etapas · ST2235 (22.022 vs 2.382) · Descomposición TBF/TAP/TAI | 0:45 min |
| **03** | **DASHBOARD** | El monitor en vivo oficial: ST_0260 (368.5h inducidas) vs ST_2235 | 0:50 min |
| **04** | **PROPAGACIÓN** | Mecanismo físico: Saturación (SAT) vs Desabastecimiento (DES) · Asfixia x16.1 | 0:50 min |
| **05** | **SIMULADOR** | Escenario What-If ST-2390 (-30% TAP $\to$ +108 motores/día) | 0:45 min |
| **06** | **INFORME DE FALLOS** | Semáforo diario, ranking de riesgo y modelo de desgaste Weibull ($t_{\text{sin\_fallo}}$ vs MTBF) | 0:50 min |
| **07** | **MEJORAS FUTURAS** | Streaming IoT · Gemelo Digital 3D · Despliegue Multi-Planta · Auto-GMAO | 0:35 min |
| **08** | **CIERRE** | Resumen y Turno de preguntas | 0:15 min |

---

## 🗣️ GUION SLIDE A SLIDE (QUÉ DECIR EN CADA DIAPOSITIVA)

---

### SLIDE 01 · PORTADA
* **Lo que se ve:** Fondo crema, logotipo LOSSIA, acento terracota, título editorial *"Informe de la línea 5 — Valladolid"*.
* **Qué decir:**
  > *"Buenos días. Somos el equipo LOSSIA. Os presentamos nuestra plataforma para la Línea 5 de Montaje de Valladolid: una solución que unifica el criterio analítico de planta, desvela los verdaderos cuellos de botella y anticipa averías antes de arrancar cada turno."*

---

### SLIDE 02 · EDA (Exploración y Calidad de Telemetría)
* **Lo que se ve:** KPIs gigantes: `16` Días, `85` Etapas, `91` Operaciones, `2.382` Motores/día.
  * Gráfico 1: Comparativa `2.382` piezas vs `22.022` paradas en `ST2235` (Alerta: Rebote de señal en PLC).
  * Gráfico 2: Descomposición del tiempo (81.8% TBF, 8.4% TAP y 9.8% TAI inducido externo).
* **Qué decir:**
  > *"Comenzamos con la fase de EDA y calidad de datos sobre 16 jornadas reales. Nuestro primer hallazgo crítico fue separar el ruido de la realidad mecánica:*  
  > *En la estación ST2235, los datos brutos marcaban 22.000 paradas diarias con solo 2.300 motores fabricados: ¡9 paradas por motor! Un análisis ingenuo habría mandado al taller a desmontar la máquina. Nuestro algoritmo detectó inmediatamente que se trataba de un rebote de señal en la fotocélula hacia la tarjeta del PLC. Corregimos el problema en software y protegimos los recursos de mantenimiento.*  
  > *Además, demostramos que casi un 10% del tiempo de la fábrica se pierde por paradas inducidas (TAI): máquinas paradas esperando a que otra termine o desatasque."*

---

### SLIDE 03 · DASHBOARD (Monitor Oficial de la Línea)
* **Lo que se ve:** La captura exacta del dashboard desarrollado por el equipo en Streamlit:
  * Tarjeta `ST_0260`: Severidad `39 %`, `368.5 h` inducidas a sus vecinas.
  * Tarjeta `ST_2235`: `14.1 h/día` TAP, `20.2 %` Dp.
  * Gauges inferiores: `95.1 %` Dp media, `78/84` etapas por encima del 90%, y matriz de tiempo de ciclo (`76/84 < 80 cmin`).
* **Qué decir:**
  > *"Este es nuestro cuadro de mandos oficial. Diseñado para que cualquier persona en planta, desde el Jefe de Unidad hasta el técnico de mantenimiento, tenga exactamente la misma verdad operativa.*  
  > *Aquí resolvemos la gran pregunta del hackathon: ¿Por qué una máquina que se para poco puede ser la más penalizante?*  
  > *Mirad la estación ST_0260: tiene una parada propia pequeña, pero genera 368.5 horas inducidas a sus vecinas. Al estar en un cuello de botella sin buffer, asfixia a toda la línea aguas arriba y aguas abajo. El dashboard la sitúa en el centro del radar con el método de flechas."*

---

### SLIDE 04 · PROPAGACIÓN (El Efecto Dominó: SAT vs DES)
* **Lo que se ve:** KPIs superiores: `ST_0260` (Puesto #20), `0.68 h` TAP, `10.92 h` Inducidas a vecinas, `x 16.1` Multiplicador de asfixia.
  * Diagrama 1 (Física del flujo): Onda inversa hacia aguas arriba (Saturación / SAT / Blocking) vs Onda directa hacia aguas abajo (Desabastecimiento / DES / Starving).
  * Diagrama 2 (El rol del buffer): Cómo un pulmón intermedio absorbe microparadas frente a la rigidez de un tramo sin pulmón.
  * Gráfico empírico comparativo: `ST_0260` (amplifica x16.1) vs `ST-2390` (amortiguada con buffer x0.9).
* **Qué decir:**
  > *"¿Cómo se propaga un cuello de botella en una línea en serie?*  
  > *La parada se transmite en dos direcciones simultáneas:*  
  > *Aguas arriba provoca SATURACIÓN (SAT o Blocking): la estación anterior no puede soltar su pieza, su buffer se llena y se detiene.*  
  > *Aguas abajo provoca DESABASTECIMIENTO (DES o Starving): la estación posterior se queda sin suministro, agota su buffer y se detiene.*  
  > *Y aquí está la clave: si el tramo carece de buffer intermedio, como ocurre en la estación ST_0260, la parada propia de sólo 40 minutos al día genera 10.9 horas de paradas inducidas a sus vecinas. ¡Un factor de amplificación de 16 veces!*  
  > *Por eso, intervenir en ST_0260 no solo repara una máquina: libera a 10 puestos adyacentes del estrangulamiento."*

---

### SLIDE 05 · SIMULADOR (Capacidad What-If & ROI)
* **Lo que se ve:** Escenario de intervención en `ST-2390`:
  * `TAP -30%` $\to$ `+1.28 h / día` recuperadas.
  * `-45%` paradas inducidas a vecinas.
  * Tarjeta verde gigante: `+108 motores / día` $\to$ `+25.000 motores / año`.
* **Qué decir:**
  > *"Diagnosticar no basta; hay que justificar la acción. Integramos un simulador de capacidad What-If:*  
  > *¿Qué ocurre si intervenimos en la máquina crítica ST-2390 reduciendo su parada propia un 30% con reapriete y lubricación?*  
  > *El simulador demuestra que se desacopla la línea: ganamos 1.28 horas netas al día y producimos 108 motores adicionales por jornada. Eso son más de 25.000 motores extra al año. El mantenimiento deja de ser un gasto y se convierte en una palanca directa de facturación."*

---

### SLIDE 06 · INFORME DE POSIBLES FALLOS (Predicción por Desgaste Temporal)
* **Lo que se ve:** Semáforo diario `⚠️ RIESGO MODERADO · JORNADA S43-D4`.
  * Top máquinas en riesgo hoy: `#1 ST0261 (65.6%)`, `#2 ST-2380 (56.9%)`, `#3 PM_0110 (55.2%)`.
  * Curva física de desgaste de Weibull ($\beta = 1.85$): relación entre horas continuas de marcha sin fallo ($t_{\text{sin\_fallo}}$) y $MTBF$.
  * Caso ST0261: 216 horas continuas sin pararse $\to$ 275% de su vida media agotada $\to$ fatiga inminente.
* **Qué decir:**
  > *"Para anticiparnos a la jornada siguiente, desarrollamos el predictor diario de averías. Pero no usamos una caja negra teórica; implementamos un modelo de supervivencia de Weibull con tasa de fallo creciente ($\beta = 1.85$).*  
  > *Rastreamos cuánto tiempo continuo lleva cada estación funcionando sin avería frente a su MTBF histórico.*  
  > *En la jornada S43-D4, la estación ST0261 acumulaba 216 horas de producción ininterrumpida: el 275% de su vida media. Su probabilidad de fallo se disparó al 65.6%. El informe diario emitió una prescripción antes del relevo de turnos: 'Inspeccionar mordazas y lubricar antes del arranque'. Evitamos la parada sorpresa a mitad de turno."*

---

### SLIDE 07 · MEJORAS FUTURAS (Roadmap)
* **Lo que se ve:** Cuadrícula de 4 tarjetas visuales:
  1. *Streaming IoT en Tiempo Real* (OPC-UA / MQTT, < 1s latencia).
  2. *Gemelo Digital 3D & Simulación Discreta* (AnyLogic, buffers flexibles, AGVs).
  3. *Despliegue Multi-Planta HORSE* (Valladolid L5 $\to$ Sevilla, Mioveni, Curitiba, Bursa).
  4. *Prescripción Autónoma con GMAO* (Disparo automático de órdenes de trabajo en SAP PM).
* **Qué decir:**
  > *"Para escalar esta solución en HORSE, proponemos 4 vías claras:*  
  > *Primero, conectar la telemetría en streaming mediante OPC-UA o MQTT con latencia subsegundo.*  
  > *Segundo, alimentar un gemelo digital 3D por eventos discretos que simule el tránsito de AGVs y buffers dinámicos.*  
  > *Tercero, escalar este motor agnóstico a las plantas de Sevilla, Mioveni o Curitiba.*  
  > *Y cuarto, integrar la prescripción directamente con SAP PM para que la orden de trabajo se genere de forma autónoma antes de que empiece el turno."*

---

### SLIDE 08 · CIERRE
* **Lo que se ve:** Logotipo LOSSIA · HORSE. Subtítulo: *"Excelencia Operativa en la Línea 5"*. Preguntas.
* **Qué decir:**
  > *"En conclusión: LOSSIA aporta rigor analítico, desvela los cuellos de botella invisibles, cuantifica el retorno de cada intervención y anticipa el riesgo diario.*  
  > *Muchas gracias por vuestra atención. Quedamos a vuestra disposición para las preguntas."*
