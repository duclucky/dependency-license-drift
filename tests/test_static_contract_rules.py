from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "dependency_license_drift.py"
CHECK_SCRIPT = ROOT / "scripts" / "check.ps1"


def test_check_script_requires_project_contract_file() -> None:
    script = CHECK_SCRIPT.read_text(encoding="utf-8")

    assert "contracts/dependency_license_drift.py is missing" in script
    assert "Test-Path $ContractPath" in script
    assert "throw" in script


def test_contract_file_name_is_not_generic_contract_py() -> None:
    assert CONTRACT.name == "dependency_license_drift.py"
    assert not (ROOT / "contracts" / "contract.py").exists()
