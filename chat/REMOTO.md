# Demo remota · cómo se conecta la página con el modelo de Kaggle

El modelo (Mistral Small 3.2 en llama.cpp) escucha en `127.0.0.1:8080` **dentro** de la sesión de
Kaggle, que no es accesible desde fuera. Un *Quick Tunnel* de Cloudflare le da una URL pública
temporal (`https://…trycloudflare.com`). La URL cambia en cada sesión y muere con ella (máx. 12 h).

Las herramientas (pandas + motor oficial) se ejecutan siempre donde corre el cliente. Al modelo
solo le llegan la pregunta, el historial enviado y los resultados que necesita para redactar.

El chat está en el dashboard: vista **«Pregunta a la línea»** (enlace «preguntar» de la barra
superior, botón flotante de abajo a la derecha o menú «Opciones»). Usa el mismo motor, la misma
línea y los mismos días que el resto del dashboard; al cambiar el periodo empieza otra
conversación. Si el modelo no responde, la vista lo avisa y el resto del dashboard sigue
funcionando.

## Archivos

| Archivo | Para qué |
|---|---|
| `04_demo_remota.ipynb` | Notebook de Kaggle: comprueba el dataset, arranca el modelo (celdas de `03`) y abre el túnel |
| `chat/crear_demo_remota.py` | Regenera `04` a partir de `03` si cambia el arranque del modelo |
| `chat/preparar_dataset_kaggle.py` | Monta la carpeta del dataset de Kaggle (sin cachés ni secretos) |
| `chat/kaggle_remoto.py` | `cloudflared`, túnel comprobado desde fuera, Streamlit en Kaggle, vigilancia |
| `chat/conexion.py` | Lado de la app: configuración, comprobación del servidor y plan B |
| `tests/test_chat_conexion.py` | Pruebas de conexión, túnel, vigilancia y paquete con un servidor simulado |
| `tests/test_chat_dashboard.py` | Pruebas del chat dentro del dashboard con un modelo simulado |

## Preparar Kaggle (una vez, y cada vez que cambie el código o los datos)

1. Publica el dataset de la línea con todo lo necesario (`lossia/`, `chat/`, `Streamlit/`,
   `.streamlit/`, `Datos_limpios/`, `Resultados/`, `simulador/` y `analisis.py`):
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
cargar el modelo. En modo `app`, si faltan dependencias del dashboard (`streamlit`, `plotly`,
`matplotlib`, `openai`), se instalan desde `Streamlit/requirements.txt` al arrancar Streamlit.

## Qué comprueba la celda de vigilancia (y qué no)

| Modo | Comprueba | Lo que eso confirma | Lo que **no** confirma |
|---|---|---|---|
| ambos | `/v1/models` **con la clave** en `127.0.0.1:8080` | llama.cpp sigue vivo y acepta la clave | que genere texto o llame bien a las herramientas |
| `modelo` | `/v1/models` con la clave **a través del túnel** | el túnel funciona y el catálogo de modelos es accesible desde fuera | lo mismo que arriba |
| `app` | `/_stcore/health` y que `/` devuelva el HTML de Streamlit, a través del túnel | el servidor de Streamlit responde desde fuera | que la página se haya renderizado sin errores ni que el chat responda |

Por eso, tras abrir el túnel, haz **una pregunta de prueba real** (abajo) antes de enseñarlo.

## Modo «app»

Streamlit corre en Kaggle y el túnel publica la **página**; el modelo no se expone.

1. En la primera celda de código deja `MODO = "app"`.
2. *Run all*. La celda «Abrir el túnel» solo imprime `Abre la página en: https://…` cuando la
   página ya responde desde fuera; si no, falla con un mensaje y se puede reintentar.
3. Abre esa URL en cualquier navegador o móvil.
4. **Pregunta de prueba:** en «preguntar», pulsa la sugerencia «¿Qué disponibilidad propia tiene
   ST-2390?» con el periodo completo («Todo»). Debe responder **77,5 %** (por debajo del 90 %)
   con el sello «Cifras verificadas con los datos de la línea». Si sale «Chat no disponible»,
   pulsa «Comprobar conexión» y revisa la salida de la celda del modelo.
5. Deja corriendo la celda «Mantener la sesión activa».

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
4. **Pregunta de prueba** (con esas variables de entorno definidas y `openai` instalado:
   `pip install -r Streamlit/requirements.txt`):
   ```bash
   py -3.13 -c "from chat.conexion import conectar; from chat.herramientas import HerramientasLinea, responder; e = conectar(); print(e.mensaje); r = responder(e.cliente(), e.config.modelo, HerramientasLinea(), '¿Qué máquina frena más la línea?'); print(r['respuesta']); print('verificada:', r['verificada'], r['cifras_no_verificadas'])"
   ```
   Debe nombrar **PM_2020** (severidad 18 %, periodo completo) y terminar con `verificada: True []`.
   Después, abre el dashboard local (`streamlit run Streamlit/app.py`) y repite la pregunta de
   ST-2390 del modo «app».

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
  correctas. Por eso la interfaz muestra bajo cada respuesta «¿De dónde sale esto?» (herramientas
  llamadas y sus resultados) y marca en amarillo las cifras que no puede respaldar.
- **Rendimiento:** el benchmark guardado en el repo (Mistral en dos T4) se midió con el flujo
  anterior. El atajo actual adelanta las herramientas de las preguntas simples **y además envía el
  catálogo de herramientas**, así que el prompt es más largo: hay que volver a medir la latencia en
  Kaggle antes de dar cifras de tiempo de respuesta.
- Cada pregunta tiene un plazo total (180 s por defecto, `plazo_s` en `preguntar`), además del
  timeout de cada petición.
- Usar un notebook de Kaggle como servidor con túnel es aceptable para una demo puntual, no como
  servicio permanente. Revisa las condiciones de uso de Kaggle.
- `cloudflared` se descarga de la última versión publicada en GitHub. Para fijar una versión,
  define `CLOUDFLARED_VERSION` (p. ej. `2025.8.1`) antes de ejecutar el notebook.
