# Dependency License Drift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build, test, deploy, document, and submit a standalone GenLayer Intelligent Contract that adjudicates dependency license drift from official npm and SPDX evidence on Studionet.

**Execution status:** Completed. Public repo pushed at `https://github.com/duclucky/dependency-license-drift`; Studionet deployment, clean retryable recovery, and accepted drift payout evidence are recorded under `docs/evidence/studionet/`.

**Architecture:** One contract owns covenant funding, case state, semantic license-drift review, package status, and credits. Validators fetch npm registry metadata and SPDX license JSON/text, compare consensus-critical meaning fields, and deterministic settlement code derives status and credit consequences.

**Tech Stack:** GenVM Python contract, `genlayer-test==0.29.2`, `pytest`, `genvm-lint`, `genlayer-js==1.1.8`, PowerShell verification scripts, target network `studionet`.

## Global Constraints

- Contract-only Intelligent Contracts submission; no frontend and no Vercel.
- Target network is `studionet`, overriding the workspace Studionet default for this project only.
- Studionet RPC is `https://studio.genlayer.com/api`; chain id is `61999`; explorer is `https://explorer-studio.genlayer.com`.
- Contract file must be pure ASCII.
- Contract header line 1 must match the current Studio pragma, line 2 is the `Depends` comment, and line 3 is `from genlayer import *`.
- Exactly one project-specific `gl.Contract` subclass.
- All value is denominated in GEN in docs and passed in base units in code (`1 GEN = 10**18`).
- No actor-hosted evidence, screenshots, hashes, or claimant JSON may trigger payout/status consequence.
- Every time-bounded write must enforce its own timestamp guard.
- Public claims require source, test, and Studionet evidence before submission.

---

### Task 1: Static Guardrails And Test Harness

**Files:**
- Modify: `D:\Genlayer Project\dependency-license-drift\scripts\check.ps1`
- Modify: `D:\Genlayer Project\dependency-license-drift\scripts\ascii_header_check.py`
- Create: `D:\Genlayer Project\dependency-license-drift\tests\test_static_contract_rules.py`
- Modify: `D:\Genlayer Project\dependency-license-drift\package.json`

**Interfaces:**
- Consumes: planned contract path `contracts/dependency_license_drift.py`.
- Produces: `npm run check`, static test functions, and ASCII/header verification relied on by all later tasks.

- [x] **Step 1: Write failing static tests**

Create `tests/test_static_contract_rules.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "dependency_license_drift.py"


def _source() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def test_contract_source_is_ascii() -> None:
    data = CONTRACT.read_bytes()
    assert all(b < 128 for b in data)


def test_contract_header_order() -> None:
    lines = CONTRACT.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# v")
    assert '"Depends": "py-genlayer:' in lines[1]
    assert lines[2] == "from genlayer import *"


def test_value_entrypoints_are_payable() -> None:
    src = _source()
    for method in ("activate_covenant", "open_case"):
        marker = f"def {method}("
        prefix = src[: src.index(marker)]
        assert "@gl.public.write.payable" in prefix.splitlines()[-3:]


def test_no_claimant_evidence_settlement_terms() -> None:
    src = _source()
    forbidden = ["githubusercontent", "screenshot", "claimant_url", "sha256_only"]
    assert not any(term in src for term in forbidden)
```

- [x] **Step 2: Run test to verify it fails because the contract is absent**

Run: `pytest tests/test_static_contract_rules.py -q`

Expected: FAIL with `FileNotFoundError` for `contracts/dependency_license_drift.py`.

- [x] **Step 3: Update check script to include static tests**

Modify `scripts/check.ps1`:

```powershell
$ErrorActionPreference = "Stop"

if (-not (Test-Path "contracts/dependency_license_drift.py")) {
  throw "contracts/dependency_license_drift.py is missing"
}

python scripts/ascii_header_check.py contracts/dependency_license_drift.py
genvm-lint check contracts/dependency_license_drift.py
pytest tests/test_static_contract_rules.py -q
gltest tests/direct

Write-Host "CHECK_OK"
```

- [x] **Step 4: Run check to verify it fails at missing contract**

Run: `npm run check`

Expected: FAIL with `contracts/dependency_license_drift.py is missing`.

- [x] **Step 5: Commit**

```bash
git add package.json scripts/ascii_header_check.py scripts/check.ps1 tests/test_static_contract_rules.py
git commit -m "test: add contract guardrail checks"
```

