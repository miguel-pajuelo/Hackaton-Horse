# LOSSIA · Dashboard de máquinas penalizantes

```bash
pip install -r requirements.txt
streamlit run app.py
```

Coloca los CSV en `data/` (`datos_hackaton.csv` = datos limpios, `config_hackaton.csv` = orden de la línea)
o súbelos desde la barra lateral. Columnas esperadas: `Operacion, Week, Jour, TBF, TAP, DES, SAT, NAP, NPR`
(+ `Linea` opcional) y en config `Operacion, Orden_OP`. Tiempos en horas.

Pestañas: Mapa de la línea · Penalizantes · Objetivos (Dp ≥ 90 %, Tcy ≤ 80 cmin, Fpm) · Detalle máquina · Tabla.
