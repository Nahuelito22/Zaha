-- =============================================================================
-- SCRUM-72 (continuación) — cerrar la exposición por RPC de las funciones nuevas
--
-- Lo levantó el linter de seguridad de Supabase justo después de aplicar
-- 20260910190000. La causa es un default de Postgres que es fácil pasar por
-- alto: al crear una función, EXECUTE queda concedido a PUBLIC. Un
-- `GRANT EXECUTE ... TO authenticated` no restringe nada, solo repite lo que ya
-- estaba. Y como PostgREST publica el esquema public, cada función quedó
-- disponible en /rest/v1/rpc/<nombre> incluso para el rol anon.
--
-- Dos consecuencias distintas, las dos indeseables:
--
--   registrar_evento_alerta()   es la función del trigger que ESCRIBE el log, y
--                               es SECURITY DEFINER. Invocarla suelta falla
--                               ("trigger functions can only be called as
--                               triggers"), así que no es explotable hoy, pero
--                               una función SECURITY DEFINER que escribe la
--                               tabla de auditoría no tiene por qué figurar en
--                               la superficie pública de la API. Se revoca a
--                               todo el mundo: la llama el trigger, punto.
--
--   verificar_cadena_auditoria() sí corre, y sin sesión devolvía la cantidad de
--                               eventos de auditoría del sistema. Es poco, pero
--                               es información de un establecimiento de salud
--                               entregada a un anónimo. Queda solo para
--                               authenticated, y adentro sigue valiendo el RLS
--                               de la tabla.
--
-- Se revocan también las dos funciones de trigger no-DEFINER por la misma razón
-- de superficie: nada que solo llame un trigger debería ser un endpoint.
-- =============================================================================

REVOKE ALL ON FUNCTION public.registrar_evento_alerta()   FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.sellar_evento_auditoria()   FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.guard_alert_audit_log()     FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION public.verificar_cadena_auditoria() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.verificar_cadena_auditoria() TO authenticated;
