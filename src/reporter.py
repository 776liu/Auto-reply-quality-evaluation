from typing import List, Dict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT_DIR / "results"


class Reporter:
    """计算统计量，筛选最差 Case，生成 Markdown 报告"""

    def __init__(self, scores: List[Dict]):
        """
        输入：ResponseBuilder 解析后的 ScoreResult 列表
        """
        self.scores = scores
        # 排除 is_error=True 的数据
        self.valid_scores = [s for s in scores if not s.get("is_error", False)]
        self.error_count = len(scores) - len(self.valid_scores)

    def compute_statistics(self) -> Dict:
        """计算四个维度的统计量"""
        if not self.valid_scores:
            return {"error": "无有效数据"}

        n = len(self.valid_scores)

        # 计算各维度平均分
        avg_factual = sum(s["factual_accuracy"] for s in self.valid_scores) / n
        avg_resolution = sum(s["problem_resolution"] for s in self.valid_scores) / n
        avg_politeness = sum(s["politeness"] for s in self.valid_scores) / n
        avg_hallucination = sum(s["hallucination_flag"] for s in self.valid_scores) / n

        # 计算综合得分
        composite_scores = []
        for s in self.valid_scores:
            score = (
                s["factual_accuracy"] * 0.35 +
                s["problem_resolution"] * 0.35 +
                s["politeness"] * 0.20 +
                (1 - s["hallucination_flag"]) * 0.10
            )
            # 有幻觉时额外惩罚
            if s["hallucination_flag"] == 1:
                score *= 0.6
            composite_scores.append(score)

        avg_composite = sum(composite_scores) / n

        return {
            "total_cases": len(self.scores),
            "valid_cases": n,
            "error_cases": self.error_count,
            "avg_factual_accuracy": round(avg_factual, 2),
            "avg_problem_resolution": round(avg_resolution, 2),
            "avg_politeness": round(avg_politeness, 2),
            "avg_hallucination_flag": round(avg_hallucination, 2),
            "avg_composite_score": round(avg_composite, 2),
            "composite_scores": composite_scores
        }

    def find_worst_cases(self, top_n: int = 3) -> List[Dict]:
        """筛选综合得分最低的 N 条 Case"""
        # 给每条数据计算综合得分
        scored = []
        for s in self.valid_scores:
            score = (
                s["factual_accuracy"] * 0.35 +
                s["problem_resolution"] * 0.35 +
                s["politeness"] * 0.20 +
                (1 - s["hallucination_flag"]) * 0.10
            )
            if s["hallucination_flag"] == 1:
                score *= 0.6
            scored.append({**s, "composite_score": round(score, 2)})

        # 按综合得分升序排列，取最低的 N 条
        scored.sort(key=lambda x: x["composite_score"])
        return scored[:top_n]

    def generate_report(self) -> str:
        """生成 Markdown 报告"""
        stats = self.compute_statistics()
        worst = self.find_worst_cases()

        lines: List[str] = []

        # ===== 标题 =====
        lines.append("# 自动回复质量评估报告")
        lines.append("")

        # ===== 1. 统计摘要 =====
        lines.append("## 一、统计摘要")
        lines.append("")
        lines.append(f"- **总 Case 数**：{stats['total_cases']}")
        lines.append(f"- **有效数据**：{stats['valid_cases']} 条")
        lines.append(f"- **评分错误/失败**：{stats['error_cases']} 条")
        lines.append("")

        lines.append("| 维度 | 平均分 | 满分 |")
        lines.append("|------|--------|------|")
        lines.append(f"| 事实准确性 (factual_accuracy) | {stats['avg_factual_accuracy']} | 5 |")
        lines.append(f"| 问题解决度 (problem_resolution) | {stats['avg_problem_resolution']} | 5 |")
        lines.append(f"| 礼貌亲和度 (politeness) | {stats['avg_politeness']} | 5 |")
        lines.append(f"| 幻觉率 (hallucination_flag) | {stats['avg_hallucination_flag']:.1%} | 0 (越低越好) |")
        lines.append("")
        lines.append(f"**综合得分（加权）**：**{stats['avg_composite_score']}** / 5")
        lines.append("")

        # ===== 2. 评分分布 =====
        lines.append("## 二、综合得分分布")
        lines.append("")

        # 按分数段统计
        ranges = [
            (4.0, 5.01, "优秀 (4.0–5.0)"),
            (3.0, 4.0, "良好 (3.0–4.0)"),
            (2.0, 3.0, "一般 (2.0–3.0)"),
            (0.0, 2.0, "较差 (0.0–2.0)"),
        ]
        lines.append("| 分数段 | 数量 |")
        lines.append("|--------|------|")
        for lo, hi, label in ranges:
            count = sum(1 for s in stats["composite_scores"] if lo <= s < hi)
            lines.append(f"| {label} | {count} |")
        lines.append("")

        # ===== 3. 最差 Case 详情 =====
        lines.append("## 三、最差 Case 详情")
        lines.append("")
        lines.append(f"以下为综合得分最低的 {len(worst)} 条 Case：")
        lines.append("")

        for i, case in enumerate(worst, 1):
            lines.append(f"### 3.{i} Case `{case['id']}`")
            lines.append("")
            lines.append(f"- **综合得分**：**{case['composite_score']}** / 5")
            lines.append("")
            lines.append("| 维度 | 得分 |")
            lines.append("|------|------|")
            lines.append(f"| 事实准确性 | {case['factual_accuracy']} |")
            lines.append(f"| 问题解决度 | {case['problem_resolution']} |")
            lines.append(f"| 礼貌亲和度 | {case['politeness']} |")
            lines.append(f"| 幻觉标记 | {case['hallucination_flag']} |")
            lines.append("")

            # 错误原因（如有）
            if case.get("is_error"):
                lines.append(f"⚠️ **错误原因**：{case.get('reason', '未知')}")
                lines.append("")
            elif case.get("reason"):
                # LLM 给出的评分理由
                reason = case["reason"].replace("\n", " ").strip()
                lines.append(f"📝 **评分理由**：{reason}")
                lines.append("")

        return "\n".join(lines)

    def save_report(self, report: str, filename: str = "report.md") -> Path:
        """保存报告到 results/ 目录"""
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        path = RESULTS_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"报告已保存到: {path}")
        return path

    def print_summary(self):
        """终端打印统计摘要"""
        stats = self.compute_statistics()
        if "error" in stats:
            print("无有效数据")
            return

        print(f"\n{'='*50}")
        print(f"评估统计摘要")
        print(f"{'='*50}")
        print(f"总计: {stats['total_cases']} 条")
        print(f"有效: {stats['valid_cases']} 条")
        print(f"错误: {stats['error_cases']} 条")
        print(f"{'='*50}")
        print(f"事实准确性:     {stats['avg_factual_accuracy']} / 5")
        print(f"问题解决度:     {stats['avg_problem_resolution']} / 5")
        print(f"礼貌亲和度:     {stats['avg_politeness']} / 5")
        print(f"幻觉率:         {stats['avg_hallucination_flag']:.1%}")
        print(f"综合得分:       {stats['avg_composite_score']} / 5")
        print(f"{'='*50}\n")