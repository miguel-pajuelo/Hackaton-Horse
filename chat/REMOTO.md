# Demo remota · cómo se conecta la página con el modelo de Kaggle

El modelo (Mistral Small 3.2 en llama.cpp) escucha en `127.0.0.1:8080` **dentro** de la sesión de
Kaggle, que no es accesible desde fuera. Un *Quick Tunnel* de Cloudflare le da una URL pública
temporal (`https://…trycloudflare.com`). La URL cambia en cada sesión y muere con ella (máx. 12 h).

Las herramientas (pandas + motor oficial) se ejecutan siempre donde corre Streamlit. Al modelo
solo le llegan la pregunta y los resultados que necesita para redactar.

## Archivos

| Archivo | Para qué |
|---|---|
| `04_demo_remota.ipynb` | Notebook de Kaggle: arranca el modelo (celdas de `03`) y abre el túnel |
| `chat/crear_demo_remota.py` | Regenera `04` a partir de `03` si cambia el arranque del modelo |
| `chat/kaggle_remoto.py` | Descarga `cloudflared`, abre el túnel, lanza Streamlit en Kaggle |
| `chat/conexion.py` | Lado de la app: lee la configuración, comprueba el servidor y pasa al plan B |
| `tests/test_chat_conexion.py` | Pruebas con un servidor simulado |

## Preparar Kaggle (una vez)

1. El dataset de la línea debe incluir `lossia/`, `chat/`, `Streamlit/`, `Datos_limpios/`,
   `Resultados/` y `.streamlit/` (sin `__pycache__`).
2. Importa `04_demo_remota.ipynb` como notebook privado y adjunta el dataset de la línea y el de
   pesos Q8_0.
3. *Add-ons → Secrets*: crea `LLM_API_KEY` con una clave larga y aleatoria (por ejemplo,
   `python -c "import secrets; print(secrets.token_urlsafe(32))"`) y actívalo para el notebook.
4. *Settings*: **GPU T4 ×2** e **Internet on**.

## Modo «app» (recomendado para la demo)

Streamlit corre en Kaggle y el túnel publica la **página**; el modelo no se expone.

1. En la primera celda de código deja `MODO = "app"`.
2. *Run all*. La celda «Abrir el túnel» imprime `Abre la página en: https://….trycloudflare.com`.
3. Abre esa URL en cualquier navegador o móvil.
4. Deja corriendo la celda «Mantener la sesión activa».

Ojo: Streamlit no tiene login. Cualquiera con la URL verá el dashboard mientras dure la sesión.

## Modo «modelo» (página fuera de Kaggle)

El túnel publica el **modelo** y la página corre en tu PC o en Streamlit Cloud.

1. `MODO = "modelo"` y *Run all*. La celda imprime la configuración.
2. Donde corra Streamlit, define (variables de entorno o *Secrets* de Streamlit Cloud):
   ```toml
   LLM_BASE_URL = "https://….trycloudflare.com/v1"
   LLM_MODEL    = "mistral-small-3.2-24b-instruct-2506-q8_0"
   LLM_API_KEY  = "el mismo valor que el secreto de Kaggle"
   ```
3. La app llama a `chat.conexion.conectar(st.secrets)` y, si responde, usa `estado.cliente()`.

Cada nueva sesión de Kaggle da otra URL: hay que actualizar `LLM_BASE_URL`.

## Plan B local (si Kaggle o el túnel fallan en directo)

`conectar()` prueba primero el servidor principal y, si no responde, el plan B:

```toml
LLM_FALLBACK_BASE_URL = "http://127.0.0.1:11434/v1"   # Ollama
LLM_FALLBACK_MODEL    = "<nombre del modelo en `ollama list`>"
```

Usa un modelo occidental con soporte de herramientas que quepa en el portátil (por ejemplo,
Ministral 3 14B o, en equipos modestos, uno más pequeño de Mistral). Comprueba su nombre exacto
con `ollama list` y prueba antes las preguntas de la demo.

## Limitaciones

- Usar un notebook de Kaggle como servidor con túnel es aceptable para una demo puntual, no como
  servicio permanente. Revisa las condiciones de uso de Kaggle.
- Las preguntas y los resultados de las herramientas pasan por Kaggle y Cloudflare.
- `llama-server` no pide clave en `/health` ni en `/v1/models`, así que `conectar()` puede dar OK
  con una clave equivocada; el error aparecerá en la primera pregunta (401).
- `cloudflared` se descarga de la última versión publicada en GitHub. Para fijar una versión,
  define `CLOUDFLARED_VERSION` (p. ej. `2025.8.1`) antes de ejecutar el notebook.
