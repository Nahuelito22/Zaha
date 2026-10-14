"""
Punto de entrada del Space de Hugging Face (SCRUM-63).

POR QUÉ ESTE ARCHIVO EXISTE, SI YA HABÍA UN Dockerfile
El plan era una Space con SDK Docker. **Hugging Face pasó Docker Spaces a plan pago**:
en el formulario de creación la opción aparece en gris con la etiqueta "Paid", incluso en
una cuenta que ya tiene Spaces Docker de antes —las viejas quedaron heredadas, las nuevas
no se pueden crear—. Los SDK gratuitos son Gradio y Static; Static no corre Python.

Así que el Space usa el SDK de Gradio y **este archivo monta la misma API de FastAPI**,
sin tocar una línea de `src/api/main.py`. La Space de Gradio no reemplaza a la API: la
contiene.

CÓMO ARRANCA ESTO EN UN SPACE, Y POR QUÉ `demo` VIVE DENTRO DE UNA FUNCIÓN
Esto costó un despliegue fallido, así que conviene dejarlo escrito.

El runtime de Gradio **inspecciona el módulo buscando un objeto `Blocks`**. Si lo
encuentra a nivel de módulo, levanta su propio servidor en el 7860. Con `demo` global,
el Space arrancaba dos servidores y el segundo moría con:

    ERROR: [Errno 98] error while attempting to bind on address ('0.0.0.0', 7860)

Por eso la pantalla se construye **dentro de `crear_app()`** y lo único que queda a nivel
de módulo es `app`, la FastAPI con Gradio ya montado. Así hay un solo servidor, lo levante
quien lo levante: si HF importa el módulo, sirve `app`; si lo ejecuta como script, lo
sirve el uvicorn de abajo.

El puerto sale de `PORT` si está definido, que es lo que hacen los Spaces que funcionan
con este patrón.

LA PANTALLA NO ES DECORACIÓN
La demostración sirve para dos cosas concretas. Primero, es lo que la cátedra puede abrir
y usar sin instalar nada. Segundo, y más importante: muestra **la explicación**, que es lo
que separa a este sistema de una calculadora. Un número suelto no se puede discutir; una
lista de contribuciones por parámetro, sí.

La pantalla declara lo mismo que la tarjeta: que esto no es un dispositivo médico y que la
reducción de alertas frente a NEWS2 todavía no está demostrada.
"""

from __future__ import annotations

import os

# `spaces` se importa ANTES que gradio, como pide la documentación de ZeroGPU. Fuera de un
# Space el paquete no existe, y eso es normal: lo instala Hugging Face.
try:
    import spaces
except ImportError:
    spaces = None

import gradio as gr

from src.api.main import app as api, cargar_modelo
from src.api.modelo import Modelo

PUERTO = 7860

# Se carga una vez, igual que en la API. Si falla, la pantalla lo dice en vez de romper:
# el Space tiene que poder arrancar para que `/salud` explique qué pasó.
try:
    MODELO: Modelo | None = Modelo()
    ERROR_DE_CARGA = ""
except Exception as exc:  # noqa: BLE001
    MODELO = None
    ERROR_DE_CARGA = f"{type(exc).__name__}: {exc}"


if spaces is not None:

    @spaces.GPU(duration=1)
    def _requisito_de_zerogpu() -> None:
        """
        Existe para que el Space arranque. No se llama nunca, y no debe llamarse.

        POR QUÉ HAY UNA FUNCIÓN DE GPU EN UN SERVICIO QUE NO USA GPU
        En el plan gratuito de Hugging Face **no hay alternativa**: Docker Spaces es de
        pago, `cpu-basic` es de pago, Static no corre Python, y los Spaces de Gradio
        gratuitos corren obligatoriamente en ZeroGPU. ZeroGPU, a su vez, verifica al
        arrancar que exista al menos una función decorada con `@spaces.GPU`, y si no la
        encuentra mata el contenedor con:

            No @spaces.GPU function detected during startup

        Eso tumbó el Space anterior. Esta función es la respuesta a esa verificación y
        nada más.

        **No se invoca a propósito.** Llamarla pediría una A10G de verdad y consumiría
        cuota de GPU para calcular un producto punto entre siete números. El modelo es una
        regresión logística de 864 bytes que corre en onnxruntime sobre la CPU del propio
        host de ZeroGPU, que es lo que queremos.

        Si algún día el proyecto tiene PRO, el camino correcto es pasar el Space a
        `cpu-basic` y borrar esto junto con el import de `spaces`.
        """
        raise RuntimeError(
            "esta funcion no debe ejecutarse: existe solo para la verificacion de arranque "
            "de ZeroGPU. Si aparece en un traceback, alguien la llamo por error."
        )


