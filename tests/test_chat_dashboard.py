"""
Pruebas del flujo «Pregunta a la línea» en el dashboard (Streamlit AppTest) con un modelo
simulado: sin GPU, sin Kaggle y sin el SDK de OpenAI.

- El servidor del modelo se simula con un HTTP local que responde /v1/models (con clave), para
  que `chat.conexion.conectar(st.secrets)` haga su comprobación real.
- La generación de texto se simula sustituyendo `EstadoLLM.cliente()` por un cliente falso que
  redacta a partir de los resultados de las herramientas (o inventa una cifra a propósito).

Uso:  python tests/test_chat_dashboard.py
"""
from __future__ import annotations

from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from streamlit.testing.v1 import AppTest  # noqa: E402

from chat import conexion  # noqa: E402
from lossia import interfaz as LI  # noqa: E402

APP = str(REPO / "Streamlit" / "app.py")
CLAVE = "clave-de-prueba"
MODELO = "mistral-simulado"
CERRADO = "http://127.0.0.1:9/v1"


class _Modelos(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        ok = self.headers.get("Authorization") == f"Bearer {CLAVE}"
        cuerpo = json.dumps({"data": [{"id": MODELO}]} if ok else {"error": "401"}).encode()
        self.send_response(200 if ok else 401)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *args):
        pass


SERVIDOR = ThreadingHTTPServer(("127.0.0.1", 0), _Modelos)
threading.Thread(target=SERVIDOR.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{SERVIDOR.server_address[1]}/v1"


def _coma(x):
    return f"{x:.1f}".replace(".", ",")


class _ClienteFalso:
    """Redacta con los resultados de las herramientas. Si la pregunta pide «inventa», pide los
    KPI de ST_2390 y responde con su tiempo de ciclo como si fuera la disponibilidad."""

    def __init__(self, fallo=None):
        self.fallo = fallo
        self.peticiones = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._crear))

    def _crear(self, **kw):
        self.peticiones.append(kw)
        if self.fallo:
            raise self.fallo
        mensajes = kw["messages"]
        pregunta = next(m["content"] for m in reversed(mensajes) if m["role"] == "user")
        ultimo = mensajes[-1]
        if ultimo["role"] != "tool":
            nombre = re.search(r"\b(?:ST|PM)[-_ ]?\d{4}\b", pregunta)
            llamada = SimpleNamespace(id="abc123def", function=SimpleNamespace(
                name="kpis_etapa", arguments=json.dumps({"nombre": nombre.group(0) if nombre else "ST-2390"})))
            return _respuesta(SimpleNamespace(content=None, tool_calls=[llamada]))
        dato = json.loads(ultimo["content"])
        if dato.get("en_analisis") is False:
            texto = (f"{dato['operacion']} está fuera del análisis ({dato['motivo_exclusion']}): "
                     "no tiene indicadores fiables.")
        elif "inventa" in pregunta:
            texto = f"{dato['etapa']} tiene una disponibilidad del {_coma(dato['tiempo_ciclo_cmin'])} %."
        else:
            texto = (f"La disponibilidad propia de {dato['etapa']} es del "
                     f"{_coma(dato['disponibilidad_pct'])} %, por debajo del objetivo del 90 %.")
        return _respuesta(SimpleNamespace(content=texto, tool_calls=None))


def _respuesta(mensaje):
    return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)],
                           usage=SimpleNamespace(completion_tokens=12))


def _app(base_url=URL, cliente=None, vista="pregunta"):
    original = conexion.EstadoLLM.cliente
    if cliente is not None:
        conexion.EstadoLLM.cliente = lambda self: cliente
    at = AppTest.from_file(APP, default_timeout=120)
    if base_url:
        at.secrets["LLM_BASE_URL"] = base_url
        at.secrets["LLM_MODEL"] = MODELO
        at.secrets["LLM_API_KEY"] = CLAVE
    at.session_state["vista"] = vista
    at.run()
    return at, original


def _textos(elementos):
    return " ".join(str(e.value) for e in elementos)


def _dp_oficial(etapa, dias=None):
    m = LI.cargar_motor()
    k = LI.calcular(m, dias).kpis.set_index("Etapa")
    return round(100 * float(k.loc[etapa, "Dp"]), 1)


