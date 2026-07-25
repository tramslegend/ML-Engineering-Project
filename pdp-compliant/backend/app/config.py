"""
Central configuration for Sentinel.

Local-dev stand-ins for AWS primitives, so the same interfaces (vault store,
audit store, secrets) can be swapped for real DynamoDB / S3 / Secrets Manager
implementations in Phase 3 without touching calling code. See infra/ for the
Terraform that would back these in ap-southeast-3.
"""
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SENTINEL_", env_file=".env", extra="ignore")

    # --- Region / compliance (§2, N17) ---
    aws_region: str = "ap-southeast-3"
    require_in_region: bool = True

    # --- Storage (local stand-ins; see infra/ for target AWS services) ---
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    vault_db_path: Path = data_dir / "vault.db"          # -> DynamoDB (F3.4)
    app_db_path: Path = data_dir / "app.db"               # -> DynamoDB triage results / review queue
    cost_ledger_db_path: Path = data_dir / "cost_ledger.db"  # -> DynamoDB cost ledger (F5.5, M6)
    audit_log_path: Path = data_dir / "audit_log.jsonl"    # -> S3 + Object Lock (F8.1)
    raw_docs_dir: Path = data_dir / "raw"                  # -> S3 SSE-KMS (F1.3), Zone A
    tokenized_docs_dir: Path = data_dir / "tokenized"      # -> S3 SSE-KMS, Zone B

    # --- Vault encryption stand-in (F3.4). Real deployment: KMS CMK. ---
    vault_encryption_key: str = "dev-only-insecure-key-replace-in-deployment"

    # --- Ingestion (F1) ---
    raw_input_ttl_days: int = 90
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB

    # --- PII detection (F2) ---
    detection_confidence_floor: float = 0.60  # below this -> human review before any model sees it (F2.7)

    # --- Local inference (F4) ---
    local_inference_url: str = "http://localhost:11434"  # Ollama-compatible default
    local_inference_model: str = "sea-lion-v4-4b"
    local_inference_timeout_s: float = 30.0  # N2
    # No live SEA-LION/Ollama endpoint is running by default in this
    # scaffold — see backend/app/pipeline.py docstring. Local tier stays
    # mocked (heuristic, low-confidence) until one is; that low confidence
    # is what routes every complaint to the real escalation tier below.
    use_mock_local_inference: bool = True

    # --- Escalation (F5) ---
    escalation_confidence_threshold: float = 0.75
    escalation_enabled: bool = True  # open question 6: default true here, flip via env in real deployment
    escalation_provider: str = "deepseek"
    escalation_kill_switch: bool = False  # F5.6 hard kill switch

    # N10 in spirit only (real deployment: Secrets Manager, never env vars) —
    # local dev reads from backend/.env, which is .gitignore'd. Unprefixed
    # (no SENTINEL_) so they match the naming already used in sibling
    # projects' .env files.
    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", validation_alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-v4-flash", validation_alias="DEEPSEEK_MODEL")
    # Safe-by-default (no API spend unless explicitly opted in). Flipped to
    # false via SENTINEL_USE_MOCK_ESCALATION=false in backend/.env.
    use_mock_escalation: bool = True

    # --- Guardrails (F6) ---
    injection_block_threshold: float = 0.70

    # --- Audit (F8) ---
    audit_retention_years: int = 7

    # --- Auth (dev-only stand-in; real deployment: proper IdP/OIDC) ---
    dev_api_token: str = "dev-analyst-token"
    dev_reidentify_token: str = "dev-reidentify-token"


settings = Settings()

for _dir in (settings.data_dir, settings.raw_docs_dir, settings.tokenized_docs_dir):
    _dir.mkdir(parents=True, exist_ok=True)
