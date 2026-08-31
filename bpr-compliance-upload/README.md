# BPR Compliance Copilot

An AML/CFT screening and regulatory report-drafting copilot for an Indonesian rural bank (**BPR — Bank Perkreditan Rakyat**), built to demonstrate how a real OJK-regulated compliance workflow can be assisted by LLM agents **without ever losing the human sign-off a regulator expects** — every AI-generated flag rationale and report narrative is cross-checked by a second agent, traceable to source facts, and written to an append-only, database-enforced audit trail.

Not a chatbot bolted onto a bank. The agent layer never gets raw database access — it goes through a **read-only FastMCP tool boundary**, mirroring the air-gapped, no-egress LLM inference subnet a real BPR deployment would require.

---

## Architecture

![Architecture diagram](https://raw.githubusercontent.com/MagicDash91/ML-Engineering-Project/main/bpr-compliance-upload/static/arc.png)

---

## Screenshots

![Dashboard](https://raw.githubusercontent.com/MagicDash91/ML-Engineering-Project/main/bpr-compliance-upload/static/b3.JPG)

![Compliance Analysis — LangGraph SQL/Python agent chat](https://raw.githubusercontent.com/MagicDash91/ML-Engineering-Project/main/bpr-compliance-upload/static/b1.JPG)

![Screening Queue](https://raw.githubusercontent.com/MagicDash91/ML-Engineering-Project/main/bpr-compliance-upload/static/b2.JPG)

![Report Editor](https://raw.githubusercontent.com/MagicDash91/ML-Engineering-Project/main/bpr-compliance-upload/static/b4.JPG)

![Audit Explorer](https://raw.githubusercontent.com/MagicDash91/ML-Engineering-Project/main/bpr-compliance-upload/static/b5.JPG)

### Live on AWS (Terraform, `ap-southeast-3`)

The full infrastructure in [`infra/`](./infra) was actually applied to a real AWS account for this deployment — VPC, ALB, ECS Fargate, RDS, CloudFront, all 68 resources — then torn down with `terraform destroy` afterward. These are from that run:

![RDS Postgres — available](https://raw.githubusercontent.com/MagicDash91/ML-Engineering-Project/main/bpr-compliance-upload/static/b6.JPG)

![S3 buckets — frontend + Terraform state](https://raw.githubusercontent.com/MagicDash91/ML-Engineering-Project/main/bpr-compliance-upload/static/b7.JPG)

![ECS cluster and service](https://raw.githubusercontent.com/MagicDash91/ML-Engineering-Project/main/bpr-compliance-upload/static/b8.JPG)

![VPC resource map](https://raw.githubusercontent.com/MagicDash91/ML-Engineering-Project/main/bpr-compliance-upload/static/b9.JPG)

---

## Workflow

### Screening → review → decision → report

```mermaid
flowchart TD
    A[CSV ingestion] -->|malformed / legacy-format rows| Q[(Quarantine)]
    A --> TX[(transactions table)]

    TX --> RULE{Rule-based screening}
    RULE -->|large_amount ≥ IDR 100,000,000| FLAG[Flag created]
    RULE -->|high_frequency: 5+ txns / 24h| FLAG
    RULE -->|profile_deviation| FLAG
    RULE -->|no rule triggered| NONE[No flag]

    FLAG --> SA["LangGraph — Screening Agent<br/>(plain-language rationale)"]
    SA --> RA["LangGraph — Reviewer Agent<br/>(cross-checks rationale actually<br/>references a real triggered rule)"]
    RA --> QUEUE[Screening Queue]

    QUEUE --> CO{Compliance Officer}
    CO -->|accept| ACC[Accepted]
    CO -->|reject| REJ[Rejected]
    CO -->|escalate| ESC[Escalated — senior review]

    ACC & REJ & ESC -.-> AUD[("Audit log<br/>(Postgres trigger — append-only,<br/>UPDATE/DELETE rejected at the DB level)")]

    subgraph MCP["Read-only FastMCP boundary — agents never get a raw DB session"]
        M1["get_customer_transactions()"]
        M2["get_period_summary(period)"]
    end

    RE[Report Editor: draft period] --> M2
    M2 --> RPA["LangGraph — Report Drafting Agent<br/>(every figure traceable to source facts)"]
    RPA --> DRAFT[Draft LBBPR-style report section]
    DRAFT --> APR{Compliance Officer approves?}
    APR -->|yes| FINAL[Approved report section]
    FINAL -.-> AUD

    AUD --> AUDITOR["Auditor — read-only audit explorer<br/>(3rd role, no write access)"]

    style MCP fill:#1f2937,stroke:#6b7280,color:#e5e7eb
    style AUD fill:#3a1f1f,stroke:#e06c75,color:#f3d4d4
```

### AWS deployment topology (Terraform, `infra/`)

```mermaid
flowchart TB
    USER(("Compliance officer /<br/>loan officer / auditor")) -->|HTTPS| CF[CloudFront]
    CF --> S3F["S3 — frontend static export"]
    USER -->|HTTPS| ALB[Application Load Balancer]

    subgraph VPC["VPC — 2 Availability Zones"]
        subgraph PUB["Public subnets"]
            ALB
            NAT1[NAT Gateway A]
            NAT2[NAT Gateway B]
        end
        subgraph APP["Private app subnets"]
            ECS["ECS Fargate<br/>backend-api service<br/>(CPU + request-count autoscaling)"]
        end
        subgraph INF["Private inference subnets — NO internet egress"]
            LLM["Self-hosted LLM<br/>(air-gap simulation)"]
        end
        subgraph DB["Private db subnets"]
            RDS[("RDS Postgres 16")]
        end
    end

    ALB --> ECS
    ECS -->|FastMCP read-only boundary| RDS
    ECS -->|pseudonymized prompts only| LLM
    ECS --> SM["Secrets Manager<br/>app + DB credentials"]
    ECS --> ECR["ECR<br/>backend-api / agent-worker"]

    style INF fill:#3a1f1f,stroke:#e06c75,color:#f3d4d4
```

---

## Key Features

| Feature | Details |
| --- | --- |
| **Rule-based screening** | Large single-transaction amount (≥ IDR 100M), high-frequency (>5 txns/24h), profile deviation — deterministic, auditable thresholds, not a black-box model |
| **Two-agent screening pipeline** | LangGraph screening agent writes a plain-language rationale; an independent reviewer agent cross-checks it actually references a rule that really fired, catching hallucinated justifications before a human ever sees them |
| **Read-only FastMCP boundary** | The report-drafting agent gets `get_customer_transactions()` / `get_period_summary()` tools only — never a raw SQLAlchemy session |
| **DB-enforced immutable audit log** | A Postgres trigger — not just application code — rejects any `UPDATE`/`DELETE` against `audit_log`, verified by running raw SQL against the trigger directly |
| **RBAC on every route** | Three roles (`loan_officer`, `compliance_officer`, `auditor`) enforced server-side, not just hidden in the UI — a loan officer's token gets a 403 on audit endpoints, not just a hidden nav item |
| **CSV ingestion with quarantine** | Malformed / legacy-format rows are routed to a quarantine table instead of silently dropped or crashing the batch |
| **Multi-provider LLM** | Same call interface routes to DeepSeek, Gemini/Gemma, NVIDIA NIM, Mistral (all OpenAI-compatible), or Ollama — swap providers via one config value, zero code changes. Defaults to a deterministic mock (`BPR_USE_MOCK_LLM=true`) so the whole pipeline runs with zero API keys |
| **LangGraph SQL/Python analysis agent** | Natural-language compliance questions ("bar chart of transaction count by type") answered against the live database with generated charts, not canned dashboards |
| **Traceable report drafting** | Every generated narrative sentence is stored alongside the exact source facts it was derived from — an auditor can see the number, not just the sentence |
| **Infrastructure as Terraform** | Full AWS module set — isolated no-egress LLM subnet, multi-AZ ALB, ECS autoscaling, RDS, CloudFront+S3, Secrets Manager, least-privilege IAM — `plan`/`apply`/`destroy` all verified against a real AWS account |

---

## Tech Stack

```
Backend         FastAPI 0.115 + Uvicorn, SQLAlchemy 2.0, Pydantic 2.9
Auth            JWT (python-jose) + bcrypt (direct, not via passlib — see note below)
Agents          LangGraph 0.2 — screening/reviewer graph + report-drafting graph
Agent boundary  FastMCP 3.2 — read-only DB tool server, isolated from the agent's LLM calls
LLM providers   DeepSeek · Gemini/Gemma (OpenAI-compatible) · NVIDIA NIM · Mistral · Ollama
                — provider-agnostic via langchain-openai / langchain-ollama; mock mode by default
Database        PostgreSQL 16 — audit_log immutability enforced by a DB trigger, not app code
Frontend        Next.js 14.2 (App Router) + TypeScript 5.6 + Tailwind 3.4
Charts          Recharts
Markdown        react-markdown + remark-gfm (report/analysis rendering)
Testing         pytest + pytest-asyncio — 14 tests, run against a real (not mocked) Postgres
Infrastructure  Terraform >=1.9, AWS provider ~5.60 — VPC, ALB, ECS Fargate, RDS, CloudFront,
                ECR, Secrets Manager, IAM — S3+DynamoDB remote state backend
```

---

## Roles (RBAC)

| Role | Can do |
| --- | --- |
| `loan_officer` | Log loan decisions, view transactions/customers |
| `compliance_officer` | Everything a loan officer can, plus: screen transactions, accept/reject/escalate flags, draft and approve reports |
| `auditor` | Read-only: audit log explorer, customer history — no write access anywhere, including no access to the flag decision or report editor UI |

All three are enforced in the FastAPI dependency layer per-route, not just conditionally rendered in the frontend nav.

---

## Project Structure

```
bpr-compliance/
├── bpr-compliance-copilot-prd.md   # Source PRD — AML/CFT screening + LBBPR report drafting
│
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, router registration
│   │   ├── config.py                # Settings — LLM provider, DB, mock/real toggle
│   │   ├── db.py / models.py        # SQLAlchemy engine + ORM models
│   │   ├── auth.py                  # JWT issue/verify, bcrypt hashing (direct, not passlib)
│   │   ├── init_db.py               # Schema + audit-log trigger creation, seed data
│   │   ├── mcp_server.py            # FastMCP read-only tool boundary (standalone process)
│   │   │
│   │   ├── agents/
│   │   │   ├── llm.py               # Multi-provider LLM call boundary (mock/real toggle)
│   │   │   ├── graph.py             # LangGraph: screening->reviewer graph, report-drafting graph
│   │   │   └── analysis.py          # LangGraph SQL/Python agent for ad-hoc compliance Q&A
│   │   │
│   │   ├── routers/                 # auth, transactions, flags, reports, loan-decisions,
│   │   │                             # audit-log, customers, dashboard, analysis
│   │   └── services/                # screening rules, ingestion+quarantine, audit, reporting
│   │
│   └── tests/                       # 14 pytest tests incl. audit-immutability, RBAC
│
├── frontend/
│   └── src/app/                     # Next.js App Router: dashboard, screening, analysis,
│                                     # report editor, loan-decisions, audit
│
├── infra/                           # Terraform — see below
│   ├── modules/                     # vpc, rds, ecs, alb, ecr, cloudfront, secrets, iam
│   └── environments/dev/            # Environment wiring + tfvars (verified end-to-end on AWS)
│
└── static/                          # README screenshots
```

---

## Infrastructure (Terraform)

`infra/` provisions the AWS architecture from the PRD's §12: a VPC with an **isolated, no-egress subnet** for LLM inference (simulating the air-gap a real BPR deployment requires), multi-AZ ALB, ECS Fargate with CPU + request-count autoscaling, RDS Postgres, CloudFront+S3 for the frontend, ECR, Secrets Manager, and separate execution/task IAM roles.

```bash
cd infra/environments/dev
terraform init
terraform plan
terraform apply
```

Notes from actually running this end to end:

- **Deployment credentials should not be the AWS root account.** Use a scoped IAM user/role limited to the services this stack touches (VPC, RDS, ECS, ELB, ECR, CloudFront, S3, Secrets Manager, IAM, DynamoDB, plus `application-autoscaling:*` for ECS scaling policies — this last one is easy to miss since it's not covered by `AmazonECS_FullAccess`).
- **Remote state matters even for a demo.** `providers.tf` supports an S3 + DynamoDB `backend "s3"` block for state + locking — don't leave state local once you're actually applying.
- **`terraform plan` succeeding does not guarantee `apply` succeeds.** Two real issues only surfaced at apply time: an RDS engine version unavailable in the target region, and the missing `application-autoscaling:TagResource` IAM permission above. Always budget time for an `apply` pass, not just `plan`.
- **RDS has deletion protection on by default** in the `rds` module — `terraform destroy` will fail on it until you disable it first (`aws rds modify-db-instance --no-deletion-protection --apply-immediately`).

---

## Security

- **RBAC enforced server-side** on every route (see [Roles](#roles-rbac))
- **Immutable audit log** — `audit_log` writes are append-only at the **database** level via a Postgres trigger; verified by attempting raw `UPDATE`/`DELETE` via `psql` directly against the table and confirming rejection
- **Pseudonymized customer references** — the report-drafting agent only ever sees `pseudonymized_id`, never raw PII, and only through the read-only FastMCP tool boundary
- **No raw DB access from the agent layer** — every DB read the agents perform goes through `app/mcp_server.py`'s two tools, never a direct SQLAlchemy session
- **CORS is configurable**, not hardcoded to a single origin
- **JWT + bcrypt** auth, hashed directly via `bcrypt` (not `passlib.CryptContext` — `passlib` 1.7.4 is incompatible with `bcrypt` >= 4.0 in this environment)

---

## API Reference

| Prefix | Endpoints | Purpose |
| --- | --- | --- |
| `/auth` | `POST /login` | Issue JWT |
| `/transactions` | `GET /` | List transactions |
| `/flags` | `POST /screen`, `GET /`, `POST /{flag_id}/decision` | Run screening, list flags, accept/reject/escalate |
| `/customers` | `GET /{customer_ref}/history` | Pseudonymized customer transaction history |
| `/reports` | `POST /draft`, `POST /{report_id}/approve` | Draft a period report section, approve it |
| `/loan-decisions` | `GET /`, `POST /` | Log and list loan committee decisions |
| `/audit-log` | `GET /` | Query the immutable audit trail |
| `/dashboard` | `GET /summary` | Aggregate counts for the overview dashboard |
| `/analysis` | `POST /query` | Natural-language compliance Q&A (LangGraph SQL/Python agent) |

---

## Installation

**Backend:**

```bash
cd backend
pip install -r requirements.txt
python -m app.init_db          # creates schema + audit-log trigger, seeds demo data
uvicorn app.main:app --reload --port 8010
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev -- -p 3010
```

**Environment (`backend/.env`):**

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/bpr_compliance
JWT_SECRET=change-me
BPR_USE_MOCK_LLM=true        # false to route through a real provider below
LLM_PROVIDER=deepseek        # deepseek | gemini | nvidia | mistral | ollama
DEEPSEEK_API_KEY=
CORS_ORIGINS=http://localhost:3010
```

**Standalone FastMCP server** (only needed if running the agent boundary out-of-process):

```bash
python -m app.mcp_server
```

---

## Testing

```bash
cd backend
pytest
```

14 tests run against a real Postgres instance (not mocked), including audit-log immutability (`test_audit_immutability.py`) and RBAC enforcement (`test_auth_rbac.py`) — the tests write into the same dev database, so `test_action` rows are visible in the audit log afterward; this is cosmetic and expected without a separate test database.

---

## License

MIT License — see `LICENSE` for details.

---

## Acknowledgements

- [LangGraph](https://github.com/langchain-ai/langgraph) — screening/reviewer and report-drafting agent graphs
- [FastMCP](https://github.com/jlowin/fastmcp) — read-only DB tool boundary for the agent layer
- [FastAPI](https://fastapi.tiangolo.com/) — backend API framework
- [Next.js](https://nextjs.org/) — frontend framework
- [Terraform](https://www.terraform.io/) + [AWS](https://aws.amazon.com/) — infrastructure as code