### Task 2: Contract Core State And Deterministic Views

**Files:**
- Create: `D:\Genlayer Project\dependency-license-drift\contracts\dependency_license_drift.py`
- Create: `D:\Genlayer Project\dependency-license-drift\tests\direct\test_dependency_license_core.py`
- Modify: `D:\Genlayer Project\dependency-license-drift\docs\README.md`

**Interfaces:**
- Produces contract methods: `activate_covenant`, `get_covenant`, `get_package_status`, `get_accounting`.
- Later tasks consume the `Covenant` storage fields `sponsor`, `package_name`, `baseline_version`, `use_profile`, `expiry`, `status`, `purse`, and `active_case_id`.

- [x] **Step 1: Write failing direct tests for covenant activation**

Create `tests/direct/test_dependency_license_core.py`:

```python
GEN = 10**18


def test_activate_covenant_locks_purse(contract, accounts):
    sponsor = accounts[0]
    contract.connect(sponsor).activate_covenant(
        args=[
            "cov-ua-parser",
            "ua-parser-js",
            "1.0.37",
            "Commercial SaaS product may not accept network-copyleft obligations.",
            4102444800,
        ]
    ).transact(value=2 * GEN)

    covenant = contract.get_covenant(args=["cov-ua-parser"]).call()
    assert covenant["status"] == "ACTIVE"
    assert covenant["package_name"] == "ua-parser-js"
    assert covenant["baseline_version"] == "1.0.37"
    assert int(covenant["purse"]) == 2 * GEN
    assert contract.get_package_status(args=["cov-ua-parser"]).call() == "ACTIVE"


def test_activate_rejects_zero_value(contract, accounts):
    sponsor = accounts[0]
    with pytest.raises(Exception):
        contract.connect(sponsor).activate_covenant(
            args=["cov-zero", "ua-parser-js", "1.0.37", "profile", 4102444800]
        ).transact(value=0)
```

Include `import pytest` at the top.

- [x] **Step 2: Run tests to verify failure**

Run: `gltest tests/direct/test_dependency_license_core.py -q`

Expected: FAIL because `activate_covenant` is not implemented.

- [x] **Step 3: Implement minimal contract core**

Create `contracts/dependency_license_drift.py` with the current Studio header copied before coding. The first implementation must include ASCII-only dataclasses, one `DependencyLicenseDrift(gl.Contract)` class, `activate_covenant`, `get_covenant`, `get_package_status`, and `get_accounting`.

- [x] **Step 4: Run core tests and static tests**

Run: `pytest tests/test_static_contract_rules.py -q`

Expected: PASS.

Run: `gltest tests/direct/test_dependency_license_core.py -q`

Expected: PASS for activation and zero-value rejection.

- [x] **Step 5: Commit**

```bash
git add contracts/dependency_license_drift.py tests/direct/test_dependency_license_core.py docs/README.md
git commit -m "feat: add covenant activation state"
```

### Task 3: Case Opening, Expiry Guards, And Value Accounting

**Files:**
- Modify: `D:\Genlayer Project\dependency-license-drift\contracts\dependency_license_drift.py`
- Create: `D:\Genlayer Project\dependency-license-drift\tests\direct\test_dependency_license_cases.py`

**Interfaces:**
- Consumes: `activate_covenant`.
- Produces: `open_case`, `close_expired`, `get_case`, `get_credit`.

- [x] **Step 1: Write failing tests for case opening and duplicate prevention**

Create `tests/direct/test_dependency_license_cases.py`:

```python
import pytest

GEN = 10**18


def _activate(contract, sponsor):
    contract.connect(sponsor).activate_covenant(
        args=["cov-1", "ua-parser-js", "1.0.37", "No network copyleft for SaaS.", 4102444800]
    ).transact(value=2 * GEN)


def test_open_case_locks_challenge_bond(contract, accounts):
    sponsor, challenger = accounts[0], accounts[1]
    _activate(contract, sponsor)
    contract.connect(challenger).open_case(args=["cov-1", "case-1", "2.0.0"]).transact(value=1 * GEN)

    case = contract.get_case(args=["case-1"]).call()
    assert case["status"] == "CASE_OPEN"
    assert case["target_version"] == "2.0.0"
    assert int(case["challenge_bond"]) == 1 * GEN


def test_duplicate_active_case_rejects(contract, accounts):
    sponsor, challenger = accounts[0], accounts[1]
    _activate(contract, sponsor)
    contract.connect(challenger).open_case(args=["cov-1", "case-1", "2.0.0"]).transact(value=1 * GEN)
    with pytest.raises(Exception):
        contract.connect(challenger).open_case(args=["cov-1", "case-2", "2.0.4"]).transact(value=1 * GEN)
```

