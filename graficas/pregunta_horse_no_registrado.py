"""
Gráfica para preguntar a HORSE por el tiempo sin estado registrado de ST_0260.

Uso:
    python graficas/pregunta_horse_no_registrado.py [OPERACION]
    (por defecto ST_0260)

Genera Resultados/pregunta_horse_no_registrado_<OP>.svg (se puede pegar en PowerPoint/Word
o abrir en el navegador). Sin dependencias aparte de pandas: el SVG se escribe a mano.
"""
from __future__ import annotations

import sys
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
JORNADA = 22.0

# Paleta de referencia (modo claro)
SURFACE, TXT, TXT2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e5e4e0"
C_TBF, C_TAP, C_IND = "#2a78d6", "#eb6834", "#1baf7a"
C_NR, C_NR_SUAVE = "#52514e", "#c3c2b7"
FONT = "Segoe UI, Helvetica, Arial, sans-serif"


def fmt(x: float, dec: int = 1) -> str:
    return f"{x:.{dec}f}".replace(".", ",")


def barra(x, y, w, h, color, redondear: str = "") -> str:
    """Rect con extremo redondeado de 4 px ('top' o 'right'), anclado a la base."""
    if h <= 0 or w <= 0:
        return ""
    r = min(4, h / 2, w / 2)
    if redondear == "top":
        d = (f"M{x},{y + h} V{y + r} Q{x},{y} {x + r},{y} H{x + w - r} Q{x + w},{y} {x + w},{y + r} "
             f"V{y + h} Z")
    elif redondear == "right":
        d = (f"M{x},{y} H{x + w - r} Q{x + w},{y} {x + w},{y + r} V{y + h - r} Q{x + w},{y + h} "
             f"{x + w - r},{y + h} H{x} Z")
    else:
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{color}"/>'
    return f'<path d="{d}" fill="{color}"/>'


def texto(x, y, s, size=13, color=TXT, anchor="start", weight="normal") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color}" text-anchor="{anchor}" '
            f'font-weight="{weight}">{escape(s)}</text>')


