"""
Método de datos (ML): matriz de influencia aprendida entre máquinas.

Idea: si la parada propia (TAP) de la máquina i provoca paradas inducidas en la máquina j,
los días en que i se para más, j tendrá más DES (si i está aguas arriba) o más SAT
(si i está aguas abajo). Lo aprendemos sin decirle al modelo el orden de la línea:

    DES_j(día) ≈ Σ_i β_ij · TAP_i(día)      y      SAT_j(día) ≈ Σ_i γ_ij · TAP_i(día)

- Regresión Lasso con coeficientes positivos (una parada no puede "quitar" paradas a otra)
  y selección automática de la regularización por validación cruzada. Con pocos días y
  muchas máquinas, Lasso deja solo las relaciones que explican de verdad la variación.
- Estabilidad: se repite el ajuste con remuestreos de días (bootstrap) y solo se aceptan
  las relaciones causa -> efecto que aparecen en la mayoría de remuestreos.
- Las horas inducidas por i en j un día = β_ij · TAP_i(día), recortadas para no superar
  la parada inducida real de j ese día. Sumando sobre j se obtiene la puntuación de i.

Como el modelo no conoce la topología, sirve de contraste: si las relaciones que encuentra
apuntan en la dirección físicamente lógica (DES desde aguas arriba, SAT desde aguas abajo)
y coinciden con el método determinista, la conclusión es robusta.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import Lasso, LassoCV
from sklearn.model_selection import KFold, cross_val_predict

from . import config as C

ESTADOS_EFECTO = ("DES", "SAT")


def _ajustar_objetivo(X: np.ndarray, y: np.ndarray, rng: np.random.Generator):
    """Devuelve (coef en horas/hora, frecuencia bootstrap, r2_cv) para un objetivo."""
    p = X.shape[1]
    if np.std(y) < 1e-9:
        return np.zeros(p), np.zeros(p), np.nan

    mu, sd = X.mean(0), X.std(0)
    sd[sd < 1e-9] = np.inf                       # máquinas sin variación no pueden explicar nada
    Z = (X - mu) / sd

    n = len(y)
    cv = KFold(n_splits=min(5, n), shuffle=True, random_state=C.ML_SEMILLA)
    modelo = LassoCV(positive=True, cv=cv, alphas=50, max_iter=20000, random_state=C.ML_SEMILLA)
    modelo.fit(Z, y)
    alpha = modelo.alpha_
    coef = modelo.coef_ / sd

    fijo = Lasso(alpha=alpha, positive=True, max_iter=20000)
    pred = cross_val_predict(fijo, Z, y, cv=cv)
    r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)

    freq = np.zeros(p)
    for _ in range(C.ML_N_BOOTSTRAP):
        idx = rng.integers(0, n, n)
        if np.std(y[idx]) < 1e-9:
            continue
        fijo.fit(Z[idx], y[idx])
        freq += fijo.coef_ > 0
    freq /= C.ML_N_BOOTSTRAP
    return coef, freq, r2


def ajustar(etapa_dia: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Ajusta un modelo por (máquina efecto, estado DES/SAT).
    Devuelve:
      - relaciones: una fila por (causa, efecto, estado) con coeficiente, frecuencia y si es estable
      - calidad:    una fila por (efecto, estado) con el R² en validación cruzada
    """
    tap = etapa_dia.pivot(index="Dia", columns="Etapa", values="TAP").fillna(0)
    etapas = list(tap.columns)
    orden = etapa_dia.drop_duplicates("Etapa").set_index("Etapa")["Orden_etapa"]
    rng = np.random.default_rng(C.ML_SEMILLA)

    filas, calidad = [], []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        for estado in ESTADOS_EFECTO:
            y_tab = etapa_dia.pivot(index="Dia", columns="Etapa", values=estado).reindex(tap.index).fillna(0)
            for j in etapas:
                causas = [e for e in etapas if e != j]
                coef, freq, r2 = _ajustar_objetivo(tap[causas].to_numpy(), y_tab[j].to_numpy(), rng)
                calidad.append({"Efecto": j, "Estado": estado, "r2_cv": r2,
                                "n_causas": int((coef > 0).sum())})
                for i, b, f in zip(causas, coef, freq):
                    if b > 0:
                        filas.append({"Causa": i, "Efecto": j, "Estado": estado,
                                      "coef_h_por_h": b, "frecuencia_bootstrap": f})

    rel = pd.DataFrame(filas, columns=["Causa", "Efecto", "Estado", "coef_h_por_h", "frecuencia_bootstrap"])
    rel["estable"] = rel["frecuencia_bootstrap"] >= C.ML_MIN_FRECUENCIA
    rel["orden_causa"] = rel["Causa"].map(orden)
    rel["orden_efecto"] = rel["Efecto"].map(orden)
    rel["causa_aguas"] = np.where(rel["orden_causa"] < rel["orden_efecto"], "arriba", "abajo")
    # DES lógico si la causa está aguas arriba; SAT lógico si está aguas abajo
    rel["direccion_logica"] = ((rel["Estado"] == "DES") & (rel["causa_aguas"] == "arriba")) | (
        (rel["Estado"] == "SAT") & (rel["causa_aguas"] == "abajo")
    )
    return rel, pd.DataFrame(calidad)


