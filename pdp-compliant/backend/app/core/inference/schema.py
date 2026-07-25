"""F4.3: the published JSON schema local/escalation models must conform to."""
from app.models.schemas import TriageOutput


def published_schema() -> dict:
    return TriageOutput.model_json_schema()