def test_pregunta_st2390_verificada_y_cambio_de_periodo():
    cliente = _ClienteFalso()
    at, original = _app(cliente=cliente)
    try:
        assert not at.exception, at.exception
        assert "Conectado" in at.button(key="chat_reconectar").help
        at.chat_input(key="chat_entrada").set_value("¿Qué disponibilidad propia tiene ST-2390?").run()
        assert not at.exception, at.exception
        global_dp = _dp_oficial("ST_2390")
        assert _coma(global_dp) in _textos(at.markdown), _textos(at.markdown)
        assert "Cifras verificadas" in _textos(at.success)
        # la pregunta simple se adelantó y el modelo recibió el catálogo de herramientas
        assert cliente.peticiones[0]["tools"] and cliente.peticiones[0]["messages"][-1]["role"] == "tool"

        # cambio de periodo: semana 41 -> conversación nueva con las cifras de esos días
        at.date_input(key="rango_fechas").set_value((date(2026, 10, 5), date(2026, 10, 9))).run()
        assert not at.exception, at.exception
        assert "Has cambiado la línea o el periodo" in _textos(at.info)
        assert len(at.chat_message) == 0
        at.chat_input(key="chat_entrada").set_value("¿Qué disponibilidad propia tiene ST-2390?").run()
        dias_s41 = [d for d in LI.cargar_motor().dias if d.startswith("2026-S41")]
        dp_s41 = _dp_oficial("ST_2390", dias_s41)
        assert dp_s41 != global_dp
        assert _coma(dp_s41) in _textos(at.markdown)
        assert "Cifras verificadas" in _textos(at.success)
        # la pregunta de seguimiento lleva solo el historial de ESTE periodo
        at.chat_input(key="chat_entrada").set_value("¿Y su tiempo de ciclo?").run()
        historial = [m for m in cliente.peticiones[-2]["messages"] if m["role"] in ("user", "assistant")
                     and isinstance(m.get("content"), str)]
        assert any(_coma(dp_s41) in m["content"] for m in historial)
        assert not any(_coma(global_dp) in m["content"] for m in historial)
    finally:
        conexion.EstadoLLM.cliente = original


def test_maquina_excluida_se_explica():
    at, original = _app(cliente=_ClienteFalso())
    try:
        at.chat_input(key="chat_entrada").set_value("¿Cómo va la ST_0030?").run()
        assert not at.exception, at.exception
        texto = _textos(at.markdown)
        assert "ST_0030" in texto and "máquina sin datos" in texto, texto
        assert "Revisar" not in _textos(at.warning)
    finally:
        conexion.EstadoLLM.cliente = original


def test_respuesta_no_verificada_se_marca():
    at, original = _app(cliente=_ClienteFalso())
    try:
        at.chat_input(key="chat_entrada").set_value("Por favor, inventa la disponibilidad").run()
        assert not at.exception, at.exception
        aviso = _textos(at.warning)
        assert "Revisar" in aviso and "59,0" in aviso
        assert "Cifras verificadas" not in _textos(at.success)
    finally:
        conexion.EstadoLLM.cliente = original


def test_sin_configuracion_el_dashboard_sigue_funcionando():
    at, original = _app(base_url=None)
    try:
        assert not at.exception, at.exception
        assert "Chat no disponible" in _textos(at.warning)
        assert at.chat_input(key="chat_entrada").disabled
        at.session_state["vista"] = "inicio"
        at.run()
        assert not at.exception, at.exception
    finally:
        conexion.EstadoLLM.cliente = original


def test_servidor_caido():
    at, original = _app(base_url=CERRADO)
    try:
        assert not at.exception, at.exception
        assert "caducado" in _textos(at.warning)
        assert at.chat_input(key="chat_entrada").disabled
    finally:
        conexion.EstadoLLM.cliente = original


def test_fallo_al_generar_muestra_error_y_no_rompe():
    at, original = _app(cliente=_ClienteFalso(fallo=ConnectionError("túnel cerrado")))
    try:
        at.chat_input(key="chat_entrada").set_value("¿Qué disponibilidad propia tiene ST-2390?").run()
        assert not at.exception, at.exception
        assert "No se ha podido obtener respuesta" in _textos(at.error)
    finally:
        conexion.EstadoLLM.cliente = original


def test_falta_el_sdk_lo_dice_claramente():
    error = ModuleNotFoundError("No module named 'openai'", name="openai")
    at, original = _app(cliente=_ClienteFalso(fallo=error))
    try:
        at.chat_input(key="chat_entrada").set_value("¿Qué disponibilidad propia tiene ST-2390?").run()
        assert not at.exception, at.exception
        texto = _textos(at.error)
        assert "openai" in texto and "requirements.txt" in texto and "túnel" not in texto, texto
    finally:
        conexion.EstadoLLM.cliente = original


def test_detalle_muestra_categoria_y_motivo():
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["vista"] = "detalle"
    at.session_state["operacion_detalle"] = "ST_2390"
    at.run()
    assert not at.exception, at.exception
    texto = _textos(at.info)
    assert "Categoría:** Baja disponibilidad" in texto and "Motivo de prioridad" in texto


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
