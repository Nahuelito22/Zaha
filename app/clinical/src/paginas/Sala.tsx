import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { PESO_RIESGO, CLASE_RIESGO, type NivelRiesgo } from '../lib/tipos'
import { ChipRiesgo, antiguedad } from '../componentes/ChipRiesgo'

type Cama = {
  encounter_id: string
  bed: string | null
  paciente: string
  mrn: string
  news2_score: number | null
  risk_level: NivelRiesgo | null
  recorded_at: string
}

type FilaCruda = {
  encounter_id: string
  news2_score: number | null
  risk_level: NivelRiesgo | null
  recorded_at: string
  patients: { first_name: string; last_name: string; mrn: string } | null
  encounters: { bed: string | null } | null
}

export function Sala() {
  const [camas, setCamas] = useState<Cama[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const cargar = useCallback(async () => {
    // Se lee de la VISTA de vigentes: una toma enmendada no puede aparecer
    // como el valor actual del paciente.
    const { data, error } = await supabase
      .from('vital_records_vigentes')
      .select(
        'encounter_id, news2_score, risk_level, recorded_at, patients(first_name, last_name, mrn), encounters(bed)',
      )
      .order('recorded_at', { ascending: false })

    if (error) {
      setError(error.message)
      return
    }

    // Una fila por cama: la toma vigente más reciente de cada episodio.
    const porEpisodio = new Map<string, Cama>()
    for (const cruda of data as unknown as FilaCruda[]) {
      if (porEpisodio.has(cruda.encounter_id)) continue
      porEpisodio.set(cruda.encounter_id, {
        encounter_id: cruda.encounter_id,
        bed: cruda.encounters?.bed ?? null,
        paciente: cruda.patients
          ? `${cruda.patients.last_name}, ${cruda.patients.first_name}`
          : '—',
        mrn: cruda.patients?.mrn ?? '',
        news2_score: cruda.news2_score,
        risk_level: cruda.risk_level,
        recorded_at: cruda.recorded_at,
      })
    }

    setCamas(
      [...porEpisodio.values()].sort(
        (a, b) =>
          PESO_RIESGO[a.risk_level ?? 'Bajo'] - PESO_RIESGO[b.risk_level ?? 'Bajo'] ||
          (a.bed ?? '').localeCompare(b.bed ?? ''),
      ),
    )
  }, [])

  useEffect(() => {
    void cargar()
  }, [cargar])

  if (error) {
    return (
      <p role="alert" className="panel text-[15px]">
        No se pudo cargar la sala: {error}
      </p>
    )
  }

  if (camas === null) return <p className="text-[15px]">Cargando sala…</p>

  if (camas.length === 0) {
    return (
      <div className="panel flex flex-col gap-2">
        <p className="text-[15px] font-semibold">No hay camas visibles.</p>
        <p className="text-[14px]" style={{ color: 'var(--c-text-muted)' }}>
          Si esperabas ver pacientes, las políticas de acceso están denegando la
          lectura. Verificá que tu perfil exista y esté activo.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-[13px]" style={{ color: 'var(--c-text-muted)' }}>
        {camas.length} camas ocupadas · ordenadas por riesgo
      </p>

      <ul className="flex flex-col gap-2">
        {camas.map((c) => {
          const edad = antiguedad(c.recorded_at)
          return (
            <li
              key={c.encounter_id}
              className={`panel risk-edge-${CLASE_RIESGO[c.risk_level ?? 'Bajo']}`}
              style={{ padding: '12px 16px' }}
            >
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <span
                  className="col-num w-14 shrink-0 text-[15px] font-bold"
                  style={{ fontFamily: 'var(--font-numeric)' }}
                >
                  {c.bed ?? '—'}
                </span>

                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[16px] font-semibold">
                    {c.paciente}
                  </span>
                  <span className="text-[12px]" style={{ color: 'var(--c-text-muted)' }}>
                    {c.mrn} ·{' '}
                    <span className={edad.vieja ? 'missing' : undefined}>
                      {edad.texto}
                    </span>
                  </span>
                </span>

                <span className="flex items-baseline gap-1">
                  <span className="vital-value">{c.news2_score ?? '—'}</span>
                  <span className="vital-unit">NEWS2</span>
                </span>

                <ChipRiesgo nivel={c.risk_level} />

                <Link
                  to={`/cargar/${c.encounter_id}`}
                  className="cbtn cbtn-secondary"
                  style={{ minHeight: 36, fontSize: 14 }}
                >
                  Cargar vitales
                </Link>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
