# language: es
Característica: Verificación del EPP de cada operario
  Como responsable de seguridad e higiene
  Quiero que el sistema verifique el EPP de cada operario
  Para actuar ante los incumplimientos sin vigilar las cámaras

  Antecedentes:
    Dado una zona "Boca de pozo" que exige casco, chaleco y guantes

  Escenario: Operario con todo su EPP
    Dado un operario en "Boca de pozo" con casco, chaleco y guantes
    Cuando transcurre el tiempo de confirmación
    Entonces el operario figura como "cumple"
    Y no se genera ninguna alerta

  Esquema del escenario: Operario al que le falta un elemento
    Dado un operario en "Boca de pozo" sin <elemento>
    Cuando transcurre el tiempo de confirmación
    Entonces se genera una alerta por "<elemento>" faltante
    Y la alerta incluye la imagen del evento

    Ejemplos:
      | elemento |
      | casco    |
      | chaleco  |
      | guantes  |

  Escenario: Una oclusión breve no genera alerta
    Dado un operario en "Boca de pozo" con todo su EPP
    Y su casco deja de verse durante menos que el tiempo de confirmación
    Cuando transcurre el tiempo de confirmación
    Entonces no se genera ninguna alerta

  Escenario: Cabeza no visible
    Dado un operario en "Boca de pozo" cuya cabeza no se ve
    Cuando transcurre el tiempo de confirmación
    Entonces el casco del operario figura como "no verificable"
    Y no se genera ninguna alerta

  Escenario: Casco en la mano no cuenta como casco puesto
    Dado un operario en "Boca de pozo" que lleva el casco en la mano
    Cuando transcurre el tiempo de confirmación
    Entonces se genera una alerta por "casco" faltante

  Escenario: Entrar a una zona sin el EPP que exige
    Dado un operario sin guantes fuera de toda zona que exija guantes
    Cuando el operario entra a "Boca de pozo"
    Entonces al cumplirse el tiempo de confirmación se genera una alerta por "guantes" faltante en "Boca de pozo"
