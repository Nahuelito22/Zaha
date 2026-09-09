-- =============================================================================
-- Realtime sobre vital_records — el tablero se entera solo (SCRUM-42)
--
-- La HU-06 pide que el panel "consuma los datos del backend en tiempo real".
-- Hasta ahora la sala leía una vez al montar: si otro enfermero cargaba una
-- toma desde otra tablet, la pantalla del office seguía mostrando el score
-- anterior sin ninguna señal de que estaba desactualizada. En un tablero de
-- triage eso es peor que no tener tablero: se delega vigilancia sobre datos
-- viejos creyendo que son actuales.
--
-- POR QUÉ ACÁ Y NO EN EL CLIENTE:
-- Realtime solo emite de tablas incluidas en la publicación `supabase_realtime`,
-- y la publicación arrancó vacía. Sin esta migración el `.subscribe()` del
-- cliente devuelve SUBSCRIBED igual y no llega ningún evento nunca — falla en
-- silencio, que es la peor forma de fallar.
--
-- POR QUÉ vital_records Y NO LA VISTA:
-- La sala lee de `vital_records_vigentes`, pero Realtime emite de TABLAS, no de
-- vistas. Se escucha la tabla base y se recarga la vista: el cliente nunca
-- deriva el estado del payload del evento, solo lo usa como aviso de "andá a
-- releer". Así una enmienda —que es un INSERT más un UPDATE del registro que
-- queda superseded— no puede dejar la pantalla en un estado intermedio.
--
-- SOBRE RLS: Realtime evalúa las políticas de la tabla por suscriptor, así que
-- esto NO abre datos a nadie: quien no puede leer una fila por `vital_records_select`
-- tampoco recibe su evento.
-- =============================================================================

-- REPLICA IDENTITY FULL para que el UPDATE que marca una toma como enmendada
-- viaje con la fila vieja además de la nueva. Sin esto el evento de una enmienda
-- es indistinguible de cualquier otro UPDATE. El costo en WAL es despreciable a
-- la escala de una sala.
ALTER TABLE public.vital_records REPLICA IDENTITY FULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'vital_records'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.vital_records;
  END IF;
END $$;
