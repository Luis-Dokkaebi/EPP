# language: es
Característica: Promoción del modelo EPP solo con umbrales acordados de antemano
  Como responsable de producto
  Quiero que un modelo nuevo solo llegue a producción si cumple umbrales acordados antes de entrenarlo
  Para no poner en las cámaras un modelo que dispare falsas alarmas o deje pasar infracciones

  Escenario: Sin presupuesto de errores decidido ningún modelo se promueve
    Dado que el presupuesto de errores todavía no está decidido
    Cuando evalúo un modelo con mediciones perfectas
    Entonces el modelo no se promueve
    Y el motivo indica que falta la decisión "D4"

  Escenario: Un modelo que cumple todos los umbrales se promueve
    Dado umbrales acordados para todas las mediciones
    Cuando evalúo un modelo que cumple cada umbral
    Entonces el modelo se promueve

  Esquema del escenario: Un modelo que incumple un umbral no se promueve
    Dado umbrales acordados para todas las mediciones
    Cuando evalúo un modelo con <medición> fuera de su umbral
    Entonces el modelo no se promueve
    Y el motivo nombra la medición <medición>

    Ejemplos:
      | medición                   |
      | detección de casco         |
      | detección de chaleco       |
      | falsas alarmas por hora    |
      | velocidad por cámara       |
      | detección de personas      |

  Escenario: Un modelo justo en el umbral se promueve
    Dado umbrales acordados para todas las mediciones
    Cuando evalúo un modelo que queda justo en cada umbral
    Entonces el modelo se promueve

  Escenario: Un modelo sin todas las mediciones no se promueve
    Dado umbrales acordados para todas las mediciones
    Cuando evalúo un modelo al que le falta la medición de falsas alarmas por hora
    Entonces el modelo no se promueve
    Y el motivo nombra la medición falsas alarmas por hora
