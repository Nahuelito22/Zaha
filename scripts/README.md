# scripts

Generadores de las figuras que van a la documentación académica del Padlet. Producen
imágenes a partir de datos reales del proyecto, no capturas de pantalla, para que se lean
bien impresas y para poder regenerarlas cuando los números cambian.

Vivían en `ayudas_y_recursos/`, que está gitignoreada, así que no se versionaban: si esa
carpeta se borraba había que rehacerlos. Por eso están acá.

| Script | Qué produce |
|---|---|
| `burndown.py` | el burndown de cada sprint |
| `figura_etiqueta.py` | la distribución de las tomas respecto del desenlace adverso (SCRUM-53) |
| `figura_sprint4.py` | estado del Sprint 4 y su trabajo no completado, desde Jira |
| `figura_sprint5.py` | estado del Sprint 5, desde Jira |
| `figura_auditoria.py` | la cadena de hashes de `alert_audit_log`, desde la base |

`figura_sprint4.py` es además **la casa del layout de tablas**: las otras dos importan su
`_tabla`. Si hay que ajustar el estilo de una tabla, se ajusta ahí y cambian todas.

## Cómo se corren

**Todos escriben en el directorio actual**, no en una ruta fija: hay que pararse donde se
quiera la salida antes de correrlos. Los burndown y las figuras de resultados van a
`Desktop\Zaha_Graficos\`; las figuras numeradas de una entrega van a la carpeta de esa
entrega, porque el número de figura es propio de la entrega y no del generador.

```bash
# todos los burndowns, o sólo uno pasándole el nombre del archivo
cd ~/Desktop/Zaha_Graficos && python <repo>/scripts/burndown.py
python <repo>/scripts/burndown.py burndown_sprint5.png

# las tablas compuestas, desde la carpeta de la entrega.
# PYTHONPATH hace falta porque importan de figura_sprint4.
cd ~/Desktop/Zaha_Entrega_02-11
PYTHONPATH=<repo>/scripts python <repo>/scripts/figura_sprint5.py
PYTHONPATH=<repo>/scripts python <repo>/scripts/figura_auditoria.py

# la figura de la etiqueta; necesita el parquet ya generado
cd ml_engine && python -m src.data.mimic_ed && python -m src.data.etiquetas
python <repo>/scripts/figura_etiqueta.py
```

## Dos cosas a tener en cuenta

**Las curvas de los burndown son inventadas, pero no arbitrarias.** El día a día de un
sprint no existe en Jira —los sprints se cargaron de forma retroactiva—, así que la curva
se construye a mano. Lo que la hace defendible es que está anclada al historial real de
git y al estado del tablero: el desplome del Sprint 2 el 10/09 son los cuatro PR de ese
día, y el Sprint 3 cierra en 0 porque las tareas bloqueadas por PhysioNet se movieron al
Sprint 4. Si se cambia el alcance de un sprint, hay que regenerar su gráfico.

**La paleta no se elige por gusto.** La línea real va en el terracota de la marca
(`#c67139`) y la ideal en gris punteado. **No usar el oliva `#7a8a5e` como segunda serie:**
el par terracota + oliva falla el control de daltonismo (ΔE 4.8 en protanopia, y 12.8 en
visión normal, por debajo del piso de 15). El gris punteado además es la convención del
burndown.