def main(op: str) -> Path:
    d = pd.read_csv(BASE / "Datos_limpios" / "datos_limpios.csv")
    d = d[d["incluir_analisis"]].copy()
    d["Dia"] = "S" + d["Week"].astype(str) + "-D" + d["Jour"].astype(str)
    d["IND"] = d["DES"] + d["SAT"]
    if "T_no_registrado_raw" in d:  # tras la regla de HORSE el hueco original queda en *_raw
        d["TBF"] = d["TBF"] - d["TBF_desde_no_reg"]
        d["TAP"] = d["TAP"] - d["TAP_desde_no_reg"]
        d["T_no_registrado"] = d["T_no_registrado_raw"]

    ranking = d.groupby("Operacion_norm")["T_no_registrado"].mean().sort_values(ascending=False)
    top = ranking.head(10)
    mediana_linea = ranking.median()
    dia = d[d["Operacion_norm"] == op].sort_values(["Week", "Jour"])
    nr_min, nr_max, nr_med = dia["T_no_registrado"].min(), dia["T_no_registrado"].max(), dia["T_no_registrado"].mean()

    # Contexto de vecinos (orden de configuración)
    orden = d.drop_duplicates("Operacion_norm").set_index("Operacion_norm")["Orden_OP"].sort_values()
    pos = list(orden.index).index(op)
    ant, sig = orden.index[pos - 1], orden.index[pos + 1]
    med = d.groupby("Operacion_norm")[["SAT", "DES"]].mean()

    W, H = 1240, 720
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
         f'font-family="{FONT}">',
         f'<rect width="{W}" height="{H}" fill="{SURFACE}"/>']

    # Título y pregunta
    s.append(texto(40, 48, f"{op}: ~{fmt(nr_med)} h al día sin ningún estado registrado", 24, weight="600"))
    s.append(texto(40, 76, f"De las {fmt(JORNADA, 0)} h de jornada, entre {fmt(nr_min)} y {fmt(nr_max)} h diarias "
                           f"no constan como funcionamiento, parada propia ni parada inducida.", 15, TXT2))

    # ---------- Panel A: ranking de tiempo sin registrar ----------
    ax, ay, aw = 40, 140, 420
    s.append(texto(ax, ay - 22, "Tiempo sin registrar por máquina", 16, weight="600"))
    s.append(texto(ax, ay - 4, "Media h/día, las 10 con más tiempo (16 días productivos)", 13, TXT2))
    lab_w, bar_h, gap = 92, 30, 8
    escala_a = (aw - lab_w - 50) / max(top.max(), 1)
    for i, (nombre, v) in enumerate(top.items()):
        y = ay + 16 + i * (bar_h + gap)
        foco = nombre == op
        s.append(texto(ax + lab_w - 8, y + bar_h / 2 + 5, nombre, 13, TXT if foco else TXT2, "end",
                       "600" if foco else "normal"))
        s.append(barra(ax + lab_w, y, v * escala_a, bar_h, C_NR if foco else C_NR_SUAVE, "right"))
        s.append(texto(ax + lab_w + v * escala_a + 6, y + bar_h / 2 + 5, f"{fmt(v)} h", 13,
                       TXT if foco else TXT2, weight="600" if foco else "normal"))
    yb = ay + 16 + len(top) * (bar_h + gap)
    s.append(texto(ax, yb + 14, f"Mediana de toda la línea: {fmt(mediana_linea, 2)} h/día", 13, TXT2))

    # ---------- Panel B: composición diaria ----------
    bx, by, bw, bh = 560, 140, 640, 400
    s.append(texto(bx, by - 22, f"Jornada diaria de {op}", 16, weight="600"))
    s.append(texto(bx, by - 4, "Horas por estado; la parte gris oscura es el tiempo sin registrar", 13, TXT2))
    px0, py0 = bx + 34, by + 62           # zona de trazado
    pw, ph = bw - 40, bh - 92
    ky = ph / JORNADA
    # Leyenda (una fila)
    leyenda = [("Funcionando (TBF)", C_TBF), ("Parada propia (TAP)", C_TAP),
               ("Parada inducida (DES+SAT)", C_IND), ("Sin registrar", C_NR)]
    lx = bx
    for nombre, c in leyenda:
        s.append(f'<rect x="{lx}" y="{by + 8}" width="12" height="12" rx="2" fill="{c}"/>')
        s.append(texto(lx + 18, by + 19, nombre, 13, TXT2))
        lx += 18 + len(nombre) * 7.0 + 22
    # Rejilla y eje
    for h in range(0, 23, 4):
        y = py0 + ph - h * ky
        s.append(f'<line x1="{px0}" x2="{px0 + pw}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        s.append(texto(px0 - 8, y + 4, f"{h}", 12, TXT2, "end"))
    y22 = py0 + ph - JORNADA * ky
    s.append(f'<line x1="{px0}" x2="{px0 + pw}" y1="{y22:.1f}" y2="{y22:.1f}" stroke="{TXT2}" '
             f'stroke-width="1" stroke-dasharray="4 3"/>')
    s.append(texto(px0 + pw, y22 - 6, "Jornada 22 h", 12, TXT2, "end"))
    s.append(texto(px0 - 30, py0 + ph / 2, "h", 12, TXT2, "middle"))
    # Barras apiladas
    n = len(dia)
    paso = pw / n
    ancho = paso * 0.62
    semana_prev = None
    for i, (_, f) in enumerate(dia.iterrows()):
        x = px0 + i * paso + (paso - ancho) / 2
        y = py0 + ph
        segs = [(f["TBF"], C_TBF), (f["TAP"], C_TAP), (f["IND"], C_IND), (f["T_no_registrado"], C_NR)]
        for k, (v, c) in enumerate(segs):
            h = v * ky
            if h <= 0:
                continue
            ultimo = k == len(segs) - 1
            s.append(barra(x, y - h, ancho, max(h - (0 if ultimo else 2), 0), c, "top" if ultimo else ""))
            y -= h
        s.append(texto(x + ancho / 2, py0 + ph + 18, f"D{f['Jour']}", 11, TXT2, "middle"))
        if f["Week"] != semana_prev:
            s.append(texto(x, py0 + ph + 36, f"S{f['Week']}", 12, TXT2))
            semana_prev = f["Week"]

    # ---------- Contexto y preguntas ----------
    cy = 590
    s.append(f'<line x1="40" x2="{W - 40}" y1="{cy - 22}" y2="{cy - 22}" stroke="{GRID}"/>')
    s.append(texto(40, cy, "Por qué importa:", 14, weight="600"))
    s.append(texto(160, cy, f"{op} parece el cuello de botella de la línea. La máquina anterior ({ant}) está saturada "
                            f"{fmt(med.loc[ant, 'SAT'])} h/día esperando por ella, y la siguiente ({sig}) desabastecida "
                            f"{fmt(med.loc[sig, 'DES'])} h/día.", 14, TXT2))
    s.append(texto(160, cy + 22, f"Pero su parada propia registrada es solo de {fmt(dia['TAP'].mean())} h/día: "
                                 f"el tiempo sin registrar podría ser la parada que falta.", 14, TXT2))
    s.append(texto(40, cy + 56, "Preguntas:", 14, weight="600"))
    preguntas = [
        "1. ¿Qué hace la máquina durante ese tiempo? ¿Paradas no codificadas como TAP, microparadas, cambios, pruebas...?",
        "2. ¿Es un fallo de la señal / del sistema de captura de esta estación?",
        "3. ¿Debemos contarlo como parada propia (TAP) en el análisis?",
    ]
    for i, p in enumerate(preguntas):
        s.append(texto(160, cy + 56 + i * 22, p, 14, TXT2))

    s.append("</svg>")
    salida = BASE / "Resultados" / f"pregunta_horse_no_registrado_{op}.svg"
    salida.parent.mkdir(exist_ok=True)
    salida.write_text("\n".join(x for x in s if x), encoding="utf-8")
    return salida


if __name__ == "__main__":
    print(main(sys.argv[1] if len(sys.argv) > 1 else "ST_0260"))
