"""
Monta la carpeta del dataset privado de Kaggle con todo lo que necesitan los notebooks 03 y 04.

Copia lossia/, chat/, Streamlit/, .streamlit/, Datos_limpios/, Resultados/ y analisis.py SIN
cachés, logs ni secretos (secrets.toml), comprueba que no falta nada y escribe
dataset-metadata.json.
No sube nada: imprime el comando de la CLI de Kaggle para publicar la nueva versión.

    py -3.13 chat/preparar_dataset_kaggle.py --id usuario/nombre-del-dataset [--destino carpeta]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from chat.kaggle_remoto import ARCHIVOS_APP, CARPETAS_APP, EXCLUIR, faltan  # noqa: E402


def preparar(dataset_id: str, destino: Path) -> Path:
    if destino.exists() and any(destino.iterdir()):
        raise SystemExit(f"{destino} no está vacía: elige otra carpeta o bórrala antes.")
    destino.mkdir(parents=True, exist_ok=True)
    for carpeta in CARPETAS_APP:
        origen = REPO / carpeta
        if not origen.exists():
            raise SystemExit(f"Falta la carpeta {carpeta}/ en el repo.")
        shutil.copytree(origen, destino / carpeta, ignore=shutil.ignore_patterns(*EXCLUIR))
    for archivo in ARCHIVOS_APP:
        shutil.copy2(REPO / archivo, destino / archivo)
    pendientes = faltan(destino, "app")
    if pendientes:
        raise SystemExit("Faltan archivos necesarios: " + ", ".join(pendientes))
    secretos = [str(p.relative_to(destino)) for p in destino.rglob("secrets.toml")]
    if secretos:
        raise SystemExit(f"Se ha colado un archivo de secretos: {secretos}")
    titulo = dataset_id.split("/", 1)[-1].replace("-", " ").capitalize()
    (destino / "dataset-metadata.json").write_text(json.dumps(
        {"id": dataset_id, "title": titulo[:50], "licenses": [{"name": "other"}]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--id", required=True, help="usuario/nombre del dataset privado de Kaggle")
    p.add_argument("--destino", type=Path, default=None,
                   help="carpeta vacía donde montarlo (por defecto, una temporal)")
    args = p.parse_args()
    destino = args.destino or Path(tempfile.mkdtemp(prefix="dataset_lossia_"))
    preparar(args.id, destino)
    archivos = sum(1 for f in destino.rglob("*") if f.is_file())
    print(f"Dataset montado en {destino} ({archivos} archivos).")
    print("Publica la nueva versión (privada) con:")
    print(f'  kaggle datasets version -p "{destino}" -m "Repo para la demo remota" -r zip')


if __name__ == "__main__":
    main()
