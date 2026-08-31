# PRD: Compliance & AML Screening Copilot for BPR (Rural Bank)

**Status:** Draft — portfolio / demo project
**Owner:** Michael Wiryaseputra
**Version:** 0.2
**Last updated:** 2026-08-30

---

## 1. Purpose & Background

BPRs (Bank Perkreditan Rakyat) operate under OJK regulatory oversight but typically run on legacy core banking software, Excel-based reporting, and manual AML/CFT (APU-PPT) screening. Compliance officers manually cross-reference transactions against watchlists and compile monthly regulatory reports (e.g. LBBPR-style) by hand from disconnected sources.

This project builds a copilot that assists — not replaces — the compliance workflow: flagging anomalous transactions, drafting regulatory report sections, and maintaining an immutable audit trail, while preserving human sign-off on every decision that matters to a regulator.

**Portfolio note:** A real BPR deployment would be fully air-gapped and physically on-prem. Since this is a demo/portfolio build, the air-gap constraint is *simulated* rather than physically enforced: the LLM inference layer runs in a private VPC subnet with no internet egress, using a self-hosted model rather than an external LLM API. This preserves the architectural pattern (no PII ever leaves a controlled boundary) while remaining deployable and demonstrable on AWS.

---

## 2. Problem Statement

- AML/CFT screening is manual, slow, and inconsistent across compliance officers
- Monthly regulatory reports are assembled by hand from core banking exports, teller logs, and committee minutes
- Loan committee decisions and their justifications aren't consistently logged in an audit-defensible way
- No single system gives an auditor a clean, traceable record of what was flagged, why, and who signed off

---

## 3. Goals

- G1: Reduce manual AML screening time per reporting cycle by surfacing anomalies automatically, ranked by risk
- G2: Draft regulatory report sections from underlying transaction/loan data, with human review before submission
- G3: Produce an immutable, queryable audit trail for every AI-assisted flag or draft
- G4: Keep all customer PII within a pseudonymization boundary before it ever reaches the LLM
- G5: Support three distinct roles (loan officer, compliance officer, auditor) with appropriate views and permissions

### Non-Goals

- Not submitting reports directly to OJK systems (human-initiated submission only)
- Not writing back to the core banking system (read-only integration)
- Not a general-purpose chatbot — scope is limited to screening, reporting, and audit workflows
- Not using real customer data — synthetic/anonymized data only for this build

---

## 4. Users & Personas

| Persona | Needs |
|---|---|
| **Compliance Officer** | Daily transaction screening queue, explainable flags, draft report generation |
| **Loan Officer** | Log committee decisions with structured rationale, quick lookup of a customer's flag history |
| **Auditor / Admin** | Read-only access to the full audit trail, export capability, user/role management |

---

## 5. Scope

**In scope**
- Transaction ingestion from core banking exports (flat file / CSV simulating legacy export)
- Rule + LLM-assisted anomaly detection for AML/APU-PPT screening
- Draft generation for LBBPR-style monthly report sections
- Structured decision logging for loan committee actions
- Append-only audit log with full rationale trail
- RBAC across the three personas

**Out of scope (this phase)**
- Direct OJK API submission
- Write access to core banking systems
- Mobile app (web only, responsive)
- Multi-bank / multi-tenant support

---

## 6. Functional Requirements

### 6.1 Data Ingestion
- FR-1: System ingests nightly CSV/flat-file exports simulating core banking transaction data
- FR-2: System validates and normalizes inconsistent legacy export formats (missing headers, mixed date formats)
- FR-3: Failed ingestion rows are quarantined with a visible error log, not silently dropped

### 6.2 Screening & Flagging
- FR-4: System screens transactions against configurable rule thresholds (amount, frequency, pattern deviation from customer profile)
- FR-5: LLM agent generates a plain-language rationale for each flagged transaction
- FR-6: A second "reviewer" agent cross-checks the first agent's flag against rule thresholds before it reaches a human
- FR-7: Compliance officer can accept, reject, or escalate any flag; the decision is logged with timestamp and user ID

### 6.3 Regulatory Report Drafting
- FR-8: System drafts LBBPR-style report sections from underlying transaction/loan data
- FR-9: Every generated figure in a draft links back to its source records
- FR-10: Reports are versioned; no draft is auto-finalized without explicit compliance officer sign-off

