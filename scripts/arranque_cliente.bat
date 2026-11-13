@echo off
rem ====================================================================
rem Arranque de Oficina Eficiencia en el equipo del cliente (SPEC/10 F-08).
rem
rem 1. Copie este archivo junto a OficinaEficiencia_VMS.exe.
rem 2. Complete los valores de abajo con los datos del cliente.
rem 3. Abra la aplicacion SIEMPRE con este archivo (o un acceso directo a el).
rem
rem La contrasena del correo queda escrita aqui: deje el archivo legible
rem solo para la cuenta de Windows que usa la aplicacion.
rem ====================================================================

rem --- Modo sombra: con 1 el sistema detecta y registra, pero NO avisa.
rem     Use 1 los dos primeros dias de la prueba. Para salir de la sombra,
rem     deje EPP_MODO_SOMBRA vacio y escriba en EPP_FIN_MODO_SOMBRA la fecha
rem     y hora de salida con huso horario, p. ej. 2026-11-17T08:00:00-06:00
rem     (lo registrado antes de esa hora se descarta sin avisar).
set "EPP_MODO_SOMBRA=1"
set "EPP_FIN_MODO_SOMBRA="

rem --- El aviso nombra al empleado (incluir) o sale anonimo (omitir).
set "EPP_ALERTAS_NOMBRE_EMPLEADO=incluir"

rem --- Avisos por correo. Sin servidor no se envia correo.
rem     Con servidor, todos los demas valores de correo son obligatorios.
set "EPP_ALERTAS_SMTP_SERVIDOR="
set "EPP_ALERTAS_SMTP_PUERTO=587"
set "EPP_ALERTAS_SMTP_USUARIO="
set "EPP_ALERTAS_SMTP_CONTRASENA="
set "EPP_ALERTAS_SMTP_REMITENTE=alertas@ejemplo.com"
rem     Varios destinatarios separados por coma, sin espacios.
set "EPP_ALERTAS_SMTP_DESTINATARIOS=seguridad@ejemplo.com"
set "EPP_ALERTAS_SMTP_TIMEOUT_S=10"

rem --- Avisos por webhook (https). Sin URL no se usa.
rem     Con URL, el secreto y el tiempo de espera son obligatorios.
set "EPP_ALERTAS_WEBHOOK_URL="
set "EPP_ALERTAS_WEBHOOK_SECRETO="
set "EPP_ALERTAS_WEBHOOK_TIMEOUT_S=10"

start "" "%~dp0OficinaEficiencia_VMS.exe"
