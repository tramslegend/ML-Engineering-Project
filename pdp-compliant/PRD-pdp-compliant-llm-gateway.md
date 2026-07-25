# Product Requirements Document

## Sentinel — PDP-Compliant LLM Gateway for Indonesian Bank Complaint Triage

| Field | Value |
|---|---|
| Version | 0.1 (draft) |
| Author | Michael Wiryaseputra |
| Date | July 2026 |
| Status | Pre-build |
| Type | Portfolio project / commercial demonstrator |

---

## 1. Problem statement

Indonesian banks receive high volumes of customer complaints through WhatsApp, email, web forms, and call-center transcripts. Triage today is manual: a human reads each complaint, classifies it, assigns severity, routes it to the right unit, and drafts an initial response. The work is repetitive, latency-sensitive, and expensive at volume.

LLMs solve this cleanly on paper. In practice these projects die in legal review, because complaints are dense with personal data — NIK, full name, account number, phone, address, transaction history — and sending that to a foreign model API is a cross-border transfer of personal data under UU PDP.

The industry's two current answers are both bad:

1. **Don't use LLMs.** Forfeits the benefit entirely.
2. **Run everything on-premise.** Correct but capital-intensive, slow to procure, and hard to scale.

**Sentinel is a third answer:** a de-identification boundary combined with in-jurisdiction local inference, which makes LLM-assisted triage legally defensible without on-prem hardware. Personal data never leaves Indonesia. Nothing that crosses any boundary contains identifying information. Every access is auditable.

---

## 2. Regulatory context

This section is a working summary, not legal advice. Any production deployment requires review by qualified Indonesian counsel.

**UU No. 27 Tahun 2022 (Pelindungan Data Pribadi)** is fully in force — the two-year transition expired 17 October 2024. As of May 2026 enforcement sits with Komdigi's Directorate General of Digital Space Supervision, with the dedicated Lembaga PDP still in the establishment process.

Provisions that directly shape this design:

| Provision | Design consequence |
|---|---|
| Cross-border transfer subject to assessment of requirements | Data must stay in `ap-southeast-3`, or be de-identified before transit |
| Data subject right to erasure | Vault-based tokenization makes erasure a single-key delete |
| Breach notification within 3×24 hours | Audit log must support rapid scope determination |
| Administrative fines to 2% of annual revenue; criminal exposure to 6 years | PII recall is a safety metric, not a quality metric |
| Controller/processor obligations | Clear role definition and DPA-ready documentation |

**Design principle derived from the above:** jurisdiction is controlled by *region selection*, not by model ownership. A locally-hosted model on an EC2 instance in Singapore is still a cross-border transfer. All compute runs in `ap-southeast-3` (Jakarta).

---

## 3. Goals and non-goals

### Goals

- **G1.** Demonstrate that LLM-assisted processing of Indonesian personal data can be architected to satisfy UU PDP without on-premise infrastructure.
- **G2.** Achieve measured PII detection recall at or near 100% on Indonesian entity types, with published methodology and honest reporting of misses.
- **G3.** Deliver triage classification accuracy competitive with a human baseline on a held-out labelled set.
- **G4.** Keep the majority of traffic resolved entirely in-jurisdiction by a local model, escalating only low-confidence cases.
- **G5.** Produce a compliance evidence pack — data residency report, audit trail, erasure demonstration — that a bank compliance officer would accept as a starting point.
- **G6.** Run continuously as a live demo at a monthly cost that a freelancer can absorb indefinitely.

### Non-goals

- **NG1.** Not a full complaint management system. No ticketing, SLA tracking, or CRM integration.
- **NG2.** Not a chatbot. No direct customer interaction. Output goes to a human analyst.
- **NG3.** Not a certified compliance product. It is an architectural demonstrator with evidence.
- **NG4.** No autonomous decisions. The system recommends; humans decide.
- **NG5.** Not multi-tenant in v1. Single-tenant, single-region.
- **NG6.** No model training or fine-tuning in v1. Off-the-shelf weights only.

