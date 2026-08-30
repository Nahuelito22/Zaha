import { CLASE_RIESGO, type NivelRiesgo } from '../lib/tipos'

/**
 * Nivel de riesgo NEWS2.
 *
 * El glifo cambia de FORMA por nivel (círculo, rombo, triángulo, triángulo
 * relleno) además de color, y el texto del nivel siempre está presente. Un
 * punto de color solo sería inaccesible para daltonismo y también ilegible
 * bajo la luz de una sala a las 4 de la mañana.
 */
export function ChipRiesgo({ nivel }: { nivel: NivelRiesgo | null }) {
  if (!nivel) {
    return <span className="missing">sin score</span>
  }
  return (
    <span className={`risk risk-${CLASE_RIESGO[nivel]}`}>
      <span className="risk-glyph" aria-hidden="true" />
      {nivel}
    </span>
  )
}

/** "hace 2 h", "hace 15 min". La antigüedad de una toma es información clínica. */
export function antiguedad(iso: string): { texto: string; vieja: boolean } {
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (min < 1) return { texto: 'recién', vieja: false }
  if (min < 60) return { texto: `hace ${min} min`, vieja: false }
  const h = Math.floor(min / 60)
  if (h < 24) return { texto: `hace ${h} h`, vieja: h >= 8 }
  return { texto: `hace ${Math.floor(h / 24)} d`, vieja: true }
}