### 6.4 Audit Trail
- FR-11: Every AI-generated flag, draft, or recommendation is written to an append-only audit log
- FR-12: Audit log entries are immutable (no update/delete path in the API)
- FR-13: Auditor role can search/filter/export the audit log

### 6.5 Access & Roles
- FR-14: Three roles (loan officer, compliance officer, auditor) with distinct permissions enforced at the API layer
- FR-15: All authentication events are logged

---

## 7. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Next.js Frontend (dashboard, screening queue, report editor) │
└───────────────────────────┬─────────────────────────────────┘
                             │ HTTPS (CloudFront + WAF)
┌───────────────────────────▼─────────────────────────────────┐
│  Application Load Balancer (multi-AZ, health checks)          │
└───────────────────────────┬─────────────────────────────────┘
                             │ round-robin across tasks
┌───────────────────────────▼─────────────────────────────────┐
│  FastAPI Backend (ECS Fargate, auto-scaling task group)       │
└───────────┬──────────────────────────────────┬────────────────┘
            │                                  │
┌───────────▼───────────┐          ┌───────────▼────────────────┐
│  LangGraph Agent Layer  │          │  FastMCP Tool Boundary      │
│  - Screening agent      │◄────────►│  - Read-only DB adapters    │
│  - Reviewer agent        │          │  - No write access to core │
│  - Report-drafting agent │          │    banking data             │
└───────────┬──────────────┘          └──────────────────────────┘
            │  (private subnet, no internet egress)
┌───────────▼──────────────────┐
│  Self-hosted LLM (Llama-3.2 /│
│  Gemma-3, fine-tuned)         │
└────────────────────────────────┘
            │
┌───────────▼──────────────────┐      ┌────────────────────────┐
│  PostgreSQL (RDS)             │      │  Pseudonymization vault │
│  - Transactions, flags        │◄────►│  (PII never reaches LLM │
│  - Append-only audit log      │      │   in raw form)           │
└────────────────────────────────┘      └────────────────────────┘
```

---

## 8. Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind |
| Backend | Python, FastAPI |
| Agent orchestration | LangGraph |
| Tool boundary / security | FastMCP |
| LLM inference | Self-hosted (Llama-3.2-3B / Gemma-3-4B, fine-tuned), no external API calls |
| Database | PostgreSQL (Amazon RDS) |
| Vector store (if needed for retrieval) | pgvector |
| Infra as code | Terraform |
| Cloud | AWS (VPC, ECS Fargate or EKS, RDS, S3, ECR, CloudFront, Secrets Manager) |
| Load balancing / scaling | AWS Application Load Balancer (multi-AZ) + ECS service auto-scaling on CPU/request count |
| CI/CD | GitHub Actions → Terraform plan/apply → ECR push → ECS/EKS deploy |
| Observability | CloudWatch + structured JSON logs |

---

## 9. Data Model (high level)

| Entity | Key fields |
|---|---|
| `customer` | pseudonymized_id, risk_profile, created_at |
| `transaction` | id, customer_ref, amount, type, timestamp, source_file |
| `flag` | id, transaction_ref, rule_triggered, agent_rationale, reviewer_verdict, status, decided_by |
| `loan_decision` | id, customer_ref, committee_notes, decision, decided_by, timestamp |
| `report_draft` | id, period, sections (jsonb), status, generated_by, approved_by |
| `audit_log` | id, actor, action, entity_ref, rationale, timestamp (append-only) |
| `user` | id, role, name, auth_provider_id |

---

## 10. API Design (high level)

| Endpoint | Method | Role | Purpose |
|---|---|---|---|
| `/auth/login` | POST | all | Authentication |
| `/transactions` | GET | compliance, auditor | List/filter transactions |
| `/flags` | GET | compliance | Screening queue |
| `/flags/{id}/decision` | POST | compliance | Accept/reject/escalate a flag |
| `/reports/draft` | POST | compliance | Trigger report draft generation |
| `/reports/{id}/approve` | POST | compliance | Sign off on a draft |
| `/loan-decisions` | POST | loan officer | Log committee decision |
| `/audit-log` | GET | auditor | Search/export audit trail |

---

## 11. Security, Privacy & Compliance Requirements

- All PII pseudonymized before reaching any LLM node
- LLM inference nodes run in a private subnet with no NAT/internet egress
- No write access from the agent layer to core banking data — read-only adapters only
- Audit log is append-only at the database level (no UPDATE/DELETE grants on that table)
- RBAC enforced server-side on every endpoint, not just hidden in the UI
- Secrets (DB credentials, API keys) managed via AWS Secrets Manager, never in code or env files
- Synthetic data only in this build — no real customer PII

---

## 12. Infrastructure & Deployment (Terraform + AWS)

**Terraform module structure**
```
infra/
  modules/
    vpc/            # private + public subnets, no egress on inference subnet
    rds/             # PostgreSQL, encrypted at rest
    ecs/              # Fargate services: backend API, agent worker
    alb/               # Application Load Balancer, target groups, health checks
    ecr/               # container registries
    cloudfront/         # Next.js frontend distribution
    secrets/              # Secrets Manager entries
    iam/                    # least-privilege roles per service
  environments/
    dev/
    prod/