---

## 4. Success metrics

| ID | Metric | Target | Why it matters |
|---|---|---|---|
| M1 | PII detection recall | ≥ 99.5%, misses individually documented | A miss is a notifiable breach |
| M2 | PII detection precision | ≥ 90% | Over-redaction destroys model utility |
| M3 | Prompt injection catch rate | ≥ 95% on internal red-team set | Complaints are attacker-authored text |
| M4 | Triage classification accuracy | Within 5pp of human baseline | Determines whether it's usable at all |
| M5 | Local-resolution rate | ≥ 70% handled without escalation | The core efficiency claim |
| M6 | Cost per complaint | Documented, all tiers | The ROI conversation |
| M7 | p95 end-to-end latency | < 60s | Async is fine; unbounded is not |
| M8 | Idle infrastructure cost | < USD 30/month | Determines whether the demo survives |
| M9 | Erasure completeness | 100% of derived tokens orphaned | Demonstrates the right-to-erasure claim |

M1 is the metric the project lives or dies on. Everything else is negotiable.

---

## 5. Users

**Primary — Complaint analyst (bank operations).** Reads triaged complaints, accepts or overrides the classification, sends the response. Needs re-identified data. Cares about time saved and not being made to look stupid by a wrong suggestion.

**Secondary — Compliance officer / DPO.** Never uses the triage output. Needs the audit trail, the residency report, and the ability to answer "what personal data went where" within hours of an incident.

**Tertiary — Operations lead.** Needs volume, throughput, and cost dashboards to justify continuation.

**Evaluator — Prospective client (the real audience).** A bank CTO or head of digital deciding whether to engage. Needs to see the numbers and the compliance evidence pack in under ten minutes.

---

## 6. System architecture

### 6.1 Trust zones

| Zone | Contents | Data classification |
|---|---|---|
| **Zone A — Restricted** | Raw ingestion, PII detector, token vault, re-identification service, analyst UI | Contains real personal data |
| **Zone B — Internal** | Local LLM inference, orchestration, vector store, guardrails, queues | Tokenized only |
| **Zone C — External** | Escalation tier — frontier model API | Tokenized only, leaves jurisdiction |

**Invariant: no artifact from Zone A crosses into Zone C.** Enforced by making the de-identification service the only path between them, and by a CI test that fails the build if raw text can reach an egress client.

### 6.2 Processing flow

1. **Ingest.** Complaint arrives via API or file upload. Written to encrypted S3 in `ap-southeast-3`. Job enqueued.
2. **Detect.** Indonesian PII detector runs over the text. Every match is classified by entity type and confidence.
3. **Pseudonymize.** Each detected entity is replaced by a stable token (`[ORANG_1]`, `[NIK_1]`, `[REKENING_1]`). Repeated mentions of the same entity within a document receive the same token, preserving referential structure. The mapping is written to the vault.
4. **Guard (input).** Tokenized text is screened for prompt injection and abuse patterns before reaching any model.
5. **Infer (local).** SEA-LION v4 4B classifies, extracts, scores severity, and drafts a response — running entirely in `ap-southeast-3`.
6. **Route.** If the local model's confidence exceeds threshold, proceed. If not, escalate the tokenized text to the frontier tier.
7. **Guard (output).** Model output is checked for policy violations, ungrounded claims, and token leakage before acceptance.
8. **Re-identify.** Tokens are resolved back to real values via the vault. This happens only in Zone A, only for authenticated and authorized users.
9. **Review.** Analyst sees the re-identified result, accepts or overrides. Override is captured as training signal.
10. **Audit.** Every step logs to an append-only store. Re-identification events log the actor.

### 6.3 Model tiers

| Tier | Model | Location | Handles |
|---|---|---|---|
| Local | Qwen-SEA-LION-v4-4B-VL | `ap-southeast-3` | Routine classification, extraction, drafting |
| Escalation | Frontier API (DeepSeek / Gemini) | External | Low-confidence, ambiguous, multi-issue |
| Control | Phi-4-mini, Qwen3 4B | `ap-southeast-3` | Benchmark comparison only |

