# language: es
Característica: Licencia de prueba del módulo EPP
  Como proveedor
  Quiero dar una prueba gratuita de 14 días que se bloquee al terminar
  Para que el cliente vea el sistema funcionando y luego lo compre

  Escenario: Prueba vigente muestra los días restantes
    Dado una licencia de prueba de 14 días emitida hace 10 días para este equipo
    Cuando abro la aplicación
    Entonces el módulo EPP está activo
    Y veo el aviso "Prueba: quedan 4 días"

  Esquema del escenario: Días restantes de la prueba
    Dado una licencia de prueba de 14 días emitida hace <dias> días para este equipo
    Cuando abro la aplicación
    Entonces veo el aviso "<aviso>"

    Ejemplos:
      | dias | aviso                  |
      | 0    | Prueba: quedan 14 días |
      | 11   | Prueba: quedan 3 días  |
      | 13   | Prueba: queda 1 día    |

  Escenario: La licencia de aprendizaje no incluye el módulo EPP
    Dado una licencia de aprendizaje emitida hoy para este equipo
    Cuando abro la aplicación
    Entonces el módulo EPP no está activo
    Y no veo ningún aviso de prueba

  Escenario: La prueba vence con la aplicación abierta
    Dado una licencia de prueba que vence en 30 minutos
    Y la aplicación está vigilando cámaras
    Cuando pasa una hora
    Entonces la vigilancia se detiene
    Y se pide una licencia para continuar
    Y los rostros, zonas e historial se conservan

  Escenario: Atrasar el reloj no extiende la prueba
    Dado una licencia de prueba vigente
    Y la aplicación ya funcionó hoy
    Cuando la fecha del equipo se atrasa dos días
    Entonces la licencia se rechaza por fecha incorrecta

  Escenario: La licencia comercial conserva lo aprendido
    Dado una licencia de prueba vencida
    Y empleados registrados durante la prueba
    Cuando activo una licencia comercial para este equipo
    Entonces los empleados registrados siguen reconociéndose

  Escenario: Licencia emitida para otro equipo
    Dado una licencia de prueba emitida para otro equipo
    Cuando intento activarla
    Entonces la activación se rechaza

  Escenario: Una sola prueba gratuita por equipo
    Dado que este equipo ya recibió su licencia de prueba
    Cuando el proveedor intenta emitirle otra licencia de prueba
    Entonces la emisión se rechaza
