# Lecciones de los agentes (principio H6)

Cada error recurrente de un agente se convierte en un lint, una prueba o un hook. Una lección sin
mecanismo que la haga cumplir no se registra aquí: primero se construye el mecanismo.
`tests/test_docs_indice.py` exige que la columna "Mecanismo" nombre un archivo o una prueba.

| ID | Error observado | Causa | Mecanismo | Entrega |
|----|-----------------|-------|-----------|---------|
| L-001 | mutmut reportaba sobrevivientes que las pruebas sí mataban | mutmut 2.4.4 solo cuenta como muerto el código de salida 1; pytest devuelve 2 en errores de colección | `scripts/ejecutar_pruebas_mutacion.py` normaliza el código | A-03 |
| L-002 | El gate quedó en verde con mutmut caído (`--use-patch-file` sin `whatthepatch`) | Se ignoraba el bit 1 del código de mutmut | `scripts/quality_gate.sh` falla con el bit 1; `whatthepatch` fijado; `test_quality_gate_falla_si_mutmut_termina_con_error` | A-04 |
| L-003 | Mutantes con *timeout* falsos (0 % en `main_ui.py`) | La caché de mutmut reutilizaba el tiempo base de otro objetivo | Caché nueva por objetivo en `scripts/quality_gate.sh` | A-04 |
| L-004 | Código mutado quedó en el árbol tras cortar mutmut | mutmut deja `*.py.bak` y el archivo mutado si se interrumpe | `scripts/quality_gate.sh` falla si encuentra `*.py.bak`; mutar en un worktree aparte | A-04 |
| L-005 | SIGSEGV/SIGILL intermitentes en la suite | Llamadas a Tk desde un hilo de fondo (Tcl 9) | Cola + sondeo con `after` en `src/main_ui.py`; `tests/test_main_ui.py` | A-04 |
| L-006 | Un paso fallido del gate devolvía 0 | `local codigo=$?` leía el código de `fi`, no el del comando | `test_quality_gate_falla_si_un_paso_posterior_falla` | A-03 |
| L-007 | `--changed` mutaba cientos de mutantes heredados en PRs apilados | Comparaba contra `origin/main` en vez de la rama base del PR | Variable `GATE_BASE` en `scripts/quality_gate.sh`; la CI la fija con la base del PR | A-04 |
| L-008 | Mutación de 28 % en un módulo bien probado | Sus pruebas no seguían la convención `tests/test_<módulo>*.py` que usa el runner | Convención de nombres en `scripts/quality_gate.sh` (`GATE_PRUEBAS_MUTACION` para excepciones) | A-05 |
| L-009 | `git commit -m x -n` pasaba el bloqueo de `--no-verify` | El analizador cortaba en `-m` | Análisis de opciones en `.claude/hooks/guardian.py`; `tests/test_guardian_hooks.py` | A-06 |
| L-010 | `pip install -r archivo  # comentario` se bloqueaba | El comentario de shell se leía como paquete | `tests/test_guardian_hooks.py` (caso de comentario) | A-06 |
| L-011 | El hook de formato tocó archivos fuera del repositorio | No se verificaba que la ruta estuviera dentro del proyecto | `_es_python_del_proyecto` en `.claude/hooks/guardian.py`; `tests/test_guardian_hooks_formato_cierre.py` | A-06 |
| L-012 | Un worktree de subagente se commiteó como *gitlink* | La carpeta de worktrees no estaba ignorada | `.claude/worktrees/` en `.gitignore` | A-04 |
| L-013 | Un archivo de pruebas pasó de 500 líneas sin que nadie lo viera | La longitud de archivo solo se revisaba a ojo | `scripts/check_tamano.py` en el gate y en pre-commit | A-06 |
| L-014 | Una tubería con `tee` podía ocultar el fallo del gate de licencias en CI | Actions no activa `pipefail` sin `shell: bash` explícito | `test_ci_licencias_no_pierde_el_codigo_de_salida_en_la_tuberia` | A-07 |
