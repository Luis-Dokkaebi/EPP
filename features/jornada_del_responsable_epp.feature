# language: es
Característica: Jornada completa del responsable de seguridad con el módulo de EPP
  Como responsable de seguridad e higiene que acaba de instalar el sistema
  Quiero configurar una zona, dejar las cámaras trabajando y recibir los avisos
  Para enterarme de cada incumplimiento sin vigilar las cámaras

  Antecedentes:
    Dado una zona "Boca de pozo" configurada que exige casco
    Y un aviso por webhook configurado para la sucursal

  Escenario: Un operario sin casco termina en un aviso con imagen que el responsable recibe
    Dado que "Ana" trabaja sin casco en "Boca de pozo" durante el tiempo de confirmación
    Cuando la sucursal despacha los avisos pendientes
    Entonces el responsable recibió un aviso por "Ana" sin casco con la imagen del evento
    Y el panel de alertas muestra a "Ana" sin casco con el aviso enviado

  Escenario: Con el canal de aviso caído la alerta no se pierde
    Dado que "Ana" trabaja sin casco en "Boca de pozo" durante el tiempo de confirmación
    Y el canal de aviso está caído
    Cuando la sucursal despacha los avisos pendientes
    Entonces el responsable no recibió ningún aviso
    Y el panel de alertas muestra a "Ana" sin casco con el aviso pendiente

  Escenario: Quien trabaja fuera de las zonas configuradas no genera avisos
    Dado que "Ana" trabaja sin casco fuera de toda zona durante diez minutos
    Cuando la sucursal despacha los avisos pendientes
    Entonces el responsable no recibió ningún aviso
    Y el panel de alertas está vacío
