# Intro de la landing — guion para Motion

Animación de entrada de `app/landing` (SCRUM-84). Lo primero que ve quien abre el sitio
en la exposición. **La reproduce el scroll, no un temporizador**: el video no tiene que
"durar bien" en tiempo real, tiene que verse bien cuadro por cuadro en cualquier punto
donde el visitante frene.

## Material de partida

| Archivo | Para qué |
|---|---|
| `Zaha_Solo_Z_Sin_Fondo.png` | El objeto que se anima. Z tallada, PNG con transparencia. |
| `Zaha.png` | Referencia de marca: los 5 símbolos con su nombre, la textura de piedra, la roca. |

Los dos en `Desktop\...\Practicas_Profesionales_3\Enfermeria\Logos\`.

## Brief (para pegar en `create_video`)

**Goal.** A 6-second brand intro for Zaha, a clinical decision-support app for nurses
built in Mendoza, Argentina. It is the first thing a visitor sees on the landing page;
playback is driven by the visitor's scroll, so every frame must hold up as a still.

**The story, in three beats.**

1. **0–2 s · The stone.** A warm, flat cream background (`#f5ead8`). Fine grain of sandstone
   comes into focus. The Z is carved into it: the outline appears first as a thin incised
   line, then the relief deepens into the brown stone texture of the reference
   (`#8c491a` to `#5a3a22`). Soft raking light from the upper left, like late afternoon sun
   on rock.
2. **2–4 s · What it carries.** The five symbols inside the Z light up one by one with a
   warm, subtle glow — no particles, no sparkles — in this order:
   spiral path (Caminos de la vida) → heart with spiral (Corazón · Cuidado) →
   sun (Conexión · Energía) → stepped mark (Tierra · Origen) → the two dots
   (Equilibrio · Armonía). Each glow settles back into the stone before the next one starts.
3. **4–6 s · Settle.** The camera eases back slightly, the light evens out, and the Z rests
   centered on the cream background, fully lit, perfectly still for the last 0.8 s.
   **The last frame must be a clean, static, centered Z on flat `#f5ead8`** — the page
   takes over from that exact frame.

**Tone.** Ancestral, calm, crafted. Andean / pre-Columbian stone carving. Warm earth
palette only: cream `#f5ead8`, terracotta `#c67139`, deep brown `#8c491a`, sand `#d9c7a8`,
sage `#7a8a5e` (sparingly).

**Camera.** Locked or very slow push. One continuous shot. No cuts.

**Do not include.**
- Any text, letters other than the Z, numbers, captions or logos other than the Z.
- Red, amber, bright orange or green glows: in this product those colors mean clinical
  risk levels and must never appear as decoration.
- Medical clichés: heartbeat lines, crosses, stethoscopes, hospital imagery.
- Particles, lens flares, sparkles, 3D spinning of the Z, morphing of its shape.
- Music or sound (the page plays it muted).

**Format.** Two renders of the same brief:
- 16:9, 1920×1080 — desktop and the projector at the exhibition.
- 9:16, 1080×1920 — phones. The Z centered with more vertical air; same beats.

## Después del render (lo hace Claude, no Motion)

1. Recodificar para scroll: H.264, sin audio, `-g 8` en escritorio y `-g 4` en el
   vertical, `+faststart`, `crf ~22`. Objetivo: **menos de 3 MB** cada uno.
2. Extraer el primer y el último cuadro como imágenes de póster.
3. Verificar que el último cuadro empalme con la página (mismo crema, Z centrada).

Requiere `ffmpeg`, que hoy no está instalado.
