$ErrorActionPreference = "Stop"

$ContractPath = "contracts/dependency_license_drift.py"
$PythonPath = ".venv/Scripts/python.exe"
$GltestPath = ".venv/Scripts/gltest.exe"

if (-not (Test-Path $ContractPath)) {
  throw "contracts/dependency_license_drift.py is missing"
}

if (Test-Path $PythonPath) {
  & $PythonPath scripts/ascii_header_check.py $ContractPath
} else {
  python scripts/ascii_header_check.py $ContractPath
}

genvm-lint check $ContractPath

if (Test-Path "tests") {
  if (Test-Path $PythonPath) {
    & $PythonPath -m pytest tests/test_static_contract_rules.py
  } else {
    python -m pytest tests/test_static_contract_rules.py
  }
}

if (Test-Path "tests/direct") {
  if (Test-Path $GltestPath) {
    & $GltestPath tests/direct
  } else {
    gltest tests/direct
  }
}

Write-Host "CHECK_OK"
