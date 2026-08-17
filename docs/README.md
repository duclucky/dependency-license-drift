# Dependency License Drift Specification

## Identity

- Idea ID: `IDEA-015`
- Project name: Dependency License Drift
- Project slug: `dependency-license-drift`
- Category: Intelligent Contracts
- Status: `DESIGN`
- Repository: local scaffold only
- Target network: `testnet-bradbury`

## One-sentence product hook

Fund a dependency-use covenant, then let GenLayer validators decide whether an official package release has materially drifted from the locked license risk profile before credits or review-required state change.

## Bradbury Network Override

Workspace default `docs/09` targets `studionet`, but this project explicitly overrides deployment to `testnet-bradbury` at user request on 2026-08-17. Current official docs identify Bradbury as a production-like testnet for real AI/LLM workloads with GenLayer RPC `https://rpc-bradbury.genlayer.com`, chain id `4221`, currency `GEN`, explorer `https://explorer-bradbury.genlayer.com`, and faucet `https://testnet-faucet.genlayer.foundation`. Local probes on 2026-08-17 confirmed `eth_chainId = 0x107d` for Bradbury RPC and the shared chain RPC.

## Trust Problem

- Decision that must not depend on one party: whether a dependency version's official license terms materially exceed the locked consumer policy.
- Why database/ordinary EVM/backend LLM is insufficient: deterministic code can compare license strings, but cannot judge semantic drift such as permissive to network-copyleft, field-of-use restriction, patent-retaliation impact, or dual-license obligation against a natural-language use profile.
- Value/rights/access at risk: sponsor-funded review/remediation credit and a canonical `REVIEW_REQUIRED` status consumed by package gates, release managers, or dependency-risk funds.

## Fingerprint

- Trust problem: package consumers and maintainers should not trust one CI operator or vendor scanner to decide whether a dependency license change requires funded remediation.
- Actors/adversary: sponsor wants accurate risk handling; challenger wants a drift credit; maintainer or integrator may prefer no disruption; downstream consumers need neutral status.
- Evidence class + authenticity mechanism: validators fetch official npm registry version metadata and canonical SPDX license JSON/text from authoritative domains; no claimant-hosted evidence can settle.
- Consensus question: does the target version's license meaning materially drift from the baseline version under the locked use profile?
- State machine: `DRAFT -> ACTIVE -> CASE_OPEN -> REVIEW_PENDING -> DRIFT_CONFIRMED | NO_DRIFT | RETRYABLE -> CREDIT_WITHDRAWN | CLOSED`.
- Direct consequence: a confirmed drift marks the covenant `REVIEW_REQUIRED` and opens challenger/remediation credit; no drift returns challenge credit to the sponsor side; retryable leaves funds locked without penalty.
- Reuse surface: dependency-risk funds, enterprise package gates, OSS consortiums, and release automation can call covenant/case/status/credit views.

## Mandatory Gate Matrix

| Gate | PASS/FAIL | Evidence/reason |
| --- | --- | --- |
| Replacement | PASS | A backend scanner can compare metadata, but biased parties still control semantic license-risk interpretation before funded remediation. |
| Judgment | PASS | The core decision is semantic: whether official license terms materially restrict the locked use profile. |
| Evidence availability | PASS | npm registry and SPDX license endpoints are public, bounded, and probeable; outage maps to `RETRYABLE`. |
| Evidence authenticity | PASS | Consequential facts are acquired by validators from npm registry and SPDX; claimant-hosted JSON, screenshots, or hashes do not settle. |
| Equivalence | PASS | Consensus locks package, versions, license IDs, drift enum, decisive obligation classes, and consequence class; rationale wording may differ. |
| Consequence | PASS | Final verdict changes covenant status and credit rights. |
| Adversarial | PASS | Sponsor, challenger, maintainer, and downstream consumers have conflicting incentives over disruption and credit. |
| State model | PASS | Per-covenant and per-case isolation, one active case, append-only verdict attempts, credits, and recovery are specified. |
| Reuse | PASS | Other builders can integrate via status and credit views without copying semantic license adjudication. |
| Contract count | PASS | One contract owns covenant funding, review, status, and credit; no pass-through consumer is justified for IC track. |
| Differentiation | PASS | It is not a generic license cure/dispute; it is version-drift adjudication from official registry plus SPDX against a locked use profile. |
| Claim-to-code | PASS | Claims map below to writes, views, tests, and Bradbury evidence. |
| Full lifecycle | PASS | Planned lifecycle: fund, open case, fetch official evidence, adjudicate, set status, withdraw credit, read zero accounting. |
| Scope honesty | PASS | It does not give legal advice, prove private deployment obligations, or inspect source code beyond official license metadata and SPDX meaning. |

