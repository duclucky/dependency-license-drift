$ErrorActionPreference = "Stop"

if (Test-Path "contracts/dependency_license_drift.py") {
  python scripts/ascii_header_check.py contracts/dependency_license_drift.py
  genvm-lint check contracts/dependency_license_drift.py
}

if (Test-Path "tests/direct") {
  gltest tests/direct
}

Write-Host "CHECK_OK"

