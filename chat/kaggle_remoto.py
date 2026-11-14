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
ARCHIVOS_APP = ("analisis.py",)   # el botón «Regenerar Resultados/» del dashboard lo importa
# Archivos que el dataset de Kaggle debe contener (rutas relativas a la raíz del repo).
NECESARIOS = {
    "base": ["lossia/interfaz.py", "chat/herramientas.py", "chat/kaggle_remoto.py",
             "chat/conexion.py", "Datos_limpios/datos_limpios.csv",
             "Datos_limpios/config_limpia.csv", "Datos_limpios/alertas.json",
             "Datos_limpios/registro_limpieza.json", "Resultados/kpis_global.csv"],
    "app": ["Streamlit/app.py", "Streamlit/graficos.py", "Streamlit/centros.py",
            "Streamlit/lossia.css", "Streamlit/requirements.txt", "Streamlit/assets/horse.png",
            "Streamlit/assets/visualizaciones/reparto.svg", ".streamlit/config.toml",
            "analisis.py"],
}
EXCLUIR = ("__pycache__", "*.pyc", ".ipynb_checkpoints", "secrets.toml", "*.log")
MODULOS_APP = ("streamlit", "plotly", "matplotlib", "openai")  # de Streamlit/requirements.txt


def faltan(repo_dir: Path, modo: str = "app") -> list[str]:
    """Archivos necesarios que no están en `repo_dir` para el modo dado ("app" o "modelo")."""
    lista = NECESARIOS["base"] + (NECESARIOS["app"] if modo == "app" else [])
    return [r for r in lista if not (Path(repo_dir) / r).is_file()]


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


def estado_demo(modo: str, url_publica: str, url_modelo_local: str, clave: str) -> dict:
    """
    Comprobación de extremo a extremo para la celda de vigilancia:
      - modelo: /v1/models CON la clave, en local y a través del túnel (mismo camino que la app).
      - app: además, que la página publicada devuelva el HTML de Streamlit.
    """
    auth = {"Authorization": f"Bearer {clave}"}
    estado = {"modelo_local": esperar_http(url_modelo_local + "/models", 10, auth)}
    if modo == "modelo":
        estado["tunel_modelo"] = esperar_http(url_publica + "/v1/models", 10, auth)
    else:
        estado["tunel_app"] = esperar_http(url_publica + "/_stcore/health", 10)
        try:
            with urllib.request.urlopen(url_publica + "/", timeout=10) as r:  # noqa: S310
                estado["pagina"] = r.status == 200 and b"streamlit" in r.read(200_000).lower()
        except OSError:
            estado["pagina"] = False
    estado["ok"] = all(estado.values())
    return estado


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
                log: Path = Path("/tmp/cloudflared.log"), ruta_salud: str = "/",
                espera_publica: float = 60):
    """
    Abre un Quick Tunnel a http://127.0.0.1:<puerto>. Devuelve (proceso, url_publica) solo cuando
    `url_publica + ruta_salud` responde 200 desde fuera; si no, cierra el túnel y lanza error.
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
    if not esperar_http(url + ruta_salud, timeout=espera_publica):
        proceso.terminate()
        raise RuntimeError(f"El túnel dio la URL {url} pero {ruta_salud} no responde desde fuera "
                           f"tras {espera_publica:.0f} s. Vuelve a ejecutar la celda; revisa {log}.")
    return proceso, url


def preparar_app(repo_dir: Path, destino: Path = Path("/kaggle/working/lossia_app")) -> Path:
    """Copia el repo a una carpeta escribible (/kaggle/input es de solo lectura)."""
    destino.mkdir(parents=True, exist_ok=True)
    for carpeta in CARPETAS_APP:
        origen = repo_dir / carpeta
        if origen.exists():
            shutil.copytree(origen, destino / carpeta, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(*EXCLUIR))
    for archivo in ARCHIVOS_APP:
        if (repo_dir / archivo).is_file():
            shutil.copy2(repo_dir / archivo, destino / archivo)
    return destino


def modulos_que_faltan() -> list[str]:
    """Dependencias del dashboard que no están instaladas en este entorno."""
    import importlib.util
    return [m for m in MODULOS_APP if importlib.util.find_spec(m) is None]


def lanzar_streamlit(app_dir: Path, puerto: int = 8501, entorno_llm: dict | None = None,
                     timeout: float = 180, log: Path = Path("/tmp/streamlit.log")):
    """
    Arranca `streamlit run Streamlit/app.py` en segundo plano con la configuración del LLM.
    Devuelve el proceso cuando la app responde en /_stcore/health.
    """
    if modulos_que_faltan():
        requisitos = app_dir / "Streamlit" / "requirements.txt"
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(requisitos)],
                       check=True)
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
