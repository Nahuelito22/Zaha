"""
Compone la figura de gestion del Sprint 5 a partir de los datos reales de Jira.

POR QUE COMPUESTA Y NO CAPTURA DE PANTALLA
Las dos razones del Sprint 4 siguen valiendo —la vista de busqueda de Jira no entra
completa en una captura y Chrome headless no genera el PNG en este entorno— y se suma una
tercera, propia de este sprint: **el Sprint 5 estuvo en estado `future` hasta el final**,
y el backlog de Jira esconde los items en Done, asi que la pantalla lo muestra con "0 work
items" aunque sus nueve items esten ahi y cerrados. Una captura del tablero no mostraria
el trabajo.

LOS DATOS SON REALES Y LA FIGURA LO DICE
Las nueve filas salen de `sprint = 7` en el proyecto SCRUM, leidas por la API el
15/10/2026. El pie declara el origen y la fecha: una tabla compuesta que se hiciera pasar
por una captura de pantalla seria peor que no tener figura.

Reusa el layout de `figura_sprint4.py` en vez de copiarlo: si se ajusta el estilo de una
tabla, se ajustan las dos.

Uso:  python scripts/figura_sprint5.py
Salida: 28_jira_sprint5.png en el directorio actual.
"""
from figura_sprint4 import _tabla, GRIS_FONDO, VERDE, VERDE_FONDO  # noqa: F401

FECHA_LECTURA = "15 de octubre de 2026"

# Leido de Jira el 15/10/2026 con `sprint = 7`. Orden: por clave, como en el tablero.
# (clave, titulo, tipo, responsable, prioridad, estado, puntos)
ITEMS = [
    ("SCRUM-61", "HU-04 — Interfaz de Alertas Explicables y Flujo One-Click",
     "Historia", "Gustavo Garcia", "High", "Done", 5),
    ("SCRUM-62", "API REST con FastAPI sirviendo el modelo con onnxruntime",
     "Tarea", "matiasghilardisalinas", "High", "Done", 8),
    ("SCRUM-63", "Desplegar la API en Hugging Face Spaces",
     "Tarea", "matiasghilardisalinas", "High", "Done", 8),
    ("SCRUM-64", "Edge Function de Supabase que envía el historial del paciente a la API",
     "Tarea", "matiasghilardisalinas", "Medium", "Done", 5),
    ("SCRUM-65", "Degradación elegante: si el Space duerme, NEWS2 sigue funcionando",
     "Tarea", "matiasghilardisalinas", "Highest", "Done", 5),
    ("SCRUM-66", "Explicabilidad de la predicción: contribución por parámetro",
     "Tarea", "matiasghilardisalinas", "High", "Done", 5),
    ("SCRUM-67", "Mostrar la predicción en /app separada visualmente del score determinístico",
     "Tarea", "Gustavo Garcia", "High", "Done", 5),
    ("SCRUM-68", "Flujo One-Click: validar / posponer alerta con registro del acuse",
     "Tarea", "Gustavo Garcia", "High", "Done", 8),
    ("SCRUM-73", "Encuadre SaMD y disposición ANMAT 9688/19",
     "Tarea", "Gustavo Garcia", "Medium", "Done", 5),
]


def figura_sprint():
    puntos = sum(i[6] for i in ITEMS)

    columnas = [("Clave", 0.035, "left"), ("Trabajo", 0.145, "left"),
                ("Responsable", 0.655, "left"), ("Prioridad", 0.815, "left"),
                ("Estado", 0.888, "left"), ("Puntos", 0.965, "right")]

    def fila(it):
        clave, titulo, tipo, resp, prio, estado, pts = it
        return {"tipo": "item", "celdas": [
            ("doble", clave, tipo), titulo, resp, prio,
            ("badge", estado, VERDE_FONDO, VERDE),
            str(pts),
        ]}

    filas = [{"tipo": "grupo",
              "texto": f"Completado — {len(ITEMS)} ítems, {puntos} puntos"}]
    filas += [fila(i) for i in ITEMS]
    filas.append({"tipo": "total", "texto": "Completado sobre comprometido",
                  "valor": f"{puntos} / {puntos}"})

    _tabla("28_jira_sprint5.png", "Sprint 5 — Integración IA",
           "13 de octubre al 2 de noviembre de 2026 · 9 ítems de trabajo · "
           "54 puntos de historia",
           columnas, filas,
           f"Datos del proyecto SCRUM en Jira, sprint «Sprint 5 — Integración IA», leídos "
           f"el {FECHA_LECTURA}. Tabla compuesta a partir de esos datos: el tablero de "
           f"Jira oculta los ítems cerrados, así que una captura de pantalla\nmostraría "
           f"este sprint vacío. Los nueve ítems quedaron cerrados: el alcance comprometido se "
           f"completó el 15 de octubre, al tercer día de la ventana.")


if __name__ == "__main__":
    figura_sprint()
