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
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from chat.herramientas import (HerramientasLinea, TOOLS, firma_llamadas, preguntar,  # noqa: E402
                               verificar_cifras)
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
    # los nombres de etapa y los días no cuentan como cifras
    assert verificar_cifras("ST_2375+ST_2376 el 2026-S40-D2", "?", []) == []


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
    respuesta, llamadas, resultados, tokens = preguntar(cliente, "simulado", H, "¿Dp de ST-2390?")
    assert llamadas == [("kpis_etapa", {"nombre": "ST-2390"})]
    assert "77.5" in respuesta and tokens == 20
    assert verificar_cifras(respuesta, "¿Dp de ST-2390?", resultados) == []
    assert cliente.peticiones[0]["tools"] == TOOLS
    assert cliente.peticiones[1]["messages"][-1]["role"] == "tool"


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
