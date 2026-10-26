# language: es
Característica: Modo sombra del piloto de EPP
  Como responsable del piloto
  Quiero que durante el modo sombra las infracciones se registren sin avisar
  Para medir el sistema en el sitio sin molestar a nadie con falsas alarmas

  Antecedentes:
    Dado un canal de aviso configurado para la sucursal

  Escenario: En modo sombra se registra sin avisar
    Dado una infracción de "Ana" sin casco pendiente de aviso
    Cuando abro la sucursal en modo sombra
    Entonces el responsable no recibió ningún aviso
    Y la infracción de "Ana" sigue pendiente de aviso

  Escenario: Al salir del modo sombra lo registrado en ese período no se avisa
    Dado una infracción de "Ana" sin casco registrada durante el modo sombra
    Y una infracción de "Luis" sin chaleco registrada después del modo sombra
    Cuando abro la sucursal tras salir del modo sombra
    Entonces el responsable recibió avisos solo por "Luis"
    Y la infracción de "Ana" figura como descartada

  Escenario: Una infracción que empieza justo al salir del modo sombra se avisa
    Dado una infracción de "Luis" sin chaleco registrada al salir del modo sombra
    Cuando abro la sucursal tras salir del modo sombra
    Entonces el responsable recibió avisos solo por "Luis"

  Escenario: Una fecha de salida del modo sombra sin huso horario se rechaza
    Dado una infracción de "Ana" sin casco registrada durante el modo sombra
    Cuando abro la sucursal con una fecha de salida del modo sombra sin huso horario
    Entonces la apertura se rechaza por la fecha de salida del modo sombra
    Y la infracción de "Ana" sigue pendiente de aviso
