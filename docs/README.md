# Mapa de la documentación

Índice del sistema de registro del repositorio (SPEC/9 §0.9, principio H1). Si agregas un documento,
enlázalo aquí: `tests/test_docs_indice.py` falla con enlaces rotos, ADR sin enlazar o documentos de
calidad sin enlazar.

## Reglas y proceso

- [CLAUDE.md](../CLAUDE.md) — constitución de calidad (idéntica a [Agents.md](../Agents.md)).
- [README.md](../README.md) — preparación del entorno de desarrollo, pre-commit y Quality Gate.
- [.github/workflows/quality-gate.yml](../.github/workflows/quality-gate.yml) — CI (Windows + Linux).

## Especificaciones (`SPEC/`)

- [Plan EPP y licencia](../SPEC/9_PLAN_EPP_Y_LICENCIA.md) — plan vigente (fases 0 a 9, §17 orden de
  entregas, §19 verificación).
- [Hallazgos de revisión](../SPEC/0_REVIEW_FINDINGS.md),
  [especificaciones](../SPEC/1_SPECIFICATIONS.md), [planificación](../SPEC/2_PLANNING.md),
  [tareas](../SPEC/3_TASKS.md), [implementación](../SPEC/4_IMPLEMENTATION.md),
  [revisión](../SPEC/5_REVIEW.md), [guía de llaves](../SPEC/6_KEYGEN_GUIDE.md),
  [build y release](../SPEC/7_BUILD_RELEASE.md),
  [revisión de código de producción](../SPEC/8_PRODUCTION_CODE_REVIEW.md) — documentos heredados.

## Decisiones de arquitectura (`docs/adr/`)

- [Plantilla de ADR](adr/plantilla.md)
- [ADR-001: Motor de IA con licencia Apache/MIT](adr/001-motor-ia.md) — provisional hasta A-13.

## Benchmarks (`docs/benchmarks/`)

- [Motores de IA](benchmarks/motor_ia.md) — bitácora de A-13 que cierra ADR-001 (bloqueada por D2).

## Calidad (`docs/quality/`)

- [Progreso del plan](quality/progreso.md) — entregas terminadas, en curso y bloqueadas.
- [Línea base 2026-10](quality/linea_base_2026-10.md) — métricas al adoptar el gate.
- [Waivers](quality/waivers.md) — excepciones del código heredado, con issue y caducidad.
- [Mutantes equivalentes](quality/mutantes_equivalentes.md) — justificación uno por uno.
- [Lecciones de los agentes](quality/lecciones_agentes.md) — cada error convertido en mecanismo.
- [Métricas del trinquete](quality/metricas.json) — pisos que solo pueden subir.

## Licencias y modelos

- [Licencias revisadas](legal/licencias_revisadas.json) — aprobaciones humanas del gate de
  licencias (las propuestas sin `aprobado_por` no cuentan).
- [Manifiesto de modelos](../models/manifest.json) — hash y licencias de cada modelo distribuido.
- [Expediente para la revisión legal (D9)](legal/revision_d9.md) — hechos y decisiones humanas
  pendientes antes del release (no es asesoría legal).

## Seguridad

- [Auditoría de seguridad](security_audit_report.md) — informe heredado.
