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
import re
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
# Lo que la API no debe importar. `gradio` SI esta instalado en el Space (el SDK lo
# exige) y arrastra pandas con el, pero `src.api.main` no puede depender de ninguno de los
# dos: la API tiene que seguir corriendo en un contenedor pelado, sin Gradio.
PESADOS = {"pandas", "sklearn", "torch", "pandera", "xgboost", "skl2onnx", "pyarrow",
           "polars", "matplotlib", "scipy", "xlrd", "httpx", "gradio"}


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
    # El nombre es lo que viene antes de cualquier especificador de version. No alcanza
    # con partir por `~=` y `==`: `pydantic` quedo con un rango `>=2.11,<2.13` por el
    # conflicto con gradio[mcp], y el parser viejo lo daba por ausente.
    declarados = {
        re.split(r"[<>=!~\[;]", linea.strip(), maxsplit=1)[0].strip().lower()
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


def test_la_tarjeta_y_el_punto_de_entrada_concuerdan():
    """
    El SDK es Gradio porque Docker Spaces paso a ser de pago. Si la tarjeta y `app.py` se
    separan --`app_file` apuntando a otro archivo, o el puerto cambiado en uno solo-- el
    Space construye bien y despues no levanta nada.
    """
    tarjeta = (RAIZ / "deploy" / "hf_space" / "README.md").read_text(encoding="utf-8")
    entrada = (RAIZ / "deploy" / "hf_space" / "app.py").read_text(encoding="utf-8")

    assert "sdk: gradio" in tarjeta
    assert "app_file: app.py" in tarjeta
    assert "sdk_version:" in tarjeta
    # El puerto ya no se fija a mano: `demo.launch()` lo resuelve con las variables que
    # pone el Space. Lo que si tiene que estar es la funcion que ZeroGPU exige.
    assert "@spaces.GPU" in entrada


def test_el_space_lleva_el_punto_de_entrada_y_no_el_dockerfile():
    publicar = _cargar_publicar()
    destinos = {d for _, d in publicar.CONTENIDO}
    assert "app.py" in destinos
    assert "Dockerfile" not in destinos, (
        "el SDK es Gradio: un Dockerfile en la raiz del Space solo confunde"
    )


def test_la_demostracion_monta_la_api_y_no_la_reimplementa():
    """
    La pantalla de Gradio tiene que servir LA MISMA API, no una copia. Si alguien
    reimplementara ahi el calculo, la demostracion y la aplicacion clinica podrian
    divergir sin que nada falle.
    """
    entrada = (RAIZ / "deploy" / "hf_space" / "app.py").read_text(encoding="utf-8")
    assert "from src.api.main import app" in entrada
    # Gradio es el servidor y la API se monta DENTRO, bajo /api. Es al reves de lo que
    # parece natural, y es obligatorio: ZeroGPU --unica opcion gratuita para Spaces de
    # Gradio-- registra la funcion @spaces.GPU desde `demo.launch()`. Con un uvicorn
    # propio esa verificacion no corre nunca y el Space muere al arrancar.
    assert "demo.launch(" in entrada
    assert 'app.mount("/api", api)' in entrada
    # Sin esto Gradio levanta un servidor Node en el mismo puerto.
    assert "ssr_mode=False" in entrada


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


def test_lo_armado_reproduce_la_estructura_que_espera_el_space():
    publicar = _cargar_publicar()
    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp)
        publicar.armar(destino)

        for esperado in ("app.py", "README.md", "requirements.txt",
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


def test_la_descripcion_corta_entra_en_el_limite_de_hugging_face():
    """
    Hugging Face rechaza el push si `short_description` pasa de 60 caracteres, y lo hace
    en un hook de pre-recepcion: el error aparece recien al empujar, no al construir.
    Ya costo un intento.
    """
    tarjeta = (RAIZ / "deploy" / "hf_space" / "README.md").read_text(encoding="utf-8")
    linea = next(
        l for l in tarjeta.splitlines() if l.startswith("short_description:")
    )
    descripcion = linea.split(":", 1)[1].strip()
    assert len(descripcion) <= 60, (
        f"son {len(descripcion)} caracteres y el limite es 60: {descripcion!r}"
    )

def test_la_pantalla_no_queda_a_nivel_de_modulo():
    """
    El runtime de Gradio inspecciona el modulo buscando un `Blocks`. Si lo encuentra a
    nivel de modulo levanta SU PROPIO servidor en el 7860, y el nuestro muere con
    "address already in use". Ya tumbo un despliegue.

    La pantalla tiene que construirse dentro de una funcion; a nivel de modulo solo puede
    quedar `app`.
    """
    entrada = (RAIZ / "deploy" / "hf_space" / "app.py").read_text(encoding="utf-8")
    sueltas = [
        l for l in entrada.splitlines()
        if l.strip().startswith(("with gr.Blocks", "demo = gr.Blocks", "demo = gr.Interface"))
        and not l.startswith((" ", "	"))
    ]
    assert not sueltas, (
        f"hay un Blocks de Gradio a nivel de modulo, movelo dentro de una "
        f"funcion: {sueltas}"
    )
    assert "def main()" in entrada

PRUEBAS = [
    test_el_space_lleva_todos_los_modulos_que_la_api_importa,
    test_la_api_no_arrastra_ninguna_dependencia_pesada,
    test_los_terceros_que_la_api_usa_estan_en_requirements_de_produccion,
    test_todos_los_origenes_declarados_existen,
    test_el_par_del_modelo_viaja_completo,
    test_el_space_no_lleva_datos_ni_notebooks,
    test_no_se_empaquetan_las_dependencias_de_desarrollo,
    test_la_tarjeta_y_el_punto_de_entrada_concuerdan,
    test_el_space_lleva_el_punto_de_entrada_y_no_el_dockerfile,
    test_la_demostracion_monta_la_api_y_no_la_reimplementa,
    test_la_pantalla_no_queda_a_nivel_de_modulo,
    test_la_tarjeta_declara_que_no_es_un_dispositivo_medico,
    test_la_descripcion_corta_entra_en_el_limite_de_hugging_face,
    test_lo_armado_reproduce_la_estructura_que_espera_el_space,
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
