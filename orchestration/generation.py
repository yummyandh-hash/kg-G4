import os
from typing import Optional

import requests
from dotenv import load_dotenv


class LLMGenerator:
    """调用 OpenAI-compatible Chat Completions API 生成最终答案。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 60,
    ):
        load_dotenv()

        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model or os.getenv("LLM_MODEL")
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "")).rstrip("/")
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")

        if not self.model:
            raise ValueError("LLM_MODEL 未配置")

        if not self.base_url:
            raise ValueError("LLM_BASE_URL 未配置")

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"

    def generate(
        self,
        question: str,
        context: str,
    ) -> str:
        """根据用户问题和检索上下文生成最终答案。"""

        system_prompt = (
            "你是中国非物质文化遗产知识问答助手。"
            "请严格依据提供的检索证据回答用户问题。"
            "不要编造证据中没有出现的事实。"
            "如果证据不足，请明确说明当前检索证据不足，"
            "不要自行补充无法从证据得到的信息。"
        )

        user_prompt = (
            f"用户问题：\n{question}\n\n"
            f"以下是检索系统提供的证据：\n"
            f"{context}\n\n"
            "请基于以上证据给出准确、简洁、自然的中文回答。"
        )

        response = requests.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                "temperature": 0.2,
            },
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        try:
            answer = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"LLM 返回格式异常：{data}"
            ) from exc

        if not answer or not answer.strip():
            raise RuntimeError("LLM 返回了空答案")

        return answer.strip()