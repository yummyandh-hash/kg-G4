from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv

from orchestration.models import Evidence


@dataclass
class GenerationResult:
    answer: str
    provider: str = "extractive"
    used_llm: bool = False


class AnswerGenerator(Protocol):
    def generate(self, query: str, evidences: list[Evidence]) -> GenerationResult:
        ...


class EvidenceAnswerGenerator:
    """Deterministic evidence-grounded fallback used when no LLM is configured."""

    def generate(self, query: str, evidences: list[Evidence]) -> GenerationResult:
        if not evidences:
            return GenerationResult(answer="现有证据不足以回答。")

        snippets = []
        for evidence in evidences[:3]:
            text = " ".join(evidence.content.split())
            snippets.append(text[:180])

        answer = "根据现有证据：" + "；".join(snippets)
        return GenerationResult(answer=answer, provider="extractive", used_llm=False)


class OpenAICompatibleAnswerGenerator:
    """Minimal OpenAI-compatible chat completion client."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout

    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[1]

    @classmethod
    def from_env(cls) -> "OpenAICompatibleAnswerGenerator | None":
        load_dotenv(cls._repo_root() / ".env", override=False)
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        if not api_key:
            return None
        return cls(api_key=api_key, model=model, base_url=base_url)

    def _chat_completions_url(self) -> str:
        root = self.base_url.rstrip("/") + "/"
        return urljoin(root, "chat/completions")

    def generate(self, query: str, evidences: list[Evidence]) -> GenerationResult:
        prompt = build_prompt(query, evidences)
        response = requests.post(
            self._chat_completions_url(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You answer questions about Chinese intangible "
                            "cultural heritage using only the provided evidence."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        answer = data["choices"][0]["message"]["content"].strip()
        return GenerationResult(
            answer=answer,
            provider=f"openai-compatible:{self.model}",
            used_llm=True,
        )


def build_prompt(query: str, evidences: list[Evidence]) -> str:
    evidence_blocks = []
    for idx, evidence in enumerate(evidences, start=1):
        source = evidence.source_url or evidence.source_id or "unknown source"
        path = " -> ".join(evidence.relation_path)
        evidence_blocks.append(
            "\n".join(
                [
                    f"[{idx}] content: {evidence.content}",
                    f"source: {source}",
                    f"path: {path}" if path else "path: none",
                ]
            )
        )

    evidence_text = "\n\n".join(evidence_blocks) or "No evidence."
    return (
        "请只依据下面的证据回答问题，不要编造证据中不存在的信息。"
        "如果证据明显不足，请回答“现有证据不足以回答”。\n\n"
        f"问题：{query}\n\n证据：\n{evidence_text}"
    )
