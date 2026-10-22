#!/usr/bin/env bash
# Quality Gate de CLAUDE.md §10 en un solo comando (SPEC/9 §0.3).
#
# Uso: scripts/quality_gate.sh [--changed] [--sin-instalar] [--sin-mutacion]
#   --changed       muta solo los archivos de src/ cambiados respecto de $GATE_BASE
#   --sin-instalar  no reinstala dependencias (paso 0 queda como omitido)
#   --sin-mutacion  no corre mutmut (paso 7 queda como omitido; CI lo corre en otro job)
#
# Se detiene en el primer paso que falla. Cada salida queda en $GATE_REPORTES/<paso>.txt
# (por defecto reports/gate/), lista para pegar en el PR. Un paso omitido nunca es aprobado.
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ" || exit 1
REPORTES="${GATE_REPORTES:-reports/gate}"
BASE="${GATE_BASE:-origin/main}"
MODULOS_CRITICOS="src/security src/storage src/analysis/efficiency_calculator.py src/zones/zone_checker.py"
UMBRAL_MUTACION_CRITICA=90
UMBRAL_MUTACION_NUEVA=85
UMBRAL_COBERTURA_DIFF=95

CAMBIADOS=0
PARCHE=()
INSTALAR=1
MUTACION=1
for opcion in "$@"; do
    case "$opcion" in
        --changed) CAMBIADOS=1 ;;
        --sin-instalar) INSTALAR=0 ;;
        --sin-mutacion) MUTACION=0 ;;
        *) echo "Opción desconocida: $opcion" >&2; exit 2 ;;
    esac
done
mkdir -p "$REPORTES"

paso() {
    local nombre="$1"
    shift
    echo "==> [$nombre] $*"
    "$@" >"$REPORTES/$nombre.txt" 2>&1
    local codigo=$?
    if [ "$codigo" -eq 0 ]; then
        echo "    OK -> $REPORTES/$nombre.txt"
        return 0
    fi
    cat "$REPORTES/$nombre.txt"
    echo "FALLA en el paso '$nombre' (código $codigo). Corrige y reinicia desde el paso 1 (CLAUDE.md §10)." >&2
    exit "$codigo"
}

omitido() {
    echo "==> [$1] omitido: $2" | tee "$REPORTES/$1.txt"
}

con_pantalla() {
    # La GUI heredada (Tk) necesita un display; en Linux sin escritorio se usa Xvfb.
    if [ -z "${DISPLAY:-}" ] && command -v xvfb-run >/dev/null 2>&1; then
        xvfb-run -a "$@"
    else
        "$@"
    fi
}

revisar_secretos() {
    # -z: los nombres versionados con espacios o acentos llegan intactos a detect-secrets.
    git ls-files -z | xargs -0 detect-secrets-hook --baseline .secrets.baseline
}

paquetes_medidos() {
    local paquete
    for paquete in src scripts tools ml .claude/hooks; do
        [ -d "$paquete" ] && printf -- "--cov=%s " "$paquete"
    done
}

piso_de_cobertura() {
    python -c "import json; print(json.load(open('docs/quality/metricas.json'))['cobertura_global_minima'])"
}

objetivos_de_mutacion() {
    if [ "$CAMBIADOS" = 1 ]; then
        git diff --name-only --diff-filter=AM "$BASE"...HEAD -- 'src/*.py' 'scripts/*.py' 'tools/*.py' 'ml/*.py' '.claude/hooks/*.py'
    else
        echo "$MODULOS_CRITICOS"
    fi
}

pruebas_de() {
    # Convención de nombres: src/ppe/domain/asociacion.py -> tests/test_*asociacion*.py.
    # Sin coincidencias se usa toda la suite; $GATE_PRUEBAS_MUTACION la reemplaza.
    local tema
    tema="$(basename "$1" .py)"
    if [ -n "${GATE_PRUEBAS_MUTACION:-}" ]; then
        echo "$GATE_PRUEBAS_MUTACION"
        return
    fi
    compgen -G "tests/test_*${tema}*.py" | tr '\n' ' ' | grep . || echo "tests"
}