SEA-LION v4 4B is chosen for Indonesian coverage, edge-suitable size, native Indonesian OCR (which may allow collapsing a separate OCR stage), and 256K context. **Selection must be confirmed by the benchmark in §10, not assumed.** Sahabat-AI (Llama3-8B CPT) is the fallback if the corpus contains substantial Javanese or Sundanese — it was instruction-tuned on ~96k Javanese and ~98k Sundanese pairs, which SEA-LION does not match for dialect depth.

---

## 7. Functional requirements

### F1 — Ingestion

- **F1.1** Accept plain text, PDF, and image uploads via authenticated REST endpoint.
- **F1.2** Return a job ID immediately; processing is asynchronous.
- **F1.3** Store raw input encrypted at rest with a customer-managed KMS key.
- **F1.4** Apply configurable TTL to raw input; default 90 days.
- **F1.5** Reject inputs above a size limit with a clear error.

### F2 — Indonesian PII detection

- **F2.1** Detect the entity types enumerated in Appendix A.
- **F2.2** Apply structural validation where the format permits it — NIK's 16-digit province/regency/date/gender encoding gives near-deterministic detection and should not rely on ML.
- **F2.3** Combine rule-based detection (structured identifiers) with a model-based recognizer (names, addresses, free-text references).
- **F2.4** Handle Indonesian name conventions explicitly, including mononyms and the absence of a surname convention.
- **F2.5** Emit a per-entity confidence score.
- **F2.6** Fail closed: if the detector errors, the document does not proceed.
- **F2.7** Route documents below a configurable detection-confidence floor to human review before any model sees them.

### F3 — Pseudonymization and vault

- **F3.1** Replace each entity with a typed, numbered token.
- **F3.2** Maintain referential consistency within a document.
- **F3.3** Do **not** maintain consistency across documents in v1 — cross-document linkage is a re-identification risk.
- **F3.4** Store mappings in DynamoDB, encrypted with a customer-managed KMS key, in `ap-southeast-3`.
- **F3.5** Vault access is restricted by IAM to the de-identification and re-identification services only. No human IAM principal has read access in normal operation.
- **F3.6** Support single-call erasure: deleting a subject's vault entries orphans every derived token system-wide.

### F4 — Local inference

- **F4.1** Serve the local model within `ap-southeast-3`.
- **F4.2** Accept only tokenized text.
- **F4.3** Produce structured output conforming to a published JSON schema.
- **F4.4** Return a self-reported confidence score per field.
- **F4.5** Enforce a timeout; timeout escalates rather than failing.
- **F4.6** Support hot-swapping the model without redeploying the application.

### F5 — Escalation routing

- **F5.1** Escalate when local confidence falls below threshold, output fails schema validation, or the complaint is flagged multi-issue.
- **F5.2** Threshold configurable at runtime without redeploy.
- **F5.3** Re-verify before egress that the payload contains no untokenized PII. This is a redundant check by design.
- **F5.4** Support provider failover with a circuit breaker.
- **F5.5** Log every escalation with reason, provider, token count, and cost.
- **F5.6** Support a hard kill switch disabling all external egress, degrading to local-only.

### F6 — Guardrails

- **F6.1 (input)** Detect prompt injection in Indonesian and English. Complaint text is untrusted, attacker-authored input.
- **F6.2 (input)** Detect and flag abusive or threatening content for priority human routing.
- **F6.3 (output)** Block responses that give financial advice.
- **F6.4 (output)** Block responses committing the bank to compensation, refund, or remediation.
- **F6.5 (output)** Block responses citing policy not present in the retrieved context.
- **F6.6 (output)** Scan for token leakage — any unresolved token in a customer-facing draft is a defect.
- **F6.7** Every guardrail trigger is logged with the triggering rule and routes to human review rather than silently dropping.

