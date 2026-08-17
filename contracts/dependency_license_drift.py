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


@allow_storage
@dataclass
class CaseRecord:
    covenant_id: str
    challenger: Address
    target_version: str
    status: str
    challenge_bond: bigint
    attempt_count: u8
    verdict: str


class DependencyLicenseDrift(gl.Contract):
    covenants: TreeMap[str, Covenant]
    cases: TreeMap[str, CaseRecord]
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
    def get_case(self, case_id: str) -> str:
        if case_id not in self.cases:
            return "{}"
        return self._case_json(self.cases[case_id])

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
        self._require_id(case_id, "case id")
        self._require_text(target_version, "target version", MAX_VERSION_LEN)
        if case_id in self.cases:
            raise gl.vm.UserError("case exists")
        if gl.message.value <= 0:
            raise gl.vm.UserError("challenge bond must be positive")
        covenant = self._require_covenant(covenant_id)
        if covenant.active_case_id != "":
            raise gl.vm.UserError("active case exists")
        if covenant.status != STATUS_ACTIVE:
            raise gl.vm.UserError("covenant not active")
        if self._now() >= covenant.expiry:
            raise gl.vm.UserError("covenant expired")
        bond = bigint(gl.message.value)
        self.cases[case_id] = CaseRecord(
            covenant_id=covenant_id,
            challenger=gl.message.sender_address,
            target_version=target_version,
            status=STATUS_CASE_OPEN,
            challenge_bond=bond,
            attempt_count=u8(0),
            verdict="",
        )
        covenant.status = STATUS_CASE_OPEN
        covenant.active_case_id = case_id
        self.covenants[covenant_id] = covenant
        self.total_locked = bigint(int(self.total_locked) + int(bond))

    @gl.public.write
    def close_expired(self, covenant_id: str) -> None:
        covenant = self._require_covenant(covenant_id)
        if self._addr_key(gl.message.sender_address) != self._addr_key(covenant.sponsor):
            raise gl.vm.UserError("unauthorized")
        if self._now() < covenant.expiry:
            raise gl.vm.UserError("covenant not expired")
        if covenant.status == STATUS_CASE_OPEN:
            raise gl.vm.UserError("active case exists")
        if covenant.status == STATUS_CLOSED:
            raise gl.vm.UserError("covenant closed")
        amount = covenant.purse
        covenant.purse = bigint(0)
        covenant.status = STATUS_CLOSED
        covenant.active_case_id = ""
        self.covenants[covenant_id] = covenant
        if amount > 0:
            self.total_locked = bigint(int(self.total_locked) - int(amount))
            self._credit(covenant.sponsor, amount)

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

    def _require_covenant(self, covenant_id: str) -> Covenant:
        if covenant_id not in self.covenants:
            raise gl.vm.UserError("unknown covenant")
        return self.covenants[covenant_id]

    def _credit(self, account: Address, amount: bigint) -> None:
        key = self._addr_key(account)
        current = self.credits[key] if key in self.credits else bigint(0)
        self.credits[key] = bigint(int(current) + int(amount))
        self.total_credits = bigint(int(self.total_credits) + int(amount))

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

    def _case_json(self, case: CaseRecord) -> str:
        return json.dumps(
            {
                "covenant_id": case.covenant_id,
                "challenger": self._addr_key(case.challenger),
                "target_version": case.target_version,
                "status": case.status,
                "challenge_bond": str(case.challenge_bond),
                "attempt_count": int(case.attempt_count),
                "verdict": case.verdict,
            },
            sort_keys=True,
        )