mutar() {
    local umbral="$1"
    shift
    local objetivo codigo fallo=0
    if [ "$#" -eq 0 ]; then
        echo "Sin código Python cambiado respecto de $BASE: no hay mutantes que generar."
        return 0
    fi
    for objetivo in "$@"; do
        [ -e "$objetivo" ] || continue
        # Caché nueva por objetivo: mutmut reutiliza el tiempo base de la corrida anterior y,
        # si las pruebas de este objetivo son más lentas, marca como timeout mutantes que mueren.
        rm -f .mutmut-cache
        con_pantalla mutmut run "${PARCHE[@]}" --paths-to-mutate "$objetivo" \
            --runner "python scripts/ejecutar_pruebas_mutacion.py -x -q -p no:randomly -m 'not slow' $(pruebas_de "$objetivo")"
        codigo=$?
        # mutmut 2 combina bits: 2 sobrevivientes, 4 timeouts, 8 sospechosos (los evalúa
        # check_mutacion.py); el bit 1 significa que mutmut mismo falló.
        if (( codigo & 1 )); then
            echo "mutmut falló al mutar $objetivo (código $codigo): revisa la salida de arriba."
            return 1
        fi
        if find src scripts tools ml .claude/hooks -name '*.py.bak' 2>/dev/null | grep -q .; then
            echo "mutmut dejó código mutado (*.py.bak): restaura con git checkout y borra los .bak."
            return 1
        fi
        mutmut results
        python scripts/check_mutacion.py .mutmut-cache "$umbral" || fallo=1
    done
    return "$fallo"
}

if [ "$INSTALAR" = 1 ]; then
    paso 0-entorno python -m pip install -r requirements-ci.txt -r requirements-dev.txt
else
    omitido 0-entorno "--sin-instalar"
fi
paso 1-formato ruff format --check .
paso 2-lint ruff check .
paso 2b-arquitectura python scripts/check_architecture.py .importlinter
paso 3-tipos mypy
# shellcheck disable=SC2046  # paquetes_medidos devuelve varias opciones a propósito
paso 4a-pruebas con_pantalla python -m pytest $(paquetes_medidos) --cov-branch \
    --cov-report=term-missing --cov-report=xml
paso 4b-cobertura-global python -m coverage report --include='src/*' \
    --fail-under="$(piso_de_cobertura)"
paso 4c-cobertura-diff diff-cover coverage.xml --compare-branch="$BASE" \
    --fail-under="$UMBRAL_COBERTURA_DIFF"
paso 5-complejidad python scripts/check_trinquete.py src docs/quality/metricas.json
paso 5b-tamano python scripts/check_tamano.py
paso 6a-bandit bandit -r src -ll
paso 6b-pip-audit pip-audit
paso 6c-secretos revisar_secretos
if [ "$MUTACION" = 0 ]; then
    omitido 7-mutacion "--sin-mutacion"
elif [ "$CAMBIADOS" = 1 ]; then
    # Solo se mutan las líneas que cambió el PR (mutmut --use-patch-file).
    git diff -U0 "$BASE"...HEAD >"$REPORTES/cambios.patch"
    PARCHE=(--use-patch-file "$REPORTES/cambios.patch")
    # shellcheck disable=SC2046
    paso 7-mutacion mutar "$UMBRAL_MUTACION_NUEVA" $(objetivos_de_mutacion)
else
    # shellcheck disable=SC2046
    paso 7-mutacion mutar "$UMBRAL_MUTACION_CRITICA" $(objetivos_de_mutacion)
fi
paso 8a-suite con_pantalla python -m pytest
paso 8b-suite-sin-cache con_pantalla python -m pytest -p no:cacheprovider
paso 9a-gemelos cmp CLAUDE.md Agents.md
paso 9b-waivers python scripts/check_waivers.py docs/quality/waivers.md
echo "Quality Gate en verde. Salidas en $REPORTES/"