### F7 — Re-identification and access control

- **F7.1** Re-identification executes only inside Zone A.
- **F7.2** Requires an authenticated principal with an explicit re-identify permission.
- **F7.3** Every event logs actor, subject, timestamp, and justification.
- **F7.4** Re-identified content is never written to application logs, traces, metrics, or the observability platform.
- **F7.5** Support partial re-identification — an analyst may need the account number without the NIK.

### F8 — Audit and compliance reporting

- **F8.1** Append-only audit log in S3 with Object Lock in compliance mode.
- **F8.2** CloudTrail data events on the vault table and KMS key.
- **F8.3** Generate a data residency report: per time period, what processing occurred where, and what left the jurisdiction.
- **F8.4** Generate a per-subject access report supporting data subject access requests.
- **F8.5** Support incident scope queries — "which subjects were affected between T1 and T2" — returning within minutes, to serve the 3×24 hour notification window.

### F9 — Human review queue

- **F9.1** Queue for low-confidence, guardrail-triggered, and detection-uncertain items.
- **F9.2** Analyst can accept, edit, or reject.
- **F9.3** All decisions captured as labelled data for evaluation.
- **F9.4** Queue depth and age exposed as metrics.

### F10 — Analyst interface

- **F10.1** List view with severity, category, age.
- **F10.2** Detail view showing the complaint, the classification, the draft response, and confidence.
- **F10.3** Visual indication of which fields were re-identified.
- **F10.4** One-click accept, inline edit, structured reject.
- **F10.5** Read-only compliance view showing the audit trail for the current item.

---

## 8. Non-functional requirements

### Performance
- **N1** p95 end-to-end under 60 seconds for text complaints.
- **N2** Local inference p95 under 30 seconds for a typical complaint.
- **N3** Sustain 100 complaints/hour without queue growth.

### Availability
- **N4** 99% for the ingestion endpoint. Processing may lag; ingestion may not drop.
- **N5** External provider outage degrades to local-only, never to total failure.
- **N6** All processing idempotent and safely retryable.

### Security
- **N7** All data encrypted at rest with customer-managed KMS keys and in transit with TLS 1.2+.
- **N8** Least-privilege IAM. No wildcard resource policies.
- **N9** No long-lived AWS credentials. CI/CD authenticates via OIDC.
- **N10** LLM provider API keys in Secrets Manager, cached via the Parameters and Secrets Lambda Extension, never in environment variables.
- **N11** Vault key rotation enabled.
- **N12** VPC endpoints for S3, DynamoDB, and Secrets Manager. Egress restricted to declared provider endpoints.

### Cost
- **N13** Idle cost under USD 30/month.
- **N14** AWS Budgets alarm at USD 50 with notification.
- **N15** Hard spend caps on all external provider keys.
- **N16** Compute scales to zero when the queue is empty.

### Compliance
- **N17** All processing in `ap-southeast-3`. Enforced by SCP or IAM condition, not convention.
- **N18** Audit log immutable and retained 7 years.
- **N19** Erasure completes within 24 hours of request.

---

## 9. Data model

| Store | Technology | Zone | Contents |
|---|---|---|---|
| Raw documents | S3, SSE-KMS, TTL | A | Original complaint text and files |
| Token vault | DynamoDB, SSE-KMS | A | `subject_id`, `token`, `entity_type`, `real_value`, `created_at` |
| Tokenized documents | S3, SSE-KMS | B | De-identified text |
| Triage results | DynamoDB | B | Classification, severity, draft, confidence, tier used |
| Policy corpus | S3 Vectors | B | Embedded bank policy chunks for grounding |
| Cost ledger | DynamoDB | B | Per-request tokens in/out, provider, tier, cost |
| Audit log | S3 + Object Lock | A | Append-only event stream |
| Eval set | S3 | A | Labelled corpus, access-restricted |

---

## 10. Evaluation plan

Evaluation is not a phase at the end. It is built first, because the metrics are the deliverable.

