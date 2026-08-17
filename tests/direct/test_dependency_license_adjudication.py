import json
from pathlib import Path

import pytest


CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "dependency_license_drift.py"
GEN = 10**18


def _activate_and_open(direct_vm, direct_deploy, sponsor, challenger, case_id="case-1"):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = sponsor
    direct_vm.value = 2 * GEN
    contract.activate_covenant(
        "cov-1",
        "ua-parser-js",
        "1.0.37",
        "Commercial SaaS may not accept AGPL or network-copyleft obligations.",
        4_102_444_800,
    )
    direct_vm.sender = challenger
    direct_vm.value = 1 * GEN
    contract.open_case("cov-1", case_id, "2.0.0")
    direct_vm.value = 0
    return contract


def _mock_mit_to_agpl(vm, llm_result):
    vm.mock_web(
        r"https://registry\.npmjs\.org/ua-parser-js/1\.0\.37",
        {
            "method": "GET",
            "status": 200,
            "body": '{"name":"ua-parser-js","version":"1.0.37","license":"MIT"}',
        },
    )
    vm.mock_web(
        r"https://registry\.npmjs\.org/ua-parser-js/2\.0\.0",
        {
            "method": "GET",
            "status": 200,
            "body": '{"name":"ua-parser-js","version":"2.0.0","license":"AGPL-3.0-or-later"}',
        },
    )
    vm.mock_web(
        r"https://spdx\.org/licenses/MIT\.json",
        {
            "method": "GET",
            "status": 200,
            "body": (
                '{"licenseId":"MIT","name":"MIT License",'
                '"isDeprecatedLicenseId":false,"licenseText":"Permission is hereby granted."}'
            ),
        },
    )
    vm.mock_web(
        r"https://spdx\.org/licenses/AGPL-3\.0-or-later\.json",
        {
            "method": "GET",
            "status": 200,
            "body": (
                '{"licenseId":"AGPL-3.0-or-later","name":"GNU Affero GPL v3.0 or later",'
                '"isDeprecatedLicenseId":false,'
                '"licenseText":"network interaction source disclosure terms"}'
            ),
        },
    )
    vm.mock_llm(
        r"(?s).*Dependency License Drift semantic reviewer.*",
        json.dumps(llm_result),
    )


def drift_result():
    return {
        "verdict": "DRIFT_CONFIRMED",
        "baseline_license_ids": ["MIT"],
        "target_license_ids": ["AGPL-3.0-or-later"],
        "obligation_classes": ["NETWORK_COPYLEFT", "SOURCE_DISCLOSURE"],
        "source_coverage": "COMPLETE",
        "consequence_class": "REVIEW_REQUIRED",
        "reason": "Target version adds network-copyleft obligations.",
    }


def test_mit_to_agpl_confirms_drift(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _activate_and_open(direct_vm, direct_deploy, direct_alice, direct_bob)
    _mock_mit_to_agpl(direct_vm, drift_result())

    contract.adjudicate_case("case-1")

    verdict = json.loads(contract.get_verdict("case-1"))
    case = json.loads(contract.get_case("case-1"))
    challenger_credit = json.loads(contract.get_credit(direct_bob))
    accounting = json.loads(contract.get_accounting())

    assert verdict["verdict"] == "DRIFT_CONFIRMED"
    assert verdict["baseline_license_ids"] == "MIT"
    assert verdict["target_license_ids"] == "AGPL-3.0-or-later"
    assert case["status"] == "DRIFT_CONFIRMED"
    assert contract.get_package_status("cov-1") == "REVIEW_REQUIRED"
    assert int(challenger_credit["credit"]) == 3 * GEN
    assert int(accounting["total_locked"]) == 0


def test_invalid_llm_verdict_reverts_without_accounting_change(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = _activate_and_open(direct_vm, direct_deploy, direct_alice, direct_bob)
    bad = drift_result()
    bad["verdict"] = "PAY_CHALLENGER"
    _mock_mit_to_agpl(direct_vm, bad)

    before = json.loads(contract.get_accounting())
    with direct_vm.expect_revert("invalid verdict"):
        contract.adjudicate_case("case-1")

    assert json.loads(contract.get_accounting()) == before
    assert contract.get_package_status("cov-1") == "CASE_OPEN"


def test_extra_llm_license_id_reverts_without_accounting_change(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = _activate_and_open(direct_vm, direct_deploy, direct_alice, direct_bob)
    bad = drift_result()
    bad["target_license_ids"] = ["AGPL-3.0-or-later", "GPL-3.0-only"]
    _mock_mit_to_agpl(direct_vm, bad)

    before = json.loads(contract.get_accounting())
    with direct_vm.expect_revert("target license mismatch"):
        contract.adjudicate_case("case-1")

    assert json.loads(contract.get_accounting()) == before


def test_unavailable_source_is_retryable_and_non_penalizing(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = _activate_and_open(direct_vm, direct_deploy, direct_alice, direct_bob)
    direct_vm.mock_web(r".*", {"method": "GET", "status": 503, "body": ""})
    direct_vm.mock_llm(r".*", json.dumps(drift_result()))

    contract.adjudicate_case("case-1")

    verdict = json.loads(contract.get_verdict("case-1"))
    case = json.loads(contract.get_case("case-1"))
    accounting = json.loads(contract.get_accounting())

    assert verdict["verdict"] == "UNVERIFIABLE"
    assert verdict["source_coverage"] == "UNAVAILABLE"
    assert case["status"] == "RETRYABLE"
    assert contract.get_package_status("cov-1") == "RETRYABLE"
    assert int(accounting["total_locked"]) == 3 * GEN
    assert int(json.loads(contract.get_credit(direct_bob))["credit"]) == 0