- [x] **Step 2: Run tests to verify failure**

Run: `gltest tests/direct/test_dependency_license_cases.py -q`

Expected: FAIL because `open_case` and `get_case` are not implemented.

- [x] **Step 3: Implement case storage and direct guards**

Add `Case` storage, `open_case`, `get_case`, and `get_credit`. Ensure `open_case` is payable, rejects zero value, rejects missing covenant, rejects non-`ACTIVE`, rejects duplicate active case, validates target version length, and checks `now < expiry` inside the entrypoint.

- [x] **Step 4: Add expiry/recovery tests**

Extend `test_dependency_license_cases.py` with the direct-mode timestamp helper used by prior workspace contracts:

```python
from datetime import datetime, timezone


def set_time(vm, timestamp: int) -> None:
    timestamp_text = datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")
    vm.warp(timestamp_text)
    import genlayer.gl as gl_module
    if getattr(gl_module, "message_raw", None) is not None:
        gl_module.message_raw["datetime"] = timestamp_text
```

Add tests:

```python
def test_open_case_rejects_at_expiry_with_stale_active_phase(contract, accounts, direct_vm):
    sponsor, challenger = accounts[0], accounts[1]
    contract.connect(sponsor).activate_covenant(
        args=["cov-exp", "ua-parser-js", "1.0.37", "profile", 100]
    ).transact(value=2 * GEN)
    set_time(direct_vm, 100)
    with pytest.raises(Exception):
        contract.connect(challenger).open_case(args=["cov-exp", "case-exp", "2.0.0"]).transact(value=1 * GEN)
    assert contract.get_package_status(args=["cov-exp"]).call() == "ACTIVE"


def test_close_expired_rejects_before_expiry_and_works_at_equality(contract, accounts, direct_vm):
    sponsor = accounts[0]
    contract.connect(sponsor).activate_covenant(
        args=["cov-close", "ua-parser-js", "1.0.37", "profile", 100]
    ).transact(value=2 * GEN)
    set_time(direct_vm, 99)
    with pytest.raises(Exception):
        contract.connect(sponsor).close_expired(args=["cov-close"]).transact()
    set_time(direct_vm, 100)
    contract.connect(sponsor).close_expired(args=["cov-close"]).transact()
    assert contract.get_package_status(args=["cov-close"]).call() == "CLOSED"
```

- [x] **Step 5: Run case tests**

Run: `gltest tests/direct/test_dependency_license_cases.py -q`

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add contracts/dependency_license_drift.py tests/direct/test_dependency_license_cases.py
git commit -m "feat: add case opening and recovery guards"
```

### Task 4: Npm/SPDX Semantic Adjudication

**Files:**
- Modify: `D:\Genlayer Project\dependency-license-drift\contracts\dependency_license_drift.py`
- Create: `D:\Genlayer Project\dependency-license-drift\tests\direct\test_dependency_license_adjudication.py`

**Interfaces:**
- Consumes: `open_case`, `get_case`.
- Produces: `adjudicate_case`, `get_verdict`, `get_package_status`, settlement credits.

- [x] **Step 1: Write failing happy-path adjudication test**

Create `tests/direct/test_dependency_license_adjudication.py`:

```python
import json

GEN = 10**18


