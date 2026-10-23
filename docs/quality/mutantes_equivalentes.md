# Mutantes equivalentes (CLAUDE.md §7)

Un mutante equivalente no cambia el comportamiento observable, así que ninguna prueba puede
matarlo. Cada uno se justifica aquí. Los demás sobrevivientes se matan con pruebas nuevas.

| Archivo | Línea original | Mutación | Por qué es equivalente |
|---------|----------------|----------|------------------------|
| `scripts/check_trinquete.py` | `RANGOS_PROHIBIDOS_CC = frozenset("CDEF")` | `frozenset("XXCDEFXX")` | Agrega la letra `X` al conjunto; radon nunca devuelve el rango `X` |
| `scripts/check_trinquete.py` | `RANGOS_PROHIBIDOS_MI = frozenset("BC")` | `frozenset("XXBCXX")` | Ídem: `mi_rank` solo devuelve `A`, `B` o `C` |
| `scripts/check_waivers.py` | `linea.strip().strip("\|")` | `strip("XX\|XX")` | `strip` recibe un conjunto de caracteres: además de `\|` quitaría `X` en los extremos, pero una fila de la tabla siempre empieza y termina con `\|` y espacios |
| `scripts/ejecutar_pruebas_mutacion.py` | `if __name__ == "__main__":` | `if __name__ != "__main__":` | **Falso sobreviviente.** Al importar el módulo mutado en la prueba, `sys.exit` corta la colección y pytest sale con código 2; mutmut 2.4 solo cuenta el código 1 como muerto. Este runner existe justamente para corregir eso en el resto del código, pero no puede usarse para mutarse a sí mismo |
| `scripts/check_architecture.py` | `CONFIGURACION_POR_DEFECTO = ".importlinter"` | `= None` | Con `None`, import-linter busca `.importlinter` en el directorio actual, que es el mismo archivo cuando el script corre desde la raíz del repositorio |
