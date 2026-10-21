# Skills de terceros — procedencia, selección y licencias

Las carpetas de `.claude/skills/` y los tres agentes `cavecrew-*` de `.claude/agents/` son
**copias literales** de los repositorios hermanos listados abajo. No se editan aquí: para
actualizarlas se vuelven a copiar desde el repositorio de origen y se actualiza el commit de
esta tabla.

| Origen | Commit | Skills conservadas | Licencia |
|--------|--------|--------------------|----------|
| [Luis-Dokkaebi/caveman](https://github.com/Luis-Dokkaebi/caveman) | `df2ccd8` | 10 de 20 (+ 3 agentes) | MIT (Julius Brussee) |
| [Luis-Dokkaebi/ECC](https://github.com/Luis-Dokkaebi/ECC) | `68e926b` | 8 de 270 | MIT (Affaan Mustafa) |
| [Luis-Dokkaebi/hallmark](https://github.com/Luis-Dokkaebi/hallmark) | `aeb42fb` | 0 de 1 | MIT (Hallmark contributors) |

## Criterio de selección

Se conserva una skill solo si aplica a este proyecto (aplicación de escritorio Windows en
Python 3.11 con visión por computadora, SQLite cifrado y reportes Excel) y no contradice
`CLAUDE.md`. Se descartan las que cumplen cualquiera de estas condiciones:

- Otro lenguaje o stack: web/React/Vue, Java, Kotlin, Swift, Go, Rust, PHP, Perl, .NET,
  Docker/Kubernetes, bases de datos de servidor.
- Otro dominio: finanzas, logística, salud, redes/homelab, marketing, redes sociales, video.
- Dependen de algo que este repo no tiene: agentes, hooks o comandos de ECC; servidores MCP;
  CLI o cuenta de Caveman Cloud; servicios externos de pago.
- Contradicen la constitución: `caveman-commit` (formato de commit distinto al de §12),
  `caveman-compress` (reescribiría `CLAUDE.md`/`Agents.md`, normativos y gemelos),
  `tdd-workflow`, `verification-loop` y `git-workflow` (umbrales y convenciones que chocan con
  §2, §6, §10 y §12), `security-review` (orientada a web y con el mismo nombre que el comando
  integrado `/security-review`).
- `hallmark`: diseño de páginas web; la interfaz de este proyecto es `customtkinter`.

## Skills conservadas

### caveman

| Skill | Para qué sirve aquí |
|-------|---------------------|
| `caveman` | Modo de respuesta comprimida, a petición (`/caveman`). |
| `caveman-review` | Revisión de código en una línea por hallazgo. |
| `caveman-explore` | Exploración de solo lectura con citas `ruta:línea`. |
| `cavecrew` | Cuándo delegar en los agentes `cavecrew-*` de `.claude/agents/`. |
| `investigate-first` | Diagnosticar fallos ambiguos (p. ej. fugas en workers de cámara) antes de editar. |
| `surgical-patch` | Corregir bugs en la capa responsable con prueba de regresión (§2, regla del bug). |
| `safe-refactor` | Refactorizar sin cambiar comportamiento, con verificación antes y después (P3). |
| `lean-build` | Funcionalidad nueva con alcance mínimo y condición de parada explícita (P6). |
| `migration` | Migraciones de esquema/datos de SQLite reversibles y verificadas. |
| `verify-and-stop` | Validar trabajo existente contra criterios de aceptación sin ampliar alcance. |

### ECC

| Skill | Para qué sirve aquí |
|-------|---------------------|
| `python-patterns` | Idioms de Python, type hints y PEP 8 (§3). |
| `python-testing` | pytest, fixtures, mocks, parametrización y cobertura (§4, §6). |
| `error-handling` | Excepciones tipadas, reintentos y errores de cara al usuario (§3). |
| `intent-driven-development` | Criterios de aceptación verificables antes de implementar (§5, §17). |
| `hexagonal-architecture` | Puertos y adaptadores para que el dominio no importe `cv2`/`ultralytics` (§16). |
| `windows-desktop-e2e` | Pruebas E2E de la app de escritorio Windows con pywinauto. |
| `mle-workflow` | Contratos de datos, evaluación y empaquetado de los modelos de detección y rostro. |
| `benchmark-optimization-loop` | Optimizar el pipeline de cámaras o la exportación con mediciones y pruebas en verde. |

## Dependencias externas conocidas

- `cavecrew` delega en los agentes de `.claude/agents/cavecrew-*.md`.
- `lean-build` menciona el "Native Core" de caveman, que no se distribuye como skill.
- Algunos `README.md` enlazan rutas relativas del repo de origen (`../../README.md`) que no
  existen aquí.

## Textos de licencia

### caveman

```text
Scope note: this MIT license covers this repository except Engine-linked
directories listed in LICENSING.md (engine/, proxy/, cacheengine/, rewriter/,
browse/, mcp/, shrink/, cavemem Go core, shared/platform/), which are licensed
under Business Source License 1.1 — see LICENSE.BSL. New Engine-linked runtime
modules default to BSL-1.1 unless explicitly classified as MIT.

MIT License

Copyright (c) 2026 Julius Brussee

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### ECC

```text
MIT License

Copyright (c) 2026 Affaan Mustafa

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
