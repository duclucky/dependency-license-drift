import json
from pathlib import Path

import pytest


CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "dependency_license_drift.py"
GEN = 10**18


def test_activate_covenant_locks_purse(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    direct_vm.value = 2 * GEN
    contract.activate_covenant(
        "cov-ua-parser",
        "ua-parser-js",
        "1.0.37",
        "Commercial SaaS product may not accept network-copyleft obligations.",
        4_102_444_800,
    )
    direct_vm.value = 0

    covenant = json.loads(contract.get_covenant("cov-ua-parser"))
    accounting = json.loads(contract.get_accounting())

    assert covenant["status"] == "ACTIVE"
    assert covenant["package_name"] == "ua-parser-js"
    assert covenant["baseline_version"] == "1.0.37"
    assert int(covenant["purse"]) == 2 * GEN
    assert contract.get_package_status("cov-ua-parser") == "ACTIVE"
    assert int(accounting["total_locked"]) == 2 * GEN


def test_activate_rejects_zero_value(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    direct_vm.value = 0
    with direct_vm.expect_revert("purse must be positive"):
        contract.activate_covenant(
            "cov-zero",
            "ua-parser-js",
            "1.0.37",
            "profile",
            4_102_444_800,
        )


def test_activate_rejects_duplicate_covenant(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    direct_vm.value = 2 * GEN
    contract.activate_covenant("cov-1", "ua-parser-js", "1.0.37", "profile", 4_102_444_800)
    with pytest.raises(Exception):
        contract.activate_covenant("cov-1", "ua-parser-js", "1.0.37", "profile", 4_102_444_800)