def horas_inducidas_dia(etapa_dia: pd.DataFrame, relaciones: pd.DataFrame,
                        solo_estables: bool = True) -> pd.DataFrame:
    """
    Atribución diaria: horas de DES/SAT de cada efecto que se explican por la TAP de cada causa.
    Si la suma atribuida supera la parada inducida real de ese día, se reescala.
    Devuelve una fila por (Dia, Causa, Efecto, Estado).
    """
    rel = relaciones[relaciones["estable"]] if solo_estables else relaciones
    if rel.empty:
        return pd.DataFrame(columns=["Dia", "Causa", "Efecto", "Estado", "horas"])
    tap = etapa_dia[["Dia", "Etapa", "TAP"]].rename(columns={"Etapa": "Causa"})
    a = rel[["Causa", "Efecto", "Estado", "coef_h_por_h"]].merge(tap, on="Causa")
    a["horas"] = a["coef_h_por_h"] * a["TAP"]

    real = etapa_dia.melt(id_vars=["Dia", "Etapa"], value_vars=list(ESTADOS_EFECTO),
                          var_name="Estado", value_name="real").rename(columns={"Etapa": "Efecto"})
    tot = a.groupby(["Dia", "Efecto", "Estado"], as_index=False)["horas"].sum().merge(
        real, on=["Dia", "Efecto", "Estado"])
    tot["factor"] = np.where(tot["horas"] > tot["real"], tot["real"] / tot["horas"].replace(0, np.nan), 1.0)
    a = a.merge(tot[["Dia", "Efecto", "Estado", "factor"]], on=["Dia", "Efecto", "Estado"])
    a["horas"] = a["horas"] * a["factor"].fillna(0)
    return a[["Dia", "Causa", "Efecto", "Estado", "horas"]]


def puntuar(atribucion: pd.DataFrame, nivel: str, etapas: pd.DataFrame) -> pd.DataFrame:
    """
    Puntuación por máquina causa y periodo: horas de parada inducida que provoca en otras.
    `etapas` = tabla con Etapa y Orden_etapa para incluir también las máquinas con 0 h.
    """
    a = atribucion.copy()
    a["Periodo"] = a["Dia"] if nivel == "dia" else C.GLOBAL
    periodos = a["Periodo"].unique() if len(a) else [C.GLOBAL]
    piv = a.pivot_table(index=["Periodo", "Causa"], columns="Estado", values="horas",
                        aggfunc="sum", fill_value=0).reset_index()
    for e in ESTADOS_EFECTO:
        if e not in piv:
            piv[e] = 0.0
    piv = piv.rename(columns={"Causa": "Etapa", "DES": "horas_DES_provocada", "SAT": "horas_SAT_provocada"})

    base = pd.MultiIndex.from_product([periodos, etapas["Etapa"]], names=["Periodo", "Etapa"]).to_frame(index=False)
    out = base.merge(etapas[["Etapa", "Orden_etapa"]], on="Etapa").merge(piv, on=["Periodo", "Etapa"], how="left")
    out[["horas_DES_provocada", "horas_SAT_provocada"]] = out[["horas_DES_provocada", "horas_SAT_provocada"]].fillna(0)
    out["horas_inducidas_ml"] = out["horas_DES_provocada"] + out["horas_SAT_provocada"]
    out["rango_ml"] = out.groupby("Periodo")["horas_inducidas_ml"].rank(ascending=False, method="first").astype(int)
    return out.sort_values(["Periodo", "rango_ml"]).reset_index(drop=True)
