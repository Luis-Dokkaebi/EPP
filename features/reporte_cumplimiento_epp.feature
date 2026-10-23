# language: es
Característica: Reporte de cumplimiento de EPP
  Como responsable de seguridad e higiene
  Quiero un reporte diario de infracciones de EPP por turno, empleado, zona y elemento
  Para ver dónde y en qué turno falla el uso del equipo de protección

  Antecedentes:
    Dado que "Ana" trabaja en el turno "Matutino"

  Escenario: Infracciones del día agrupadas por empleado y elemento
    Dado que "Ana" estuvo sin casco 10 minutos a las 08:00
    Y que "Ana" estuvo sin casco 5 minutos a las 09:00
    Cuando genero el reporte de cumplimiento del día
    Entonces el reporte muestra para "Ana", en su turno, 2 infracciones sin casco que suman 15 minutos

  Escenario: Una infracción que cruza la medianoche cuenta solo hasta el fin del día
    Dado que "Ana" estuvo sin casco 20 minutos a las 23:50
    Cuando genero el reporte de cumplimiento del día
    Entonces el reporte muestra para "Ana", en su turno, 1 infracciones sin casco que suman 10 minutos

  Escenario: Día sin infracciones
    Dado que no hubo infracciones en el día
    Cuando genero el reporte de cumplimiento del día
    Entonces el reporte indica que no hubo infracciones en el período
