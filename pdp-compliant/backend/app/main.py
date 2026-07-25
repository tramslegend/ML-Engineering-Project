"""
Sentinel — PDP-compliant LLM gateway. FastAPI app entrypoint.

This process is the scaffold's stand-in for API Gateway + Lambda + Step
Functions (§11) — everything downstream of the router layer is written so
that lifting it into that architecture is a packaging exercise, not a
rewrite: each pipeline step in app/pipeline.py is already a discrete,
idempotent function.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import analyst, compliance, ingestion, ops, reidentify, review_queue

app = FastAPI(
    title="Sentinel — PDP-Compliant LLM Gateway",
    description="Indonesian bank complaint triage with a de-identification boundary. See PRD-pdp-compliant-llm-gateway.md.",
    version="0.1.0",
)

# Dev-only: the vanilla JS frontend is served separately (frontend/) during
# local development. A real deployment serves it from CloudFront/S3 on the
# same origin as the API, making this unnecessary.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion.router)
app.include_router(analyst.router)
app.include_router(reidentify.router)
app.include_router(review_queue.router)
app.include_router(compliance.router)
app.include_router(ops.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "region": "ap-southeast-3"}
