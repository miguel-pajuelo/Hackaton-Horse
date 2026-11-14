"""Servidor OpenAI-compatible mínimo para probar el dashboard sin Kaggle.
/v1/models y /v1/chat/completions (con clave). Pide kpis_etapa de la máquina citada y redacta
con el resultado de la herramienta; si la pregunta contiene «inventa», cambia de indicador."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import sys

CLAVE, MODELO = "clave-local", "mistral-simulado"


def coma(x):
    return f"{x:.1f}".replace(".", ",")


def redactar(mensajes):
    pregunta = next(m["content"] for m in reversed(mensajes) if m["role"] == "user")
    ultimo = mensajes[-1]
    if ultimo["role"] != "tool":
        nombre = re.search(r"\b(?:ST|PM)[-_ ]?\d{4}\b", pregunta)
        return {"role": "assistant", "content": None, "tool_calls": [{
            "id": "abc123def", "type": "function", "function": {
                "name": "kpis_etapa",
                "arguments": json.dumps({"nombre": nombre.group(0) if nombre else "ST-2390"})}}]}
    d = json.loads(ultimo["content"])
    if d.get("en_analisis") is False:
        texto = f"{d['operacion']} está fuera del análisis ({d['motivo_exclusion']}): no tiene indicadores fiables."
    elif "error" in d:
        texto = d["error"]
    elif "inventa" in pregunta:
        texto = f"{d['etapa']} tiene una disponibilidad del {coma(d['tiempo_ciclo_cmin'])} %."
    else:
        texto = (f"La disponibilidad propia de {d['etapa']} es del {coma(d['disponibilidad_pct'])} %, "
                 f"{'por encima' if d['disponibilidad_pct'] >= 90 else 'por debajo'} del objetivo del 90 %.")
    return {"role": "assistant", "content": texto}


class H(BaseHTTPRequestHandler):
    def _enviar(self, codigo, cuerpo):
        b = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _autorizado(self):
        if self.headers.get("Authorization") != f"Bearer {CLAVE}":
            self._enviar(401, {"error": "clave"})
            return False
        return True

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/") == "/health":
            return self._enviar(200, {"status": "ok"})
        if self._autorizado():
            self._enviar(200, {"object": "list", "data": [{"id": MODELO, "object": "model"}]})

    def do_POST(self):  # noqa: N802
        if not self._autorizado():
            return
        datos = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msg = redactar(datos["messages"])
        self._enviar(200, {"id": "x", "object": "chat.completion", "created": 0, "model": MODELO,
                           "choices": [{"index": 0, "message": msg,
                                        "finish_reason": "tool_calls" if msg.get("tool_calls") else "stop"}],
                           "usage": {"prompt_tokens": 1, "completion_tokens": 12, "total_tokens": 13}})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    print(f"modelo simulado en http://127.0.0.1:{puerto}/v1", flush=True)
    ThreadingHTTPServer(("127.0.0.1", puerto), H).serve_forever()
