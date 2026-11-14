# Benchmark de referencia de Mistral Small 3.2 24B Q8_0

- La versión 1 del notebook privado de Kaggle completó las 15 preguntas en dos Tesla T4. El detalle está en `llm_benchmark.csv`.
- El verificador aceptó las cifras en 15 de 15 respuestas. La revisión manual detectó que la pregunta 4 daba en minutos valores medidos en centésimas de minuto.
- Las llamadas coincidieron con las esperadas en 13 de 15 preguntas (86,7 %). En la 4 se aplicó un filtro de categoría incorrecto y en la 9 faltó consultar el glosario.
- La latencia media fue de 11,69 s. La media por pregunta fue de 8,42 tokens/s, incluyendo los turnos de herramientas.
- Los picos de VRAM fueron de 13.509 MiB y 12.891 MiB en las dos T4.
- En los casos sin datos, la respuesta sobre temperatura confundió la falta de mediciones con el acceso en tiempo real. La de costes reconoció que la cifra no estaba disponible.
- Ante la premisa falsa, Mistral consultó la etapa correcta, pero afirmó que ST_0030 no produce. El motor la excluye por falta de datos y no permite concluir cuánto produce.
