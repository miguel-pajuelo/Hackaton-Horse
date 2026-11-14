"""
Pruebas de las herramientas del chat (chat/herramientas.py).

Comprueban que el chat da las MISMAS cifras que el motor oficial (Resultados/*.csv), que entiende
los nombres de máquina en cualquier formato, que responde con claridad ante máquinas excluidas o
inexistentes, que respeta el periodo seleccionado y que el bucle de herramientas funciona con un
modelo simulado. No necesitan GPU ni servidor de LLM.

Uso:  python -m pytest tests/test_chat_herramientas.py     (o  python tests/test_chat_herramientas.py)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from chat.herramientas import (HerramientasLinea, TOOLS, _consulta_directa,  # noqa: E402
                               firma_llamadas, preguntar, responder, verificar_cifras)
from lossia import config as C, interfaz as LI  # noqa: E402

H = HerramientasLinea()
RES = C.DIR_RESULTADOS


def _csv(nombre):
    return pd.read_csv(RES / f"{nombre}.csv").query("Periodo == 'GLOBAL'")


# ---------- mismas cifras que el motor oficial ----------
def test_kpis_coinciden_con_resultados():
    k = _csv("kpis_global").set_index("Etapa")
    for etapa in ["ST_2390", "ST_0260", "ST_0015", "ST_2375+ST_2376", "PM_2020"]:
        r = H.kpis_etapa(etapa)
        f = k.loc[etapa]
        assert r["etapa"] == etapa
        assert r["disponibilidad_pct"] == round(100 * f.Dp, 1)
        assert r["horas"]["parada_propia_TAP"] == round(f.TAP, 1)
        assert r["horas"]["parada_inducida_TAI"] == round(f.TAI, 1)
        assert r["tiempo_ciclo_cmin"] == round(f.Tcy_cmin, 1)
        assert r["fpm_paros_por_1000_piezas"] == round(f.Fpm, 1)
        assert r["cumple_disponibilidad"] == bool(f.cumple_Dp)


def test_prioridades_siguen_el_orden_oficial():
    p = _csv("prioridades_global")
    p = p[p.categoria.fillna("") != ""].sort_values("orden_vista")
    r = H.prioridades(n=5)
    assert [e["etapa"] for e in r["etapas"]] == p.Etapa.head(5).tolist()
    assert r["total_con_prioridad"] == len(p)
    assert r["etapas"][0]["motivo"] == p.iloc[0].motivo


def test_cuello_principal_coincide():
    d = _csv("determinista_global")
    principal = d.loc[d.es_principal.astype(bool), "Etapa"].iloc[0]
    r = H.cuello_botella()
    principales = [c["etapa"] for c in r["cuellos_relevantes"] if c["es_principal"]]
    assert principales == [principal]
    assert H.resumen_linea()["cuello_de_botella_principal"]["etapa"] == principal


def test_mantenimiento_sigue_el_orden_oficial():
    m = _csv("mantenimiento_global").sort_values("rango_mant")
    r = H.mantenimiento(n=4)
    assert [e["etapa"] for e in r["etapas"]] == m.Etapa.head(4).tolist()


def test_resumen_linea():
    r = H.resumen_linea()
    k = _csv("kpis_global")
    assert r["etapas_analizadas"] == len(k)
    assert r["periodo"]["dias"] == len(H.motor.dias)
    assert r["etapas_que_incumplen_disponibilidad"] == int((k.cumple_Dp == False).sum())  # noqa: E712
    assert {e["operacion"] for e in r["operaciones_excluidas"]} >= {"ST_0030", "PM2130"}


# ---------- nombres ----------
def test_nombres_en_cualquier_formato():
    for nombre in ["ST-2390", "ST_2390", "ST2390", "st 2390"]:
        assert H.kpis_etapa(nombre)["etapa"] == "ST_2390"
    # operaciones en paralelo fusionadas en una etapa
    assert H.kpis_etapa("ST2376")["etapa"] == "ST_2375+ST_2376"
    assert H.kpis_etapa("ST-2375")["etapa"] == "ST_2375+ST_2376"
    assert "nota_paralelo" in H.kpis_etapa("ST2375")


def test_maquina_excluida_responde_claro():
    r = H.kpis_etapa("ST_0030")
    assert r["en_analisis"] is False
    assert r["motivo_exclusion"] == "máquina sin datos"
    assert r["alertas"] and r["alertas"][0]["causa_probable"]
    assert H.alertas("ST0030")["en_analisis"] is False


def test_maquina_inexistente_no_rompe():
    r = H.kpis_etapa("ST-9999")
    assert "error" in r
    assert "error" in H.ejecutar("kpis_etapa", {"nombre": 123})
    assert H.ejecutar("no_existe", {}) == {"error": "Herramienta desconocida."}
    assert "error" in H.ejecutar("prioridades", {"n": 3, "categoria": "inventada"})


def test_datos_dudosos_se_avisan():
    r = H.kpis_etapa("ST2235")
    assert r["datos"]["datos_dudosos"] is True
    assert "nota_tiempo_ciclo" in r
    a = H.alertas("ST2235")
    assert a["n_alertas"] >= 2 and a["datos_dudosos"] is True


# ---------- periodo ----------
def test_periodo_igual_que_el_dashboard():
    dias = H.motor.dias[:3]
    h = HerramientasLinea(dias=dias, motor=H.motor)
    esperado = LI.calcular(H.motor, dias).kpis.set_index("Etapa").loc["ST_2390"]
    r = h.kpis_etapa("ST2390")
    assert r["periodo"]["dias"] == 3 and r["periodo"]["es_periodo_completo"] is False
    assert r["disponibilidad_pct"] == round(100 * esperado.Dp, 1)
    # un día suelto
    h.fijar_dias([H.motor.dias[0]])
    assert h.kpis_etapa("ST2390")["periodo"]["dias"] == 1
    try:
        h.fijar_dias(["1999-S01-D1"])
    except ValueError:
        pass
    else:
        raise AssertionError("debería rechazar días sin datos")


# ---------- verificador y bucle con modelo simulado ----------
def test_verificador_de_cifras():
    resultados = [H.kpis_etapa("ST2390")]
    assert verificar_cifras("ST-2390 tiene una disponibilidad del 77,5 %.", "?", resultados) == []
    assert verificar_cifras("ST-2390 tiene una disponibilidad del 64,0 %.", "?", resultados) == ["64,0"]
    # los nombres de etapa y los días no cuentan como cifras, pero deben existir en las fuentes
    assert verificar_cifras("ST_2375+ST_2376 el 2026-S40-D2", "?", [H.kpis_etapa("ST2375")]) == []
    assert verificar_cifras("ST_2375+ST_2376 el 2026-S40-D2", "?", []) == \
        ["ST_2375+ST_2376", "2026-S40-D2"]


def test_firma_llamadas_normaliza_nombres():
    assert firma_llamadas([("kpis_etapa", {"nombre": "ST-2390"})]) == \
        firma_llamadas([("kpis_etapa", {"nombre": "st_2390"})])
    assert firma_llamadas([("glosario", {"termino": "parada inducida"})]) == \
        firma_llamadas([("glosario", {"termino": "TAI"})])


class _ClienteSimulado:
    """Imita client.chat.completions.create: primero pide una herramienta, luego responde."""

    def __init__(self):
        self.peticiones = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.peticiones.append(kw)
        if len(self.peticiones) == 1:
            llamada = SimpleNamespace(id="c1", function=SimpleNamespace(
                name="kpis_etapa", arguments=json.dumps({"nombre": "ST-2390"})))
            mensaje = SimpleNamespace(content=None, tool_calls=[llamada])
        else:
            dato = json.loads(kw["messages"][-1]["content"])
            texto = f"La disponibilidad de {dato['etapa']} es {dato['disponibilidad_pct']} %."
            mensaje = SimpleNamespace(content=texto, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)],
                               usage=SimpleNamespace(completion_tokens=10))


def test_bucle_preguntar_con_modelo_simulado():
    cliente = _ClienteSimulado()
    pregunta = "¿Y cuánto marca esa etapa?"
    respuesta, llamadas, resultados, tokens = preguntar(cliente, "simulado", H, pregunta)
    assert llamadas == [("kpis_etapa", {"nombre": "ST-2390"})]
    assert "77.5" in respuesta and tokens == 20
    assert verificar_cifras(respuesta, pregunta, resultados) == []
    assert cliente.peticiones[0]["tools"] == TOOLS
    assert cliente.peticiones[1]["messages"][-1]["role"] == "tool"


def _cliente_que_responde(texto, peticiones):
    def crear(**peticion):
        peticiones.append(peticion)
        mensaje = SimpleNamespace(content=texto, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)],
                               usage=SimpleNamespace(completion_tokens=10))
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=crear)))


def test_consulta_directa_adelanta_datos_en_una_llamada_y_mantiene_herramientas():
    peticiones = []
    cliente = _cliente_que_responde("La disponibilidad propia de ST-2390 es 77,5 %.", peticiones)
    historial = [{"role": "assistant", "content": "¿Qué indicador quieres consultar?"}]
    respuesta, llamadas, resultados, tokens = preguntar(
        cliente, "simulado", H, "¿Qué disponibilidad propia tiene ST-2390?", historial=historial,
    )
    peticion, = peticiones                       # una sola petición al modelo
    mensajes = peticion["messages"]
    assert peticion["tools"] == TOOLS            # el modelo puede pedir más datos si le faltan
    assert mensajes[1] == historial[0]
    llamada, = mensajes[-2]["tool_calls"]
    assert llamada["function"]["name"] == "kpis_etapa"
    assert re.fullmatch(r"[A-Za-z0-9]{9}", llamada["id"])   # formato que exige Mistral
    assert mensajes[-1]["role"] == "tool" and json.loads(mensajes[-1]["content"]) == resultados[0]
    assert llamadas == [("kpis_etapa", {"nombre": "ST-2390"})]
    assert resultados[0]["disponibilidad_pct"] == 77.5
    assert "77,5 %" in respuesta and tokens == 10
    assert 0 < peticion["timeout"] <= 180


# ---------- problemas detectados en la auditoría ----------
def test_verificador_exige_la_cifra_de_la_etapa_nombrada():
    r = [H.kpis_etapa("ST2390"), H.kpis_etapa("ST0260")]
    assert verificar_cifras("ST_2390 95,7 % / ST_0260 77,5 %", "?", r) == ["95,7", "77,5"]
    assert verificar_cifras("ST_2390 tiene un 95,7 % y ST_0260 un 77,5 %.", "?", r) != []
    assert verificar_cifras("La disponibilidad de ST_2390 es 77,5 % y la de ST_0260 es 95,7 %.",
                            "?", r) == []
    assert verificar_cifras("77,5 % en ST_2390.", "?", r) == []
    assert verificar_cifras("ST_2390 no cumple: 77,5 % frente al objetivo del 90 %.", "?", r) == []
    # operaciones en paralelo: la cifra de la etapa agrupada vale citando una de sus operaciones
    assert verificar_cifras("ST_2375 tiene 96,3 % de disponibilidad.", "?",
                            [H.kpis_etapa("ST2375")]) == []
    # zona de un cuello: las etapas citadas como límites no le roban la cifra al cuello
    assert verificar_cifras("ST_0260 afecta desde ST_0259 hasta ST_0295 con 368,5 h inducidas.",
                            "?", [H.cuello_botella()]) == []


def test_verificador_redondeo_pregunta_formatos_e_identificadores():
    assert verificar_cifras("Abre 23 h.", "?", [{"h": 22.0}]) == ["23"]
    assert verificar_cifras("ST_2390 para 4 h al día.", "?", [H.kpis_etapa("ST2390")]) == []
    assert verificar_cifras("Tiene 95,7 %.", "¿Tiene ST_2390 un 95,7 %?", []) == ["95,7"]
    assert verificar_cifras("Las 3 primeras son ST_0260, ST_0261 y PM_2020.", "¿Qué 3?",
                            [H.prioridades(3)]) == []
    assert verificar_cifras("Hizo 1.234 piezas.", "?", [{"npr": 1234}]) == []
    assert verificar_cifras("ST_2390 hizo 24.484 piezas.", "?", [H.kpis_etapa("ST2390")]) == []
    assert verificar_cifras("Paró 22h.", "?", []) == ["22"]
    assert verificar_cifras("ST_9999 el 2099-S99-D9", "?", [H.kpis_etapa("ST2390")]) == \
        ["ST_9999", "2099-S99-D9"]
    assert verificar_cifras("ST_2390 desde 2026-S40-D2", "?", [H.kpis_etapa("ST2390")]) == []


def test_verificador_liga_cifra_a_etapa_indicador_y_unidad():
    """Casos reproducidos en la segunda auditoría."""
    a, b = H.kpis_etapa("ST2390"), H.kpis_etapa("ST0260")
    # 59,0 es el tiempo de ciclo (cmin) de ST_2390, no su disponibilidad (77,5 %)
    assert verificar_cifras("ST_2390 tiene una disponibilidad del 59,0 %.", "?", [a]) == ["59,0"]
    assert verificar_cifras("El tiempo de ciclo de ST_2390 es 59,0 cmin.", "?", [a]) == []
    assert verificar_cifras("ST_2390 tiene 77,5 % de disponibilidad y un tiempo de ciclo de "
                            "59,0 cmin.", "?", [a]) == []
    assert verificar_cifras("ST_2390 tiene 59,0 % de disponibilidad y un tiempo de ciclo de "
                            "77,5 cmin.", "?", [a]) == ["59,0", "77,5"]
    # intercambio entre máquinas y comparación correcta
    assert verificar_cifras("ST_2390 95,7 % / ST_0260 77,5 %", "?", [a, b]) == ["95,7", "77,5"]
    assert verificar_cifras("La disponibilidad de ST_2390 es 77,5 % y la de ST_0260 es 95,7 %, "
                            "por encima del objetivo del 90 %.", "?", [a, b]) == []
    # otras unidades e indicadores
    assert verificar_cifras("ST_2390 se para 4,4 h al día (parada propia).", "?", [a]) == []
    assert verificar_cifras("Su Fpm es de 393,3 paros por cada 1000 piezas.", "?", [a]) == []
    assert verificar_cifras("ST_2390 hace 59,0 paros por cada 1000 piezas.", "?", [a]) == ["59,0"]
    assert verificar_cifras("ST_2390 registró 9.630 paradas propias.", "?", [a]) == []
    # una lista numerada no confunde el número de viñeta con un dato
    p = [H.prioridades(3)]
    assert verificar_cifras("1. ST_0260: severidad 39,3 %.\n2. ST_0261: severidad 18,0 %.",
                            "?", p) == []
    assert verificar_cifras("1. ST_0260: severidad 18,0 %.", "?", p) == ["18,0"]


def test_nombre_no_confirmado_solo_vale_para_negarlo():
    no_existe = H.kpis_etapa("ST_9999")
    assert "error" in no_existe
    assert verificar_cifras("ST_9999 existe.", "¿Existe ST_9999?", [no_existe]) == ["ST_9999"]
    assert verificar_cifras("No existe ninguna máquina ST_9999 en la línea.", "¿Existe ST_9999?",
                            [no_existe]) == []
    assert verificar_cifras("ST_9999 tiene un 80 % de disponibilidad.", "¿Y ST_9999?", []) == \
        ["80", "ST_9999"]


def test_respuesta_sin_herramientas_no_queda_verificada():
    peticiones = []
    cliente = _cliente_que_responde("La disponibilidad es del 85 %.", peticiones)
    salida = responder(cliente, "simulado", H, "¿Qué tal va la línea en general?")
    assert salida["sin_datos"] is True and salida["verificada"] is False
    assert salida["cifras_no_verificadas"] == ["85"]


def test_preguntas_compuestas_no_se_adelantan():
    assert _consulta_directa("¿Qué tres máquinas penalizan más por baja disponibilidad?", H) == []
    assert _consulta_directa("¿Qué es la disponibilidad y qué disponibilidad tiene ST_2390?", H) == []
    assert _consulta_directa("¿Qué 3 máquinas penalizan más la línea?", H) == \
        [("prioridades", {"n": 3})]


def test_argumentos_fuera_de_rango_no_rompen_el_bucle():
    for n in (1e999, float("nan"), 0, 21, True, "3", None):
        assert "error" in H.ejecutar("prioridades", {"n": n}), n
    assert "error" in H.ejecutar("kpis_etapa", ["ST2390"])
    assert H.ejecutar("prioridades", {"n": 3.0})["etapas"]

    llamadas_hechas = []

    def crear(**peticion):
        llamadas_hechas.append(peticion)
        if len(llamadas_hechas) == 1:
            llamada = SimpleNamespace(id="abc123def", function=SimpleNamespace(
                name="prioridades", arguments='{"n": 1e999}'))
            mensaje = SimpleNamespace(content=None, tool_calls=[llamada])
        else:
            mensaje = SimpleNamespace(content="No he podido consultar el ranking.", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)], usage=None)

    cliente = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=crear)))
    respuesta, _, resultados, _ = preguntar(cliente, "simulado", H, "Dame el ranking, porfa")
    assert "error" in resultados[0] and respuesta


def test_seleccion_vacia_no_pasa_al_periodo_global():
    h = HerramientasLinea(motor=H.motor).fijar_dias([])
    assert h.sin_dias
    for nombre, args in [("resumen_linea", {}), ("kpis_etapa", {"nombre": "ST2390"}),
                         ("prioridades", {"n": 3})]:
        assert "ningún día" in h.ejecutar(nombre, args)["error"]
    assert "definicion" in h.ejecutar("glosario", {"termino": "TAI"})
    assert h.fijar_dias(None).ejecutar("resumen_linea", {})["etapas_analizadas"] == 84


def test_plazo_total_de_la_pregunta():
    cliente = _cliente_que_responde("Hola", [])
    try:
        preguntar(cliente, "simulado", H, "Hola", plazo_s=0)
    except TimeoutError:
        pass
    else:
        raise AssertionError("debería agotar el plazo")


def test_esquema_de_herramientas():
    nombres = [t["function"]["name"] for t in TOOLS]
    assert nombres == ["resumen_linea", "kpis_etapa", "prioridades", "cuello_botella",
                       "mantenimiento", "alertas", "glosario"]
    for t in TOOLS:
        assert hasattr(H, t["function"]["name"])
        json.dumps(t)  # serializable para la API


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