ENCABEZADO = """
# Zaha — estimación de deterioro clínico

Prototipo académico de un sistema de soporte a la decisión clínica para enfermería.

> **No es un dispositivo médico.** No está autorizado por ANMAT ni por ninguna autoridad
> regulatoria, y no debe usarse para decidir sobre personas reales.

Esta pantalla es una demostración. La interfaz real es la aplicación clínica; acá abajo
está la misma API que ella consume, documentada en **`/docs`**.
"""


def estimar(
    frecuencia_respiratoria: float,
    spo2: float,
    temperatura: float,
    presion_sistolica: float,
    frecuencia_cardiaca: float,
    confusion_nueva: bool,
    edad: float,
    sensibilidad: float,
):
    """Devuelve (resumen en markdown, tabla de contribuciones)."""
    if MODELO is None:
        return f"**El modelo no cargó.** {ERROR_DE_CARGA}", []

    valores = {
        "frecuencia_respiratoria": frecuencia_respiratoria,
        "spo2": spo2,
        "temperatura": temperatura,
        "presion_sistolica": presion_sistolica,
        "frecuencia_cardiaca": frecuencia_cardiaca,
        "confusion": 1 if confusion_nueva else 0,
        "edad": edad,
    }

    try:
        p = MODELO.predecir(valores, sensibilidad)
    except Exception as exc:  # noqa: BLE001
        return f"**No se pudo estimar.** {exc}", []

    punto = p.punto
    veredicto = "ALERTA" if p.alerta else "sin alerta"
    resumen = (
        f"### {veredicto} — probabilidad estimada {p.probabilidad:.3f}\n\n"
        f"- Punto de operación: sensibilidad objetivo **{punto.sensibilidad_objetivo:.0%}**, "
        f"umbral **{punto.umbral:.3f}**\n"
        f"- Tasa de alertas esperada con ese umbral: "
        f"**{punto.tasa_de_alertas_esperada:.1%}**\n\n"
        f"_{MODELO.metadatos.get('advertencia', '')}_"
    )

    filas = []
    if p.explicacion and p.explicacion.reconstruye_la_probabilidad:
        filas = [
            [c.parametro, c.valor, round(c.contribucion, 4), c.direccion]
            for c in p.explicacion.contribuciones
        ]

    return resumen, filas


