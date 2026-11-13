from pathlib import Path
from lossia import config

# Cada línea apunta a sus propios datos limpios y resultados oficiales.
CENTROS = {
    "valladolid": {
        "nombre": "Valladolid",
        "lineas": {
            "linea_5": {
                "nombre": "Línea 5",
                "datos": config.DIR_LIMPIOS,
                "resultados": config.DIR_RESULTADOS,
            },
        },
    },
}
