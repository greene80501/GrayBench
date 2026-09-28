# Protected Value Track Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the separately named protected semantic Qiskit track around explicit value contracts and evidence-gated task admission, without treating candidate-controlled serialization as proof of native Python or Qiskit objects.

**Architecture:** Public task contracts define the allowed input and value representation; private oracle cases and expected results remain in a separate trusted artifact. An isolated candidate process returns only a bounded declared value. A trusted process checks that value against frozen semantic cases. A release manifest lists every intended normal or hard task and every exclusion before generation, while individual task cards carry requirement, alternative, mutant, and independent-review evidence. The existing ledger and provider adapters schedule generations under a new track ID, with native and protected reports kept separate.

**Tech Stack:** Python 3.12, Pydantic 2, SQLite, Docker, pinned Qiskit 2.4.2 image, pytest.

**Spec:** `docs/superpowers/specs/2026-09-27-dual-track-qhe-design.md`

## Global Constraints

- New protected track ID: `graybench-protected-semantic-v1`; existing `upstream`, graph recipe, and `qhe-pinned-native-v1` IDs keep their meanings.
- One report contains exactly one of normal or hard. A public-contract revision cannot be reported as an unchanged pinned QHE task.
- A candidate may fabricate any valid value the public task permits. No score claims that a native class, side effect, alias, method call, or in-process operation was attested unless the declared value contract actually makes it observable.
- Candidate containers have no private tests, reference answers, credentials, host user files, or Docker socket. The judge lives outside the candidate process and uses bounded typed data.
- All 302 pinned task records enter the admission inventory, including eight external-service tasks per suite. No admission decision is inferred from a reference pass, a successful transport, or an absence of known findings.
- A release declares the expected task IDs and exclusions before scored generation. Unsupported value interfaces, infrastructure errors, unreviewed cards, and missing evidence block a publication score.
- The new track remains development-only until two independent qualified task reviews, complete controls, capability checks, and clean-machine reproduction have been verified. Do not create a headline score from this plan's foundation increment.
- Preserve historical ledgers, task bytes, recipe identities, and prior evidence.

## Review Focus

- A card with a positive reference but no wrong mutant or independent alternative must remain pending; Task 1 tests this.
- A card cannot claim QHE identity after its public prompt or output contract changes; Tasks 1 and 3 test ancestry and new contract IDs.
- Candidate-supplied serialized bytes are an answer value, never attestation of the native object or computation that produced them; Tasks 2 and 3 test this.
- Private cases and expected values must never enter a provider request or candidate container; Tasks 2 and 4 test boundaries.
- A partial or post-hoc selected task set cannot acquire a 151-task or admitted-release label; Tasks 1 and 4 test frozen population and exclusions.

---

### Task 1: Machine-checkable task admission inventory

**Files:**
- Create: `engine/src/graybench/task_admission.py`
- Create: `engine/tests/test_task_admission.py`
- Modify: `engine/src/graybench/cli.py`

**Interfaces:**
- Consumes: `JudgeTask`, pinned `PINS`, `load_suite`, `Contract`, `source_manifest`.
- Produces: `TaskCard` with track, source suite/key/digest, optional revised public-contract digest, requirement-level test/alternative/mutant evidence, known findings, dependency status, and two independent reviewer attestations; `AdmissionInventory` with 302 ordered card identities and pinned source provenance; `build_pending_inventory(cache: Path) -> AdmissionInventory`; `validate_inventory(inventory, cache: Path) -> None`; `admission_blockers(card: TaskCard) -> tuple[str, ...]`. The CLI command `admission-inventory CACHE OUTPUT` writes a content-addressed, all-pending artifact without admitting tasks.

- [x] **Step 1: Write failing tests** for all 302 pinned records, distinct normal/hard keys, exact source digests, preservation of eight external-service tags per suite, altered pinned file rejection, missing/duplicate card rejection, absent revised public contract, positive-only controls, missing negative mutants, unresolved known findings, and duplicate or unqualified reviewers. Assert all generated cards remain pending and no release score can be derived from them.
- [x] **Step 2: Run** `engine/.venv/Scripts/python.exe -m pytest engine/tests/test_task_admission.py -q`; expect missing interface failure.
- [x] **Step 3: Implement** the contracts and pure validators. Use evidence digests rather than model-generated judgments or free-text claims as proof of a control; reviewer attestations remain explicit evidence records, not cryptographic identity claims. Re-read pinned parquet and require the exact 302 ordered keys on validation. Add the CLI writer with exclusive creation.
- [x] **Step 4: Run** focused tests against synthetic and real pinned caches, Ruff, and the full admission CLI for 302 pending cards; expect no admitted tasks.
- [x] **Step 5: Commit** the inventory foundation and tests.