```

**Key AWS resources**
- VPC with isolated subnet for LLM inference (no internet route)
- ECS Fargate (or EKS if you want to reuse existing K8s experience) for backend + agent services
- Application Load Balancer in front of the backend, spanning at least 2 AZs, with `/health` target group checks
- ECS service auto-scaling policy (scale out on CPU >70% or request count per target) so the screening queue and report drafting stay responsive under a spike in concurrent officers/auditors
- RDS PostgreSQL, encrypted, private subnet only
- S3 + CloudFront for the Next.js static/SSR frontend (or Amplify if preferring managed hosting)
- ECR for container images
- Secrets Manager for credentials
- CloudWatch for logs/metrics, with alarms on ingestion failures and audit log write failures

---

## 13. CI/CD Pipeline

1. **PR opened** → GitHub Actions runs lint, unit tests, `terraform plan` (posts plan as PR comment)
2. **Merge to main** → build & push Docker images to ECR (backend, agent worker)
3. **Terraform apply** (manual approval gate for prod) → provisions/updates infra
4. **Deploy** → ECS service update / EKS rollout with health checks
5. **Post-deploy** → smoke tests against `/health` endpoints, automatic rollback on failure

---

## 14. Non-Functional Requirements

- **Availability:** target 99.5% for the dashboard (not a live-transaction system, so this is generous)
- **Performance:** screening queue loads flagged transactions in <2s for a 10k-row daily batch
- **Auditability:** every AI-generated artifact traceable to source data and model version used
- **Observability:** structured logs for every agent decision, ingestion job, and API call
- **Scalability:** backend runs behind a multi-AZ ALB with auto-scaling ECS tasks, so a spike in concurrent compliance officers/auditors (e.g. everyone logging in before a reporting deadline) doesn't degrade the screening queue; single-AZ RDS is fine for this phase but the ALB removes the backend as a single point of failure

---

## 15. Milestones & Roadmap

| Week | Deliverable |
|---|---|
| 1 | Terraform base infra (VPC, RDS, ECR) + CI/CD skeleton |
| 2 | Ingestion pipeline + data normalization, FastAPI CRUD + RBAC |
| 3 | LangGraph screening + reviewer agents, self-hosted LLM wired via FastMCP |
| 4 | Report-drafting agent + audit log (append-only) |
| 5 | Next.js frontend: screening queue, report editor, audit explorer |
| 6 | End-to-end testing with synthetic data, deploy to prod environment, polish |

---

## 16. Risks & Open Questions

- **Risk:** Self-hosted LLM accuracy may be insufficient for nuanced AML pattern detection → mitigate with rule-based pre-filtering + human review on all flags
- **Risk:** Legacy export format assumptions may not generalize → build ingestion with a quarantine/error-visibility path from day one
- **Open question:** ECS Fargate vs EKS for the agent workers — EKS gives more control and reuses existing K8s experience, Fargate is faster to stand up for a portfolio timeline
- **Open question:** Whether to source a real (anonymized) BPR dataset or fully synthesize one for realism

---

## 17. Success Metrics

- % reduction in manual screening time (simulated against a baseline manual process)
- Number of flags correctly identified vs. false positive rate on a synthetic labeled test set
- Time from data ingestion to draft report availability
- Full audit trail completeness (100% of AI-assisted actions logged and traceable)
