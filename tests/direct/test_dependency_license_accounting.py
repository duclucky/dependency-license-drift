import json
from pathlib import Path


CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "dependency_license_drift.py"
GEN = 10**18


def to_hex(address) -> str:
    if hasattr(address, "as_hex"):
        return address.as_hex
    if isinstance(address, bytes):
        return "0x" + address.hex()
    return str(address)


def _activate_and_open(direct_vm, direct_deploy, sponsor, challenger):
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
    contract.open_case("cov-1", "case-1", "2.0.0")
    direct_vm.value = 0
    return contract


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


def _mock_mit_to_agpl(vm):
    vm.mock_web(
        r"https://registry\.npmjs\.org/ua-parser-js/1\.0\.37",
        {"method": "GET", "status": 200, "body": '{"name":"ua-parser-js","version":"1.0.37","license":"MIT"}'},
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
            "body": '{"licenseId":"MIT","isDeprecatedLicenseId":false,"licenseText":"Permission."}',
        },
    )
    vm.mock_web(
        r"https://spdx\.org/licenses/AGPL-3\.0-or-later\.json",
        {
            "method": "GET",
            "status": 200,
            "body": (
                '{"licenseId":"AGPL-3.0-or-later","isDeprecatedLicenseId":false,'
                '"licenseText":"network interaction source disclosure terms"}'
            ),
        },
    )
    vm.mock_llm(r"(?s).*Dependency License Drift semantic reviewer.*", json.dumps(drift_result()))


def test_withdraw_rejects_without_credit(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("no credit"):
        contract.withdraw_credit()


def test_accounting_view_has_zero_credit_for_unknown(direct_deploy, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    credit = json.loads(contract.get_credit(direct_charlie))
    assert credit["account"] == to_hex(direct_charlie).lower()
    assert int(credit["credit"]) == 0


def test_withdrawal_debits_before_external_send(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _activate_and_open(direct_vm, direct_deploy, direct_alice, direct_bob)
    _mock_mit_to_agpl(direct_vm)
    contract.adjudicate_case("case-1")

    sends = []

    def capture_send(vm, request):
        post = request["EthSend"]
        sends.append({"address": post["address"], "value": post["value"], "calldata": post["calldata"]})
        return {"ok": None}

    direct_vm._gl_call_hook = capture_send
    direct_vm.sender = direct_bob
    contract.withdraw_credit()

    assert int(sends[0]["value"]) == 3 * GEN
    assert sends[0]["address"].as_hex.lower() == to_hex(direct_bob).lower()
    assert sends[0]["calldata"] == b""
    assert int(json.loads(contract.get_credit(direct_bob))["credit"]) == 0
    assert int(json.loads(contract.get_accounting())["total_credits"]) == 0
    with direct_vm.expect_revert("no credit"):
        contract.withdraw_credit()