### 10.1 Corpus

Construct 300–500 synthetic complaints, hand-labelled:
- Realistic Indonesian complaint language, mixed formal and informal
- A deliberate Javanese and Sundanese code-switching subset
- Full Indonesian PII entity coverage per Appendix A
- Ground-truth PII spans, category, severity
- An adversarial subset containing injection attempts

**Synthetic only.** No real customer data enters this project at any stage.

### 10.2 Model benchmark

Run SEA-LION v4 4B, Sahabat-AI 8B, Qwen3 4B, and Phi-4-mini across the corpus. Measure classification accuracy, extraction F1, schema compliance rate, Indonesian and dialect subset performance separately, tokens/sec on the target instance, and memory footprint at Q4_K_M.

Publish the results. This benchmark is a standalone portfolio artifact.

### 10.3 PII red team

Adversarial cases the detector must survive: NIK with spaces or dots, phone numbers written as words, names embedded mid-sentence without capitalization, addresses in non-standard order, account numbers split across lines, mononym names, and nickname references.

Report recall honestly. A published 97% with documented failure modes is more credible than an unverified 100%.

### 10.4 Injection red team

Indonesian-language injection attempts written as plausible complaint text. Measure catch rate; document every bypass.

---

## 11. Infrastructure specification

All resources in `ap-southeast-3`, all defined in Terraform, no console changes.

| Component | Service | Notes |
|---|---|---|
| API | API Gateway HTTP API + Lambda | Presigned S3 upload |
| Queue | SQS + DLQ | Absorbs bursts; concurrency is the throttle |
| Orchestration | Step Functions | Native retries, visual execution history |
| Local inference | ECS Fargate or EC2 ASG, CPU | 4B at Q4_K_M needs no GPU |
| Vault | DynamoDB + KMS CMK | |
| Vector store | S3 Vectors | Scales to zero; storage is cents per GB |
| Secrets | Secrets Manager | Provider keys, rotation enabled |
| Audit | S3 + Object Lock, CloudTrail | Compliance mode |
| Frontend | S3 + CloudFront | |
| CI/CD | GitHub Actions + OIDC | No stored AWS credentials |
| Observability | CloudWatch + X-Ray | Tokenized data only |

**CPU inference is the default.** A 4B model at Q4_K_M is roughly 2.5GB and runs acceptably on general-purpose compute. This avoids the G-family vCPU service quota (defaults to zero and requires a request that can take days), NVIDIA driver and AMI management, and roughly 3× the hourly cost. If the benchmark shows CPU throughput is inadequate, revisit — g5 instances are available in `ap-southeast-3`.

**Terraform practices:** AMI selected via `data "aws_ami"` with a name filter, never a hardcoded ID. Volatile configuration in SSM Parameter Store rather than `user_data`, since `user_data` changes force instance replacement. Model weights baked into a Packer AMI or synced from S3 with checksum verification, never pulled from the internet on boot. Remote state in S3 with DynamoDB locking.

---

## 12. Delivery phases

Scoped for a solo builder working evenings and weekends.

### Phase 0 — Evaluation harness (1 week)
Build the labelled corpus and the scoring scripts. Nothing else starts until this exists.
**Exit:** 300+ labelled complaints, scoring runs end to end.

### Phase 1 — De-identification core (2 weeks)
Indonesian PII detector, pseudonymization, vault, erasure. Runs as a library with a CLI. No AWS yet.
**Exit:** M1 and M2 measured and published.

### Phase 2 — Local inference (1 week)
Model benchmark, winner selected, structured output schema, containerized service.
**Exit:** M4 measured; benchmark published.

### Phase 3 — AWS deployment (2 weeks)
Full Terraform stack in `ap-southeast-3`. Async pipeline operational end to end.
**Exit:** Live endpoint, M7 and M8 measured.

### Phase 4 — Guardrails and escalation (2 weeks)
Injection detection, output policy, grounding check, escalation tier with failover.
**Exit:** M3 and M5 measured.

