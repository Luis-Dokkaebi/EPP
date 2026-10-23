# language: es
Característica: Reporte de asistencia por rango de fechas
  Como supervisor de oficina
  Quiero elegir el rango de fechas del reporte
  Para revisar solo el período que me interesa

  Escenario: Rango válido
    Dado el rango de fechas desde "2026-10-01" hasta "2026-10-22"
    Cuando genero el reporte de asistencia
    Entonces el reporte cubre del "2026-10-01" al "2026-10-22"

  Escenario: Rango de un solo día
    Dado el rango de fechas desde "2026-10-22" hasta "2026-10-22"
    Cuando genero el reporte de asistencia
    Entonces el reporte cubre del "2026-10-22" al "2026-10-22"

  Esquema del escenario: Fecha mal escrita
    Dado el rango de fechas desde "<desde>" hasta "2026-10-22"
    Cuando genero el reporte de asistencia
    Entonces se me avisa "Fecha inválida: «<desde>». Usa el formato AAAA-MM-DD."
    Y no se consulta ningún dato

    Ejemplos:
      | desde      |
      | 22/10/2026 |
      | 2026-02-30 |

  Escenario: Fecha inicial posterior a la final
    Dado el rango de fechas desde "2026-10-23" hasta "2026-10-22"
    Cuando genero el reporte de asistencia
    Entonces se me avisa "La fecha «Desde» (2026-10-23) es posterior a «Hasta» (2026-10-22)."
    Y no se consulta ningún dato
