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
MAX_WEB_BODY_LEN = 200000

STATUS_ACTIVE = "ACTIVE"
STATUS_CLOSED = "CLOSED"
STATUS_CASE_OPEN = "CASE_OPEN"
STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
STATUS_RETRYABLE = "RETRYABLE"
STATUS_DRIFT_CONFIRMED = "DRIFT_CONFIRMED"
STATUS_NO_DRIFT = "NO_DRIFT"

VERDICT_DRIFT_CONFIRMED = "DRIFT_CONFIRMED"
VERDICT_NO_DRIFT = "NO_DRIFT"
VERDICT_UNVERIFIABLE = "UNVERIFIABLE"

CONSEQUENCE_REVIEW_REQUIRED = "REVIEW_REQUIRED"
CONSEQUENCE_NO_DRIFT = "NO_DRIFT"
CONSEQUENCE_RETRY = "RETRY"

SOURCE_COMPLETE = "COMPLETE"
SOURCE_UNAVAILABLE = "UNAVAILABLE"

OBLIGATION_NETWORK_COPYLEFT = "NETWORK_COPYLEFT"
OBLIGATION_SOURCE_DISCLOSURE = "SOURCE_DISCLOSURE"
OBLIGATION_FIELD_OF_USE = "FIELD_OF_USE"
OBLIGATION_PATENT_RETALIATION = "PATENT_RETALIATION"
OBLIGATION_COMMERCIAL_RESTRICTION = "COMMERCIAL_RESTRICTION"


@gl.evm.contract_interface
class Recipient:
    class View:
        pass

    class Write:
        pass


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


@allow_storage
@dataclass
class VerdictRecord:
    case_id: str
    verdict: str
    baseline_license_ids: str
    target_license_ids: str
    obligation_classes: str
    source_coverage: str
    consequence_class: str
    reason: str