## Actors, Roles, And Incentives

| Actor | Permissions | Value at risk | Incentive to bias |
| --- | --- | --- | --- |
| Sponsor | Create/fund covenant, close expired idle covenant, withdraw sponsor credit | Funded purse and challenge bond outcome | Minimize disruption and deny valid drift |
| Challenger | Open case with target version, receive drift credit if confirmed | Challenge bond | Overstate license risk |
| Downstream consumer | Read canonical status | Release/package access decision | Needs neutral status |
| Validators | Fetch and judge evidence | Network consensus role | Must agree on meaning, not JSON shape |

## Scope And Non-Goals

In scope: npm package versions, SPDX-listed licenses, locked use profiles, semantic drift classes, Bradbury deployment evidence.

Out of scope: legal advice, private commercial license documents, source-code scanning, PyPI/Maven in v1, GitHub README license claims, screenshots, claimant-hosted audit reports.

## State Model

Stable IDs: `covenant_id`, `case_id`, `attempt_id`, package name, baseline version, target version.

Structured storage: covenant record, case record, verdict attempt, credit ledger, status view. All `TreeMap` keys will be `str`; value amounts use `bigint`.

State machine:

```text
DRAFT --activate/sponsor+value--> ACTIVE
ACTIVE --open_case/challenger+bond--> CASE_OPEN
CASE_OPEN --adjudicate/anyone--> REVIEW_PENDING -> DRIFT_CONFIRMED | NO_DRIFT | RETRYABLE
DRIFT_CONFIRMED --withdraw_credit/challenger--> CREDIT_WITHDRAWN
NO_DRIFT --withdraw_credit/sponsor--> CREDIT_WITHDRAWN
ACTIVE|RETRYABLE --close_expired/sponsor after expiry--> CLOSED
```

Temporal entrypoint rules: covenant expiry uses half-open deadline semantics (`now < expiry` is active, equality is expired). `open_case` checks expiry directly. `close_expired` checks sponsor, state, zero active case or retryable state, and `now >= expiry` directly.

## Write-Method Safety Matrix

| Method | Caller | Allowed states | Forbidden states | Temporal/expiry gate | Idempotency | Value/accounting effect | Views affected | Negative tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `activate_covenant` | Sponsor | New covenant ID | Existing covenant | `now < expiry`; equality late for activation | Duplicate ID rejects | Locks sponsor purse | `get_covenant`, `get_accounting` | zero value, duplicate, expired, wrong value |
| `open_case` | Challenger | `ACTIVE` | `CASE_OPEN`, terminal, `CLOSED` | `now < expiry`; stale state after expiry rejects | One active case per covenant | Locks challenge bond | `get_case`, `get_covenant` | wrong state, expired boundary, duplicate, zero bond |
| `adjudicate_case` | Anyone | `CASE_OPEN`, `RETRYABLE` | terminal, closed | N/A; legality derives from state and source availability | Attempt ID append-only; settled case rejects | Opens credits or keeps locked on retry | `get_verdict`, `get_credit`, `get_status` | malicious leader, missing source, invalid enum, duplicate settle |
| `withdraw_credit` | Credited address | Credit > 0 | No credit | N/A; credit ownership only | Zeroes before transfer; second call rejects | Transfers native GEN to caller | `get_credit`, `get_accounting` | wrong caller, double withdraw, transfer invariant |
| `close_expired` | Sponsor | `ACTIVE` with no active case, or `RETRYABLE` | `CASE_OPEN`, terminal settled | `now >= expiry`; equality expired | Second close rejects | Credits remaining locked funds to sponsor | `get_covenant`, `get_credit` | wrong caller, expiry - 1, exact expiry, active case, double close |

## Value-Destination Matrix

