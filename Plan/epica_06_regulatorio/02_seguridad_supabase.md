# Configuración de seguridad de la base antes de la defensa

`SCRUM-87` · Épica 6 · Verificado el 19/10/2026

> **Qué es este documento.** Las tres decisiones de seguridad que quedaron pendientes al
> publicar el sistema (`SCRUM-85`), qué se hizo con cada una y **cómo se verificó desde
> afuera**. Un cambio en un panel de configuración no cuenta como hecho hasta que el
> servidor responde distinto: el 19/10 se encontró que las dos primeras figuraban como
> "decididas" el 15/10 y ninguna estaba aplicada.

---

## Resumen

| Decisión | Estado | Cómo se verificó |
|---|---|---|
| Cerrar el registro público | ✅ Aplicada | `/auth/v1/settings` → `disable_signup: true`; un intento de registro devuelve `422 signup_disabled` |
| Protección de contraseñas filtradas | ⛔ No disponible en el plan | El panel responde que requiere el plan Pro |
| Funciones `SECURITY DEFINER` ejecutables por usuarios autenticados | ✅ Se dejan así, a propósito | Un anónimo recibe `permission denied` en las dos |

---

## 1. Registro público: cerrado

**Por qué.** Con el sistema publicado en `zahasalud.com.ar`, el registro abierto permitía
que cualquiera se creara una cuenta y entrara a la aplicación clínica. Los pacientes son
ficticios, pero una cuenta nueva puede **cargar tomas** en una tabla que, por diseño, no
admite borrado (`vital_records` es *append-only*): una carga de prueba de un desconocido
quedaría para siempre en el historial.

**Qué se hizo.** Se desactivó *Allow new users to sign up* en Supabase Auth. Las cuentas
existentes —la de demostración para la cátedra y las de enfermería de prueba— siguen
funcionando. Las cuentas nuevas las crea el administrador.

**Verificado:**

```
GET  /auth/v1/settings  → "disable_signup": true
POST /auth/v1/signup    → 422 {"error_code":"signup_disabled",
                               "msg":"Signups not allowed for this instance"}
```

## 2. Protección de contraseñas filtradas: no disponible

**Qué es.** Supabase puede rechazar contraseñas que aparecen en filtraciones conocidas,
consultando la base de HaveIBeenPwned.

**Qué pasó.** Al activarla, el panel respondió: *"Configuring leaked password protection
via HaveIBeenPwned.org is available on Pro Plans and up"*. El proyecto usa el plan
gratuito, así que **queda desactivada** y el advisor de seguridad la va a seguir marcando.

**Por qué el riesgo residual es bajo.** Esa protección actúa cuando **un usuario elige** su
contraseña al registrarse o al cambiarla. Con el registro cerrado (punto 1), las únicas
cuentas son las que crea el administrador, que elige contraseñas que no están filtradas. El
control que falta queda reemplazado por uno de procedimiento.

**Qué haría falta en un despliegue real.** Pasar al plan Pro y activarla, o bien gestionar
la identidad con el proveedor de la institución (inicio de sesión institucional), que es lo
que correspondería de todos modos en un hospital. Va al documento de gestión de riesgos
(`SCRUM-75`).

## 3. Funciones `SECURITY DEFINER`: se dejan ejecutables por usuarios autenticados

El advisor de seguridad marca dos funciones que un usuario **con sesión** puede llamar por
la API (`/rest/v1/rpc/...`). Se dejan así a propósito, por estas razones:

### `current_profile_role()`

Devuelve **el rol de quien la llama** (enfermero, médico o jefe, o nada si su perfil está
inactivo) y nada más. Es la pieza
sobre la que se apoyan las políticas RLS: la usan **11 políticas** de
`20260521000200_rls_policies.sql`. Tiene que ser `SECURITY DEFINER` para leer la tabla de
perfiles sin que esa lectura dispare a su vez las políticas de la misma tabla (recursión).
Quitarle el permiso a `authenticated` rompería el acceso de todos los usuarios.

### `verificar_cadena_auditoria()`

Recorre la bitácora de auditoría y comprueba que la cadena de hashes esté intacta. Devuelve
**solo un resumen**: si la cadena está intacta, cuántos eventos tiene, y en qué eslabón se
rompe si se rompió. **Nunca devuelve filas de la bitácora** ni datos de pacientes.

Una corrección respecto de lo que dice el comentario de la migración
`20260910193000_alert_audit_log_revocar_rpc.sql` ("adentro sigue valiendo el RLS de la
tabla"): eso no es exacto. Una función `SECURITY DEFINER` corre con los permisos de su
dueño y **no** aplica el RLS de las tablas que lee. Lo que la hace segura no es el RLS sino
**lo que devuelve**: un resumen de integridad, sin contenido.

Que cualquier usuario con sesión pueda verificar la integridad de la bitácora es
deseable: es la propiedad que la hace auditable.

**Verificado que ningún anónimo las alcanza:**

```
POST /rest/v1/rpc/verificar_cadena_auditoria  (sin sesión) → 42501 permission denied
POST /rest/v1/rpc/current_profile_role        (sin sesión) → 42501 permission denied
POST /rest/v1/rpc/registrar_evento_alerta     (sin sesión) → la función no está expuesta
```

La tercera es la función del trigger que escribe la bitácora: no figura en la API para
nadie, que es lo correcto.

---

## Cómo repetir la verificación

Con la URL del proyecto y la clave publicable (que son públicas por diseño):

```bash
curl -s "$SUPABASE_URL/auth/v1/settings" -H "apikey: $CLAVE_PUBLICABLE"   # disable_signup
curl -s -X POST "$SUPABASE_URL/rest/v1/rpc/current_profile_role" \
     -H "apikey: $CLAVE_PUBLICABLE" -H "Content-Type: application/json" -d '{}'
```

Y el advisor de seguridad del panel de Supabase: tiene que mostrar exactamente dos avisos
(las funciones del punto 3, aceptadas) y el de contraseñas filtradas (punto 2, limitación
del plan). Cualquier aviso nuevo es un problema real.
