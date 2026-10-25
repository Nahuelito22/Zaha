# app/landing — el sitio público

Astro 6 + Tailwind 4, servido en la raíz de [zahasalud.com.ar](https://zahasalud.com.ar).

## Correrlo

```bash
npm ci
npm run dev        # http://localhost:4321
npm run build      # -> dist/
```

En desarrollo, `/api/motor/*` se redirige al Space de Hugging Face (`astro.config.mjs`). En
producción lo hace la regla de `vercel.json` de la raíz.

## Páginas

| Ruta | Archivo | Qué es |
|---|---|---|
| `/` | `src/pages/index.astro` | La landing: intro de la Z tallada, el producto, la tecnología y la demo del motor |
| `/manual` | `src/pages/manual.astro` | El manual de uso para enfermería, ilustrado con capturas de la app |

`src/components/DemoMotor.astro` es el formulario "Probá la estimación", que le pega al
motor de IA real.

## La intro

La Z de la marca se enciende símbolo por símbolo, cada uno con su lema, y al final vuela al
ícono de la barra.

- **Con mouse** avanza con el scroll.
- **En pantallas táctiles** avanza con un botón *Continuar*, un pulso por toque: el scroll
  con inercia del teléfono se pasaba de largo.
- `?pasos` fuerza el modo con botón y `?animar` fuerza la animación aunque el sistema pida
  reducir el movimiento. Los dos sirven para presentar desde una máquina ajena.

Los moldes de cada símbolo salen de `scripts/vectorizar_z.py`, y el favicon y la imagen para
redes de `scripts/generar_marca_web.py`.
