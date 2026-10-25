# app/clinical — la aplicación de enfermería

PWA en React 19 + Vite + TypeScript, servida en `zahasalud.com.ar/app`. Es lo que se usa al
pie de la cama: la sala ordenada por riesgo, la carga de signos vitales, el detalle de cada
paciente con sus alertas y la estimación del modelo.

Cómo se usa, pantalla por pantalla: [`MANUAL_ENFERMERIA.md`](MANUAL_ENFERMERIA.md), o la
versión ilustrada en [zahasalud.com.ar/manual](https://zahasalud.com.ar/manual).

## Correrla

```bash
cp .env.example .env.local      # URL de Supabase y clave publicable
npm ci
npm run dev                     # http://localhost:5173/app/
npm run build                   # tsc + vite build -> dist/
npm run lint                    # oxlint
node --test src/lib/*.test.ts   # pruebas (node:test, no Vitest)
```

La clave publicable no es un secreto: quien decide qué se ve son las políticas RLS de la
base. La clave de servicio no va nunca acá.

## Qué hay

| Ruta | Qué es |
|---|---|
| `src/paginas/Login.tsx` | Ingreso. Única pantalla con la paleta de marca |
| `src/paginas/Sala.tsx` | La sala: internaciones activas con su última toma, ordenadas por riesgo, en vivo |
| `src/paginas/CargarVitales.tsx` | Carga de los 7 parámetros con confirmación |
| `src/paginas/EnmendarToma.tsx` | Corrección de una toma con una enmienda |
| `src/paginas/DetallePaciente.tsx` | Puntaje vigente, aporte de cada parámetro, estimación, alertas e historial |
| `src/componentes/` | Alertas, estimación del modelo, cola offline, chip de riesgo, campos de la carga |
| `src/lib/cola.ts` | Cola offline en IndexedDB (Dexie), idempotente por `id` generado en el cliente |
| `src/lib/enmienda.ts`, `alertas.ts`, `prediccion.ts` | Lógica pura, con sus pruebas |

## Tres reglas que gobiernan el código

1. **La pantalla nunca calcula NEWS2.** Lo calcula la base con un trigger y se lee de vuelta.
   Sin conexión, la toma queda guardada y "sin puntaje".
2. **Nada se edita ni se borra.** Corregir es una enmienda, que queda visible junto al
   original.
3. **La estimación del modelo nunca parece la escala.** Va en violeta punteado, fuera de los
   colores de riesgo, que están reservados a los cuatro niveles de NEWS2.

Los estilos salen de `design_system/clinical.css` (capa clínica, neutra). El login usa la
capa de marca (`brand.css`). Ver [`design_system/README.md`](../../design_system/README.md).
