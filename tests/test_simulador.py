"""
Pruebas del simulador de capacidad (lossia/simulador.py).

Comprueba con una línea sintética calculada a mano y con los datos reales:
- sin mejoras no hay ganancia; la ganancia nunca es negativa y crece con la mejora
- la ganancia de una etapa está acotada por el siguiente cuello (techo)
- mejorar varias etapas gana al menos lo que la mejor de ellas sola
- el modelo reproduce la producción real (calibración < 5 %)

Uso:  python tests/test_simulador.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from lossia import simulador as S  # noqa: E402

fallos: list[str] = []


def ok(cond: bool, nombre: str) -> None:
    print(f"  {'OK ' if cond else 'FALLO'}  {nombre}")
    if not cond:
        fallos.append(nombre)


def linea_sintetica() -> pd.DataFrame:
    """
    Un día, tres etapas con 100 motores. Capacidades (TBF+DES+SAT) / (TBF/NPR):
      A: (18+2+0)/(18/100) = 111.1   B: (19+0+0)/(19/100) = 100 (cuello)   C: (17+3+0)/(17/100) = 117.6
    """
    filas = [("A", 1, 18, 2, 0), ("B", 2, 19, 0, 0), ("C", 3, 17, 3, 0)]
    return pd.DataFrame([{"Dia": "D1", "Etapa": e, "Orden_etapa": o, "TBF": tbf, "TAP": 22 - tbf - des - sat,
                          "DES": des, "SAT": sat, "NPR": 100, "en_cadena": True}
                         for e, o, tbf, des, sat in filas])


def main() -> None:
    print("\n[sintético] línea de 3 etapas calculada a mano")
    ed = linea_sintetica()
    cap = S.capacidades(ed).iloc[0]
    ok(abs(cap["A"] - 2000 / 18) < 1e-9 and abs(cap["B"] - 100) < 1e-9 and abs(cap["C"] - 2000 / 17) < 1e-9,
       "capacidades = (TBF + DES + SAT) / (TBF / NPR)")
    ok(S.simular(ed, {})["resumen"]["ganancia_total"] == 0, "sin mejoras no hay ganancia")
    r = S.simular(ed, {"B": 0.5})["resumen"]
    ok(abs(r["ganancia_total"] - (2000 / 18 - 100)) < 1e-9,
       "mejorar el cuello gana hasta el siguiente cuello (A: 111.1 → +11.1)")
    ok(S.simular(ed, {"A": 0.5})["resumen"]["ganancia_total"] == 0, "mejorar una no-cuello no gana nada")
    ok(S.simular(ed, {"X": 0.1})["resumen"]["ignoradas"] == ["X"], "etapas desconocidas se informan")
    try:
        S.simular(ed, {"B": 1.0})
        ok(False, "rechaza reducciones del 100 %")
    except ValueError:
        ok(True, "rechaza reducciones del 100 %")

    print("\n[datos reales]")
    ed = S._cargar_etapa_dia()
    cal = S.calibracion(ed)
    err = cal["error_pct"].abs().mean()
    ok(err < 5, f"calibración: error medio {err:.1f} % < 5 %")

    pot = S.potencial(ed, 0.10)
    ok((pot["ganancia_media_dia"] >= -1e-9).all(), "ninguna mejora reduce la producción")
    ok((pot["ganancia_media_dia"] <= pot["techo_media_dia"] + 1e-9).all(),
       "la ganancia nunca supera el techo (siguiente cuello)")

    etapa = pot.iloc[0]["Etapa"]
    g = [S.simular(ed, {etapa: p})["resumen"]["ganancia_media_dia"] for p in (0, 0.05, 0.10, 0.2, 0.5)]
    ok(all(b >= a - 1e-9 for a, b in zip(g, g[1:])), f"ganancia monótona con la mejora ({etapa}: {np.round(g, 1)})")

    top = pot.head(3)["Etapa"].tolist()
    sola = max(S.simular(ed, {e: 0.10})["resumen"]["ganancia_media_dia"] for e in top)
    juntas = S.simular(ed, {e: 0.10 for e in top})["resumen"]["ganancia_media_dia"]
    ok(juntas >= sola - 1e-9, f"mejorar {top} a la vez ({juntas:.1f}) ≥ la mejor sola ({sola:.1f})")

    print()
    if fallos:
        print(f"FALLOS ({len(fallos)}):")
        for f in fallos:
            print("  -", f)
        sys.exit(1)
    print("Todas las pruebas del simulador han pasado.")


if __name__ == "__main__":
    main()