### Task 2: Bounded value-only candidate boundary

**Files:**
- Create: `engine/src/graybench/protected_value_contract.py`
- Create: `engine/src/graybench/protected_value_worker.py`
- Create: `engine/src/graybench/protected_value_runner.py`
- Create: `engine/tests/test_protected_value_runner.py`

**Interfaces:**
- Consumes: one frozen public task/value contract, a first returned completion, an immutable image and limits.
- Produces: an explicit versioned JSON value channel with a strict bounded type/shape schema and a candidate runner that receives only public instructions and call inputs. Candidate stdout cannot be a verdict. The host treats a declared valid value as the answer, without claiming it proves native object origin.

- [x] **Step 1: Write failing tests** for exact public-only mounts, no oracle/test bytes, bounded depth/size, non-finite numbers, duplicate keys, wrong output shape, early exit, forged pass text, candidate encoder monkeypatch, and multiple private-input calls. A forged but semantically valid value is allowed as a value answer, not accepted as native-object evidence.
- [x] **Step 2: Run** focused tests and record the initial failures.
- [x] **Step 3: Implement** the standalone worker and host supervisor with explicit result-channel and resource identities. Keep private cases outside the candidate container; the judge may send call inputs but not expected outputs or test code.
- [x] **Step 4: Run** focused tests and pinned-image controls; commit.

### Task 3: Trusted semantic oracle and reviewed controls

**Files:**
- Create: `engine/src/graybench/protected_semantic_judge.py`
- Create: `engine/src/graybench/protected_task20.py`
- Create: `engine/tests/test_protected_semantic_judge.py`
- Add: reviewed task-20 value-contract evidence under `docs/reliability-evidence/`.

**Interfaces:**
- Consumes: Task 2 value channel and frozen private case/test manifest.
- Produces: `ProtectedSemanticJudge.evaluate(task, completion) -> Judgment` with manifest containing the revised public contract, oracle/test hashes, value schema, image, resource limits and track; a task-20 GHZ-state value-contract development example with reference and independent-correct controls plus deliberate wrong mutants.

- [ ] **Step 1: Write failing tests** for correct alternatives, wrong-sized and empty-state mutants, fabricated pass markers, source/test drift, malformed or unsupported values, and disclosure boundaries. Show explicitly that a valid GHZ value can pass without proving the candidate constructed a native `QuantumCircuit`.
- [ ] **Step 2: Run** focused tests; expect failure.
- [ ] **Step 3: Implement** the trusted oracle and one honest public representation revision, keeping its ancestry and new contract ID visible. Do not mark the task admitted merely because these automated cases pass.
- [ ] **Step 4: Run** pinned-image reference and mutant controls, Ruff; commit.

### Task 4: Frozen protected campaigns and release-blocked reporting

**Files:**
- Modify: `engine/src/graybench/contracts.py`
- Modify: `engine/src/graybench/ledger.py`
- Modify: `engine/src/graybench/ledger_evidence.py`
- Create: `engine/src/graybench/protected_campaign.py`
- Create: `engine/tests/test_protected_campaign.py`
- Modify: `engine/src/graybench/cli.py`

**Interfaces:**
- Consumes: Tasks 1-3, existing `GenerationRunner`, append-only judgment claim path, and pinned source/runtimes.
- Produces: a separate `graybench-protected-semantic-v1` development campaign and suite-specific report whose denominator and exclusions are frozen before generation. Publication remains false until a later independent release gate verifies complete admission and reproduction.

- [ ] **Step 1: Write failing tests** for cross-track and cross-suite rejection, request/test/oracle/source drift, interrupted judgment, missing/unsupported case blocking, no post-hoc task removal, 143-versus-151 labeling, and historical V3/native ledger compatibility.
- [ ] **Step 2: Run** focused tests; expect failure.
- [ ] **Step 3: Implement** additive protocol identity and CLI plan/create/step commands, reusing exact-request generation and claim-first judgment. Keep all output development-only and expose every exclusion.
- [ ] **Step 4: Run** focused tests, full engine suite, Ruff, and pinned-image reference/wrong controls; commit and update the draft PR.

## Follow-on release work

This plan builds a general protected value boundary and admission record; it does not complete the 302 task reviews. Subsequent review work must author defensible contracts, positive alternatives, wrong mutants, and reviewer attestations for every included task, then implement an external release gate and clean-machine reproduction. Adapter source attestation, typed provider settings, response extraction correction, and provider campaigns remain separate blockers. Existing graph recipes are retained as historical development evidence and must not be silently promoted into this new track.
