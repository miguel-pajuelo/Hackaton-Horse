"""
Conexión de la app con el servidor del LLM (llama.cpp en Kaggle, local u Ollama).

La app no sabe dónde corre el modelo: lee la configuración, comprueba qué servidor responde y
usa el primero disponible. Así la misma app funciona:
  - en remoto, con el modelo en Kaggle detrás de un túnel (LLM_BASE_URL = https://…/v1),
  - con Streamlit dentro de Kaggle (LLM_BASE_URL = http://127.0.0.1:8080/v1),
  - con el plan B local (LLM_FALLBACK_BASE_URL = http://127.0.0.1:11434/v1, Ollama).

Configuración (variables de entorno o st.secrets, mismo nombre):
    LLM_BASE_URL, LLM_MODEL, LLM_API_KEY                         servidor principal
    LLM_FALLBACK_BASE_URL, LLM_FALLBACK_MODEL, LLM_FALLBACK_API_KEY   plan B (opcional)
    LLM_TIMEOUT                                                  segundos por petición (120)

Uso:
    from chat.conexion import conectar
    estado = conectar()            # prueba principal y luego plan B
    if estado.ok:
        cliente = estado.cliente() # cliente OpenAI listo para preguntar(...)
    else:
        st.warning(estado.mensaje)
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import time
import urllib.error
import urllib.request

CLAVES = ("BASE_URL", "MODEL", "API_KEY")


@dataclass(frozen=True)
class ConfigLLM:
    nombre: str          # "principal" o "plan B"
    base_url: str        # acaba en /v1
    modelo: str
    api_key: str = "local"
    timeout: float = 120.0


@dataclass
class EstadoLLM:
    ok: bool
    mensaje: str
    config: ConfigLLM | None = None
    latencia_ms: float | None = None
    intentos: list[dict] = field(default_factory=list)

    def cliente(self):
        """Cliente del SDK de OpenAI para `chat.herramientas.preguntar`."""
        if not self.ok or self.config is None:
            raise RuntimeError(self.mensaje)
        from openai import OpenAI  # import tardío: la app funciona sin el SDK si no hay chat
        return OpenAI(base_url=self.config.base_url, api_key=self.config.api_key,
                      timeout=self.config.timeout, max_retries=0)


def _leer(nombre, secretos=None):
    valor = os.environ.get(nombre)
    if valor:
        return valor.strip()
    if secretos is not None:
        try:
            valor = secretos.get(nombre)
        except Exception:  # noqa: BLE001  (st.secrets lanza si no hay secrets.toml)
            valor = None
        if valor:
            return str(valor).strip()
    return None


def _normalizar_url(url):
    url = url.rstrip("/")
    return url if url.endswith("/v1") else url + "/v1"


def configuraciones(secretos=None) -> list[ConfigLLM]:
    """Servidores configurados, en orden de preferencia. `secretos` puede ser `st.secrets`."""
    timeout = float(_leer("LLM_TIMEOUT", secretos) or 120)
    salida = []
    for prefijo, nombre in (("LLM_", "principal"), ("LLM_FALLBACK_", "plan B")):
        url, modelo, clave = (_leer(prefijo + c, secretos) for c in CLAVES)
        if url and modelo:
            salida.append(ConfigLLM(nombre, _normalizar_url(url), modelo, clave or "local", timeout))
    return salida


def _get(url, api_key, timeout):
    peticion = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:  # noqa: S310 (URL de config)
        return json.loads(respuesta.read().decode("utf-8") or "{}")


def comprobar(config: ConfigLLM, timeout: float = 8.0) -> EstadoLLM:
    """¿Responde el servidor y sirve el modelo configurado? No genera texto (es rápido)."""
    inicio = time.perf_counter()
    try:
        datos = _get(config.base_url + "/models", config.api_key, timeout)
    except urllib.error.HTTPError as e:
        motivo = ("clave LLM_API_KEY incorrecta" if e.code in (401, 403)
                  else f"el servidor respondió con error {e.code}")
        return EstadoLLM(False, f"Servidor {config.nombre}: {motivo}.", config)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return EstadoLLM(False, f"Servidor {config.nombre} no disponible ({config.base_url}). "
                                "Si es Kaggle, puede que la sesión o el túnel hayan caducado.", config)
    latencia = (time.perf_counter() - inicio) * 1000
    modelos = [m.get("id") for m in datos.get("data", []) if isinstance(m, dict)]
    if modelos and config.modelo not in modelos:
        return EstadoLLM(False, f"Servidor {config.nombre}: no sirve el modelo «{config.modelo}» "
                                f"(disponibles: {', '.join(modelos)}).", config, latencia)
    return EstadoLLM(True, f"Conectado al servidor {config.nombre} ({config.modelo}).", config,
                     latencia)


def conectar(secretos=None, timeout: float = 8.0) -> EstadoLLM:
    """Prueba los servidores configurados en orden y devuelve el primero que responde."""
    configs = configuraciones(secretos)
    if not configs:
        return EstadoLLM(False, "El chat no está configurado: define LLM_BASE_URL y LLM_MODEL "
                                "(y LLM_API_KEY si el servidor la pide).")
    intentos = []
    for config in configs:
        estado = comprobar(config, timeout)
        intentos.append({"servidor": config.nombre, "url": config.base_url, "ok": estado.ok,
                         "mensaje": estado.mensaje, "latencia_ms": estado.latencia_ms})
        if estado.ok:
            estado.intentos = intentos
            return estado
    return EstadoLLM(False, " · ".join(i["mensaje"] for i in intentos), intentos=intentos)
