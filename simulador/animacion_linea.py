"""
Animación de la Línea 5 a partir del simulador (reto LOSSIA, Hackathon HORSE).

Simula una jornada y guarda, minuto a minuto, el estado de cada etapa:
    funcionando (TBF) · parada propia (TAP) · bloqueada / saturada (SAT) · sin piezas (DES)
y cuántas piezas hay en cada buffer entre etapas. Genera una página HTML
autónoma con la línea dibujada en zigzag que se reproduce como un vídeo.

Incluye dos escenarios con los mismos números aleatorios, para comparar:
    · Situación actual
    · Sin paradas en la etapa indicada con --mejorar (por defecto PM_2250)

Uso (desde la raíz del repo):
    python simulador/animacion_linea.py
    python simulador/animacion_linea.py --mejorar ST_0260 --paso 30

Salida: simulador/salidas/animacion_linea.html
Para meterlo luego en Streamlit:
    st.components.v1.html(Path(".../animacion_linea.html").read_text(), height=900)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from simulador_linea import H, cargar_parametros, piezas_necesarias, produccion_media, simular, tiempos_servicio


def estados(p, res, ciclo, t0, t1, paso_s, origen=None):
    """Devuelve, por fotograma, una cadena con el estado de cada etapa y otra con los buffers."""
    S, C, D = res["S"], res["C"], res["D"]
    T = np.arange(t0, t1, paso_s)
    n = S.shape[0]
    est = np.zeros((len(T), n), dtype=np.int8)
    for i in range(n):
        k = np.clip(np.searchsorted(S[i], T, side="right") - 1, 0, S.shape[1] - 1)
        s, c, d = S[i, k], C[i, k], D[i, k]
        e = np.full(len(T), 3, dtype=np.int8)        # 3 = sin piezas (DES)
        e[T < d] = 2                                 # 2 = bloqueada (SAT)
        e[T < c] = 1                                 # 1 = parada propia (TAP)
        e[T < s + ciclo[i]] = 0                      # 0 = funcionando
        est[:, i] = e
    buf = np.zeros((len(T), max(n - 1, 0)), dtype=np.int16)
    for i in range(n - 1):
        salidos = np.searchsorted(np.sort(D[i]), T, side="right")
        entrados = np.searchsorted(S[i + 1], T, side="right")
        buf[:, i] = np.clip(salidos - entrados, 0, 35)
    # Motores terminados desde el inicio de la jornada, con el mismo origen en los dos escenarios
    # (los terminados por la situación actual antes de t0): así quitar paradas nunca resta.
    salidas = np.sort(D[-1])
    if origen is None:
        origen = int(np.searchsorted(salidas, t0))
    producidos = np.searchsorted(salidas, T, side="right") - origen
    alfabeto = "0123456789abcdefghijklmnopqrstuvwxyz"
    return {
        "est": ["".join(map(str, fila)) for fila in est],
        "buf": ["".join(alfabeto[x] for x in fila) for fila in buf],
        "prod": producidos.astype(int).tolist(),
    }


OSCURO = """
  :root { --bg: transparent; --panel: #FBF8F1; --ink: #0A2540; --muted: #3C5878; --line: #C9BFA3;
          --ok: #3C7A5E; --stop: #B8441F; --sat: #4F6D8F; --des: #C9973F; }
  body { font-family: 'Inter', system-ui, sans-serif; }
  header { display: none; }
  .card, button, select, .seg { border-radius: 2px; }
  .kpi .l { font-family: 'IBM Plex Mono', ui-monospace, monospace; text-transform: uppercase; letter-spacing: .06em; font-size: 11px; }
  .kpi .v { font-family: 'IBM Plex Serif', Georgia, serif; font-weight: 500; }
  button.play { background: #0A2540; color: #F5F1E8; border-color: #0A2540; }
  .seg button.on { background: #0A2540; color: #F5F1E8; }
  .maq rect { rx: 2; }
  .bufbg { fill: #E4DCC8; } .buffill { fill: #3C5878; } .flecha { stroke: #B7AC90; }
  #tip { background: #0A2540; color: #F5F1E8; border-radius: 2px; }
  input[type=range] { accent-color: #B8441F; }
  .barra, .tiempo, #lienzo, .nota { padding-left: 0; padding-right: 0; }
  .barra:first-of-type { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
  .barra:first-of-type .controles { grid-column: 1 / -1; justify-content: flex-start; }
  .kpi { min-width: 0; min-height: 96px; padding: 14px 16px; }
  .kpi .v { font-size: 26px; }
  .card { background: #FBF8F1; border-color: #C9BFA3; }
  .leyenda { padding: 4px 0; }
  #lienzo { padding-top: 4px; }
  .nota { display: none; }
  #lienzo { padding-bottom: 0; }
"""


def construir_html(raiz: Path, mejorar, factor: float = 0.0, buffer=8, paso: int = 60,
                   semilla: int = 2026, oscuro: bool = False):
    """Simula la jornada en dos escenarios y devuelve (html, motores_actual, motores_mejora).
    mejorar: una etapa, una lista de etapas o un dict {etapa: factor} para mejorar cada una
    en distinta medida. factor = fracción de las paradas que se mantiene (0 = sin paradas)."""
    p, horas_dia, real = cargar_parametros(raiz)
    if isinstance(mejorar, dict):
        factores = {e: float(f) for e, f in mejorar.items()}
    else:
        factores = {e: factor for e in ([mejorar] if isinstance(mejorar, str) else list(mejorar or []))}
    mejorar = list(factores)
    desconocidas = [e for e in mejorar if e not in set(p["Etapa"])]
    if desconocidas:
        raise ValueError(f"No existe la etapa {', '.join(desconocidas)}")
    horizonte = horas_dia * H
    t0, t1 = horizonte, 2 * horizonte
    K = piezas_necesarias(p, horizonte)
    ciclo = p["ciclo_s"].to_numpy()
    reducciones = {round((1 - f) * 100) for f in factores.values()}
    quien = mejorar[0] if len(mejorar) == 1 else f"{len(mejorar)} etapas"
    if not mejorar:
        nombre_mejora = "Sin mejoras"
    elif reducciones == {100}:
        nombre_mejora = f"Sin paradas en {quien}"
    elif len(reducciones) == 1:
        nombre_mejora = f"{quien} con {reducciones.pop()} % menos paradas"
    else:
        nombre_mejora = f"{quien} mejoradas"
    escenarios, piezas = {}, []
    for nombre, quitar in [("Situación actual", None), (nombre_mejora, mejorar)]:
        rng = np.random.default_rng(semilla)
        t, paradas = tiempos_servicio(p, K, rng)
        for etapa in (quitar or []):
            i = int(p.index[p["Etapa"] == etapa][0])
            t[i] -= paradas[i] * (1 - factores[etapa])
        res = simular(t, buffer, horizonte, guardar=True)
        if quitar is None:   # terminados antes de la jornada mostrada: mismo origen en los dos escenarios
            origen = int(np.searchsorted(np.sort(res["D"][-1]), t0))
        escenarios[nombre] = estados(p, res, ciclo, t0, t1, paso, origen=origen)
        # Las cifras de producción salen de varias jornadas seguidas (no solo de la animada):
        # una sola jornada depende mucho de qué paradas largas caen ese día y del efecto de borde.
        piezas.append(int(round(produccion_media(p, factores if quitar else {}, buffer, horizonte, semilla))))
    datos = {
        "etapas": p["Etapa"].tolist(), "orden": p["Orden"].astype(int).tolist(),
        "n_par": p["n_par"].astype(int).tolist(), "paso": paso,
        "buffer": ([int(buffer)] * (len(p) - 1) if np.isscalar(buffer) else [int(b) for b in buffer]),
        "real": round(real), "escenarios": escenarios,
    }
    plantilla = (Path(__file__).parent / "plantilla_animacion.html").read_text(encoding="utf-8")
    html = plantilla.replace("/*__DATOS__*/null", json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    if oscuro:
        fuentes = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&'
                   'family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Serif:wght@500&display=swap">')
        html = html.replace("<title>", fuentes + "<title>", 1).replace("</style>", OSCURO + "</style>", 1)
    return html, piezas[0], piezas[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", type=Path, default=Path("."))
    ap.add_argument("--mejorar", default="PM_2250", help="etapa cuyas paradas se eliminan en el 2.º escenario")
    ap.add_argument("--buffer", type=int, default=8, help="tamaño de buffer (el calibrado es 8)")
    ap.add_argument("--paso", type=int, default=60, help="segundos entre fotogramas")
    ap.add_argument("--semilla", type=int, default=2026)
    a = ap.parse_args()
    try:
        html, base, mejora = construir_html(a.raiz, a.mejorar, buffer=a.buffer, paso=a.paso, semilla=a.semilla)
    except ValueError as e:
        raise SystemExit(str(e))
    print(f"Situación actual: {base} motores · Sin paradas en {a.mejorar}: {mejora} motores")
    salida = a.raiz / "simulador" / "salidas" / "animacion_linea.html"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(html, encoding="utf-8")
    print(f"Animación guardada en {salida} ({salida.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
