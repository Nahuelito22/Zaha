"""
Pruebas del contenido del Space de Hugging Face (SCRUM-63).

EL MODO DE FALLA QUE ESTO ATAJA
El despliegue es una lista de archivos escrita a mano en `deploy/hf_space/publicar.py`. Si
alguien agrega un módulo que la API importa y se olvida de sumarlo a esa lista, acá no
pasa nada: las pruebas siguen verdes, el PR se mergea, y el Space arranca y muere con un
ImportError que recién se ve en los logs de Hugging Face. Lo mismo si la API pasa a
importar algo que no está en `requirements.txt` de producción — en el entorno de
desarrollo está instalado y nadie se entera hasta que el contenedor falla.

Las dos cosas se verifican resolviendo los imports **en frío, en un intérprete aparte**, y
no leyendo el código: un `import` dentro de una función no aparece en la cabecera del
archivo pero sí rompe el contenedor.

    cd ml_engine && .venv/Scripts/python -m pytest tests/test_despliegue.py -q

Corre TAMBIÉN sin pytest:

    cd ml_engine && .venv/Scripts/python tests/test_despliegue.py
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

warnings.filterwarnings("ignore")

ML_ENGINE = Path(__file__).resolve().parents[1]
RAIZ = ML_ENGINE.parent
PUBLICAR = RAIZ / "deploy" / "hf_space" / "publicar.py"

# Lo que el contenedor de produccion NO lleva, por decision del ADR-004. Si la API llegara
# a importar cualquiera de estos, el Space no arranca.
PESADOS = {"pandas", "sklearn", "torch", "pandera", "xgboost", "skl2onnx", "pyarrow",
           "polars", "matplotlib", "scipy", "xlrd", "httpx"}


def _cargar_publicar():
    spec = importlib.util.spec_from_file_location("publicar", PUBLICAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _modulos_que_carga_la_api() -> dict:
    """
    Importa `src.api.main` en un intérprete limpio y devuelve qué cargó.

    En proceso no sirve: las otras pruebas ya dejaron medio `sys.modules` poblado.
    """
    # Propios = los que viven bajo `ml_engine/src`. El venv esta DENTRO de ml_engine, asi
    # que filtrar por la raiz del proyecto se traga todo site-packages.
    guion = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, %r)\n"
        "import src.api.main\n"
        "FUENTE = Path(%r) / 'src'\n"
        "def propio(m):\n"
        "    f = getattr(m, '__file__', None)\n"
        "    if not f:\n"
        "        return False\n"
        "    try:\n"
        "        Path(f).resolve().relative_to(FUENTE)\n"
        "    except ValueError:\n"
        "        return False\n"
        "    return True\n"
        "propios = sorted(n for n, m in sys.modules.items() if propio(m))\n"
        "terceros = sorted({n.split('.')[0] for n in sys.modules})\n"
        "print(json.dumps({'propios': propios, 'terceros': terceros,\n"
        "                  'archivos': {n: sys.modules[n].__file__ for n in propios}}))\n"
    ) % (str(ML_ENGINE), str(ML_ENGINE))

    salida = subprocess.run(
        [sys.executable, "-c", guion],
        capture_output=True, text=True, cwd=str(ML_ENGINE),
    )
    if salida.returncode != 0:
        raise AssertionError(f"la API no importa en frio:\n{salida.stderr}")
    return json.loads(salida.stdout.strip().splitlines()[-1])


# -- el contenido cubre lo que la API importa ----------------------------------------


def test_el_space_lleva_todos_los_modulos_que_la_api_importa():
    publicar = _cargar_publicar()
    cargado = _modulos_que_carga_la_api()

    empaquetados = {
        (RAIZ / origen).resolve() for origen, _ in publicar.CONTENIDO
    }

    faltantes = []
    for nombre, archivo in cargado["archivos"].items():
        ruta = Path(archivo).resolve()
        # Los `__init__.py` de paquetes implicitos no son archivos reales del repo.
        if not ruta.exists():
            continue
        if ruta not in empaquetados:
            faltantes.append(f"{nombre} ({ruta.relative_to(RAIZ).as_posix()})")

    assert not faltantes, (
        "la API importa modulos que publicar.py NO copia al Space; el contenedor "
        "arrancaria y moriria con ImportError:\n  " + "\n  ".join(faltantes)
    )


def test_la_api_no_arrastra_ninguna_dependencia_pesada():
    """
    Si esto falla, alguien importó pandas o scikit-learn desde la API. En desarrollo no se
    nota porque están instalados; en el contenedor de producción no están.
    """
    cargado = _modulos_que_carga_la_api()
    encontrados = sorted(PESADOS.intersection(cargado["terceros"]))
    assert not encontrados, f"la API importa dependencias que no van al contenedor: {encontrados}"


def test_los_terceros_que_la_api_usa_estan_en_requirements_de_produccion():
    requisitos = (ML_ENGINE / "requirements.txt").read_text(encoding="utf-8")
    declarados = {
        linea.split("~=")[0].split("==")[0].strip().lower()
        for linea in requisitos.splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    }
    # Nombre de import -> nombre de paquete, cuando no coinciden.
    usados = {"fastapi", "pydantic", "numpy", "onnxruntime"}
    faltantes = sorted(u for u in usados if u not in declarados)
    assert not faltantes, f"la API usa paquetes no declarados en requirements.txt: {faltantes}"


# -- el contenido es completo y coherente ---------------------------------------------


def test_todos_los_origenes_declarados_existen():
    publicar = _cargar_publicar()
    faltantes = [o for o, _ in publicar.CONTENIDO if not (RAIZ / o).exists()]
    assert not faltantes, f"publicar.py declara archivos que no existen: {faltantes}"


def test_el_par_del_modelo_viaja_completo():
    """Un .onnx sin su sidecar es inservible: no dice el orden de las columnas ni el umbral."""
    publicar = _cargar_publicar()
    destinos = {d for _, d in publicar.CONTENIDO}
    assert "models/zaha_baseline.onnx" in destinos
    assert "models/zaha_baseline.metadata.json" in destinos


def test_el_space_no_lleva_datos_ni_notebooks():
    publicar = _cargar_publicar()
    prohibidos = (".ipynb", ".parquet", ".csv", ".xls")
    coladas = [
        o for o, _ in publicar.CONTENIDO
        if o.endswith(prohibidos) or "/data/" in o or "/notebooks/" in o
    ]
    assert not coladas, f"se colaron datos o notebooks al Space: {coladas}"


def test_no_se_empaquetan_las_dependencias_de_desarrollo():
    publicar = _cargar_publicar()
    origenes = {o for o, _ in publicar.CONTENIDO}
    assert "ml_engine/requirements.txt" in origenes
    assert "ml_engine/requirements-dev.txt" not in origenes


def test_el_dockerfile_declara_el_puerto_que_el_space_espera():
    publicar = _cargar_publicar()
    dockerfile = (RAIZ / "deploy" / "hf_space" / "Dockerfile").read_text(encoding="utf-8")
    tarjeta = (RAIZ / "deploy" / "hf_space" / "README.md").read_text(encoding="utf-8")

    assert "7860" in dockerfile
    assert "app_port: 7860" in tarjeta
    assert "sdk: docker" in tarjeta
    del publicar


def test_la_tarjeta_declara_que_no_es_un_dispositivo_medico():
    """
    Es un prototipo academico publicado en una plataforma publica. Que no esta autorizado
    por ANMAT tiene que estar escrito donde se lee primero, no en un anexo.
    """
    tarjeta = (RAIZ / "deploy" / "hf_space" / "README.md").read_text(encoding="utf-8")
    assert "no es un dispositivo médico" in tarjeta.lower()
    assert "ANMAT" in tarjeta
    assert "no está demostrada" in tarjeta


# -- el contenido armado funciona --------------------------------------------------------


def test_lo_armado_reproduce_la_estructura_que_espera_el_dockerfile():
    publicar = _cargar_publicar()
    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp)
        publicar.armar(destino)

        for esperado in ("Dockerfile", "README.md", "requirements.txt",
                         "src/__init__.py", "src/api/main.py", "src/rangos.py",
                         "models/zaha_baseline.onnx"):
            assert (destino / esperado).exists(), f"falta {esperado} en lo armado"


def test_la_api_arranca_desde_el_directorio_armado():
    """
    La verificación de verdad: importar la API desde el árbol que se va a copiar al
    contenedor, no desde el repo. Es lo más cerca de construir la imagen que se puede
    llegar sin un demonio de Docker.
    """
    publicar = _cargar_publicar()
    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp)
        publicar.armar(destino)

        salida = subprocess.run(
            [sys.executable, "-c",
             "import src.api.modelo as m; "
             "mod = m.Modelo(); "
             "p = mod.predecir({'frecuencia_respiratoria': 26, 'spo2': 91, "
             "'temperatura': 38.4, 'presion_sistolica': 96, "
             "'frecuencia_cardiaca': 122, 'confusion': 1, 'edad': 81}, 0.70); "
             "assert p.explicacion.reconstruye_la_probabilidad; "
             "print('OK', round(p.probabilidad, 6))"],
            capture_output=True, text=True, cwd=str(destino),
        )
        assert salida.returncode == 0, (
            f"la API no corre desde el arbol armado:\n{salida.stderr}"
        )
        assert "OK" in salida.stdout


PRUEBAS = [
    test_el_space_lleva_todos_los_modulos_que_la_api_importa,
    test_la_api_no_arrastra_ninguna_dependencia_pesada,
    test_los_terceros_que_la_api_usa_estan_en_requirements_de_produccion,
    test_todos_los_origenes_declarados_existen,
    test_el_par_del_modelo_viaja_completo,
    test_el_space_no_lleva_datos_ni_notebooks,
    test_no_se_empaquetan_las_dependencias_de_desarrollo,
    test_el_dockerfile_declara_el_puerto_que_el_space_espera,
    test_la_tarjeta_declara_que_no_es_un_dispositivo_medico,
    test_lo_armado_reproduce_la_estructura_que_espera_el_dockerfile,
    test_la_api_arranca_desde_el_directorio_armado,
]


if __name__ == "__main__":
    fallos = []
    for prueba in PRUEBAS:
        try:
            prueba()
        except AssertionError as e:
            fallos.append(f"{prueba.__name__}: {e}")

    if fallos:
        print(f"FALLARON {len(fallos)} de {len(PRUEBAS)}:")
        for f in fallos:
            print("  -", f)
        raise SystemExit(1)
    print(f"OK: {len(PRUEBAS)} pruebas del contenido del Space")
