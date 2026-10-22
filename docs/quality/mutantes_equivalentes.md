# Mutantes equivalentes (CLAUDE.md §7)

Un mutante equivalente no cambia el comportamiento observable, así que ninguna prueba puede
matarlo. Cada uno se justifica aquí. Los demás sobrevivientes se matan con pruebas nuevas.

| Archivo | Línea original | Mutación | Por qué es equivalente |
|---------|----------------|----------|------------------------|
| `scripts/check_trinquete.py` | `RANGOS_PROHIBIDOS_CC = frozenset("CDEF")` | `frozenset("XXCDEFXX")` | Agrega la letra `X` al conjunto; radon nunca devuelve el rango `X` |
| `scripts/check_trinquete.py` | `RANGOS_PROHIBIDOS_MI = frozenset("BC")` | `frozenset("XXBCXX")` | Ídem: `mi_rank` solo devuelve `A`, `B` o `C` |
| `scripts/check_waivers.py` | `linea.strip().strip("\|")` | `strip("XX\|XX")` | `strip` recibe un conjunto de caracteres: además de `\|` quitaría `X` en los extremos, pero una fila de la tabla siempre empieza y termina con `\|` y espacios |
