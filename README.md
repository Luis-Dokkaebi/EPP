# oficina_eficiencia

## Desarrollo

Las reglas de calidad están en `CLAUDE.md` (idéntico a `Agents.md`). Entorno con Python 3.11:

```bash
python -m pip install -r requirements-ci.txt -r requirements-dev.txt   # Linux
python -m pip install -r requirements.txt -r requirements-dev.txt      # Windows
pre-commit install   # formato, lint, arquitectura, gemelos, tamaño y secretos en cada commit
```

- Quality Gate completo: `scripts/quality_gate.sh` (Linux) o `scripts/quality_gate.ps1`
  (Windows). Con `--changed` / `-Changed` solo muta lo que cambió respecto a `GATE_BASE`
  (por defecto `origin/main`).
- Gate de licencias (en rojo hasta cerrar AC-001): `pre-commit run licencias --hook-stage manual`.
- Un falso positivo de secretos se marca con `# pragma: allowlist secret` o se audita con
  `detect-secrets audit .secrets.baseline`.
