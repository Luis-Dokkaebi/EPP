# language: es
Característica: Alertas de EPP al responsable de seguridad
  Como responsable de seguridad e higiene
  Quiero recibir cada infracción una sola vez con su evidencia
  Para no perder eventos ni saturarme de avisos

  Antecedentes:
    Dado una zona "Boca de pozo" que exige casco y chaleco

  Escenario: Una infracción sostenida se notifica una sola vez
    Dado un operario identificado como "Ana" sin casco en "Boca de pozo" desde hace 10 minutos
    Cuando se evalúan las alertas pendientes
    Entonces el responsable recibió exactamente una alerta por "Ana" sin casco

  Escenario: Falla temporal del canal de aviso
    Dado una infracción registrada y el canal de aviso caído
    Cuando el canal de aviso se restablece
    Entonces el responsable recibe la alerta pendiente
    Y la infracción figura como notificada

  Escenario: Operario no identificado
    Dado un operario no identificado sin chaleco en "Boca de pozo"
    Cuando se genera la alerta
    Entonces la alerta indica "persona no identificada" y adjunta la imagen
