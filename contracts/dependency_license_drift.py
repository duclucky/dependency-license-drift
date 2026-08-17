# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *

import json
from dataclasses import dataclass
from datetime import datetime, timezone


GEN = 10**18
MAX_ID_LEN = 64
MAX_PACKAGE_LEN = 214
MAX_VERSION_LEN = 64
MAX_PROFILE_LEN = 1200

STATUS_ACTIVE = "ACTIVE"
STATUS_CLOSED = "CLOSED"
STATUS_CASE_OPEN = "CASE_OPEN"
STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
STATUS_RETRYABLE = "RETRYABLE"


@allow_storage
@dataclass
class Covenant:
    sponsor: Address
    package_name: str
    baseline_version: str
    use_profile: str
    expiry: bigint
    status: str
    purse: bigint
    active_case_id: str


class DependencyLicenseDrift(gl.Contract):
    covenants: TreeMap[str, Covenant]
    credits: TreeMap[str, bigint]
    total_locked: bigint
    total_credits: bigint

    def __init__(self) -> None:
        self.total_locked = bigint(0)
        self.total_credits = bigint(0)

    @gl.public.view
    def get_covenant(self, covenant_id: str) -> str:
        if covenant_id not in self.covenants:
            return "{}"
        return self._covenant_json(self.covenants[covenant_id])

    @gl.public.view
    def get_package_status(self, covenant_id: str) -> str:
        if covenant_id not in self.covenants:
            return "UNKNOWN"
        covenant = self.covenants[covenant_id]
        if covenant.status == STATUS_CASE_OPEN:
            return STATUS_CASE_OPEN
        return covenant.status

    @gl.public.view
    def get_credit(self, account: Address) -> str:
        key = self._addr_key(account)
        amount = self.credits[key] if key in self.credits else bigint(0)
        return json.dumps({"account": key, "credit": str(amount)}, sort_keys=True)

    @gl.public.view
    def get_accounting(self) -> str:
        return json.dumps(
            {
                "total_locked": str(self.total_locked),
                "total_credits": str(self.total_credits),
                "total_locked_gen": str(int(self.total_locked) // GEN),
                "total_credits_gen": str(int(self.total_credits) // GEN),
            },
            sort_keys=True,
        )

    @gl.public.write.payable
    def activate_covenant(
        self,
        covenant_id: str,
        package_name: str,
        baseline_version: str,
        use_profile: str,
        expiry: int,
    ) -> None:
        self._require_id(covenant_id, "covenant id")
        self._require_text(package_name, "package name", MAX_PACKAGE_LEN)
        self._require_text(baseline_version, "baseline version", MAX_VERSION_LEN)
        self._require_text(use_profile, "use profile", MAX_PROFILE_LEN)
        if covenant_id in self.covenants:
            raise gl.vm.UserError("covenant exists")
        if gl.message.value <= 0:
            raise gl.vm.UserError("purse must be positive")
        expiry_value = bigint(expiry)
        if self._now() >= expiry_value:
            raise gl.vm.UserError("expiry must be future")
        purse = bigint(gl.message.value)
        self.covenants[covenant_id] = Covenant(
            sponsor=gl.message.sender_address,
            package_name=package_name,
            baseline_version=baseline_version,
            use_profile=use_profile,
            expiry=expiry_value,
            status=STATUS_ACTIVE,
            purse=purse,
            active_case_id="",
        )
        self.total_locked = bigint(int(self.total_locked) + int(purse))

    @gl.public.write.payable
    def open_case(self, covenant_id: str, case_id: str, target_version: str) -> None:
        raise gl.vm.UserError("case opening not implemented")

    def _require_id(self, value: str, name: str) -> None:
        if value == "" or len(value) > MAX_ID_LEN:
            raise gl.vm.UserError(name + " invalid")

    def _require_text(self, value: str, name: str, max_len: int) -> None:
        if value == "" or len(value) > max_len:
            raise gl.vm.UserError(name + " invalid")

    def _addr_key(self, account: Address) -> str:
        if hasattr(account, "as_hex"):
            return account.as_hex.lower()
        return Address(account).as_hex.lower()

    def _now(self) -> bigint:
        try:
            raw = gl.message_raw.get("datetime", "")
        except Exception:
            try:
                raw = gl.message.datetime
            except Exception:
                return bigint(0)
        raw_text = str(raw)
        if raw_text.isdigit():
            return bigint(int(raw_text))
        try:
            normalized = raw_text[:-1] + "+00:00" if raw_text.endswith("Z") else raw_text
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return bigint(int(parsed.timestamp()))
        except Exception:
            return bigint(0)

    def _covenant_json(self, covenant: Covenant) -> str:
        return json.dumps(
            {
                "sponsor": self._addr_key(covenant.sponsor),
                "package_name": covenant.package_name,
                "baseline_version": covenant.baseline_version,
                "use_profile": covenant.use_profile,
                "expiry": str(covenant.expiry),
                "status": covenant.status,
                "purse": str(covenant.purse),
                "active_case_id": covenant.active_case_id,
            },
            sort_keys=True,
        )
