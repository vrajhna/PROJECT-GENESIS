"""Versioned prompt templates. No model call happens without a versioned prompt."""

from __future__ import annotations

PROMPTS: dict[str, dict[str, str]] = {
    "spec.extract": {
        "v1": "Extract structured requirements (id, description, priority, acceptance, verification) from this specification. Ask for clarification when essential requirements are ambiguous. Never invent integrations, credentials or business requirements.\n\nSPECIFICATION:\n{spec}",
    },
    "plan.make": {
        "v1": "Produce an implementation plan (phases, dependencies, acceptance per phase) for these requirements. Keep each phase small and verifiable.\n\nREQUIREMENTS:\n{requirements}",
    },
    "test.interpret": {
        "v1": "Interpret these test results. Report root cause hypotheses ranked by evidence, never by confidence. Propose the smallest verifying test for each.\n\nRESULTS:\n{results}",
    },
    "repair.propose": {
        "v1": "Propose the minimal patch fixing this failure. Touch the fewest files possible. State which tests prove the fix and which regressions to run.\n\nFAILURE:\n{failure}",
    },
}


def get_prompt(name: str, version: str = "latest") -> tuple[str, str]:
    versions = PROMPTS.get(name)
    if not versions:
        raise KeyError(f"unknown prompt: {name}")
    if version == "latest":
        version = sorted(versions)[-1]
    template = versions.get(version)
    if template is None:
        raise KeyError(f"unknown version {version} for prompt {name}")
    return version, template


def render(name: str, variables: dict[str, str], version: str = "latest") -> tuple[str, str]:
    resolved, template = get_prompt(name, version)
    try:
        return resolved, template.format(**variables)
    except KeyError as e:
        raise KeyError(f"missing prompt variable: {e}")
