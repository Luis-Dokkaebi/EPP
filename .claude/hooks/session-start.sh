#!/bin/bash
# SessionStart para sesiones de Claude Code en la nube (SPEC/9 §0.6, principio H8).
# Instala Python 3.11, el runtime instalable en Linux (requirements-ci.txt), las herramientas
# de calidad (requirements-dev.txt) y PowerShell 7 (prueba de scripts/quality_gate.ps1) en
# .venv, y deja ese entorno activo para la sesión. Idempotente: si todo está, no reinstala.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
    exit 0
fi

cd "${CLAUDE_PROJECT_DIR:?}"
VERSION_UV="0.11.32"
VERSION_PWSH="7.4.6"

command -v uv >/dev/null 2>&1 || python3 -m pip install --user "uv==${VERSION_UV}"
uv python install 3.11
[ -x .venv/bin/python ] || uv venv -p 3.11 .venv
uv pip install --python .venv/bin/python --index-strategy unsafe-best-match \
    -r requirements-ci.txt -r requirements-dev.txt

if ! command -v pwsh >/dev/null 2>&1 && [ ! -x .venv/pwsh/pwsh ]; then
    mkdir -p .venv/pwsh
    curl -sSL "https://github.com/PowerShell/PowerShell/releases/download/v${VERSION_PWSH}/powershell-${VERSION_PWSH}-linux-x64.tar.gz" \
        | tar xz -C .venv/pwsh
    chmod +x .venv/pwsh/pwsh
fi
[ -x .venv/pwsh/pwsh ] && ln -sf "$PWD/.venv/pwsh/pwsh" .venv/bin/pwsh

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
    echo "export VIRTUAL_ENV=\"$PWD/.venv\"" >>"$CLAUDE_ENV_FILE"
    echo "export PATH=\"$PWD/.venv/bin:\$PATH\"" >>"$CLAUDE_ENV_FILE"
fi
