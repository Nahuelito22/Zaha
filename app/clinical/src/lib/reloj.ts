import { useEffect, useState } from 'react'

/**
 * Un instante que avanza solo.
 *
 * React re-renderiza cuando cambian props o estado, nunca porque pasó el
 * tiempo. Todo lo que se dibuja en función de "hace cuánto" —la antigüedad de
 * una toma, sobre todo— se congela en el valor que tenía al montar. En una
 * pantalla de escritorio que se abre al empezar la guardia y no se toca en
 * ocho horas, eso significa mostrar "hace 10 min" sobre una medición de la
 * madrugada.
 *
 * El intervalo por defecto es de 30 s porque la unidad más chica que muestra
 * `antiguedad` es el minuto: alcanza para que el texto no se atrase de forma
 * perceptible sin despertar al dispositivo cada segundo, que en una tablet a
 * batería al pie de la cama sí se nota.
 */
export function useAhora(intervaloMs = 30_000): number {
  const [ahora, setAhora] = useState(() => Date.now())

  useEffect(() => {
    const id = setInterval(() => setAhora(Date.now()), intervaloMs)
    return () => clearInterval(id)
  }, [intervaloMs])

  return ahora
}