def crear_demo() -> gr.Blocks:
    """
    Arma la pantalla de demostración.

    **`demo` no puede salir de esta función.** Un `Blocks` a nivel de módulo hace que
    el runtime de Gradio levante un segundo servidor y el Space muera con «address
    already in use».
    """

    with gr.Blocks(title="Zaha — estimación de deterioro clínico") as demo:
        gr.Markdown(ENCABEZADO)

        with gr.Row():
            with gr.Column():
                fr = gr.Number(label="Frecuencia respiratoria (rpm)", value=20, minimum=0, maximum=80)
                sat = gr.Number(label="Saturación de oxígeno (%)", value=96, minimum=50, maximum=100)
                temp = gr.Number(label="Temperatura (°C)", value=36.6, minimum=25, maximum=45)
                pas = gr.Number(label="Presión sistólica (mmHg)", value=130, minimum=30, maximum=300)
                fc = gr.Number(label="Frecuencia cardíaca (lpm)", value=78, minimum=0, maximum=300)
                conf = gr.Checkbox(
                    label="Confusión NUEVA (la «C» de ACVPU)",
                    info="Confusión de aparición reciente, no un deterioro cognitivo previo.",
                )
                edad = gr.Number(label="Edad (años)", value=65, minimum=0, maximum=120)
                sens = gr.Radio(
                    label="Sensibilidad objetivo",
                    info="Elegir el punto de operación es una decisión clínica: define cuántas alertas por turno recibe la guardia.",
                    choices=[0.5, 0.6, 0.7, 0.8],
                    value=0.7,
                )
                boton = gr.Button("Estimar", variant="primary")

            with gr.Column():
                salida = gr.Markdown()
                tabla = gr.Dataframe(
                    headers=["parámetro", "valor", "contribución (log-odds)", "dirección"],
                    label="De dónde sale la estimación, de mayor a menor influencia",
                    interactive=False,
                )

        gr.Markdown(
            "La descomposición es **exacta**, no una aproximación: el modelo es una regresión "
            "logística, así que las contribuciones suman el logit por identidad algebraica. "
            "Si alguna vez no reconstruyeran la probabilidad servida, la tabla aparece vacía "
            "en lugar de mostrar una explicación que no describe al modelo."
        )

        boton.click(
            estimar,
            inputs=[fr, sat, temp, pas, fc, conf, edad, sens],
            outputs=[salida, tabla],
        )

    return demo

# QUIEN LEVANTA EL SERVIDOR: GRADIO, NO NOSOTROS. Y NO ES UN DETALLE.
# Costo cinco despliegues, asi que queda escrito entero.
#
# En el plan gratuito de Hugging Face los Spaces de Gradio corren OBLIGATORIAMENTE en
# ZeroGPU: Docker es de pago, `cpu-basic` es de pago, y Static no corre Python. Y ZeroGPU
# verifica al arrancar que exista una funcion decorada con `@spaces.GPU`; si no la
# encuentra, mata el contenedor con
#
#     No @spaces.GPU function detected during startup
#
# Esa verificacion se dispara desde `demo.launch()`. Mientras serviamos la FastAPI con
# uvicorn propio --via `gr.mount_gradio_app`-- la funcion decorada ESTABA DEFINIDA y aun
# asi el Space moria: el camino de arranque de Gradio nunca se recorria, asi que nadie la
# registraba. Se comprobo desplegando un Space de Gradio minimo con la misma funcion, que
# arranco y quedo en RUNNING.
#
# Entonces se invierte el montaje: Gradio es el servidor y nuestra API se monta DENTRO,
# bajo /api. `launch()` ademas resuelve solo el puerto, el host y el root_path del Space,
# que es justo lo que antes haciamos a mano y mal.
#
# CONSECUENCIA EN LAS RUTAS: la API queda en /api/salud, /api/prediccion, /api/modelo y
# /api/docs. La raiz es la pantalla. El secreto ZAHA_API_URL de Supabase tiene que incluir
# el /api final.
def main() -> None:
    # Starlette NO ejecuta el ciclo de vida de una aplicacion montada, asi que el modelo
    # se carga a mano. Sin esto /api/salud responderia "degradado" para siempre.
    cargar_modelo()

    demo = crear_demo()

    # ssr_mode=False: Gradio 6 activa el renderizado del lado del servidor al detectar un
    # Space, y eso levanta un servidor Node en el mismo puerto. Con el montaje anterior
    # eso tumbaba el arranque; se deja apagado porque no aporta nada a un formulario.
    app, _, _ = demo.launch(
        prevent_thread_lock=True,
        ssr_mode=False,
    )

    app.mount("/api", api)
    print("[zaha] API montada en /api", flush=True)

    # launch(prevent_thread_lock=True) devuelve enseguida; sin esto el proceso termina y
    # el contenedor se apaga.
    demo.block_thread()


if __name__ == "__main__":
    main()
