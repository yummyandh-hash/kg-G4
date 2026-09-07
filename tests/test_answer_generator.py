from pathlib import Path

from orchestration import answer_generator as ag


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [
                {
                    "message": {
                        "content": "测试回答",
                    }
                }
            ]
        }


def test_generate_uses_chat_completions_endpoint(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(ag.requests, "post", fake_post)

    generator = ag.OpenAICompatibleAnswerGenerator(
        api_key="dummy-key",
        model="tju-llm",
        base_url="https://ai.tju.edu.cn/api/v3/",
    )
    result = generator.generate("苏绣是什么？", [])

    assert captured["url"] == "https://ai.tju.edu.cn/api/v3/chat/completions"
    assert captured["json"]["model"] == "tju-llm"
    assert "messages" in captured["json"]
    assert result.answer == "测试回答"
    assert result.used_llm is True


def test_from_env_loads_repo_env_and_builds_generator(monkeypatch):
    calls = {}

    def fake_load_dotenv(path, override=False):
        calls["path"] = path
        calls["override"] = override
        return True

    monkeypatch.setattr(ag, "load_dotenv", fake_load_dotenv)
    monkeypatch.setenv("LLM_API_KEY", "dummy-key")
    monkeypatch.setenv("LLM_MODEL", "tju-llm")
    monkeypatch.setenv("LLM_BASE_URL", "https://ai.tju.edu.cn/api/v3/")

    generator = ag.OpenAICompatibleAnswerGenerator.from_env()

    assert generator is not None
    assert generator.model == "tju-llm"
    assert generator.base_url == "https://ai.tju.edu.cn/api/v3/"
    assert calls["override"] is False
    assert Path(calls["path"]).name == ".env"
    assert Path(calls["path"]).parent.name == "kg-g5"
