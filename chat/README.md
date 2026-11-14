# Pregunta a la línea en Kaggle

## Ejecutar el notebook

1. Abre `03_llm_kaggle.ipynb` en un notebook privado de Kaggle.
2. Selecciona **GPU T4 ×2** y habilita Internet para instalar llama.cpp. Añade como entradas [el dataset privado de la línea](https://www.kaggle.com/datasets/miguelpajuelo/horse-lossia-linea-5-datos-limpios) y [los pesos privados Q8_0](https://www.kaggle.com/datasets/miguelpajuelo/horse-mistral-small-32-24b-q8).
   El dataset de la línea debe contener estas carpetas del repo, con su estructura: `lossia/`, `chat/`, `Datos_limpios/` y `Resultados/`. El notebook localiza el repo por `lossia/interfaz.py` e importa `chat/herramientas.py`.
3. Ejecuta las celdas en orden. El servidor se inicia en `http://127.0.0.1:8080/v1` con CUDA, contexto de 16.384 tokens, una secuencia y temperatura 0,15 en el cliente. El notebook valida el hash de los pesos antes de cargarlo.
4. La prueba guarda `Datos_modelo/llm_benchmark.csv` en la salida de Kaggle. La columna de juicio preliminar ayuda a localizar las tres respuestas que requieren revisión semántica.

## Herramientas

Las cifras salen del motor oficial (`lossia.interfaz.cargar_motor` y `calcular`), el mismo que usa el dashboard: misma unidad de análisis por etapa (operaciones en paralelo fusionadas), mismas prioridades y mismo método de flechas. El modelo no calcula nada.

| Herramienta | Devuelve |
|---|---|
| `resumen_linea()` | Periodo, etapas analizadas, operaciones excluidas, incumplimientos de Dp y Tcy, cuello de botella principal y nº de alertas |
| `kpis_etapa(nombre)` | Horas por estado, Dp, Tcy, Fpm, categoría y motivo de prioridad, fiabilidad de los datos y alertas. Acepta `ST-0260`, `ST_0260`, `ST0260`… |
| `prioridades(n, categoria)` | Ranking oficial (`orden_vista`) con categoría y motivo |
| `cuello_botella()` | Cuellos relevantes del método de flechas: severidad, zona afectada y horas inducidas |
| `mantenimiento(n)` | Ranking por horas de parada propia al día, con aviso de datos dudosos |
| `alertas(nombre)` | Alertas de `alertas.json` con causa probable y recomendación |
| `glosario(termino)` | Definiciones fijas de los indicadores y conceptos |

`HerramientasLinea(dias=[...])` o `fijar_dias([...])` limita las respuestas al mismo periodo que tenga seleccionado el dashboard (días `AAAA-SWW-DD`). Sin días se usa el periodo completo.

Pruebas sin GPU: `python tests/test_chat_herramientas.py`.

## Conectar el cliente

El proceso cliente ejecuta las herramientas contra su copia de `Datos_limpios/` y `Resultados/` y envía al modelo solo los resultados necesarios para contestar.

```python
import os
from openai import OpenAI
from chat.herramientas import HerramientasLinea, preguntar

cliente = OpenAI(
    base_url=os.environ["LLM_BASE_URL"],
    api_key=os.environ.get("LLM_API_KEY", "local"),
)
herramientas = HerramientasLinea()  # o HerramientasLinea("Datos_limpios", "Resultados", dias=[...])
respuesta, llamadas, resultados, tokens = preguntar(
    cliente, os.environ["LLM_MODEL"], herramientas, "¿Qué disponibilidad propia tiene ST-2390?"
)
print(respuesta)
```

- llama.cpp local usa `LLM_BASE_URL=http://127.0.0.1:8080/v1` y `LLM_MODEL=mistral-small-3.2-24b-instruct-2506-q8_0` si lanzas con ese alias. Activa `--jinja`.
- Ollama local usa `LLM_BASE_URL=http://127.0.0.1:11434/v1` y el nombre instalado en `LLM_MODEL`. El modelo y su plantilla deben soportar herramientas.

## Exposición temporal opcional

Revisa las [condiciones de Kaggle](https://www.kaggle.com/terms) antes de exponer el endpoint. La duración máxima de una sesión de GPU es de 12 horas y el servidor se detiene con la sesión. [Documentación de Kaggle Notebooks](https://www.kaggle.com/docs/notebooks)

Para una prueba interactiva autorizada, configura `LLM_API_KEY` en el entorno del kernel antes de arrancar el servidor y en el entorno del cliente. Usa una clave larga y aleatoria. Con `cloudflared` instalado, ejecuta `cloudflared tunnel --url http://127.0.0.1:8080` en la misma sesión. Usa la URL HTTPS que imprima más `/v1` como `LLM_BASE_URL`, con el mismo alias y la misma clave. Usa el cliente en modo sin streaming y detén el túnel al acabar. Las consultas y los resultados que envíes al modelo pasarán por Kaggle y Cloudflare. [Documentación de Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)