def test_mit_to_agpl_confirms_drift(contract, accounts, client):
    sponsor, challenger = accounts[0], accounts[1]
    contract.connect(sponsor).activate_covenant(
        args=["cov-1", "ua-parser-js", "1.0.37", "Commercial SaaS may not accept AGPL or network-copyleft obligations.", 4102444800]
    ).transact(value=2 * GEN)
    contract.connect(challenger).open_case(args=["cov-1", "case-1", "2.0.0"]).transact(value=1 * GEN)

    client.provider.make_request(method="sim_installMocks", params={
        "web_mocks": {
            "https://registry.npmjs.org/ua-parser-js/1.0.37": {"status": 200, "body": "{\"name\":\"ua-parser-js\",\"version\":\"1.0.37\",\"license\":\"MIT\"}"},
            "https://registry.npmjs.org/ua-parser-js/2.0.0": {"status": 200, "body": "{\"name\":\"ua-parser-js\",\"version\":\"2.0.0\",\"license\":\"AGPL-3.0-or-later\"}"},
            "https://spdx.org/licenses/MIT.json": {"status": 200, "body": "{\"licenseId\":\"MIT\",\"name\":\"MIT License\",\"isDeprecatedLicenseId\":false,\"licenseText\":\"Permission is hereby granted...\"}"},
            "https://spdx.org/licenses/AGPL-3.0-or-later.json": {"status": 200, "body": "{\"licenseId\":\"AGPL-3.0-or-later\",\"name\":\"GNU Affero General Public License v3.0 or later\",\"isDeprecatedLicenseId\":false,\"licenseText\":\"network interaction source disclosure terms\"}"}
        },
        "llm_mocks": {
            ".*": json.dumps({
                "verdict": "DRIFT_CONFIRMED",
                "baseline_license_ids": ["MIT"],
                "target_license_ids": ["AGPL-3.0-or-later"],
                "obligation_classes": ["NETWORK_COPYLEFT", "SOURCE_DISCLOSURE"],
                "source_coverage": "COMPLETE",
                "reason": "Target version adds network-copyleft obligations."
            })
        },
    })

    contract.adjudicate_case(args=["case-1"]).transact()
    verdict = contract.get_verdict(args=["case-1"]).call()
    assert verdict["verdict"] == "DRIFT_CONFIRMED"
    assert contract.get_package_status(args=["cov-1"]).call() == "REVIEW_REQUIRED"
    assert int(contract.get_credit(args=[str(challenger.address)]).call()) > 0
```

- [x] **Step 2: Run test to verify failure**

Run: `gltest tests/direct/test_dependency_license_adjudication.py -q`

Expected: FAIL because adjudication is not implemented.

- [x] **Step 3: Implement nondeterministic leader and meaning validator**

Implement `adjudicate_case` with:
- deterministic source URL construction for npm and SPDX only;
- web render/get inside a no-arg leader function;
- LLM prompt with locked JSON schema and allowed enums;
- `gl.vm.run_nondet(leader_fn, validator_fn)`;
- validator returning `False` unless `leader_res` is `gl.vm.Return`;
- validator comparing verdict, license ID sets, obligation class set, and complete source coverage.

- [x] **Step 4: Add malicious-output tests**

Add tests for invalid enum, missing source coverage, extra license ID, format-valid but wrong target version, and `UNVERIFIABLE` leaving accounting unchanged.

- [x] **Step 5: Run adjudication tests**

Run: `gltest tests/direct/test_dependency_license_adjudication.py -q`

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add contracts/dependency_license_drift.py tests/direct/test_dependency_license_adjudication.py
git commit -m "feat: add semantic license drift adjudication"
```

### Task 5: Withdrawal, Accounting Invariants, And Full Local Check

**Files:**
- Modify: `D:\Genlayer Project\dependency-license-drift\contracts\dependency_license_drift.py`
- Create: `D:\Genlayer Project\dependency-license-drift\tests\direct\test_dependency_license_accounting.py`
- Modify: `D:\Genlayer Project\dependency-license-drift\docs\README.md`

**Interfaces:**
- Consumes: credit ledger from adjudication.
- Produces: `withdraw_credit` and complete accounting proof views.

- [x] **Step 1: Write failing withdrawal tests**

Create `tests/direct/test_dependency_license_accounting.py`:

```python
import pytest


def test_withdraw_rejects_without_credit(contract, accounts):
    user = accounts[1]
    with pytest.raises(Exception):
        contract.connect(user).withdraw_credit(args=[]).transact()


def test_accounting_view_has_zero_credit_for_unknown(contract, accounts):
    user = accounts[2]
    assert int(contract.get_credit(args=[str(user.address)]).call()) == 0
```

- [x] **Step 2: Run tests to verify failure**

Run: `gltest tests/direct/test_dependency_license_accounting.py -q`

Expected: FAIL until `withdraw_credit` and unknown-credit view behavior are complete.

- [x] **Step 3: Implement withdrawal**

Debit caller credit before transfer. Use the correct EOA/EVM transfer interface from `docs/08`; do not use nonexistent `gl.eth.send_value`. Ensure second withdrawal rejects and accounting cannot go negative.

- [x] **Step 4: Run full local checks**

Run: `npm run check`

