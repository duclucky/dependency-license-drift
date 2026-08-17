$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

function Assert-Success($Label) {
  if ($LASTEXITCODE -ne 0) {
    throw "$Label failed with exit code $LASTEXITCODE"
  }
}

$ContractPath = "contracts/dependency_license_drift.py"
$PythonPath = ".venv/Scripts/python.exe"
$GenvmLintPath = ".venv/Scripts/genvm-lint.exe"
$GltestPath = ".venv/Scripts/gltest.exe"

if (-not (Test-Path $ContractPath)) {
  throw "contracts/dependency_license_drift.py is missing"
}

if (Test-Path $PythonPath) {
  & $PythonPath scripts/ascii_header_check.py $ContractPath
  Assert-Success "ascii_header_check"
} else {
  python scripts/ascii_header_check.py $ContractPath
  Assert-Success "ascii_header_check"
}

if (Test-Path $GenvmLintPath) {
  & $GenvmLintPath check $ContractPath
  Assert-Success "genvm-lint"
} else {
  genvm-lint check $ContractPath
  Assert-Success "genvm-lint"
}

if (Test-Path "tests") {
  if (Test-Path $PythonPath) {
    & $PythonPath -m pytest tests/test_static_contract_rules.py
    Assert-Success "static pytest"
  } else {
    python -m pytest tests/test_static_contract_rules.py
    Assert-Success "static pytest"
  }
}

if (Test-Path "tests/direct") {
  if (Test-Path $GltestPath) {
    & $GltestPath tests/direct
    Assert-Success "direct gltest"
  } else {
    gltest tests/direct
    Assert-Success "direct gltest"
  }
}

Write-Host "CHECK_OK"
