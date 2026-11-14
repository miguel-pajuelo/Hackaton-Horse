"""
Utilidades para la demo remota desde una sesión de Kaggle.

Dos modos (ver 04_demo_remota.ipynb y chat/REMOTO.md):
  A) Túnel al MODELO (puerto 8080): la app corre fuera (tu PC, Streamlit Cloud) y usa la URL del
     túnel como LLM_BASE_URL.
  B) Streamlit DENTRO de Kaggle + túnel a la APP (puerto 8501): abres la página desde cualquier
     navegador; la app habla con el modelo por 127.0.0.1, sin exponer el modelo.

El túnel es un Quick Tunnel de Cloudflare (sin cuenta). La URL cambia en cada sesión y deja de
funcionar cuando la sesión de Kaggle termina.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

URL_CLOUDFLARED = "https://github.com/cloudflare/cloudflared/releases/{version}/cloudflared-linux-amd64"
_URL_TUNEL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
CARPETAS_APP = ("lossia", "chat", "Streamlit", "Datos_limpios", "Resultados", ".streamlit")


def buscar_url_tunel(texto: str) -> str | None:
    """Extrae la URL pública de la salida de cloudflared."""
    m = _URL_TUNEL.search(texto)
    return m.group(0) if m else None


def esperar_http(url: str, timeout: float = 120, cabeceras: dict | None = None) -> bool:
    """Espera a que `url` responda 200 (servidor arrancado)."""
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        try:
            peticion = urllib.request.Request(url, headers=cabeceras or {})
            with urllib.request.urlopen(peticion, timeout=3) as r:  # noqa: S310
                if r.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(1.5)
    return False


def descargar_cloudflared(destino: Path = Path("/tmp/cloudflared"), version: str | None = None) -> Path:
    """Descarga el binario oficial de cloudflared (Linux x86-64). `version` p. ej. '2025.8.1'."""
    if destino.is_file():
        return destino
    version = version or os.environ.get("CLOUDFLARED_VERSION")
    url = URL_CLOUDFLARED.format(version=f"download/{version}" if version else "latest/download")
    parcial = destino.with_suffix(".part")
    subprocess.run(["curl", "-fsSL", "--connect-timeout", "30", "-o", str(parcial), url], check=True)
    parcial.chmod(0o755)
    parcial.replace(destino)
    subprocess.run([str(destino), "--version"], check=True)
    return destino


def abrir_tunel(puerto: int, binario: Path | None = None, timeout: float = 90,
                log: Path = Path("/tmp/cloudflared.log")):
    """
    Abre un Quick Tunnel a http://127.0.0.1:<puerto>. Devuelve (proceso, url_publica).
    La salida de cloudflared se sigue volcando a `log` mientras el túnel esté abierto.
    """
    binario = binario or descargar_cloudflared()
    proceso = subprocess.Popen(
        [str(binario), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{puerto}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    encontrada = {}
    lista = threading.Event()

    def leer():
        with log.open("a") as salida:
            for linea in proceso.stdout:
                salida.write(linea)
                salida.flush()
                if not lista.is_set() and (url := buscar_url_tunel(linea)):
                    encontrada["url"] = url
                    lista.set()

    threading.Thread(target=leer, daemon=True).start()
    if not lista.wait(timeout):
        proceso.terminate()
        raise RuntimeError(f"cloudflared no dio una URL en {timeout:.0f} s. Revisa {log}.")
    url = encontrada["url"]
    # el registro DNS del túnel tarda unos segundos en propagarse
    esperar_http(url, timeout=45)
    return proceso, url


def preparar_app(repo_dir: Path, destino: Path = Path("/kaggle/working/lossia_app")) -> Path:
    """Copia el repo a una carpeta escribible (/kaggle/input es de solo lectura)."""
    destino.mkdir(parents=True, exist_ok=True)
    for carpeta in CARPETAS_APP:
        origen = repo_dir / carpeta
        if origen.exists():
            shutil.copytree(origen, destino / carpeta, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return destino


def lanzar_streamlit(app_dir: Path, puerto: int = 8501, entorno_llm: dict | None = None,
                     timeout: float = 180, log: Path = Path("/tmp/streamlit.log")):
    """
    Arranca `streamlit run Streamlit/app.py` en segundo plano con la configuración del LLM.
    Devuelve el proceso cuando la app responde en /_stcore/health.
    """
    try:
        import streamlit  # noqa: F401
    except ImportError:
        requisitos = app_dir / "Streamlit" / "requirements.txt"
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(requisitos),
                        "openai"], check=True)
    entorno = os.environ.copy()
    entorno.update({k: str(v) for k, v in (entorno_llm or {}).items()})
    salida = log.open("w")
    proceso = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "Streamlit/app.py",
         "--server.port", str(puerto), "--server.address", "127.0.0.1",
         "--server.headless", "true", "--browser.gatherUsageStats", "false"],
        cwd=app_dir, env=entorno, stdout=salida, stderr=subprocess.STDOUT)
    if not esperar_http(f"http://127.0.0.1:{puerto}/_stcore/health", timeout):
        proceso.terminate()
        raise RuntimeError(f"Streamlit no arrancó en {timeout:.0f} s:\n" + log.read_text()[-4000:])
    return proceso
