"""
Pruebas de chat/conexion.py y chat/kaggle_remoto.py con un servidor HTTP simulado (sin GPU,
sin Kaggle y sin red externa).

Uso:  python tests/test_chat_conexion.py
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from chat.conexion import comprobar, conectar, configuraciones, ConfigLLM  # noqa: E402
from chat.kaggle_remoto import buscar_url_tunel, esperar_http  # noqa: E402

VARIABLES = [f"LLM_{p}{c}" for p in ("", "FALLBACK_") for c in ("BASE_URL", "MODEL", "API_KEY")]


class _Servidor(BaseHTTPRequestHandler):
    clave = "secreta"
    modelos = ["mistral-test"]

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            return self._json(200, {"status": "ok"})
        if self.path == "/v1/models":
            if self.headers.get("Authorization") != f"Bearer {self.clave}":
                return self._json(401, {"error": "no autorizado"})
            return self._json(200, {"data": [{"id": m} for m in self.modelos]})
        self._json(404, {})

    def _json(self, codigo, cuerpo):
        datos = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, *args):
        pass


def _arrancar():
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _Servidor)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor, f"http://127.0.0.1:{servidor.server_address[1]}"


SERVIDOR, URL = _arrancar()
CERRADO = "http://127.0.0.1:9"  # puerto sin servidor


def _entorno(**valores):
    for v in VARIABLES:
        os.environ.pop(v, None)
    os.environ.update(valores)


def test_sin_configuracion():
    _entorno()
    estado = conectar()
    assert not estado.ok and "LLM_BASE_URL" in estado.mensaje


def test_conecta_y_normaliza_url():
    _entorno(LLM_BASE_URL=URL + "/", LLM_MODEL="mistral-test", LLM_API_KEY="secreta")
    assert configuraciones()[0].base_url == URL + "/v1"
    estado = conectar()
    assert estado.ok and estado.config.nombre == "principal" and estado.latencia_ms is not None


def test_clave_incorrecta():
    estado = comprobar(ConfigLLM("principal", URL + "/v1", "mistral-test", "otra"))
    assert not estado.ok and "clave" in estado.mensaje


def test_modelo_que_no_sirve():
    estado = comprobar(ConfigLLM("principal", URL + "/v1", "otro-modelo", "secreta"))
    assert not estado.ok and "mistral-test" in estado.mensaje


def test_kaggle_caido_pasa_a_plan_b():
    _entorno(LLM_BASE_URL=CERRADO + "/v1", LLM_MODEL="mistral-test", LLM_API_KEY="secreta",
             LLM_FALLBACK_BASE_URL=URL + "/v1", LLM_FALLBACK_MODEL="mistral-test",
             LLM_FALLBACK_API_KEY="secreta")
    estado = conectar(timeout=2)
    assert estado.ok and estado.config.nombre == "plan B"
    assert [i["ok"] for i in estado.intentos] == [False, True]


def test_todo_caido_da_mensaje_claro():
    _entorno(LLM_BASE_URL=CERRADO + "/v1", LLM_MODEL="m")
    estado = conectar(timeout=2)
    assert not estado.ok and "caducado" in estado.mensaje
    try:
        estado.cliente()
    except RuntimeError:
        pass
    else:
        raise AssertionError("no debería crear cliente sin servidor")


def test_lee_st_secrets():
    _entorno()
    secretos = {"LLM_BASE_URL": URL, "LLM_MODEL": "mistral-test", "LLM_API_KEY": "secreta"}
    assert conectar(secretos).ok


def test_url_del_tunel():
    salida = ("2026-11-14T10:00:00Z INF |  https://rojo-azul-verde-casa.trycloudflare.com  |\n")
    assert buscar_url_tunel(salida) == "https://rojo-azul-verde-casa.trycloudflare.com"
    assert buscar_url_tunel("INF Starting tunnel") is None


def test_esperar_http():
    assert esperar_http(URL + "/health", timeout=5)
    assert not esperar_http(CERRADO + "/health", timeout=2)


def test_notebook_demo_se_genera():
    from chat import crear_demo_remota
    crear_demo_remota.main()
    nb = json.loads(crear_demo_remota.DESTINO.read_text(encoding="utf-8"))
    codigo = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    for i, fuente in enumerate(codigo):
        compile(fuente, f"celda{i}", "exec")
    todo = "\n".join(codigo)
    assert "abrir_tunel(8501)" in todo and "abrir_tunel(8080)" in todo
    assert "llama-server" in todo or "servidor" in todo  # arranque del modelo heredado de 03


if __name__ == "__main__":
    pruebas = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    fallos = 0
    for prueba in pruebas:
        try:
            prueba()
            print(f"OK    {prueba.__name__}")
        except Exception as e:  # noqa: BLE001
            fallos += 1
            print(f"FALLO {prueba.__name__}: {e!r}")
    print(f"\n{len(pruebas) - fallos}/{len(pruebas)} pruebas superadas")
    sys.exit(1 if fallos else 0)