| Value item | Payer/source | Locked state | Release destination | Refund destination | Forfeit destination | Terminal states covered | Duplicate/late/retry behavior | Canonical proof view |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sponsor purse | Sponsor | `ACTIVE`, `CASE_OPEN`, `RETRYABLE` | Challenger/remediation credit on `DRIFT_CONFIRMED` | Sponsor credit on expiry close | N/A | `DRIFT_CONFIRMED`, `NO_DRIFT`, `CLOSED` | Retry keeps locked; duplicate settlement rejects | `get_accounting`, `get_credit` |
| Challenge bond | Challenger | `CASE_OPEN`, `RETRYABLE` | Challenger credit on `DRIFT_CONFIRMED` | Challenger credit on `RETRYABLE` close policy if specified | Sponsor credit on `NO_DRIFT` | `DRIFT_CONFIRMED`, `NO_DRIFT`, `CLOSED` | Duplicate settlement rejects; late open rejects | `get_case`, `get_credit` |

## Evidence Policy

Authoritative sources: `https://registry.npmjs.org/<package>/<version>` and `https://spdx.org/licenses/<licenseId>.json`.

Bounds: package name length, semver/version length, response size, allowed domains, HTTPS only, one baseline version and one target version per case, SPDX IDs normalized to locked allowlist grammar.

Failure policy: unavailable source, missing license, non-SPDX expression, deprecated ID, malformed JSON, conflicting source, or unsupported expression maps to `RETRYABLE`/`UNVERIFIABLE` with no payout or slash.

Fact authentication matrix:

| Consequential fact | Who can fabricate it? | Authoritative source / issuer | Verification method | Replay/timestamp binding | Failure consequence | Required negative test |
| --- | --- | --- | --- | --- | --- | --- |
| Package version license field | Package publisher can set metadata, but registry is authoritative for published version metadata | npm registry | Validator fetch from registry host/version path | Covenant/case binds package and versions | `RETRYABLE` if missing/malformed | claimant JSON with same fields cannot settle |
| License text and canonical ID | SPDX project controls list | SPDX | Validator fetch exact SPDX JSON | Case binds observed license IDs | `RETRYABLE` if unsupported/deprecated | fake SPDX URL rejected |
| Drift meaning | No actor may submit final verdict | GenLayer validators | Independent LLM/web replay and semantic validator | Attempt ID append-only | invalid output rejects before mutation | format-valid but meaning-invalid result rejected |

## Consensus Design

Leader task: fetch npm baseline metadata, target metadata, SPDX license JSON/text for both normalized license IDs, then ask LLM to classify drift under the locked use profile.

Consensus-critical fields:

| Field | Type/bounds | Comparison rule | Why critical |
| --- | --- | --- | --- |
| `verdict` | `DRIFT_CONFIRMED`, `NO_DRIFT`, `UNVERIFIABLE` | exact enum | Drives status and credit |
| `obligation_classes` | bounded set | set equality | Explains material drift |
| `baseline_license_ids` | bounded SPDX IDs | set equality | Source coverage |
| `target_license_ids` | bounded SPDX IDs | set equality | Source coverage |
| `consequence_class` | contract-derived | must match derived class | Prevents LLM-controlled payouts |

Validator: re-fetches official evidence, re-runs semantic task, compares meaning fields only, rejects non-`gl.vm.Return`, invalid enums, incomplete coverage, extra IDs, or inconsistent consequence class.

## Consequence And Accounting

| Verdict | Canonical state change | Consumer action | Value movement |
| --- | --- | --- | --- |
| `DRIFT_CONFIRMED` | Covenant status `REVIEW_REQUIRED` | Package gate blocks or requires review | Challenger/remediation credit opens |
| `NO_DRIFT` | Covenant remains `ACTIVE` or case closed | Package gate remains allowed | Sponsor-side credit opens for challenge bond |
| `UNVERIFIABLE` | Case `RETRYABLE` | No hard package decision | Funds remain locked or non-penalizing recovery |

Accepted/finalized boundary: public claims use finalized Bradbury receipts and canonical reads.

## Reusable Interface

Write methods: `activate_covenant`, `open_case`, `adjudicate_case`, `withdraw_credit`, `close_expired`.

View methods: `get_covenant`, `get_case`, `get_verdict`, `get_package_status`, `get_credit`, `get_accounting`.

Consumer/callback: none in v1; other builders consume views.

## Threat Model