Expected: ASCII/header OK, `genvm-lint check` passes and recognizes `DependencyLicenseDrift`, static tests pass, direct tests pass.

- [x] **Step 5: Commit**

```bash
git add contracts/dependency_license_drift.py tests/direct/test_dependency_license_accounting.py docs/README.md
git commit -m "feat: add credit withdrawal accounting"
```

### Task 6: Studionet Deploy Script And Evidence

**Files:**
- Create: `D:\Genlayer Project\dependency-license-drift\scripts\deploy_Studionet.mjs`
- Create: `D:\Genlayer Project\dependency-license-drift\tests\deployment_parser.test.mjs`
- Create: `D:\Genlayer Project\dependency-license-drift\docs\evidence\Studionet\README.md`
- Modify: `D:\Genlayer Project\dependency-license-drift\package.json`

**Interfaces:**
- Consumes: verified contract and `.env` secret presence.
- Produces: sanitized `deployment.json`, `lifecycle.json`, and explorer URLs.

- [x] **Step 1: Write parser fixture tests**

Create `tests/deployment_parser.test.mjs` with fixtures for raw Studio-style `consensus_data.leader_receipt[].execution_result` and normalized SDK `txExecutionResultName`.

- [x] **Step 2: Run parser tests to verify failure**

Run: `node --test tests/deployment_parser.test.mjs`

Expected: FAIL because parser does not exist.

- [x] **Step 3: Implement deploy script**

Create `scripts/deploy_Studionet.mjs` with commands:
- `inspect`;
- `deploy`;
- `schema`;
- `demo`;
- `verify`.

The script must read `.env` without printing values, require `GENLAYER_NETWORK=studionet`, refuse to resume a deployment whose network/source commit/header hash differs, and write only allowlisted evidence fields.

- [x] **Step 4: Run safe inspect**

Run: `node scripts/deploy_Studionet.mjs inspect`

Expected: reports Studionet RPC, chain id `61999`, wallet address presence, and balance presence without printing private key.

- [x] **Step 5: Commit**

```bash
git add scripts/deploy_Studionet.mjs tests/deployment_parser.test.mjs docs/evidence/Studionet/README.md package.json
git commit -m "feat: add Studionet deployment tooling"
```

### Task 7: Studionet Lifecycle, Docs, Public Repo, Submission Packet

**Files:**
- Modify: `D:\Genlayer Project\dependency-license-drift\README.md`
- Modify: `D:\Genlayer Project\dependency-license-drift\docs\README.md`
- Modify: `D:\Genlayer Project\docs\IDEA-REGISTRY.md`
- Create/modify: `D:\Genlayer Project\dependency-license-drift\docs\evidence\Studionet\deployment.json`
- Create/modify: `D:\Genlayer Project\dependency-license-drift\docs\evidence\Studionet\lifecycle.json`

**Interfaces:**
- Consumes: deploy script and verified local checks.
- Produces: public evidence and copy-ready Portal fields.

- [x] **Step 1: Run pre-deploy local check**

Run: `npm run check`

Expected: all checks pass.

- [x] **Step 2: Deploy to Studionet**

Run: `node scripts/deploy_Studionet.mjs deploy`

Expected: finalized deploy receipt with execution `SUCCESS`, Studionet contract address, and schema read.

- [x] **Step 3: Run lifecycle demo**

Run: `node scripts/deploy_studionet.mjs demo`

Expected: finalized activation, case opening, adjudication, credit withdrawal, and canonical reads showing `REVIEW_REQUIRED` and correct accounting.

- [x] **Step 4: Audit public tree**

Run:

```powershell
git status --short
git diff --check
git ls-files
rg -n "<secret-or-internal-file-markers>" .
```

Expected: no secret/internal files; `.env` ignored.

- [x] **Step 5: Commit evidence and docs**

```bash
git add README.md docs/README.md docs/evidence/studionet/deployment.json docs/evidence/studionet/drift-payout.json docs/evidence/studionet/recovery.json
git commit -m "docs: record Studionet lifecycle evidence"
```

- [x] **Step 6: Push public GitHub repo**

Create public repo `dependency-license-drift`, set `origin`, and push `main`. Verify remote URL and public tree before writing submission text.

- [x] **Step 7: Draft Portal fields**

Provide:
- Title: `Dependency License Drift`
- Description under 1000 characters with exact count
- Evidence URL: public GitHub repo
- Studionet contract explorer URL
