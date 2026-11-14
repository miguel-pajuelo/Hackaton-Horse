# Demo remota · cómo se conecta la página con el modelo de Kaggle

El modelo (Mistral Small 3.2 en llama.cpp) escucha en `127.0.0.1:8080` **dentro** de la sesión de
Kaggle, que no es accesible desde fuera. Un *Quick Tunnel* de Cloudflare le da una URL pública
temporal (`https://…trycloudflare.com`). La URL cambia en cada sesión y muere con ella (máx. 12 h).

Las herramientas (pandas + motor oficial) se ejecutan siempre donde corre el cliente. Al modelo
solo le llegan la pregunta, el historial enviado y los resultados que necesita para redactar.

> **Estado actual:** el dashboard (`Streamlit/app.py`) **todavía no tiene la pestaña de chat**.
> El modo `app` publica hoy el dashboard; el chat se puede usar desde el notebook (celda
> «Hacer una consulta» de `03`) o desde cualquier cliente compatible con OpenAI en modo `modelo`.
> Cuando se integre la pestaña, usará `chat.conexion.conectar(st.secrets)` y
> `chat.herramientas.responder(...)` sin cambiar nada de esta guía.

## Archivos

| Archivo | Para qué |
|---|---|
| `04_demo_remota.ipynb` | Notebook de Kaggle: comprueba el dataset, arranca el modelo (celdas de `03`) y abre el túnel |
| `chat/crear_demo_remota.py` | Regenera `04` a partir de `03` si cambia el arranque del modelo |
| `chat/preparar_dataset_kaggle.py` | Monta la carpeta del dataset de Kaggle (sin cachés ni secretos) |
| `chat/kaggle_remoto.py` | `cloudflared`, túnel comprobado desde fuera, Streamlit en Kaggle, vigilancia |
| `chat/conexion.py` | Lado de la app: configuración, comprobación del servidor y plan B |
| `tests/test_chat_conexion.py` | Pruebas con un servidor simulado |

## Preparar Kaggle (una vez, y cada vez que cambie el código o los datos)

1. Publica el dataset de la línea con todo lo necesario (`lossia/`, `chat/`, `Streamlit/`,
   `.streamlit/`, `Datos_limpios/`, `Resultados/`):
   ```bash
   py -3.13 chat/preparar_dataset_kaggle.py --id <usuario>/<dataset-de-la-linea>
   ```
   El script comprueba que no falta ningún archivo y que no se cuela `secrets.toml`, e imprime el
   comando `kaggle datasets version … -r zip` para subir la nueva versión.
2. Importa `04_demo_remota.ipynb` como notebook privado y adjunta el dataset de la línea y el de
   pesos Q8_0.
3. *Add-ons → Secrets*: crea `LLM_API_KEY` con una clave larga y aleatoria (por ejemplo,
   `python -c "import secrets; print(secrets.token_urlsafe(32))"`) y actívalo para el notebook.
4. *Settings*: **GPU T4 ×2** e **Internet on**.

Si al dataset le falta algo, la segunda celda de código lo dice (lista de archivos) antes de
cargar el modelo.

## Modo «app»

Streamlit corre en Kaggle y el túnel publica la **página**; el modelo no se expone.

1. En la primera celda de código deja `MODO = "app"`.
2. *Run all*. La celda «Abrir el túnel» solo imprime `Abre la página en: https://…` cuando la
   página ya responde desde fuera; si no, falla con un mensaje y se puede reintentar.
3. Abre esa URL en cualquier navegador o móvil.
4. Deja corriendo la celda «Mantener la sesión activa».

**Privacidad:** Streamlit no tiene login. Cualquiera con la URL puede ver el dashboard **y
descargar sus datos** (botón «Descargar CSV» con los KPI de la selección) mientras dure la
sesión. `LLM_API_KEY` protege el modelo, no la página. Comparte la URL solo con el jurado.

## Modo «modelo» (página fuera de Kaggle)

El túnel publica el **modelo** y la página corre en tu PC o en Streamlit Cloud.

1. `MODO = "modelo"` y *Run all*. La celda imprime la configuración.
2. Donde corra el cliente, define (variables de entorno o *Secrets* de Streamlit Cloud):
   ```toml
   LLM_BASE_URL = "https://….trycloudflare.com/v1"
   LLM_MODEL    = "mistral-small-3.2-24b-instruct-2506-q8_0"
   LLM_API_KEY  = "el mismo valor que el secreto de Kaggle"
   LLM_TIMEOUT  = "120"   # opcional: segundos por petición (1-600)
   ```
3. `conectar(st.secrets)` comprueba `/v1/models` **con la clave**: detecta servidor caído, clave
   incorrecta (401), modelo distinto o respuesta inesperada, y entonces prueba el plan B.

Por el túnel viajan las peticiones a la API (con la cabecera de autorización), las preguntas, el
historial enviado y los resultados de las herramientas. Cada sesión nueva da otra URL: hay que
actualizar `LLM_BASE_URL`.

## Plan B local (si Kaggle o el túnel fallan en directo)

`conectar()` prueba primero el servidor principal y, si no responde, el plan B:

```toml
LLM_FALLBACK_BASE_URL = "http://127.0.0.1:11434/v1"   # Ollama
LLM_FALLBACK_MODEL    = "<nombre del modelo en `ollama list`>"
```

Usa un modelo occidental con soporte de herramientas que quepa en el portátil (por ejemplo,
Ministral 3 14B o, en equipos modestos, uno más pequeño de Mistral). Comprueba su nombre exacto
con `ollama list` y prueba antes las preguntas de la demo.

## Garantías y límites del chat

- Cada respuesta pasa por `verificar_cifras`: cada cifra debe estar en los resultados de las
  herramientas **y pertenecer a la etapa nombrada en esa frase**, con tolerancia de redondeo de
  media unidad del último decimal. Los códigos de máquina, alerta o día citados deben existir en
  los resultados. De la pregunta solo se aceptan cantidades pequeñas («las 3 máquinas»).
  Una respuesta sin consultar herramientas no puede dar cifras verificadas.
- El verificador comprueba cifras, no el razonamiento: una frase puede ser engañosa con cifras
  correctas. Por eso la interfaz debe mostrar siempre de dónde sale cada dato.
- Cada pregunta tiene un plazo total (180 s por defecto, `plazo_s` en `preguntar`), además del
  timeout de cada petición.
- Usar un notebook de Kaggle como servidor con túnel es aceptable para una demo puntual, no como
  servicio permanente. Revisa las condiciones de uso de Kaggle.
- `cloudflared` se descarga de la última versión publicada en GitHub. Para fijar una versión,
  define `CLOUDFLARED_VERSION` (p. ej. `2025.8.1`) antes de ejecutar el notebook.
