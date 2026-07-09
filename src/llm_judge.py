# src/judge_engine.py

import time
from openai import OpenAI
from src.config import get_api_key, get_base_url, get_model_name, get_temperature, get_max_tokens, get_top_p, get_retry_config


class LLMJudge:
    """调用硅基流动 API 进行评分，包含指数退避重试"""

    def __init__(self):
        self.client = OpenAI(
            api_key=get_api_key(),
            base_url=get_base_url()   
        )
        self.model_name = get_model_name()
        self.temperature = get_temperature()
        self.max_tokens = get_max_tokens()
        self.top_p = get_top_p()
        self.retry_config = get_retry_config()

    def judge(self, prompt: str) -> dict:
        """发送评分请求，返回原始响应字典或错误信息"""
        max_attempts = self.retry_config["max_attempts"]       
        backoff_timeout = self.retry_config["backoff_timeout"] 
        backoff_server_error = self.retry_config["backoff_server_error"]  

        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=self.top_p,
                    response_format={"type": "json_object"}
                )

                return {"raw_response": response.choices[0].message.content}

            except Exception as e:
                error_msg = str(e)


                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    if attempt < max_attempts - 1:
                        wait = backoff_timeout[attempt]
                        print(f"[LLMJudge] 超时重试 {attempt + 1}/{max_attempts}，等待 {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"[LLMJudge] 超时重试耗尽 ({max_attempts} 次): {error_msg}")
                        return {"error": f"超时重试耗尽: {error_msg}"}


                elif "500" in error_msg or "502" in error_msg or "503" in error_msg or "rate" in error_msg.lower():
                    if attempt < max_attempts - 1:
                        wait = backoff_server_error[attempt] if attempt < len(backoff_server_error) else backoff_server_error[-1]
                        print(f"[LLMJudge] 服务器错误重试 {attempt + 1}/{max_attempts}，等待 {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"[LLMJudge] 服务器错误重试耗尽 ({max_attempts} 次): {error_msg}")
                        return {"error": f"服务器错误重试耗尽: {error_msg}"}

                # 其他未知错误，不重试，直接返回
                else:
                    return {"error": f"未知错误: {error_msg}"}

        return {"error": "重试耗尽（未知原因）"}