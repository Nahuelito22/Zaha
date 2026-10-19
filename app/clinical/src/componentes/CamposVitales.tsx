import {
  CAMPOS_NUMERICOS,
  OPCIONES_ACVPU,
  RANGOS,
  fueraDeRango,
  type ACVPU,
  type CampoNumerico,
} from '../lib/tipos'

/**
 * Los 7 parámetros de NEWS2, tal como se cargan.
 *
 * Lo comparten la carga de una toma y su corrección: si la enmienda tuviera su
 * propio formulario, los rangos o el orden podrían divergir, y corregir un dato
 * se volvería distinto de cargarlo.
 */
export function CamposVitales({
  valores,
  onValor,
  oxigeno,
  onOxigeno,
  acvpu,
  onAcvpu,
}: {
  valores: Record<CampoNumerico, string>
  onValor: (campo: CampoNumerico, valor: string) => void
  oxigeno: boolean
  onOxigeno: (v: boolean) => void
  acvpu: ACVPU | null
  onAcvpu: (v: ACVPU | null) => void
}) {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2">
        {CAMPOS_NUMERICOS.map((campo) => {
          const r = RANGOS[campo]
          const malo = fueraDeRango(campo, valores[campo])
          return (
            <label key={campo} className="flex flex-col gap-1.5">
              <span className="vital-label">
                {r.etiqueta} ({r.unidad})
              </span>
              <input
                className="cinput"
                type="number"
                inputMode="decimal"
                step={campo === 'temperature' ? '0.1' : '1'}
                value={valores[campo]}
                aria-invalid={malo}
                aria-describedby={malo ? `${campo}-error` : undefined}
                onChange={(e) => onValor(campo, e.target.value)}
                required
              />
              {malo && (
                <span id={`${campo}-error`} className="ctext-2xs font-semibold">
                  Fuera del rango posible ({r.min}–{r.max} {r.unidad}). Revisá el
                  valor cargado.
                </span>
              )}
            </label>
          )
        })}

        <fieldset className="flex flex-col gap-1.5">
          <legend className="vital-label">Oxígeno suplementario</legend>
          <div className="flex gap-2">
            <button
              type="button"
              className={`cbtn ${oxigeno ? 'cbtn-secondary' : 'cbtn-primary'} flex-1`}
              aria-pressed={!oxigeno}
              onClick={() => onOxigeno(false)}
            >
              Aire ambiente
            </button>
            <button
              type="button"
              className={`cbtn ${oxigeno ? 'cbtn-primary' : 'cbtn-secondary'} flex-1`}
              aria-pressed={oxigeno}
              onClick={() => onOxigeno(true)}
            >
              Con oxígeno
            </button>
          </div>
        </fieldset>
      </div>

      {/* DESPLEGABLE, NO CINCO BOTONES.
          Eran cinco destinos táctiles pegados en una grilla de dos columnas, y
          en un teléfono sostenido con una mano eso es una fuente de toques
          equivocados: se elige «Confusión nueva» cuando se quiso «Alerta», y
          ese error cambia el puntaje en 3 puntos y dispara una alerta. El
          desplegable obliga a un gesto deliberado, garantiza que haya una sola
          opción elegida, y de paso devuelve el ancho que ocupaban cinco
          botones. */}
      <label className="flex flex-col gap-1.5">
        <span className="vital-label">Nivel de consciencia (ACVPU)</span>
        <select
          className="cselect"
          value={acvpu ?? ''}
          onChange={(e) => onAcvpu((e.target.value || null) as ACVPU | null)}
          required
        >
          {/* La opción vacía existe para que «todavía no elegí» sea un estado
              representable. Sin ella el desplegable mostraría «Alerta» de
              entrada y un campo sin tocar parecería contestado. */}
          <option value="">Elegir nivel…</option>
          {OPCIONES_ACVPU.map((o) => (
            <option key={o.valor} value={o.valor}>
              {o.sigla} · {o.texto}
            </option>
          ))}
        </select>
      </label>
    </>
  )
}