class DependencyLicenseDrift(gl.Contract):
    covenants: TreeMap[str, Covenant]
    cases: TreeMap[str, CaseRecord]
    verdicts: TreeMap[str, VerdictRecord]
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
    def get_verdict(self, case_id: str) -> str:
        if case_id not in self.cases:
            return "{}"
        case = self.cases[case_id]
        if int(case.attempt_count) == 0:
            return "{}"
        key = self._verdict_key(case_id, int(case.attempt_count) - 1)
        if key not in self.verdicts:
            return "{}"
        return self._verdict_json(self.verdicts[key])

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
        sponsor_amount = covenant.purse
        challenger_amount = bigint(0)
        if covenant.status == STATUS_RETRYABLE and covenant.active_case_id in self.cases:
            retry_case = self.cases[covenant.active_case_id]
            challenger_amount = retry_case.challenge_bond
            retry_case.challenge_bond = bigint(0)
            self.cases[covenant.active_case_id] = retry_case
        total_refund = bigint(int(sponsor_amount) + int(challenger_amount))
        covenant.purse = bigint(0)
        covenant.status = STATUS_CLOSED
        covenant.active_case_id = ""
        self.covenants[covenant_id] = covenant
        if total_refund > 0:
            self.total_locked = bigint(int(self.total_locked) - int(total_refund))
            if sponsor_amount > 0:
                self._credit(covenant.sponsor, sponsor_amount)
            if challenger_amount > 0:
                self._credit(retry_case.challenger, challenger_amount)

    @gl.public.write
    def cancel_covenant(self, covenant_id: str) -> None:
        covenant = self._require_covenant(covenant_id)
        if self._addr_key(gl.message.sender_address) != self._addr_key(covenant.sponsor):
            raise gl.vm.UserError("unauthorized")
        if covenant.active_case_id != "":
            raise gl.vm.UserError("active case exists")
        if covenant.status != STATUS_ACTIVE:
            raise gl.vm.UserError("covenant not active")
        refund = covenant.purse
        covenant.purse = bigint(0)
        covenant.status = STATUS_CLOSED
        self.covenants[covenant_id] = covenant
        if refund > 0:
            self.total_locked = bigint(int(self.total_locked) - int(refund))
            self._credit(covenant.sponsor, refund)

    @gl.public.write
    def recover_retryable(self, covenant_id: str) -> None:
        covenant = self._require_covenant(covenant_id)
        if covenant.status != STATUS_RETRYABLE:
            raise gl.vm.UserError("covenant not retryable")
        if covenant.active_case_id == "" or covenant.active_case_id not in self.cases:
            raise gl.vm.UserError("retryable case missing")
        case_id = covenant.active_case_id
        case = self.cases[case_id]
        caller = self._addr_key(gl.message.sender_address)
        if caller != self._addr_key(covenant.sponsor) and caller != self._addr_key(case.challenger):
            raise gl.vm.UserError("unauthorized")
        sponsor_amount = covenant.purse
        challenger_amount = case.challenge_bond
        total_refund = bigint(int(sponsor_amount) + int(challenger_amount))
        covenant.purse = bigint(0)
        covenant.status = STATUS_CLOSED
        covenant.active_case_id = ""
        case.challenge_bond = bigint(0)
        case.status = STATUS_CLOSED
        self.covenants[covenant_id] = covenant
        self.cases[case_id] = case
        if total_refund > 0:
            self.total_locked = bigint(int(self.total_locked) - int(total_refund))
            if sponsor_amount > 0:
                self._credit(covenant.sponsor, sponsor_amount)
            if challenger_amount > 0:
                self._credit(case.challenger, challenger_amount)

    @gl.public.write
    def adjudicate_case(self, case_id: str) -> None:
        if case_id not in self.cases:
            raise gl.vm.UserError("unknown case")
        case = self.cases[case_id]
        if case.status not in (STATUS_CASE_OPEN, STATUS_RETRYABLE):
            raise gl.vm.UserError("case already settled")
        covenant = self._require_covenant(case.covenant_id)
        baseline_url = self._npm_url(covenant.package_name, covenant.baseline_version)
        target_url = self._npm_url(covenant.package_name, case.target_version)

        def unavailable():
            return {
                "verdict": VERDICT_UNVERIFIABLE,
                "baseline_license_ids": [],
                "target_license_ids": [],
                "obligation_classes": [],
                "source_coverage": SOURCE_UNAVAILABLE,
                "consequence_class": CONSEQUENCE_RETRY,
                "reason": "official source unavailable",
            }

        def leader_fn():
            baseline_body = self._web_body(gl.nondet.web.get(baseline_url))
            target_body = self._web_body(gl.nondet.web.get(target_url))
            if baseline_body == "" or target_body == "":
                return unavailable()
            baseline_license = self._metadata_license(
                baseline_body, covenant.package_name, covenant.baseline_version
            )
            target_license = self._metadata_license(
                target_body, covenant.package_name, case.target_version
            )
            if baseline_license == "" or target_license == "":
                return unavailable()
            baseline_spdx = self._spdx_body(baseline_license)
            target_spdx = self._spdx_body(target_license)
            if baseline_spdx == "" or target_spdx == "":
                return unavailable()
            attempt = self._derive_bounded_verdict(
                case_id,
                baseline_license,
                target_license,
                baseline_spdx,
                target_spdx,
                covenant.use_profile,
            )
            return self._verdict_dict(attempt)

        raw = gl.eq_principle.strict_eq(leader_fn)
        attempt = self._normalize_verdict(raw, case_id)
        key = self._verdict_key(case_id, int(case.attempt_count))
        self.verdicts[key] = attempt
        case.attempt_count = u8(int(case.attempt_count) + 1)
        case.verdict = attempt.verdict

        if attempt.consequence_class == CONSEQUENCE_RETRY:
            case.status = STATUS_RETRYABLE
            covenant.status = STATUS_RETRYABLE
            self.cases[case_id] = case
            self.covenants[case.covenant_id] = covenant
            return

        if attempt.consequence_class == CONSEQUENCE_REVIEW_REQUIRED:
            payout = bigint(int(covenant.purse) + int(case.challenge_bond))
            covenant.purse = bigint(0)
            covenant.status = STATUS_REVIEW_REQUIRED
            covenant.active_case_id = ""
            case.challenge_bond = bigint(0)
            case.status = STATUS_DRIFT_CONFIRMED
            self.total_locked = bigint(int(self.total_locked) - int(payout))
            self._credit(case.challenger, payout)
            self.cases[case_id] = case
            self.covenants[case.covenant_id] = covenant
            return

        if attempt.consequence_class == CONSEQUENCE_NO_DRIFT:
            bond = case.challenge_bond
            case.challenge_bond = bigint(0)
            case.status = STATUS_NO_DRIFT
            covenant.status = STATUS_ACTIVE
            covenant.active_case_id = ""
            self.total_locked = bigint(int(self.total_locked) - int(bond))
            self._credit(covenant.sponsor, bond)
            self.cases[case_id] = case
            self.covenants[case.covenant_id] = covenant
            return

        raise gl.vm.UserError("unknown consequence")

    @gl.public.write
    def withdraw_credit(self) -> None:
        sender = gl.message.sender_address
        key = self._addr_key(sender)
        if key not in self.credits or int(self.credits[key]) == 0:
            raise gl.vm.UserError("no credit")
        amount = self.credits[key]
        self.credits[key] = bigint(0)
        self.total_credits = bigint(int(self.total_credits) - int(amount))
        Recipient(sender).emit_transfer(value=u256(amount))

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

    def _npm_url(self, package_name: str, version: str) -> str:
        return "https://registry.npmjs.org/" + package_name + "/" + version

    def _spdx_url(self, license_id: str) -> str:
        return "https://spdx.org/licenses/" + license_id + ".json"

    def _web_body(self, response) -> str:
        try:
            if response.status != 200 or response.body is None:
                return ""
            try:
                text = response.body.decode("utf-8")
            except Exception:
                text = str(response.body)
            if len(text) > MAX_WEB_BODY_LEN:
                return ""
            return text
        except Exception:
            return ""

    def _metadata_license(self, body: str, package_name: str, version: str) -> str:
        try:
            data = json.loads(body)
            if str(data.get("name", "")) != package_name:
                return ""
            if str(data.get("version", "")) != version:
                return ""
            return self._single_spdx_id(str(data.get("license", "")))
        except Exception:
            return ""

    def _single_spdx_id(self, raw: str) -> str:
        value = raw.strip()
        if value.startswith("(") and value.endswith(")"):
            value = value[1:-1].strip()
        if value == "":
            return ""
        upper = value.upper()
        if " OR " in upper or " AND " in upper or " WITH " in upper:
            return ""
        if "/" in value or "\\" in value or ":" in value or ".." in value:
            return ""
        return value

    def _spdx_body(self, license_id: str) -> str:
        body = self._web_body(gl.nondet.web.get(self._spdx_url(license_id)))
        if body == "":
            return ""
        try:
            data = json.loads(body)
            if str(data.get("licenseId", "")) != license_id:
                return ""
            if bool(data.get("isDeprecatedLicenseId", False)):
                return ""
            return body
        except Exception:
            return ""

    def _normalize_verdict(self, raw, case_id: str) -> VerdictRecord:
        if isinstance(raw, str):
            data = json.loads(raw)
        else:
            data = raw
        verdict = str(data.get("verdict", "")).upper()
        source_coverage = str(data.get("source_coverage", "")).upper()
        consequence_class = str(data.get("consequence_class", "")).upper()
        baseline_license_ids = self._normalize_id_list(data.get("baseline_license_ids", []))
        target_license_ids = self._normalize_id_list(data.get("target_license_ids", []))
        obligation_classes = self._normalize_obligation_list(data.get("obligation_classes", []))
        reason = str(data.get("reason", ""))[:600]

        if verdict not in (VERDICT_DRIFT_CONFIRMED, VERDICT_NO_DRIFT, VERDICT_UNVERIFIABLE):
            raise gl.vm.UserError("invalid verdict")
        if source_coverage not in (SOURCE_COMPLETE, SOURCE_UNAVAILABLE):
            raise gl.vm.UserError("invalid source coverage")
        if consequence_class not in (
            CONSEQUENCE_REVIEW_REQUIRED,
            CONSEQUENCE_NO_DRIFT,
            CONSEQUENCE_RETRY,
        ):
            raise gl.vm.UserError("invalid consequence")

        if source_coverage == SOURCE_UNAVAILABLE:
            if verdict != VERDICT_UNVERIFIABLE or consequence_class != CONSEQUENCE_RETRY:
                raise gl.vm.UserError("unavailable meaning mismatch")
            return VerdictRecord(
                case_id,
                verdict,
                baseline_license_ids,
                target_license_ids,
                obligation_classes,
                source_coverage,
                consequence_class,
                reason,
            )

        if verdict == VERDICT_DRIFT_CONFIRMED:
            if consequence_class != CONSEQUENCE_REVIEW_REQUIRED:
                raise gl.vm.UserError("drift consequence mismatch")
            if obligation_classes == "":
                raise gl.vm.UserError("drift obligations missing")
        if verdict == VERDICT_NO_DRIFT and consequence_class != CONSEQUENCE_NO_DRIFT:
            raise gl.vm.UserError("no drift consequence mismatch")
        if verdict == VERDICT_UNVERIFIABLE and consequence_class != CONSEQUENCE_RETRY:
            raise gl.vm.UserError("unverifiable consequence mismatch")

        return VerdictRecord(
            case_id,
            verdict,
            baseline_license_ids,
            target_license_ids,
            obligation_classes,
            source_coverage,
            consequence_class,
            reason,
        )

    def _normalize_verdict_with_expected(
        self, raw, case_id: str, baseline_license: str, target_license: str
    ) -> VerdictRecord:
        verdict = self._normalize_verdict(raw, case_id)
        if verdict.source_coverage == SOURCE_COMPLETE:
            if verdict.baseline_license_ids != baseline_license:
                raise gl.vm.UserError("baseline license mismatch")
            if verdict.target_license_ids != target_license:
                raise gl.vm.UserError("target license mismatch")
        return verdict

    def _derive_bounded_verdict(
        self,
        case_id: str,
        baseline_license: str,
        target_license: str,
        baseline_spdx: str,
        target_spdx: str,
        use_profile: str,
    ) -> VerdictRecord:
        reason = "bounded SPDX classifier derived consequence"
        baseline_obligations = self._derive_obligations(baseline_license, baseline_spdx)
        target_obligations = self._derive_obligations(target_license, target_spdx)
        new_obligations = []
        for item in self._csv_items(target_obligations):
            if item not in self._csv_items(baseline_obligations):
                new_obligations.append(item)
        disallowed = []
        for item in new_obligations:
            if self._profile_disallows(use_profile, target_license, item):
                disallowed.append(item)
        disallowed.sort()
        if baseline_license != target_license and len(disallowed) > 0:
            return VerdictRecord(
                case_id,
                VERDICT_DRIFT_CONFIRMED,
                baseline_license,
                target_license,
                ",".join(disallowed),
                SOURCE_COMPLETE,
                CONSEQUENCE_REVIEW_REQUIRED,
                reason,
            )
        return VerdictRecord(
            case_id,
            VERDICT_NO_DRIFT,
            baseline_license,
            target_license,
            "",
            SOURCE_COMPLETE,
            CONSEQUENCE_NO_DRIFT,
            reason,
        )

    def _derive_obligations(self, license_id: str, spdx_body: str) -> str:
        try:
            data = json.loads(spdx_body)
            text = (
                license_id
                + " "
                + str(data.get("name", ""))
                + " "
                + str(data.get("licenseText", ""))
            ).lower()
        except Exception:
            text = license_id.lower()
        items = []
        if "agpl" in text or "affero" in text or ("network" in text and "source" in text):
            items.append(OBLIGATION_NETWORK_COPYLEFT)
            items.append(OBLIGATION_SOURCE_DISCLOSURE)
        elif "gpl" in text or "source" in text:
            items.append(OBLIGATION_SOURCE_DISCLOSURE)
        if "noncommercial" in text or "non-commercial" in text:
            items.append(OBLIGATION_COMMERCIAL_RESTRICTION)
        if "field of use" in text:
            items.append(OBLIGATION_FIELD_OF_USE)
        if "patent retaliation" in text:
            items.append(OBLIGATION_PATENT_RETALIATION)
        deduped = []
        for item in items:
            if item not in deduped:
                deduped.append(item)
        deduped.sort()
        return ",".join(deduped)

    def _profile_disallows(self, use_profile: str, license_id: str, obligation: str) -> bool:
        text = (use_profile + " " + license_id).lower()
        if obligation == OBLIGATION_NETWORK_COPYLEFT:
            return "network-copyleft" in text or "network copyleft" in text or "agpl" in text
        if obligation == OBLIGATION_SOURCE_DISCLOSURE:
            return "source disclosure" in text or "source-disclosure" in text or "agpl" in text
        if obligation == OBLIGATION_COMMERCIAL_RESTRICTION:
            return "commercial restriction" in text or "noncommercial" in text
        if obligation == OBLIGATION_FIELD_OF_USE:
            return "field of use" in text or "field-of-use" in text
        if obligation == OBLIGATION_PATENT_RETALIATION:
            return "patent retaliation" in text
        return False

    def _verdict_dict(self, verdict: VerdictRecord) -> dict:
        return {
            "case_id": verdict.case_id,
            "verdict": verdict.verdict,
            "baseline_license_ids": self._csv_items(verdict.baseline_license_ids),
            "target_license_ids": self._csv_items(verdict.target_license_ids),
            "obligation_classes": self._csv_items(verdict.obligation_classes),
            "source_coverage": verdict.source_coverage,
            "consequence_class": verdict.consequence_class,
            "reason": verdict.reason,
        }

    def _csv_items(self, csv_value: str):
        if csv_value == "":
            return []
        return csv_value.split(",")

    def _normalize_id_list(self, raw) -> str:
        items = []
        for item in raw:
            normalized = self._single_spdx_id(str(item))
            if normalized == "":
                raise gl.vm.UserError("invalid license id")
            if normalized not in items:
                items.append(normalized)
        items.sort()
        return ",".join(items)

    def _normalize_obligation_list(self, raw) -> str:
        allowed = (
            OBLIGATION_NETWORK_COPYLEFT,
            OBLIGATION_SOURCE_DISCLOSURE,
            OBLIGATION_FIELD_OF_USE,
            OBLIGATION_PATENT_RETALIATION,
            OBLIGATION_COMMERCIAL_RESTRICTION,
        )
        items = []
        for item in raw:
            normalized = str(item).upper()
            if normalized not in allowed:
                raise gl.vm.UserError("invalid obligation")
            if normalized not in items:
                items.append(normalized)
        items.sort()
        return ",".join(items)

    def _verdict_equivalent(self, first: VerdictRecord, second: VerdictRecord) -> bool:
        return (
            first.verdict == second.verdict
            and first.baseline_license_ids == second.baseline_license_ids
            and first.target_license_ids == second.target_license_ids
            and first.obligation_classes == second.obligation_classes
            and first.source_coverage == second.source_coverage
            and first.consequence_class == second.consequence_class
        )

    def _verdict_key(self, case_id: str, attempt_index: int) -> str:
        return case_id + ":attempt:" + str(attempt_index)

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

    def _verdict_json(self, verdict: VerdictRecord) -> str:
        return json.dumps(
            {
                "case_id": verdict.case_id,
                "verdict": verdict.verdict,
                "baseline_license_ids": verdict.baseline_license_ids,
                "target_license_ids": verdict.target_license_ids,
                "obligation_classes": verdict.obligation_classes,
                "source_coverage": verdict.source_coverage,
                "consequence_class": verdict.consequence_class,
                "reason": verdict.reason,
            },
            sort_keys=True,
        )
