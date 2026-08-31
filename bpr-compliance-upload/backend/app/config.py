from urllib.parse import urlsplit, urlunsplit

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://bpr:bpr@localhost:5433/bpr_compliance"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # LLM inference layer. Mirrors the PRD's air-gapped self-hosted LLM node
    # (Llama-3.2 / Gemma-3, private-subnet, no egress). This is a portfolio
    # build so there is no real fine-tuned model to host; BPR_USE_MOCK_LLM=false
    # flips the same interface over to a live model to demonstrate the
    # architecture works end-to-end with a real model. BPR_LLM_PROVIDER picks
    # which one -- "deepseek" (original) or "gemini" (Gemma via Google's
    # OpenAI-compatible endpoint, free-tier) -- both go through the same
    # langchain_openai.ChatOpenAI interface, so no calling code branches on
    # provider.
    use_mock_llm: bool = True
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemma-4-31b-it"
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    mistral_api_key: str = ""
    mistral_base_url: str = "https://api.mistral.ai/v1"
    mistral_model: str = "mistral-small-latest"
    ollama_api_key: str = ""
    ollama_base_url: str = "https://ollama.com"
    ollama_model: str = "gemma4:31b-cloud"

    # Compliance Analysis's one deliberate exception to the PRD's air-gapped,
    # no-egress LLM design: a fallback research step (Tavily web search,
    # Wikipedia, ArXiv) reached ONLY when the internal SQL/Python analysis
    # genuinely couldn't answer a question (see analysis.py's _needs_research)
    # -- never a first resort, and it never gets database contents, only the
    # user's own question text.
    tavily_api_key: str = ""

    # Compliance Analysis agent (LangGraph + LangChain SQL Agent + LangChain
    # pandas/Python agent). These agents generate and execute their own SQL /
    # Python, so -- unlike the rest of the agent layer, which only ever reads
    # through the FastMCP tool boundary in app/mcp_server.py -- they connect
    # to Postgres directly. To keep the "agents get no write access to core
    # banking data" invariant anyway, they connect as a dedicated read-only
    # role (bpr_analyst_ro, provisioned by init_db.py) instead of the app's
    # normal read-write credential, and that role is never granted SELECT on
    # the users table (avoids exposing auth_provider_id/hashed_password to
    # LLM-generated queries).
    analyst_ro_password: str = "change-me-analyst-ro"

    quarantine_dir: str = "../data/quarantine"

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3010"]

    class Config:
        env_prefix = "BPR_"
        env_file = ".env"

    @property
    def analysis_database_url(self) -> str:
        parts = urlsplit(self.database_url)
        host = parts.hostname or "localhost"
        if parts.port:
            host = f"{host}:{parts.port}"
        netloc = f"bpr_analyst_ro:{self.analyst_ro_password}@{host}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


settings = Settings()