| Threat | Attack | Mitigation | Test |
| --- | --- | --- | --- |
| Claimant-hosted fake evidence | Challenger submits JSON proving drift | Contract ignores claimant URLs; fetches only registry/SPDX | fake JSON cannot settle |
| Format-valid malicious leader | Leader returns valid JSON but mismatched IDs | Settlement invariants compare exact IDs and derived consequence | invalid meaning rejected |
| Prompt injection in license text | Text says ignore policy | Prompt treats evidence as data; allowed enums only | injection fixture |
| Late case after expiry | Caller opens case with stale `ACTIVE` state | `open_case` checks timestamp directly | boundary tests |
| Double withdrawal | Credited caller repeats withdraw | zero credit before transfer | duplicate withdraw test |

## Test Plan

Happy path: MIT baseline to AGPL target opens `REVIEW_REQUIRED` and challenger credit.

Negative coverage: unauthorized sponsor actions, duplicate IDs, expired activation/open, no active case double settlement, fake source, unsupported license expression, missing SPDX, malicious output, prompt injection, accounting unchanged on rejection, no double withdraw, retryable source failure.

## Claim-To-Code Matrix

| Product claim | Contract method/state | View/read | Direct test | Network evidence |
| --- | --- | --- | --- | --- |
| Official registry/SPDX evidence drives verdict | `adjudicate_case` | `get_verdict` | mocked npm/SPDX happy path and source failure | Bradbury finalized adjudication |
| Drift creates review-required status | `DRIFT_CONFIRMED` state | `get_package_status` | MIT->AGPL case | Bradbury canonical read |
| No claimant-hosted evidence can settle | source allowlist guard | `get_case` | fake JSON rejected | local test; no network claim needed |
| Credits withdraw once | `withdraw_credit` | `get_credit`, `get_accounting` | double-withdraw/accounting test | Bradbury withdraw receipt |
| Expiry is entrypoint-enforced | `open_case`, `close_expired` | `get_covenant` | deadline -1, =, +1 stale-state tests | Bradbury expiry recovery if used |

## Analogue And Differentiation Matrix

| Analogue/prior idea | Similar dimensions | Structural difference | Collision decision |
| --- | --- | --- | --- |
| Open Source License Cure Bond | Software/license domain | This is official package-version drift against a locked use profile, not generic cure or free-form dispute | Allowed with strict scope |
| Semantic Interface Covenant | Software evidence and semantic compatibility | It judges interface behavior and quarantine; this judges registry/SPDX license obligations and review credit | Not duplicate |
| Disclosure Dividend | OSS ecosystem and rewards | It apportions vulnerability reward among researchers; this resolves dependency license drift | Not duplicate |
| Deterministic license scanner | npm/SPDX metadata | Scanner compares strings; contract adjudicates material semantic drift and settles value | Replacement PASS |

## Deployment And Evidence Plan

- Network: `testnet-bradbury`
- GenLayer RPC: `https://rpc-bradbury.genlayer.com`
- Chain ID: `4221`
- Explorer: `https://explorer-bradbury.genlayer.com`
- Faucet: `https://testnet-faucet.genlayer.foundation`
- Actors/wallet separation: sponsor and challenger EOAs if value lifecycle needs adversarial separation.
- Deploy steps: local check, safe config discovery, faucet/balance check, CLI or script deploy with `testnet-bradbury`, schema read, lifecycle txs, finalized receipts, canonical reads.
- Evidence path: `docs/evidence/bradbury/`
- Resume/idempotency: active deployment identity binds network, source commit, contract header/API family, address, txs, and lifecycle IDs.

## Definition Of Done

- [ ] Reusable primitive.
- [ ] Semantic validator judgment.
- [ ] Direct consequence.
- [ ] Reuse proof through documented views.
- [ ] Adversarial direct tests.
- [ ] Bradbury deployment and lifecycle.
- [ ] Canonical evidence.

## Honest Limitations

No legal advice; npm-only v1; SPDX expressions outside the supported grammar are retryable; private commercial licenses are out of scope; no frontend or Vercel deployment is planned for this Intelligent Contracts submission.

## Kill Criteria

Kill or redesign if the verdict becomes deterministic string matching, if actor-hosted evidence can move funds, if the semantic validator checks only JSON shape, if npm/SPDX access fails on Bradbury without a retryable path, or if the design collapses into a generic license-dispute contract.

