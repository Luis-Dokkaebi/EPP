# Constitución de Calidad — Restricciones Extremas para Agentes

> **Premisa (estilo "Uncle Bob"):** el humano **no va a leer** línea por línea el código que
> escriben los agentes. Esa es la única forma de aprovechar su productividad.
> A cambio, el código se somete a **restricciones extremas**: pruebas unitarias, pruebas
> Gherkin, procedimientos de control de calidad, métricas de calidad, pruebas de mutación,
> cobertura y muchas otras. La confianza no se otorga: **se gana superando todas las puertas**.

**Este archivo es normativo y obligatorio.** Aplica a Claude y a cualquier otro agente
(Codex, Copilot, Cursor, Gemini, agentes propios) que toque este repositorio o cualquier otro
donde se copie este documento.

> **Gemelos sincronizados:** `CLAUDE.md` y `Agents.md` deben ser **byte a byte idénticos**.
> Si modificas uno, copia el otro en el mismo commit. Un PR que los deje divergentes se rechaza.

---

## Índice

1. [Ley Cero y principios](#1-ley-cero-y-principios)
2. [Ciclo de trabajo obligatorio (TDD)](#2-ciclo-de-trabajo-obligatorio-tdd)
3. [Restricciones de diseño de código](#3-restricciones-de-diseño-de-código)
4. [Pruebas unitarias](#4-pruebas-unitarias)
5. [Pruebas Gherkin / BDD](#5-pruebas-gherkin--bdd)
6. [Cobertura de pruebas](#6-cobertura-de-pruebas)
7. [Pruebas de mutación](#7-pruebas-de-mutación)
8. [Métricas de calidad](#8-métricas-de-calidad)
9. [Seguridad](#9-seguridad)
10. [Procedimiento de control de calidad (Quality Gate)](#10-procedimiento-de-control-de-calidad-quality-gate)
11. [Definition of Done](#11-definition-of-done)
12. [Protocolo de commits](#12-protocolo-de-commits)
13. [Protocolo de Pull Request](#13-protocolo-de-pull-request)
14. [Prohibiciones absolutas](#14-prohibiciones-absolutas)
15. [Excepciones y deuda técnica](#15-excepciones-y-deuda-técnica)
16. [Reglas específicas de este proyecto](#16-reglas-específicas-de-este-proyecto)
17. [Contrato del agente](#17-contrato-del-agente)
18. [Apéndice A — Instalación de herramientas](#apéndice-a--instalación-de-herramientas)
19. [Apéndice B — Plantillas](#apéndice-b--plantillas)

---

## 1. Ley Cero y principios

**LEY CERO — La suite verde manda.**
Ningún cambio se considera terminado, ni se commitea, ni se propone en un PR si la puerta de
calidad (§10) no pasa **completa y en verde**, ejecutada localmente por el agente, con la
**salida real pegada** en el reporte final (§17).

**Principios rectores:**

| # | Principio | Significado operativo |
|---|-----------|----------------------|
| P1 | *El código no leído debe ser código probado* | Toda línea nueva nace con una prueba que la justifica. |
| P2 | *La prueba es la especificación* | Si el comportamiento no está en un test o un `.feature`, no existe y puede romperse. |
| P3 | *Regla del Boy Scout* | Dejas el módulo que tocas más limpio de lo que lo encontraste. |
| P4 | *Regla del trinquete (ratchet)* | Las métricas solo pueden mejorar. Bajar un umbral es una violación grave (§14). |
| P5 | *Falla ruidosa* | Prefiere romper en voz alta a degradar en silencio. Nada de `except: pass`. |
| P6 | *Alcance mínimo* | Haces lo pedido, completo, y nada más. Refactors oportunistas van en commit aparte. |
| P7 | *Honestidad de reporte* | Si algo falla, se reporta con la salida cruda. Jamás "pasó" sin haberlo ejecutado. |

---

## 2. Ciclo de trabajo obligatorio (TDD)

### Las tres leyes de TDD (no negociables)

1. No escribes código de producción salvo para hacer pasar una prueba unitaria que **falla**.
2. No escribes más prueba unitaria de la necesaria para fallar (no compilar = fallar).
3. No escribes más código de producción del necesario para hacer pasar la prueba que falla.

### Ciclo por cada unidad de trabajo

```
1. ENTENDER  → Lee el código existente y SPEC/. Identifica el comportamiento exacto pedido.
2. ROJO      → Escribe la(s) prueba(s) que describen el comportamiento. EJECÚTALAS y comprueba
               que fallan por la razón correcta. Pega la salida roja en tu bitácora.
3. VERDE     → Implementa lo mínimo para que pasen. Nada de código "por si acaso".
4. REFACTOR  → Limpia con la suite en verde: nombres, duplicación, complejidad, capas.
5. PUERTA    → Ejecuta el Quality Gate completo (§10).
6. COMMIT    → Solo si todo está en verde (§12).
```

**Regla del test que nunca falló:** si una prueba nueva pasa a la primera sin haber visto el
rojo, es sospechosa. Rómpela a propósito (invierte el assert o sabotea la implementación),
confirma que falla, restaura. Un test que no puede fallar no prueba nada.

**Regla del bug:** todo defecto reportado se reproduce **primero** con una prueba que falla.
Esa prueba se queda para siempre como test de regresión, con referencia al issue en el nombre
o en el docstring.

---

## 3. Restricciones de diseño de código

### Límites duros (verificables por herramienta)

| Restricción | Límite | Cómo se mide |
|-------------|--------|--------------|
| Longitud de función/método | ≤ 40 líneas (objetivo ≤ 20) | `ruff` (`PLR0915`), revisión |
| Complejidad ciclomática por función | ≤ 10 | `ruff --select C901`, `radon cc -n C` |
| Parámetros por función | ≤ 5 (objetivo ≤ 3) | `ruff` (`PLR0913`) |
| Niveles de anidamiento | ≤ 3 | `ruff`, revisión |
| Longitud de línea | ≤ 100 caracteres | `ruff format` / `black` |
| Longitud de archivo | ≤ 500 líneas | revisión; si se excede, se divide por responsabilidad |
| Índice de mantenibilidad | grado A o B | `radon mi -n B` |
| Duplicación de código | 0 bloques ≥ 6 líneas repetidos | revisión / `ruff` |
| Tipado estático | 100 % de funciones públicas anotadas | `mypy` |
| Retornos booleanos "mágicos" | prohibidos números/strings mágicos | `ruff` (`PLR2004`) |

### Reglas de diseño

- **SRP:** una clase, una razón para cambiar. Un módulo, un concepto.
- **Nombres reveladores de intención:** sin abreviaturas crípticas, sin `data`, `info`, `tmp`,
  `mgr2`, `process()`. El nombre debe hacer innecesario el comentario.
- **Funciones que hacen una cosa:** consulta **o** comando, nunca ambos (CQS).
- **Argumentos booleanos prohibidos** en APIs públicas: parten la función en dos; crea dos funciones.
- **Sin efectos colaterales ocultos:** si una función escribe en disco, red, DB o estado global,
  el nombre lo dice.
- **Errores como excepciones tipadas**, nunca como códigos de retorno ni `None` ambiguo.
  Excepciones propias por dominio; nunca `except Exception:` sin re-lanzar o registrar y actuar.
- **Comentarios:** solo para explicar el *porqué*. Un comentario que explica el *qué* es un
  síntoma de código mal nombrado: renombra en vez de comentar.
- **Sin código muerto ni comentado.** El historial de git es el archivo muerto.
- **Sin `TODO`/`FIXME` sin issue asociado** (`# TODO(#123): ...`).
- **Dependencias hacia adentro:** la lógica de negocio no importa GUI, ni framework, ni driver
  de cámara. Los detalles dependen de las políticas, nunca al revés.
- **Configuración por inyección**, no por constantes globales dispersas.

---

## 4. Pruebas unitarias

### Estructura

- Framework: **pytest**. Ubicación: `tests/`, espejo de `src/` (`src/zones/zone_checker.py`
  → `tests/test_zone_checker.py`).
- Nombre del test = frase de comportamiento:
  `test_<unidad>_<condición>_<resultado_esperado>`
  Ej.: `test_zone_checker_punto_fuera_del_poligono_retorna_falso`.
- Patrón **AAA** explícito y separado por líneas en blanco: *Arrange / Act / Assert*.
- **Un comportamiento por test.** Varios `assert` están bien si describen un solo hecho.

### Principios F.I.R.S.T. (obligatorios)

| Letra | Regla | Consecuencia práctica |
|-------|-------|----------------------|
| **F**ast | Toda la suite unitaria < 60 s | Sin `sleep`, sin I/O real, sin modelos pesados |
| **I**ndependent | Cualquier orden, cualquier subconjunto | Sin estado compartido entre tests; `pytest -p no:randomly` no debe ser necesario |
| **R**epeatable | Mismo resultado siempre | Sin red, sin reloj real (congela con `freezegun`/fixture), sin aleatoriedad sin semilla |
| **S**elf-validating | Pasa o falla, sin inspección humana | Prohibido `print` como verificación |
| **T**imely | Escrito antes del código | Ver §2 |

### Restricciones de tests

- **Prohibido `if`/`for`/`try` con lógica condicional dentro de un test.** Si necesitas ramas,
  son varios tests o un `@pytest.mark.parametrize`.
- **Prohibido `time.sleep`.** Usa relojes falsos, eventos o esperas deterministas.
- **Prohibido tocar recursos reales:** red, cámara física, disco fuera de `tmp_path`, base de
  datos de producción, hora del sistema. Usa dobles de prueba.
- **Prohibido mockear la unidad bajo prueba.** Se mockean sus colaboradores, no ella misma.
- **Prohibido test sin assert** (o solo `assert True`).
- **Prohibido `pytest.mark.skip` / `xfail` nuevos** sin issue enlazado y fecha de caducidad.
- **Casos obligatorios por unidad:** camino feliz, cada rama de error, **límites** (0, 1, N,
  máximo, negativo, vacío, `None`, unicode) y el caso patológico conocido del dominio.
- Fixtures compartidas en `tests/conftest.py`; nada de setup copiado y pegado.
- Los tests son código de producción: se les aplican §3 (nombres, duplicación, tamaño).

---

## 5. Pruebas Gherkin / BDD

Todo **criterio de aceptación** visible para el usuario o el cliente B2B se expresa además como
escenario Gherkin. Los `.feature` son el contrato con el negocio; los unitarios son el contrato
con el diseño. **Ambos son obligatorios**, no se sustituyen entre sí.

### Estructura

```
features/
  <capacidad>.feature          # p. ej. reporte_eficiencia.feature
  steps/
    test_<capacidad>_steps.py  # implementación de los pasos (pytest-bdd)
```

Herramienta: **pytest-bdd** (se ejecuta dentro de la misma suite pytest y suma a cobertura).

### Reglas de escritura

- Idioma **español**, usando `# language: es` y las palabras clave `Característica`,
  `Escenario`, `Dado`, `Cuando`, `Entonces`, `Y`, `Esquema del escenario`, `Ejemplos`.
- **Lenguaje del negocio, cero detalles técnicos.** Prohibido nombrar clases, funciones, tablas
  SQL, endpoints, widgets o rutas de archivo en un `.feature`.
- Un escenario = un comportamiento observable. **Un solo `Cuando`** por escenario.
- `Dado` = estado previo, `Cuando` = acción, `Entonces` = resultado observable. Nunca mezclar.
- **Declarativo, no imperativo.** ✅ `Cuando genero el reporte del turno de la mañana`
  ❌ `Cuando hago clic en el botón "Generar" de la pestaña 2`.
- Escenarios **independientes**: ninguno depende de que otro se haya ejecutado antes.
- `Antecedentes` (Background) solo para contexto compartido genuino, máximo 4 pasos.
- Usa `Esquema del escenario` + `Ejemplos` para variaciones; nada de copiar escenarios.
- **Cada `.feature` cubre al menos:** el camino feliz, un caso de error de negocio y un límite.
- Los pasos se implementan reutilizando helpers; prohibido lógica de negocio dentro de un step.

### Ejemplo canónico

```gherkin
# language: es
Característica: Reporte de eficiencia por empleado
  Como supervisor de oficina
  Quiero un reporte de eficiencia del día
  Para identificar desviaciones de productividad

  Antecedentes:
    Dado un empleado registrado llamado "Ana"

  Escenario: Empleado presente toda la jornada
    Dado que "Ana" estuvo en su zona de trabajo 8 horas de una jornada de 8 horas
    Cuando genero el reporte de eficiencia del día
    Entonces la eficiencia de "Ana" es del 100 %

  Esquema del escenario: Eficiencia proporcional al tiempo en zona
    Dado que "Ana" estuvo en su zona de trabajo <horas> horas de una jornada de 8 horas
    Cuando genero el reporte de eficiencia del día
    Entonces la eficiencia de "Ana" es del <eficiencia> %

    Ejemplos:
      | horas | eficiencia |
      | 0     | 0          |
      | 2     | 25         |
      | 4     | 50         |
      | 8     | 100        |

  Escenario: Jornada sin registros de presencia
    Dado que "Ana" no tiene registros de presencia en el día
    Cuando genero el reporte de eficiencia del día
    Entonces el reporte indica "sin datos" para "Ana"
    Y no se reporta un error al usuario
```

---

## 6. Cobertura de pruebas

| Métrica | Umbral mínimo | Regla |
|---------|---------------|-------|
| Cobertura de **líneas del código nuevo/modificado** (diff coverage) | **95 %** | Bloqueante |
| Cobertura de **ramas** del código nuevo/modificado | **90 %** | Bloqueante |
| Cobertura global del proyecto | **nunca puede bajar** respecto a `main` | Bloqueante (trinquete P4) |
| Cobertura global — objetivo | ≥ 85 % líneas | Se sube por trinquete, nunca se baja |
| Módulos críticos (`src/security/`, `src/storage/`, `src/analysis/`, `src/ppe/`) | **100 % de ramas** | Bloqueante |

Reglas:

- La cobertura es un **piso, no una meta**. 100 % de cobertura con asserts débiles es fraude;
  por eso existen las pruebas de mutación (§7).
- `# pragma: no cover` requiere comentario justificando y solo se admite en ramas realmente
  inalcanzables (p. ej. `if TYPE_CHECKING`). Cada uso se revisa en el PR.
- Prohibido excluir archivos de la medición para subir el número.

```bash
pytest --cov=src --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=85
```

---

## 7. Pruebas de mutación

La cobertura demuestra que el código **se ejecuta**; la mutación demuestra que los tests
**detectan errores**. Herramienta: **mutmut** (alternativa: `cosmic-ray`).

| Alcance | Mutation score mínimo |
|---------|----------------------|
| Módulos críticos: `src/security/`, `src/storage/`, `src/analysis/efficiency_calculator.py`, `src/zones/zone_checker.py`, `src/ppe/` | **90 %** |
| Código nuevo o modificado en el PR | **85 %** |
| Resto del proyecto | trinquete: nunca baja |

Reglas:

- Todo **mutante sobreviviente es un hueco de prueba**: se mata escribiendo una prueba nueva,
  no ajustando el umbral ni excluyendo el módulo.
- Los mutantes que sobreviven por ser equivalentes se documentan uno por uno en
  `docs/quality/mutantes_equivalentes.md` con su justificación.
- En cambios grandes, la mutación puede ejecutarse solo sobre los archivos tocados
  (`mutmut run --paths-to-mutate src/<modulo>`), pero **debe ejecutarse**.

```bash
mutmut run --paths-to-mutate src/security/
mutmut results
```

---

## 8. Métricas de calidad

Todas se ejecutan en el Quality Gate (§10) y **todas deben salir limpias**.

| Dimensión | Herramienta | Criterio de aprobación |
|-----------|-------------|------------------------|
| Formato | `ruff format --check` (o `black --check`) | 0 diferencias |
| Lint / estilo / bugs | `ruff check` | **0 hallazgos**, sin `# noqa` nuevos sin justificar |
| Tipos | `mypy src/` | 0 errores en módulos ya tipados; los nuevos nacen tipados |
| Complejidad | `radon cc src -n C` | 0 funciones con grado C o peor |
| Mantenibilidad | `radon mi src -n B` | 0 archivos con grado C o peor |
| Imports muertos / código muerto | `ruff check --select F401,F841` | 0 hallazgos |
| Seguridad estática | `bandit -r src -ll` | 0 hallazgos High/Medium |
| Dependencias vulnerables | `pip-audit` | 0 vulnerabilidades conocidas explotables |
| Secretos | `detect-secrets scan` o `gitleaks detect` | 0 secretos |
| Pruebas | `pytest` | 100 % en verde, 0 skips nuevos |
| Cobertura | `pytest-cov` | §6 |
| Mutación | `mutmut` | §7 |

**Regla del trinquete (P4):** los umbrales de este documento solo se editan **al alza**.
Bajar un umbral, relajar una regla de lint o añadir una exclusión para "poner el build en
verde" es una violación grave (§14) y motivo de rechazo automático del PR.

---

## 9. Seguridad

- **Nunca** commitees claves, certificados, `.pem` privados, tokens, contraseñas ni rutas de
  licencia reales. Secretos por variable de entorno o almacén seguro.
- **SQL siempre parametrizado.** Prohibida la concatenación o f-strings para construir queries.
  Toda consulta nueva exige un test de inyección análogo a `tests/test_report_sql_injection.py`.
- **Validación de toda entrada externa** (archivos, rutas, CSV/XLSX, argumentos CLI, datos de
  cámara, respuestas de red) en el borde del sistema.
- **Sin rutas absolutas hardcodeadas.** Usa `config/path_utils.py`.
- **Criptografía:** solo primitivas de `cryptography`/`pycryptodome` con parámetros vigentes.
  Prohibido implementar cripto propia, MD5/SHA1 para seguridad, o modos ECB.
- **Logs sin datos sensibles** (rostros, embeddings, claves, identificadores personales en claro).
- Cualquier cambio en `src/security/` exige, además del gate normal: pruebas de mutación
  ≥ 90 %, revisión explícita del modelo de amenazas en el PR y `bandit` sin hallazgos.

---

## 10. Procedimiento de control de calidad (Quality Gate)

**Ejecutar en este orden. Si un paso falla, se corrige y se reinicia desde el paso 1.**
No se avanza al siguiente paso con el anterior en rojo.

```bash
# 0) Entorno limpio y reproducible
python -m pip install -r requirements.txt -r requirements-dev.txt

# 1) Formato
ruff format --check .

# 2) Lint
ruff check .

# 3) Tipos
mypy src/

# 4) Pruebas unitarias + BDD + cobertura
pytest --cov=src --cov-branch --cov-report=term-missing --cov-fail-under=85 -q

# 5) Métricas de complejidad y mantenibilidad
radon cc src -n C      # no debe listar nada
radon mi src -n B      # no debe listar nada

# 6) Seguridad
bandit -r src -ll
pip-audit

# 7) Mutación (sobre lo tocado, o sobre módulos críticos)
mutmut run --paths-to-mutate src/<modulo_tocado>
mutmut results

# 8) Verificación final: suite completa desde cero, dos veces (detecta tests acoplados)
pytest -q && pytest -q -p no:cacheprovider
```

**Salida esperada:** todos los comandos con código de salida `0`.
El agente **pega en su reporte final** (§17) la salida real de los pasos 4, 5, 6 y 7.

> Si una herramienta no está instalada, **instálala** (Apéndice A) y déjala declarada en
> `requirements-dev.txt`. "No estaba instalada" **no** es una excusa válida para saltar un paso;
> si es imposible instalarla en el entorno, se declara explícitamente en el reporte como
> **paso omitido**, nunca como aprobado.

---

## 11. Definition of Done

Una tarea está terminada **solo si se cumple todo**:

- [ ] Existe al menos una prueba unitaria que falló antes de la implementación y ahora pasa.
- [ ] Los criterios de aceptación de negocio están en un `.feature` con sus steps implementados.
- [ ] Cobertura de líneas del diff ≥ 95 % y de ramas ≥ 90 %; la global no bajó.
- [ ] Mutation score del código tocado ≥ 85 % (≥ 90 % si es módulo crítico).
- [ ] Quality Gate (§10) completo en verde, con salidas pegadas en el reporte.
- [ ] Cero `skip`, `xfail`, `noqa`, `type: ignore` o `pragma: no cover` nuevos sin justificación
      escrita en el PR.
- [ ] Sin código muerto, comentado, ni `TODO` sin issue.
- [ ] Documentación actualizada si cambió comportamiento público (`README.md`, `SPEC/`, `docs/`).
- [ ] `VERSION` actualizado si el cambio es liberable.
- [ ] `CLAUDE.md` y `Agents.md` siguen siendo idénticos.
- [ ] Commits atómicos con mensaje conforme a §12.
- [ ] Reporte final del agente entregado con el formato de §17.

---

## 12. Protocolo de commits

- **Un commit = un cambio coherente.** Formato, refactor y funcionalidad van en commits separados.
- **Conventional Commits** en español:

```
<tipo>(<ámbito>): <resumen en imperativo, ≤ 72 caracteres>

<cuerpo: qué y por qué, no cómo>

Pruebas: <qué pruebas se añadieron/modificaron>
Refs: #<issue>
```

Tipos: `feat`, `fix`, `refactor`, `test`, `docs`, `perf`, `build`, `chore`, `sec`.

- **Prohibido commitear con la suite en rojo.**
- **Prohibido `git commit --no-verify`** y prohibido desactivar hooks.
- **Prohibido `git push --force`** sobre ramas compartidas (`main`, ramas con PR abierto de otro).
  Si es imprescindible sobre tu propia rama, usa `--force-with-lease` y decláralo.
- Cada commit debe dejar el repositorio en estado **compilable y verde**.
- Nada de commits "WIP" en la rama del PR.

---

## 13. Protocolo de Pull Request

### Requisitos de entrada

Un PR se abre **solo** con el Quality Gate en verde. El PR debe ser pequeño y revisable:
objetivo **≤ 400 líneas de diff** (sin contar lockfiles ni generados). Si es mayor, se divide.

### Plantilla obligatoria del PR

````markdown
## Qué cambia
<Descripción funcional en lenguaje de negocio.>

## Por qué
<Problema o requisito que resuelve. Enlace al issue/SPEC.>

## Cómo se verificó
### Pruebas añadidas
- Unitarias: <lista>
- Gherkin: <escenarios>

### Evidencia del Quality Gate (salida real)
```
<salida de pytest --cov>
<salida de ruff / mypy>
<salida de radon>
<salida de bandit / pip-audit>
<salida de mutmut results>
```

## Métricas
| Métrica | Antes | Después | Umbral |
|---|---|---|---|
| Cobertura global | | | no baja |
| Cobertura del diff | | | ≥ 95 % |
| Mutation score (módulos tocados) | | | ≥ 85 % |
| Hallazgos ruff / mypy / bandit | | | 0 |

## Riesgos y plan de reversión
<Qué puede romperse y cómo se revierte.>

## Checklist (Definition of Done §11)
- [ ] ... (todos los ítems marcados)
````

### Reglas de revisión

- **El PR se aprueba por evidencia, no por lectura del código.** Sin evidencia pegada, se rechaza.
- Un PR que baje cualquier umbral, borre pruebas, o añada exclusiones para pasar el gate se
  **rechaza automáticamente**, sin discusión.
- Los comentarios de revisión se resuelven con **código y pruebas**, no con explicaciones.
- No se hace merge con checks en rojo, ni con conversaciones sin resolver.

---

## 14. Prohibiciones absolutas

Cualquiera de estas acciones invalida el trabajo completo y obliga a revertir:

1. ❌ **Borrar, saltar (`skip`/`xfail`), comentar o debilitar una prueba** para poner el build
   en verde.
2. ❌ **Bajar un umbral** de cobertura, mutación, complejidad o lint.
3. ❌ **Ampliar tolerancias numéricas** (`pytest.approx`, epsilons) para que un assert pase.
4. ❌ **Añadir exclusiones** (`--ignore`, `exclude`, `# noqa`, `# type: ignore`,
   `# pragma: no cover`) sin justificación escrita y aprobada.
5. ❌ **Reportar como aprobado un paso que no se ejecutó.** Es la falta más grave.
6. ❌ Escribir la implementación antes que la prueba.
7. ❌ `except Exception: pass` o cualquier supresión silenciosa de errores.
8. ❌ Commitear secretos, claves privadas, `.pem`, credenciales o datos personales reales.
9. ❌ `git commit --no-verify`, desactivar hooks, o `push --force` a ramas compartidas.
10. ❌ Tocar archivos fuera del alcance de la tarea (refactors sorpresa, reformateo masivo).
11. ❌ Actualizar o añadir dependencias sin fijar versión y sin pasar `pip-audit`.
12. ❌ Modificar archivos generados/binarios (`*.whl`, `*.pt`, `*.xlsx` de prueba) sin
    instrucción explícita.
13. ❌ Cambiar `CLAUDE.md` o `Agents.md` sin sincronizar el gemelo.
14. ❌ Mockear la unidad bajo prueba, o escribir tests que solo verifican que un mock fue llamado
    cuando el comportamiento real es verificable.

---

## 15. Excepciones y deuda técnica

Las reglas se pueden incumplir **solo** mediante un waiver explícito:

1. Se abre un issue titulado `WAIVER: <regla> en <archivo>`.
2. Se documenta en `docs/quality/waivers.md`:

   | ID | Regla incumplida | Archivo | Motivo técnico | Riesgo | Fecha límite | Issue |
   |----|------------------|---------|----------------|--------|--------------|-------|

3. Se marca en el código con referencia al issue:
   `# noqa: C901  # WAIVER-#123: pipeline de tracking, se divide en el sprint 7`.
4. Todo waiver tiene **fecha de caducidad**. Un waiver vencido bloquea el siguiente PR que toque
   ese archivo.
5. **El agente nunca se auto-otorga un waiver**: lo propone en el reporte final y espera decisión
   humana.

---

## 16. Reglas específicas de este proyecto

Contexto: aplicación de escritorio Python 3.11 (visión por computadora + reportes de eficiencia),
distribuida como ejecutable Windows con protección DRM.

### Arquitectura y capas

```
src/acquisition/  → captura de video y enumeración de cámaras
src/detection/    → detección de personas (YOLO)
src/tracking/     → seguimiento, workers por cámara, pipeline
src/recognition/  → reconocimiento facial
src/zones/        → geometría de zonas y pertenencia
src/inference/    → puerto DetectorPort y adaptadores de motor (ONNX Runtime; Ultralytics temporal)
src/ppe/          → EPP: dominio (elementos, asociación, reglas) y casos de uso
src/alerts/       → alertas: dominio, outbox y adaptadores de canal (email, webhook)
src/analysis/     → estado, eficiencia, generación de reportes
src/storage/      → persistencia (SQLite + cifrado)
src/security/     → DRM, cifrado de DB, crash logger
src/gui/          → interfaz (customtkinter)
config/           → configuración y utilidades de rutas
```

Reglas de dependencia: `gui` → `analysis`/`storage` → dominio. **La lógica de dominio
(`zones`, `analysis`, `storage`, `ppe`, `alerts`) no importa `gui`, `cv2`, `ultralytics`, `torch`,
`onnxruntime` ni `customtkinter`.** Si necesita un detector, recibe `DetectorPort` inyectado.
Un import prohibido es un fallo de PR: lo verifican `.importlinter` y `scripts/check_architecture.py`.

### Pruebas en este dominio

- **Nada de cámaras, modelos ni pesos reales en tests.** `yolov8n.pt`, `dlib` y `face_recognition`
  se sustituyen por dobles. Un test unitario jamás carga un modelo de 6 MB.
- La base de datos de prueba vive en `tmp_path`; jamás se toca `data/`.
- La geometría de zonas se prueba con casos límite explícitos: punto en el vértice, punto en la
  arista, polígono cóncavo, polígono degenerado, coordenadas negativas.
- Los cálculos de eficiencia se prueban con: jornada completa, jornada vacía, solapamientos,
  cambios de turno a medianoche, huso horario y datos fuera de rango.
- Los hilos/workers de cámara se prueban con **liberación de recursos verificada** (ver
  `tests/test_camera_worker_leaks.py`): todo `start()` tiene su `stop()` probado, sin fugas.
- Los reportes Excel se verifican por contenido (celdas, hojas, tipos), no por tamaño de archivo.
- Todo cambio en DRM/cifrado exige tests de fallback y de manipulación (llave inválida,
  archivo corrupto, reloj alterado).

### Entorno

- Python **3.11**. Dependencias **fijadas por versión** en `requirements.txt`.
- Herramientas de calidad en `requirements-dev.txt` (no van al ejecutable).
- Documentación viva en `SPEC/`: si cambias comportamiento especificado, actualizas el `SPEC`
  correspondiente en el mismo PR.
- El build (`compilar_exe.bat`, `gui_app.spec`, `obfuscate.py`) no se toca sin instrucción
  explícita; cualquier cambio ahí exige prueba de humo del ejecutable documentada en el PR.

---

## 17. Contrato del agente

### Al empezar una tarea

1. Lee este documento completo.
2. Lee el código y los `SPEC/` relevantes **antes** de escribir nada.
3. Enuncia por escrito: el comportamiento esperado, los casos límite y el plan de pruebas.
4. Si la petición es ambigua **y** las interpretaciones llevan a trabajos distintos, pregunta.
   Si no, elige la interpretación razonable, decláralo y continúa.

### Durante

5. Sigue el ciclo TDD (§2) sin atajos.
6. No amplíes el alcance. Lo que descubras de paso se anota, no se arregla en el mismo commit.

### Al terminar — reporte final obligatorio

```markdown
## Resumen
<Qué se implementó, en una frase.>

## Pruebas escritas
- <test> — <comportamiento que fija>

## Evidencia del Quality Gate
| Paso | Comando | Resultado |
|------|---------|-----------|
| Formato | ruff format --check . | ✅ / ❌ / ⏭️ omitido (motivo) |
| Lint | ruff check . | |
| Tipos | mypy src/ | |
| Pruebas + cobertura | pytest --cov ... | ✅ 142 passed, cobertura 87 % (+1 %) |
| Complejidad | radon cc src -n C | |
| Seguridad | bandit -r src -ll ; pip-audit | |
| Mutación | mutmut run --paths-to-mutate ... | ✅ score 91 % |

<salidas crudas pegadas>

## Definition of Done
<checklist de §11 marcado>

## Riesgos, supuestos y deuda detectada
<lo que no se hizo y por qué; waivers propuestos>
```

**Regla de honestidad (P7):** un paso no ejecutado se reporta como ⏭️ **omitido** con su motivo.
Escribir ✅ sin haber ejecutado el comando es la violación más grave de este documento y anula
toda la confianza del sistema.

---

## Apéndice A — Instalación de herramientas

`requirements-dev.txt` sugerido:

```
pytest==8.1.1
pytest-cov==5.0.0
pytest-bdd==7.1.2
pytest-mock==3.14.0
pytest-timeout==2.3.1
pytest-randomly==3.15.0
freezegun==1.4.0
ruff==0.4.4
mypy==1.10.0
radon==6.0.1
bandit==1.7.8
pip-audit==2.7.3
mutmut==2.4.4
detect-secrets==1.5.0
pre-commit==3.7.1
```

```bash
python -m pip install -r requirements-dev.txt
pre-commit install        # activa el gate mínimo en cada commit
```

Configuración recomendada (`pyproject.toml`), a crear cuando se adopte el gate completo:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "C90", "N", "UP", "S", "A", "C4", "T20", "PL", "RUF"]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.pytest.ini_options]
testpaths = ["tests", "features"]
addopts = "-q --strict-markers --strict-config"
timeout = 60

[tool.coverage.run]
branch = true
source = ["src"]

[tool.mypy]
python_version = "3.11"
warn_unused_ignores = true
disallow_untyped_defs = true
```

---

## Apéndice B — Plantillas

### Test unitario canónico

```python
import pytest

from zones.zone_checker import ZoneChecker


class TestZoneCheckerPertenencia:
    def test_punto_dentro_del_poligono_retorna_verdadero(self) -> None:
        # Arrange
        zona = ZoneChecker(poligono=[(0, 0), (10, 0), (10, 10), (0, 10)])

        # Act
        resultado = zona.contiene(punto=(5, 5))

        # Assert
        assert resultado is True

    @pytest.mark.parametrize(
        "punto",
        [(-1, 5), (11, 5), (5, -1), (5, 11)],
        ids=["izquierda", "derecha", "abajo", "arriba"],
    )
    def test_punto_fuera_del_poligono_retorna_falso(self, punto: tuple[int, int]) -> None:
        zona = ZoneChecker(poligono=[(0, 0), (10, 0), (10, 10), (0, 10)])

        assert zona.contiene(punto=punto) is False

    def test_poligono_con_menos_de_tres_vertices_es_invalido(self) -> None:
        with pytest.raises(ValueError, match="al menos 3 vértices"):
            ZoneChecker(poligono=[(0, 0), (1, 1)])
```

### Steps de Gherkin canónicos

```python
from pytest_bdd import scenarios, given, when, then, parsers

scenarios("../reporte_eficiencia.feature")


@given(parsers.parse('un empleado registrado llamado "{nombre}"'), target_fixture="empleado")
def empleado(nombre: str, repositorio_empleados) -> Empleado:
    return repositorio_empleados.registrar(nombre)


@when("genero el reporte de eficiencia del día", target_fixture="reporte")
def generar_reporte(servicio_reportes, fecha_actual) -> Reporte:
    return servicio_reportes.generar_diario(fecha_actual)


@then(parsers.parse('la eficiencia de "{nombre}" es del {porcentaje:d} %'))
def verificar_eficiencia(reporte: Reporte, nombre: str, porcentaje: int) -> None:
    assert reporte.eficiencia_de(nombre) == porcentaje
```

---

## Cierre

> No confío en el código porque lo haya leído.
> Confío en el código porque **tuvo que superar todas estas restricciones y pruebas**.

Si una regla de este documento estorba, **no la rompas: propón cambiarla** en un PR aparte,
con argumentos y datos. Mientras esté escrita aquí, es ley.
