import os
import logging


class LLMClient:
    """A small wrapper that returns an explainable text for an anomaly.
    If `OPENAI_API_KEY` is set, this stub can be extended to call OpenAI.
    For now it provides a deterministic explanation based on inputs so the
    project runs without external credentials.
    """

    def __init__(self, api_key_env='OPENAI_API_KEY'):
        self.api_key = os.environ.get(api_key_env)

    def explain_anomaly(self, metric_name: str, result: dict) -> str:
        # If user has configured an API key, optionally extend here.
        reason = result.get('reason', 'unknown')
        conf = result.get('confidence', 0.0)
        expl = result.get('explanation', '')

        text = (
            f"Metric {metric_name} flagged as {reason} (confidence={conf:.2f}). "
            f"Details: {expl}"
        )

        if self.api_key:
            logging.info("OPENAI_API_KEY detected but LLM call is not implemented in stub.")

        return text
