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

CÓMO ARRANCA ESTO EN UN SPACE
Hugging Face ejecuta `python app.py` como script. Se nota en el ejemplo oficial de la
documentación, que cierra con `if __name__ == "__main__": gradio_app.launch()`: si HF
importara el módulo en vez de ejecutarlo, ese guard nunca se cumpliría y la aplicación no
levantaría nunca. Como lo ejecuta, alcanza con que algo quede escuchando en el 7860, y eso
lo puede hacer uvicorn directamente.

LA PANTALLA NO ES DECORACIÓN
La demostración sirve para dos cosas concretas. Primero, es lo que la cátedra puede abrir
y usar sin instalar nada. Segundo, y más importante: muestra **la explicación**, que es lo
que separa a este sistema de una calculadora. Un número suelto no se puede discutir; una
lista de contribuciones por parámetro, sí.

La pantalla declara lo mismo que la tarjeta: que esto no es un dispositivo médico y que la
reducción de alertas frente a NEWS2 todavía no está demostrada.
"""

from __future__ import annotations

import gradio as gr
import uvicorn

from src.api.main import app as api
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


# La demostración va en la raíz porque es lo que Hugging Face muestra en la pestaña App.
# La API queda disponible en /salud, /modelo, /prediccion y /docs, igual que siempre.
app = gr.mount_gradio_app(api, demo, path="/")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PUERTO)
