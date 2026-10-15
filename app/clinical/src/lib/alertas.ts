/**
 * Acuse de alertas en un clic (SCRUM-68).
 *
 * QUE REGISTRA Y QUIEN
 * La aplicación sólo escribe los campos del acuse sobre `alerts`. El registro de
 * auditoría lo hace la base: el trigger `alerts_registrar_auditoria` inserta en
 * `alert_audit_log` con la cadena de hashes, y ese log es append-only de verdad — sin
 * GRANT de UPDATE ni DELETE. La app **no puede** escribirlo ni corregirlo, que es
 * justamente lo que le da valor probatorio.
 *
 * LOS DOS ACTOS, Y POR QUE NO SON TRES
 * `validar` y `posponer` son los de HU-04. La base también modela `descartada` —falsa
 * alarma— pero no se expone acá: no es parte del flujo de un clic, y marcar algo como
 * ruido merece más fricción que atenderlo. Queda disponible en el esquema para cuando
 * SCRUM-69 necesite medir cuántas alertas fueron ruido.
 *
 * POSPONER NO ES DESCARTAR, Y LA DIFERENCIA IMPORTA
 * Una alerta pospuesta vuelve sola a la cola cuando vence el plazo: la vista
 * `alertas_en_cola` la incluye de nuevo, sin que nadie reescriba la fila. Así la firma
 * de quien pospuso y hasta cuándo queda intacta. Si "posponer" se hubiera mapeado a
 * 'descartada', cada enfermera ocupada habría registrado una falsa alarma, y eso
 * contamina la métrica que el proyecto existe para medir.
 *
 * NO HAY CAMPO DE NOTA
 * `acknowledgement_note` existe en la tabla y queda en NULL. Un clic es un clic: pedir
 * texto rompería el flujo que este ticket viene a construir. Una nota libre es otra
 * afordancia, no ésta.
 */

/** Minutos por defecto de una postergación. Visible en el botón: el usuario no adivina. */
export const MINUTOS_POSPONER = 30

export type AccionAlerta = 'validar' | 'posponer'

/** Lo que se escribe en `alerts`. Nada más: el resto lo rechaza el trigger de la base. */
export type AcusePayload = {
  status: 'reconocida' | 'pospuesta'
  acknowledged_by: string
  acknowledged_at: string
  postponed_until: string | null
}

/**
 * Arma el acuse. Puro a propósito: es la parte que puede equivocarse en silencio
 * —un estado que no corresponde, un plazo ausente— y la que tiene prueba.
 *
 * `ahora` entra por parámetro para que las pruebas no dependan del reloj real.
 */
export function construirAcuse(
  accion: AccionAlerta,
  perfilId: string,
  ahora: Date = new Date(),
  minutos: number = MINUTOS_POSPONER,
): AcusePayload {
  if (!perfilId) {
    // Sin firma la base rechaza el UPDATE (`alerta_resuelta_tiene_firma`), pero
    // fallar acá da un error que se entiende en vez de uno de Postgres.
    throw new Error('no se puede acusar una alerta sin identidad de quien la acusa')
  }

  const instante = ahora.toISOString()
  if (accion === 'validar') {
    return {
      status: 'reconocida',
      acknowledged_by: perfilId,
      acknowledged_at: instante,
      // Validar limpia el plazo: si la alerta venia pospuesta, dejarlo seria
      // afirmar que sigue esperando algo que ya se resolvio.
      postponed_until: null,
    }
  }

  if (!(minutos > 0)) {
    throw new Error('posponer exige un plazo futuro')
  }
  return {
    status: 'pospuesta',
    acknowledged_by: perfilId,
    acknowledged_at: instante,
    postponed_until: new Date(ahora.getTime() + minutos * 60_000).toISOString(),
  }
}

/** Texto del botón. Que diga el plazo evita que posponer sea una caja negra. */
export function etiquetaAccion(accion: AccionAlerta, minutos = MINUTOS_POSPONER): string {
  return accion === 'validar' ? 'Validar' : `Posponer ${minutos} min`
}
