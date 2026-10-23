<#
.SYNOPSIS
Quality Gate de CLAUDE.md §10 en un solo comando, para Windows (SPEC/9 §0.3).

.DESCRIPTION
Equivalente de scripts/quality_gate.sh. Se detiene en el primer paso que falla y guarda cada
salida en $env:GATE_REPORTES\<paso>.txt (por defecto reports/gate). Un paso omitido nunca es
aprobado.

.EXAMPLE
pwsh scripts/quality_gate.ps1 -SinMutacion
#>
[CmdletBinding()]
param(
    [switch]$Changed,
    [switch]$SinInstalar,
    [switch]$SinMutacion
)

Set-Location (Join-Path $PSScriptRoot '..')
$Reportes = if ($env:GATE_REPORTES) { $env:GATE_REPORTES } else { 'reports/gate' }
$Base = if ($env:GATE_BASE) { $env:GATE_BASE } else { 'origin/main' }
$ModulosCriticos = @('src/security', 'src/storage', 'src/analysis/efficiency_calculator.py', 'src/zones/zone_checker.py')
New-Item -ItemType Directory -Force -Path $Reportes | Out-Null

function Invoke-Paso([string]$Nombre, [scriptblock]$Comando) {
    Write-Host "==> [$Nombre] $Comando"
    $archivo = Join-Path $Reportes "$Nombre.txt"
    $global:LASTEXITCODE = 0
    & $Comando *> $archivo
    $codigo = $global:LASTEXITCODE
    if ($codigo -eq 0) {
        Write-Host "    OK -> $archivo"
        return
    }
    Get-Content $archivo | Write-Host
    [Console]::Error.WriteLine("FALLA en el paso '$Nombre' (código $codigo). Corrige y reinicia desde el paso 1 (CLAUDE.md §10).")
    exit $codigo
}

function Write-Omitido([string]$Nombre, [string]$Motivo) {
    "==> [$Nombre] omitido: $Motivo" | Tee-Object -FilePath (Join-Path $Reportes "$Nombre.txt")
}

function Get-OpcionesDeCobertura {
    @('src', 'scripts', 'tools', 'ml') | Where-Object { Test-Path $_ } | ForEach-Object { "--cov=$_" }
}

function Get-PisoDeCobertura {
    python -c "import json; print(json.load(open('docs/quality/metricas.json'))['cobertura_global_minima'])"
}

function Get-PruebasDe([string]$Archivo) {
    # Convención de nombres: src/ppe/domain/asociacion.py -> tests/test_*asociacion*.py.
    if ($env:GATE_PRUEBAS_MUTACION) { return $env:GATE_PRUEBAS_MUTACION }
    $tema = [IO.Path]::GetFileNameWithoutExtension($Archivo)
    $pruebas = @(Get-ChildItem -Path tests -Filter "test_*$tema*.py" | ForEach-Object { "tests/$($_.Name)" })
    if ($pruebas.Count -eq 0) { return 'tests' }
    return ($pruebas -join ' ')
}

function Invoke-Mutacion([double]$Umbral, [string[]]$Objetivos, [string[]]$Parche = @()) {
    if ($Objetivos.Count -eq 0) {
        Write-Output "Sin código Python cambiado respecto de ${Base}: no hay mutantes que generar."
        return
    }
    Remove-Item -Force -ErrorAction SilentlyContinue .mutmut-cache
    foreach ($objetivo in $Objetivos) {
        if (Test-Path $objetivo) {
            $pruebas = Get-PruebasDe $objetivo
            mutmut run @Parche --paths-to-mutate $objetivo --runner "python scripts/ejecutar_pruebas_mutacion.py -x -q -p no:randomly -m 'not slow' $pruebas"
            # mutmut 2 combina bits: 2, 4 y 8 los evalúa check_mutacion.py; el bit 1 es un fallo de mutmut.
            if ($LASTEXITCODE -band 1) {
                Write-Output "mutmut falló al mutar $objetivo (código $LASTEXITCODE)."
                $global:LASTEXITCODE = 1
                return
            }
        }
    }
    if (Get-ChildItem -Path src, scripts -Recurse -Filter '*.py.bak') {
        Write-Output 'mutmut dejó código mutado (*.py.bak): restaura con git checkout y borra los .bak.'
        $global:LASTEXITCODE = 1
        return
    }
    mutmut results
    python scripts/check_mutacion.py .mutmut-cache $Umbral
}

if ($SinInstalar) {
    Write-Omitido '0-entorno' '-SinInstalar'
} else {
    Invoke-Paso '0-entorno' { python -m pip install -r requirements.txt -r requirements-dev.txt }
}
Invoke-Paso '1-formato' { ruff format --check . }
Invoke-Paso '2-lint' { ruff check . }
Invoke-Paso '2b-arquitectura' { python scripts/check_architecture.py .importlinter }
Invoke-Paso '3-tipos' { mypy }
$opcionesCobertura = Get-OpcionesDeCobertura
Invoke-Paso '4a-pruebas' {
    python -m pytest @opcionesCobertura --cov-branch --cov-report=term-missing --cov-report=xml
}
$piso = Get-PisoDeCobertura
Invoke-Paso '4b-cobertura-global' { python -m coverage report --include='src/*' --fail-under=$piso }
Invoke-Paso '4c-cobertura-diff' { diff-cover coverage.xml --compare-branch=$Base --fail-under=95 }
Invoke-Paso '5-complejidad' { python scripts/check_trinquete.py src docs/quality/metricas.json }
Invoke-Paso '6a-bandit' { bandit -r src -ll }
Invoke-Paso '6b-pip-audit' { pip-audit }
if ($SinMutacion) {
    Write-Omitido '7-mutacion' '-SinMutacion'
} elseif ($Changed) {
    $objetivos = @(git diff --name-only --diff-filter=AM "$Base...HEAD" -- 'src/*.py' 'scripts/*.py' 'tools/*.py' 'ml/*.py')
    # Solo se mutan las líneas que cambió el PR (mutmut --use-patch-file).
    $archivoParche = Join-Path $Reportes 'cambios.patch'
    git diff -U0 "$Base...HEAD" | Out-File -Encoding utf8 $archivoParche
    Invoke-Paso '7-mutacion' { Invoke-Mutacion 85 $objetivos @('--use-patch-file', $archivoParche) }
} else {
    Invoke-Paso '7-mutacion' { Invoke-Mutacion 90 $ModulosCriticos }
}
Invoke-Paso '8a-suite' { python -m pytest }
Invoke-Paso '8b-suite-sin-cache' { python -m pytest -p no:cacheprovider }
Invoke-Paso '9a-gemelos' {
    if ((Get-FileHash CLAUDE.md).Hash -ne (Get-FileHash Agents.md).Hash) {
        Write-Output 'CLAUDE.md y Agents.md difieren: copia uno sobre el otro en el mismo commit.'
        $global:LASTEXITCODE = 1
    }
}
Invoke-Paso '9b-waivers' { python scripts/check_waivers.py docs/quality/waivers.md }
Write-Host "Quality Gate en verde. Salidas en $Reportes/"
