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

## Cómo se corren

Ambos escriben en `C:\Users\matia\Desktop\Zaha_Graficos\`, que es la carpeta desde la que
las imágenes se suben a Drive.

```bash
# los tres burndowns, o sólo uno pasándole el nombre del archivo
python scripts/burndown.py
python scripts/burndown.py burndown_sprint3.png

# la figura de la etiqueta; necesita el parquet ya generado
cd ml_engine && python -m src.data.mimic_ed && python -m src.data.etiquetas
python scripts/figura_etiqueta.py
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
