import os
import time
from openai import OpenAI
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class TjuLlmClient:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL")
        self.model_name = os.getenv("LLM_MODEL")
        self.client = None

        if not all([self.api_key, self.base_url, self.model_name]):
            print("[WARN] LLM环境变量缺失，LLM不可用")
            return

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(self, messages: list, temperature=0.1, max_tokens=512):
        if self.client is None:
            return None
        t0 = time.time()
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            cost = time.time() - t0
            content = resp.choices[0].message.content
            print(f"[LLM测速]耗时 {cost:.2f}s")
            return content
        except Exception as e:
            print(f"[LLM ERROR] {e}")
            return None


if __name__ == "__main__":
    llm = TjuLlmClient()
    out = llm.chat(messages=[{"role":"user","content":"简单介绍苏绣"}])
    print("\n输出结果：")
    print(out)
