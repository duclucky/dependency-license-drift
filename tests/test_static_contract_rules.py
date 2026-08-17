from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "dependency_license_drift.py"
CHECK_SCRIPT = ROOT / "scripts" / "check.ps1"


def test_check_script_requires_project_contract_file() -> None:
    script = CHECK_SCRIPT.read_text(encoding="utf-8")

    assert "contracts/dependency_license_drift.py is missing" in script
    assert "Test-Path $ContractPath" in script
    assert "throw" in script


def test_check_script_fails_on_native_command_errors() -> None:
    script = CHECK_SCRIPT.read_text(encoding="utf-8")

    assert '$env:PYTHONUTF8 = "1"' in script
    assert "function Assert-Success" in script
    assert "$LASTEXITCODE" in script


def test_contract_file_name_is_not_generic_contract_py() -> None:
    assert CONTRACT.name == "dependency_license_drift.py"
    assert not (ROOT / "contracts" / "contract.py").exists()


def test_contract_source_is_ascii() -> None:
    data = CONTRACT.read_bytes()
    assert all(byte < 128 for byte in data)


def test_contract_header_order() -> None:
    lines = CONTRACT.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# v")
    assert '"Depends": "py-genlayer:' in lines[1]
    assert lines[2] == "from genlayer import *"


def test_value_entrypoints_are_payable() -> None:
    source = CONTRACT.read_text(encoding="utf-8")
    for method in ("activate_covenant", "open_case"):
        marker = f"def {method}("
        assert marker in source
        prefix = source[: source.index(marker)]
        nearby = [line.strip() for line in prefix.splitlines()[-3:]]
        assert "@gl.public.write.payable" in nearby


def test_no_claimant_evidence_settlement_terms() -> None:
    source = CONTRACT.read_text(encoding="utf-8")
    forbidden = ["githubusercontent", "screenshot", "claimant_url", "sha256_only"]
    assert not any(term in source for term in forbidden)
