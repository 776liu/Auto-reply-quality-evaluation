import json
import re


class ResponseBuilder:
    """解析 LLM 返回的 JSON，处理异常情况"""

    @staticmethod
    def parse(case_id: str, llm_result: dict) -> dict:
        """
        输入：
            case_id: 数据 id（如 "case_01"）
            llm_result: LLMJudge 返回的字典（{"raw_response": "..."} 或 {"error": "..."}）
        输出：ScoreResult 字典
        """
        # 1. LLM 调用失败
        if "error" in llm_result:
            return {
                "id": case_id,
                "factual_accuracy": -1,
                "problem_resolution": -1,
                "politeness": -1,
                "hallucination_flag": -1,
                "reason": llm_result["error"],
                "is_error": True,
                "raw_response": ""
            }

        raw_text = llm_result.get("raw_response", "")

        # 2. 尝试解析 JSON
        try:
            scores = json.loads(raw_text)
        except json.JSONDecodeError:
            # 3. 清洗 Markdown 代码块后再试
            cleaned = ResponseBuilder._clean_json(raw_text)
            if cleaned:
                try:
                    scores = json.loads(cleaned)
                except json.JSONDecodeError:
                    return ResponseBuilder._error(case_id, raw_text, "JSON解析失败")
            else:
                return ResponseBuilder._error(case_id, raw_text, "JSON解析失败且清洗无效")

        # 4. 提取字段，缺失时填充 -1 并在 reason 中标记 MISSING_FIELD
        expected_fields = ["factual_accuracy", "problem_resolution", "politeness", "hallucination_flag"]
        missing = [f for f in expected_fields if f not in scores]

        result = {
            "id": case_id,
            "factual_accuracy": scores.get("factual_accuracy", -1),
            "problem_resolution": scores.get("problem_resolution", -1),
            "politeness": scores.get("politeness", -1),
            "hallucination_flag": scores.get("hallucination_flag", -1),
            "reason": scores.get("reason", ""),
            "is_error": False,
            "raw_response": raw_text
        }

        if missing:
            result["reason"] = f"MISSING_FIELD: {', '.join(missing)} | " + result["reason"]

        return result

    @staticmethod
    def _clean_json(text: str) -> str:
        """清洗 LLM 返回文本，尝试提取 JSON 对象（处理 Markdown 代码块包裹）"""
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return match.group(0) if match else ""

    @staticmethod
    def _error(case_id: str, raw_text: str, reason: str) -> dict:
        """生成错误结果"""
        return {
            "id": case_id,
            "factual_accuracy": -1,
            "problem_resolution": -1,
            "politeness": -1,
            "hallucination_flag": -1,
            "reason": reason,
            "is_error": True,
            "raw_response": raw_text
        }