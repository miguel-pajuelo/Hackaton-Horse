# LOSSIA · Línea 5, Montaje Valladolid

Desde la raíz del repositorio:

```bash
python -m pip install -r Streamlit/requirements.txt
python -m streamlit run Streamlit/app.py
```

El resumen muestra tres indicadores, los principales hallazgos y el informe de calidad de toda la línea. Las cinco tarjetas abren las categorías de visualización. El menú **Opciones** da acceso al detalle por máquina, la tabla y el restablecimiento de filtros. El botón de descarga exporta el CSV con los filtros de la barra lateral aplicados.

**Opciones → Configuración de datos** permite cambiar los CSV. Por defecto se cargan `Datos_limpios/datos_limpios.csv` y `Datos_limpios/config_limpia.csv`. El CSV de datos espera `Operacion, Week, Jour, TBF, TAP, DES, SAT, NAP, NPR` con tiempos en horas. Si falta `Orden_OP`, se cruza con el CSV de configuración por `Operacion` y `Linea` cuando la columna existe en ambas fuentes.

Se mantienen los criterios iniciales de limpieza. Se analizan las operaciones con `incluir_analisis` y se incluyen las filas con TAP sospechoso hasta que se active su exclusión. Los informes JSON y de limpieza del repositorio se muestran con la fuente predeterminada.

El logotipo se extrajo de `Informacion_RETO/presntacion_reto_lossia.pptx` (`ppt/media/image22.png`).
