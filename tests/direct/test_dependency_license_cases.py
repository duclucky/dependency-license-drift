import json
import sys
from datetime import datetime, timezone
from pathlib import Path


CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "dependency_license_drift.py"
GEN = 10**18


def set_time(vm, timestamp: int) -> None:
    timestamp_text = datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")
    vm.warp(timestamp_text)
    gl_module = sys.modules.get("genlayer.gl")
    if gl_module is not None and getattr(gl_module, "message_raw", None) is not None:
        gl_module.message_raw["datetime"] = timestamp_text


def _deploy_and_activate(direct_vm, direct_deploy, sponsor, covenant_id="cov-1", expiry=4_102_444_800):
    set_time(direct_vm, 0)
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = sponsor
    direct_vm.value = 2 * GEN
    contract.activate_covenant(
        covenant_id,
        "ua-parser-js",
        "1.0.37",
        "Commercial SaaS may not accept AGPL or network-copyleft obligations.",
        expiry,
    )
    direct_vm.value = 0
    return contract


def test_open_case_locks_challenge_bond(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy_and_activate(direct_vm, direct_deploy, direct_alice)

    direct_vm.sender = direct_bob
    direct_vm.value = 1 * GEN
    contract.open_case("cov-1", "case-1", "2.0.0")
    direct_vm.value = 0

    case = json.loads(contract.get_case("case-1"))
    covenant = json.loads(contract.get_covenant("cov-1"))
    accounting = json.loads(contract.get_accounting())

    assert case["status"] == "CASE_OPEN"
    assert case["covenant_id"] == "cov-1"
    assert case["target_version"] == "2.0.0"
    assert int(case["challenge_bond"]) == 1 * GEN
    assert covenant["active_case_id"] == "case-1"
    assert contract.get_package_status("cov-1") == "CASE_OPEN"
    assert int(accounting["total_locked"]) == 3 * GEN


def test_duplicate_active_case_rejects(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy_and_activate(direct_vm, direct_deploy, direct_alice)

    direct_vm.sender = direct_bob
    direct_vm.value = 1 * GEN
    contract.open_case("cov-1", "case-1", "2.0.0")
    with direct_vm.expect_revert("active case exists"):
        contract.open_case("cov-1", "case-2", "2.0.4")


def test_open_case_rejects_at_expiry_with_stale_active_phase(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = _deploy_and_activate(direct_vm, direct_deploy, direct_alice, "cov-exp", expiry=100)

    set_time(direct_vm, 100)
    direct_vm.sender = direct_bob
    direct_vm.value = 1 * GEN
    with direct_vm.expect_revert("covenant expired"):
        contract.open_case("cov-exp", "case-exp", "2.0.0")
    direct_vm.value = 0

    assert contract.get_package_status("cov-exp") == "ACTIVE"
    assert int(json.loads(contract.get_accounting())["total_locked"]) == 2 * GEN


def test_close_expired_rejects_before_expiry_and_works_at_equality(
    direct_vm, direct_deploy, direct_alice
):
    contract = _deploy_and_activate(direct_vm, direct_deploy, direct_alice, "cov-close", expiry=100)

    set_time(direct_vm, 99)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("covenant not expired"):
        contract.close_expired("cov-close")

    set_time(direct_vm, 100)
    contract.close_expired("cov-close")

    assert contract.get_package_status("cov-close") == "CLOSED"
    assert int(json.loads(contract.get_accounting())["total_locked"]) == 0


def test_sponsor_can_cancel_active_covenant_before_expiry(direct_vm, direct_deploy, direct_alice):
    contract = _deploy_and_activate(direct_vm, direct_deploy, direct_alice, "cov-cancel", expiry=100)

    set_time(direct_vm, 50)
    direct_vm.sender = direct_alice
    contract.cancel_covenant("cov-cancel")

    covenant = json.loads(contract.get_covenant("cov-cancel"))
    credit = json.loads(contract.get_credit(direct_alice))
    accounting = json.loads(contract.get_accounting())

    assert covenant["status"] == "CLOSED"
    assert int(covenant["purse"]) == 0
    assert int(credit["credit"]) == 2 * GEN
    assert int(accounting["total_locked"]) == 0


def test_cancel_active_covenant_rejects_wrong_caller_and_open_case(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = _deploy_and_activate(direct_vm, direct_deploy, direct_alice, "cov-guard", expiry=100)

    set_time(direct_vm, 50)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("unauthorized"):
        contract.cancel_covenant("cov-guard")

    direct_vm.value = 1 * GEN
    contract.open_case("cov-guard", "case-guard", "2.0.0")
    direct_vm.value = 0
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("active case exists"):
        contract.cancel_covenant("cov-guard")
