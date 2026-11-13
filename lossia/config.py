"""
Parámetros del análisis de máquinas penalizantes (reto LOSSIA).

Todo lo que es una decisión de diseño está aquí para poder cambiarlo sin tocar la lógica.
"""
from __future__ import annotations

from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DIR_LIMPIOS = BASE / "Datos_limpios"
DIR_RESULTADOS = BASE / "Resultados"

# --- Referencias de la presentación del reto ---------------------------------
TCY_MAX_CMIN = 80.0      # tiempo de ciclo objetivo (centiminutos por pieza)
DP_MIN = 0.90            # disponibilidad propia mínima TBF / (TBF + TAP)
CMIN_POR_HORA = 6000.0   # 1 h = 60 min = 6000 cmin

# --- Estructura de la línea ---------------------------------------------------
# Tipos que NO forman parte de la cadena serie del método determinista
# (sí entran en los KPIs y en la lista de mantenimiento).
TIPOS_FUERA_CADENA = {"Manutención / auxiliar"}

# Grupos de estaciones en paralelo que se fusionan en una sola etapa.
#   None  -> se detectan automáticamente a partir de las entradas 'posible_paralelo'
#            de registro_limpieza.json (operaciones cercanas en Orden_OP)
#   []    -> no se fusiona nada
#   [["ST_2375", "ST_2376"], ...] -> grupos fijados a mano (Operacion_norm)
GRUPOS_PARALELO: list[list[str]] | None = None
DISTANCIA_MAX_PARALELO = 3   # posiciones de Orden_OP para agrupar paralelos detectados

# --- Método determinista -----------------------------------------------------
# Severidad mínima (fracción del tiempo requerido) para considerar un cuello de botella
# "relevante". Por debajo, las flechas convergen pero la evidencia es débil (ruido).
SEVERIDAD_MIN = 0.05

# --- Granularidades -----------------------------------------------------------
GLOBAL = "GLOBAL"
NIVELES = ("global", "dia")
