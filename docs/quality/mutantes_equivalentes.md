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
| `src/main_ui.py` | `INTERVALO_SONDEO_ESCANEO_MS = 100` | `INTERVALO_SONDEO_ESCANEO_MS = 101` | Solo corre 1 ms el sondeo con el que el hilo de Tk revisa si terminó el escaneo de cámaras: se muestra el mismo resultado, en el mismo hilo y en el mismo orden. Distinguir 100 de 101 ms exigiría una prueba atada al reloj real (§4 prohíbe esa dependencia) |
| `scripts/check_mutacion.py` | `.strip("`")` (nombre de archivo) | `.strip("XX`XX")` | Además de las comillas quitaría `X` en los extremos del nombre; ningún archivo del repositorio empieza ni termina con `X` |
| `scripts/check_mutacion.py` | `... if tabla.is_file() else ""` | `else "XXXX"` | Un texto sin filas de tabla da el mismo conteo vacío que la cadena vacía |
| `scripts/check_licenses.py` | `BLOQUE_LECTURA = 1 << 20` | `2 << 20`, `1 << 21`, `None` | El tamaño del bloque de lectura no cambia el sha256; con `None`, `read()` lee el archivo entero y el resumen es el mismo |
| `scripts/check_licenses.py` | `PROHIBIDA = 2` | `PROHIBIDA = 3` | El valor solo se usa para ordenar la gravedad (`max`/`min`); 3 conserva el orden |
| `scripts/check_licenses.py` | `text=True` (pip-licenses) | `text=False` | `json.loads` acepta `bytes`: el resultado es el mismo |
| `scripts/check_licenses.py` | `check=True` (pip-licenses) | `check=False` | Si pip-licenses falla, ambos fallan ruidosamente (`CalledProcessError` o `JSONDecodeError` sobre una salida vacía) |
| `src/tracking/annotator.py` | `GROSOR_TEXTO = 1` | `GROSOR_TEXTO = None` | `cv2.putText` toma `None` como su grosor por omisión, que es 1: la imagen es idéntica (la huella de `test_annotator.py` no cambia) |
| `src/tracking/annotator.py` | `fuente = cv2.FONT_HERSHEY_SIMPLEX` | `fuente = None` | `FONT_HERSHEY_SIMPLEX` vale 0 y OpenCV convierte `None` en 0: misma fuente, misma imagen |
| `src/ppe/domain/ventana_temporal.py` | `presentes_seguidos: int = 0` | `presentes_seguidos: int = 1` | El contador vuelve a 0 en cada frame AUSENTE antes de que su valor pueda influir; antes del primer AUSENTE, llegar a M frames presentes "recupera" un estado que ya es PRESENTE y sin ausencia abierta. El valor inicial nunca es observable |
