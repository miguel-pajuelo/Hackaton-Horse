"""
Genera 04_demo_remota.ipynb a partir de 03_llm_kaggle.ipynb.

Toma de 03 las celdas que preparan la sesión y arrancan el modelo (hasta "Servir el modelo",
incluida) y añade las celdas de la demo remota. Así el arranque del modelo vive en un solo sitio:
si cambia 03, se vuelve a ejecutar este script.

    py -3.13 chat/crear_demo_remota.py
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
ORIGEN = REPO / "03_llm_kaggle.ipynb"
DESTINO = REPO / "04_demo_remota.ipynb"
ULTIMA_CELDA = "## Servir el modelo"


def celda(tipo, texto):
    c = {"cell_type": tipo, "metadata": {}, "source": texto.strip("\n").splitlines(keepends=True)}
    if tipo == "code":
        c.update(outputs=[], execution_count=None)
    return c


INTRO = celda("markdown", """
# Demo remota · Pregunta a la línea

Arranca Mistral Small 3.2 en las dos T4 (mismas celdas que `03_llm_kaggle.ipynb`) y lo deja
accesible desde fuera de Kaggle con un túnel temporal de Cloudflare. Guía: `chat/REMOTO.md`.

**Antes de empezar**
- Acelerador **GPU T4 ×2** e **Internet activado**.
- Entradas: dataset de la línea (con `lossia/`, `chat/`, `Streamlit/`, `Datos_limpios/`,
  `Resultados/`) y dataset de pesos Q8_0.
- *Add-ons → Secrets*: crea `LLM_API_KEY` con una clave larga y aleatoria y actívalo para este
  notebook. Sin clave, cualquiera con la URL del túnel podría usar el modelo.

**Modo** (variable `MODO` en la celda siguiente)
- `"app"` (recomendado): Streamlit corre aquí y el túnel publica la **página**. El modelo no se
  expone. Abre la URL desde cualquier navegador.
- `"modelo"`: el túnel publica el **modelo**. La página corre fuera (tu PC, Streamlit Cloud) con
  `LLM_BASE_URL` = URL del túnel + `/v1`.
""")

SECRETO = celda("code", """
import os

MODO = "app"   # "app" o "modelo"

try:
    from kaggle_secrets import UserSecretsClient
    os.environ["LLM_API_KEY"] = UserSecretsClient().get_secret("LLM_API_KEY")
except Exception as error:
    raise RuntimeError("Añade el secreto LLM_API_KEY en Add-ons → Secrets y actívalo "
                       "para este notebook.") from error
print("Clave cargada desde Kaggle Secrets (no se muestra).")
""")

def celda_comprobacion():
    """Celda autónoma (no importa nada del repo) que dice qué falta en el dataset."""
    from chat.kaggle_remoto import NECESARIOS  # se incrusta el valor, el notebook no lo importa
    return celda("code", f"""
# Comprobar que el dataset de la línea trae todo lo necesario ANTES de cargar el modelo.
NECESARIOS = {NECESARIOS!r}
requeridos = NECESARIOS["base"] + (NECESARIOS["app"] if MODO == "app" else [])
pendientes = [r for r in requeridos if not (repo_dir / r).is_file()]
if pendientes:
    raise RuntimeError(
        "Al dataset de la línea le faltan estos archivos del repo: " + ", ".join(pendientes)
        + ". Vuelve a publicarlo con: py -3.13 chat/preparar_dataset_kaggle.py --id <usuario/dataset>")
print(f"Dataset completo para el modo {{MODO!r}} ({{len(requeridos)}} archivos comprobados).")
""")


REMOTO_MD = celda("markdown", """
## Abrir el túnel

Tarda unos segundos. La URL cambia en cada sesión y deja de funcionar cuando la sesión termina
(máximo 12 h).
""")

REMOTO = celda("code", """
from chat.kaggle_remoto import abrir_tunel, lanzar_streamlit, preparar_app

entorno_llm = {"LLM_BASE_URL": LLM_BASE_URL, "LLM_MODEL": LLM_MODEL, "LLM_API_KEY": clave}

if MODO == "app":
    app_dir = preparar_app(repo_dir)
    proceso_app = lanzar_streamlit(app_dir, puerto=8501, entorno_llm=entorno_llm)
    proceso_tunel, url_publica = abrir_tunel(8501, ruta_salud="/_stcore/health")
    print("Abre la página en:", url_publica)
    print("Aviso: la página no tiene login. Cualquiera con esta URL puede ver el dashboard y "
          "descargar sus datos (botón «Descargar CSV») mientras dure la sesión. "
          "No compartas la URL fuera del jurado.")
elif MODO == "modelo":
    proceso_tunel, url_publica = abrir_tunel(8080, ruta_salud="/health")
    print("Configura la app externa (variables de entorno o st.secrets):")
    print(f'  LLM_BASE_URL = "{url_publica}/v1"')
    print(f'  LLM_MODEL    = "{LLM_MODEL}"')
    print('  LLM_API_KEY  = el mismo valor que el secreto LLM_API_KEY de Kaggle')
else:
    raise ValueError('MODO debe ser "app" o "modelo"')
""")

VIVO_MD = celda("markdown", """
## Mantener la sesión activa

Deja esta celda ejecutándose durante la demo. Cada 5 minutos comprueba de extremo a extremo, con
la clave, que el modelo responde en local y a través del túnel; en modo `app`, además, que la
página publicada devuelve el dashboard. Para pararla, interrumpe la celda; los servidores siguen
hasta cerrar la sesión.
""")

VIVO = celda("code", """
import time
from chat.kaggle_remoto import estado_demo

inicio = time.monotonic()
while time.monotonic() - inicio < 11.5 * 3600:
    estado = estado_demo(MODO, url_publica, LLM_BASE_URL, clave)
    estado["proceso_tunel"] = proceso_tunel.poll() is None
    if MODO == "app":
        estado["proceso_app"] = proceso_app.poll() is None
    caidos = [k for k, v in estado.items() if k != "ok" and not v]
    print(time.strftime("%H:%M"), "· OK" if not caidos else "· CAÍDO: " + ", ".join(caidos),
          flush=True)
    time.sleep(300)
""")


def main():
    origen = json.loads(ORIGEN.read_text(encoding="utf-8"))
    celdas = origen["cells"]
    fin = next(i for i, c in enumerate(celdas)
               if c["cell_type"] == "markdown" and "".join(c["source"]).startswith(ULTIMA_CELDA))
    base = celdas[1:fin + 2]  # sin el título de 03; incluye la celda de código que sirve el modelo
    for c in base:
        if c["cell_type"] == "code":
            c["outputs"], c["execution_count"] = [], None
    # la comprobación va justo después de la celda que define repo_dir, antes de cargar el modelo
    primera_codigo = next(i for i, c in enumerate(base) if c["cell_type"] == "code")
    assert "repo_dir" in "".join(base[primera_codigo]["source"]), "03 ya no define repo_dir ahí"
    base.insert(primera_codigo + 1, celda_comprobacion())
    nb = dict(origen)
    nb["cells"] = [INTRO, SECRETO, *base, REMOTO_MD, REMOTO, VIVO_MD, VIVO]
    DESTINO.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{DESTINO.name}: {len(nb['cells'])} celdas ({len(base)} tomadas de {ORIGEN.name})")


if __name__ == "__main__":
    main()
