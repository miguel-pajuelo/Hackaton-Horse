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

from simulador_linea import H, cargar_parametros, piezas_necesarias, simular, tiempos_servicio


def estados(p, res, ciclo, t0, t1, paso_s):
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
    producidos = np.searchsorted(np.sort(D[-1]), T, side="right") - np.searchsorted(np.sort(D[-1]), t0)
    alfabeto = "0123456789abcdefghijklmnopqrstuvwxyz"
    return {
        "est": ["".join(map(str, fila)) for fila in est],
        "buf": ["".join(alfabeto[x] for x in fila) for fila in buf],
        "prod": producidos.astype(int).tolist(),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", type=Path, default=Path("."))
    ap.add_argument("--mejorar", default="PM_2250", help="etapa cuyas paradas se eliminan en el 2.º escenario")
    ap.add_argument("--buffer", type=int, default=8, help="tamaño de buffer (el calibrado es 8)")
    ap.add_argument("--paso", type=int, default=60, help="segundos entre fotogramas")
    ap.add_argument("--semilla", type=int, default=2026)
    a = ap.parse_args()

    p, horas_dia, real = cargar_parametros(a.raiz)
    if a.mejorar not in set(p["Etapa"]):
        raise SystemExit(f"No existe la etapa {a.mejorar}. Opciones: {', '.join(p['Etapa'])}")
    horizonte = horas_dia * H
    t0, t1 = horizonte, 2 * horizonte
    K = piezas_necesarias(p, horizonte)
    ciclo = p["ciclo_s"].to_numpy()

    escenarios = {}
    for nombre, quitar in [("Situación actual", None), (f"Sin paradas en {a.mejorar}", a.mejorar)]:
        rng = np.random.default_rng(a.semilla)
        t, paradas = tiempos_servicio(p, K, rng)
        if quitar:
            i = int(p.index[p["Etapa"] == quitar][0])
            t[i] -= paradas[i]
        res = simular(t, a.buffer, horizonte, guardar=True)
        escenarios[nombre] = estados(p, res, ciclo, t0, t1, a.paso)
        print(f"{nombre}: {res['piezas']} motores en {horas_dia:.0f} h")

    datos = {
        "etapas": p["Etapa"].tolist(),
        "orden": p["Orden"].astype(int).tolist(),
        "n_par": p["n_par"].astype(int).tolist(),
        "buffer": a.buffer,
        "paso": a.paso,
        "real": round(real),
        "escenarios": escenarios,
    }
    plantilla = (Path(__file__).parent / "plantilla_animacion.html").read_text(encoding="utf-8")
    html = plantilla.replace("/*__DATOS__*/null", json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    salida = a.raiz / "simulador" / "salidas" / "animacion_linea.html"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(html, encoding="utf-8")
    print(f"Animación guardada en {salida} ({salida.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
