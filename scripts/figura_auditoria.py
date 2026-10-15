"""
Compone la figura de la bitacora de auditoria con los eventos REALES de la base (SCRUM-72).

QUE PRUEBA ESTA FIGURA
Que cada acuse de una alerta queda firmado por una persona y encadenado al anterior: el
`hash previo` de cada fila es, literalmente, el `hash` de la fila de arriba. Alterar o
borrar un evento del medio rompe la cadena desde ahi hacia abajo, y la funcion
`verificar_cadena_auditoria()` lo detecta.

POR QUE ESTAN LAS DOS FILAS DE PRUEBA
Los eventos 18 y 19 son de una prueba de desarrollo. **No se pueden borrar**, y eso no es
un descuido: la tabla es append-only por diseno, sin UPDATE ni DELETE para ningun rol.
Dejarlas a la vista demuestra la propiedad mejor que cualquier explicacion.

El equivalente del Sprint 3 (figura 16) se hizo con HTML + Chrome headless. Ese metodo ya
no funciona en este entorno --devuelve codigo 0 y no escribe el archivo--, asi que esta se
compone con matplotlib, que ademas da consistencia con el resto de las figuras.

Uso:  python scripts/figura_auditoria.py
Salida: 30_log_auditoria.png en el directorio actual.
"""
from figura_sprint4 import _tabla

FECHA_LECTURA = "15 de octubre de 2026"

# Leido de public.alert_audit_log por el MCP de Supabase el 15/10/2026.
# Los hashes van truncados a 16 caracteres: el completo es SHA-256 y no entra en la
# figura. El truncado conserva lo que la figura necesita mostrar, que es la coincidencia
# entre el hash de una fila y el hash previo de la siguiente.
# (seq, evento, actor, momento, hash_previo, hash)
EVENTOS = [
    (18, "pospuesta", "Dr. Ricardo Olguín", "14/10/2026 23:16",
     "30a5aeb16b97a536", "2dca8abc6e4ccdcd"),
    (19, "pospuesta", "Dr. Ricardo Olguín", "14/10/2026 23:16",
     "2dca8abc6e4ccdcd", "00978bb20dc87d19"),
    (20, "reconocida", "Lic. Vanina Soledad Agüero", "15/10/2026 00:18",
     "00978bb20dc87d19", "2cacb2dff8cca623"),
    (21, "pospuesta", "Lic. Vanina Soledad Agüero", "15/10/2026 00:19",
     "2cacb2dff8cca623", "4feeccd79d43e204"),
]


def figura_auditoria():
    columnas = [("Evento", 0.035, "left"), ("Acuse", 0.105, "left"),
                ("Firmado por", 0.230, "left"), ("Momento", 0.470, "left"),
                ("Hash previo", 0.625, "left"), ("Hash del evento", 0.800, "left")]

    filas = [{"tipo": "item", "celdas": [
        str(seq), evento, actor, momento, ("mono", previo), ("mono", h),
    ]} for seq, evento, actor, momento, previo, h in EVENTOS]

    filas.append({"tipo": "total", "texto": "verificar_cadena_auditoria()",
                  "valor": "Íntegra · 21 eventos"})

    _tabla("30_log_auditoria.png",
           "Bitácora de auditoría: cada acuse firmado y encadenado",
           "Últimos cuatro eventos de public.alert_audit_log · tabla sin UPDATE ni DELETE "
           "para ningún rol",
           columnas, filas,
           f"Datos reales leídos de la base del proyecto el {FECHA_LECTURA}; los hashes "
           f"son SHA-256 truncados a 16 caracteres para que entren en la figura. El hash "
           f"previo de cada fila es el hash de la fila anterior: borrar o\nalterar un "
           f"evento del medio rompe la cadena desde ahí hacia abajo. Los eventos 18 y 19 "
           f"son de una prueba de desarrollo y siguen a la vista porque la tabla es "
           f"append-only y no admite borrado.",
           ancho=16.4)


if __name__ == "__main__":
    figura_auditoria()
