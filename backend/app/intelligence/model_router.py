"""Model router: routine → Spark, complex → Wonder. IDs from env only."""

from __future__ import annotations

from .meta_client import MetaClient, MetaConfig

COMPLEX_HINTS = ("architect", "debug", "multi-file", "plan", "schema", "threat")


class ModelRouter:
    def __init__(self, client: MetaClient | None = None) -> None:
        self.client = client or MetaClient()

    def pick_model(self, task_kind: str) -> str:
        cfg: MetaConfig = self.client.config
        if any(h in task_kind.lower() for h in COMPLEX_HINTS):
            return cfg.advanced_model
        return cfg.primary_model

    def run(self, task_kind: str, user_input: str) -> dict:
        model = self.pick_model(task_kind)
        result = self.client.respond(model, user_input)
        result["model"] = model
        result["task_kind"] = task_kind
        return result