### Phase 5 — Compliance surface (1 week)
Audit log, residency report, erasure demonstration, analyst UI.
**Exit:** Compliance evidence pack complete.

### Phase 6 — Publication (1 week)
Architecture writeup, benchmark post, live demo, video walkthrough, GitHub release.
**Exit:** Shipped.

**Total: ~10 weeks part-time.** Phases 0–2 alone constitute a defensible portfolio artifact if the schedule slips.

---

## 13. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| PII recall plateaus below target | Undermines the entire claim | Fail-closed design; human review for low-confidence detection; report honestly rather than hiding it |
| 4B model too weak for triage quality | Forces escalation rate up, weakening the local-first claim | Escalation tier already designed in; fall back to Sahabat-AI 8B |
| CPU inference too slow | Forces GPU, raising cost 3× | Benchmark in Phase 2 before committing infrastructure |
| Scope creep into a full complaint system | Never ships | NG1 is explicit; guardrail the roadmap |
| Synthetic corpus unrepresentative | Metrics don't transfer to real data | State the limitation prominently; treat numbers as indicative |
| `ap-southeast-3` service gaps | Architecture rework mid-build | Verify every service's regional availability in Phase 3 planning |
| Regulatory interpretation wrong | Claims don't survive legal review | Frame as demonstrator; obtain counsel review before any client pitch |
| Cost overrun on the live demo | Demo goes offline | Budget alarms, scale-to-zero, hard provider caps |

---

## 14. Open questions

1. Does a GGUF build of the SEA-LION v4 4B VL variant exist? Vision models often lag on quantization support, and the answer determines CPU versus GPU.
2. Can the VL model's native Indonesian OCR replace a separate OCR stage, and at what accuracy cost?
3. What confidence threshold optimizes the local-resolution rate against quality? Empirical, resolved in Phase 4.
4. Does cross-document token consistency have enough analytical value to justify its re-identification risk in a later version?
5. Is the audit log's 7-year retention the correct figure under applicable OJK record-keeping rules? Needs verification.
6. Should the escalation tier be disabled by default, making external egress strictly opt-in per deployment?

---

## Appendix A — Indonesian PII taxonomy

| Entity | Format | Detection approach |
|---|---|---|
| NIK | 16 digits encoding province, regency, DOB, gender | Structural validation — near-deterministic |
| NPWP | 15 or 16 digits | Pattern + checksum |
| Nomor KK | 16 digits | Pattern, disambiguate from NIK by context |
| BPJS number | 13 digits | Pattern |
| Bank account | Variable, bank-specific | Pattern + context keywords |
| Card number | 16 digits | Luhn validation |
| Phone | `+62`, `62`, `08` prefixes | Pattern |
| Email | Standard | Pattern |
| Person name | Mononyms common; no surname convention | Model-based NER, Indonesian-tuned |
| Address | RT/RW, Kelurahan, Kecamatan, Kabupaten | Pattern + NER hybrid |
| Plat nomor | Regional letter prefix + digits + suffix | Pattern |
| Date of birth | Multiple Indonesian formats | Pattern + context |
| Employer / institution | Free text | NER, lower confidence |

Names and addresses are the hard cases. Structured identifiers are near-solved by validation logic; free-text entities carry essentially all of the residual recall risk, and that is where evaluation effort should concentrate.

---

## Appendix B — Terminology

| Term | Meaning |
|---|---|
| De-identification | Removing or replacing identifying elements such that the remaining data cannot reasonably identify a subject |
| Pseudonymization | Replacing identifiers with reversible tokens; reversal requires separately-held information |
| Token vault | The encrypted store holding token-to-value mappings; the only thing that makes pseudonymization reversible |
| Zone A / B / C | Trust zones per §6.1 |
| Escalation | Routing a tokenized document to the external frontier tier when local confidence is insufficient |
| Grounding check | Verifying every factual claim in generated output traces to retrieved source context |
