"""
Arma el contenido del Space de Hugging Face y lo deja listo para empujar (SCRUM-63).

POR QUE HACE FALTA ARMAR ALGO Y NO SE EMPUJA EL REPO ENTERO
El repositorio del Space es su propio repositorio git, y su raíz tiene que tener el
`Dockerfile` y el `README.md` con el encabezado de Spaces. Además, mandar el monorepo
completo subiría la aplicación clínica, los notebooks y los datos crudos a un contenedor
que sólo tiene que servir un modelo.

QUE SE COPIA — la lista está acá abajo, explícita a propósito
`CONTENIDO` es el contrato de despliegue. Si alguien agrega un módulo que la API importa y
no lo suma a esta lista, el Space arranca y muere con un ImportError. Por eso
`tests/test_despliegue.py` verifica que esta lista cubra todo lo que la API importa de
verdad, resolviendo los imports en frío en vez de confiar en que alguien se acordó.

ESTE SCRIPT NO MANEJA CREDENCIALES
No pide, no lee y no guarda ningún token. Prepara el directorio y, si ya existe una copia
de trabajo del Space, sincroniza los archivos. El `git push` lo hace una persona con sus
propias credenciales de Hugging Face.

    python deploy/hf_space/publicar.py --destino ../zaha-api-space

Después, dentro de ese directorio:

    git add -A && git commit -m "..." && git push
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ESTE_DIRECTORIO = Path(__file__).resolve().parent

# (origen relativo a la raíz del repo, destino relativo a la raíz del Space)
# Sólo lo que la API necesita en tiempo de ejecución. Nada de notebooks, datos crudos,
# aplicación clínica ni las dependencias de desarrollo.
CONTENIDO: list[tuple[str, str]] = [
    ("deploy/hf_space/Dockerfile", "Dockerfile"),
    ("deploy/hf_space/README.md", "README.md"),
    ("deploy/hf_space/.dockerignore", ".dockerignore"),
    # Produccion: fastapi, uvicorn, pydantic, onnxruntime, numpy. Sin torch ni pandas.
    ("ml_engine/requirements.txt", "requirements.txt"),
    # El paquete. `src/__init__.py` NO existe en el repo (src es un paquete implicito);
    # el script lo crea en el destino para que el contenedor no dependa de eso.
    ("ml_engine/src/rangos.py", "src/rangos.py"),
    ("ml_engine/src/api/__init__.py", "src/api/__init__.py"),
    ("ml_engine/src/api/main.py", "src/api/main.py"),
    ("ml_engine/src/api/modelo.py", "src/api/modelo.py"),
    # El par indivisible: un .onnx sin su sidecar no dice en que orden espera las
    # columnas, ni que umbral usar, ni con que explicar la prediccion.
    ("ml_engine/models/zaha_baseline.onnx", "models/zaha_baseline.onnx"),
    ("ml_engine/models/zaha_baseline.metadata.json", "models/zaha_baseline.metadata.json"),
]

# `src` es un paquete implícito en el repo. Dentro del contenedor conviene que sea
# explícito: un paquete de espacio de nombres depende de que nada más se llame `src` en
# el sys.path, y eso es una condición que no controlamos en una imagen ajena.
PAQUETES_A_CREAR = ["src/__init__.py"]


def armar(destino: Path) -> list[Path]:
    escritos = []
    for origen_rel, destino_rel in CONTENIDO:
        origen = RAIZ / origen_rel
        if not origen.exists():
            raise SystemExit(f"falta {origen_rel} — no se arma un Space incompleto")
        salida = destino / destino_rel
        salida.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, salida)
        escritos.append(salida)

    for paquete in PAQUETES_A_CREAR:
        salida = destino / paquete
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text("", encoding="utf-8")
        escritos.append(salida)

    return escritos


def main() -> None:
    parser = argparse.ArgumentParser(description="Armar el contenido del Space (SCRUM-63)")
    parser.add_argument(
        "--destino",
        type=Path,
        required=True,
        help="copia de trabajo del repositorio del Space (git clone de huggingface.co/spaces/...)",
    )
    args = parser.parse_args()

    destino = args.destino.resolve()
    destino.mkdir(parents=True, exist_ok=True)

    escritos = armar(destino)

    print(f"Contenido del Space armado en {destino}\n")
    for ruta in escritos:
        print(f"  {ruta.relative_to(destino).as_posix()}")

    if not (destino / ".git").exists():
        print(
            "\nOJO: ese directorio no es un repositorio git. El Space se clona primero:\n"
            "  git clone https://huggingface.co/spaces/Zaha-CDSS/<nombre> "
            f"{destino.name}"
        )
        sys.exit(1)

    print("\nFalta empujarlo, con tus credenciales de Hugging Face:")
    print(f"  cd {destino}")
    print('  git add -A && git commit -m "feat: API de inferencia (SCRUM-63)" && git push')


if __name__ == "__main__":
    main()
