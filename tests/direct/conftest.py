from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from gltest.direct.loader import deploy_contract


DIRECT_SDK_VERSION = "v0.2.16"


def _install_windows_stdin_patch() -> None:
    if os.name != "nt":
        return

    from gltest.direct import loader
    from gltest.direct.vm import VMContext

    if getattr(loader, "_dependency_license_drift_windows_stdin_patch", False):
        return

    def inject_message_to_fd0(vm: VMContext) -> None:
        from genlayer.py import calldata
        from genlayer.py.types import Address

        sender = Address(vm.sender) if isinstance(vm.sender, bytes) else vm.sender
        contract = Address(vm._contract_address) if isinstance(vm._contract_address, bytes) else vm._contract_address
        origin = Address(vm.origin) if isinstance(vm.origin, bytes) else vm.origin
        encoded = calldata.encode(
            {
                "contract_address": contract,
                "sender_address": sender,
                "origin_address": origin,
                "stack": [],
                "value": vm._value,
                "datetime": vm._datetime,
                "is_init": False,
                "chain_id": vm._chain_id,
                "entry_kind": 0,
                "entry_data": b"",
                "entry_stage_data": None,
            }
        )

        fd, path = tempfile.mkstemp()
        try:
            os.write(fd, encoded)
            os.lseek(fd, 0, os.SEEK_SET)
            vm._original_stdin_fd = os.dup(0)
            os.dup2(fd, 0)
            vm._dependency_license_drift_stdin_temp_path = path
        finally:
            os.close(fd)

    original_cleanup = VMContext._cleanup_after_deactivate

    def cleanup_after_deactivate(self: VMContext) -> None:
        try:
            original_cleanup(self)
        finally:
            path = getattr(self, "_dependency_license_drift_stdin_temp_path", None)
            if path:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
                self._dependency_license_drift_stdin_temp_path = None

    loader._inject_message_to_fd0 = inject_message_to_fd0
    loader._dependency_license_drift_windows_stdin_patch = True
    VMContext._cleanup_after_deactivate = cleanup_after_deactivate


_install_windows_stdin_patch()


@pytest.fixture
def direct_deploy(direct_vm):
    def _deploy(contract_path: str | Path, *args, sdk_version: str = DIRECT_SDK_VERSION, **kwargs):
        path = Path(contract_path)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        return deploy_contract(path, direct_vm, *args, sdk_version=sdk_version, **kwargs)

    return _deploy


def to_hex(address) -> str:
    if hasattr(address, "as_hex"):
        return address.as_hex
    if isinstance(address, bytes):
        from genlayer.py.types import Address

        return Address(address).as_hex
    return str(address)
