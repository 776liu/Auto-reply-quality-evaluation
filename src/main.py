"""自动回复质量评估流水线 — 主入口"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中（支持 python src/main.py 方式运行）
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.data_router import load_and_align
from src.task_builder import TaskBuilder
from src.llm_judge import LLMJudge
from src.response_builder import ResponseBuilder
from src.reporter import Reporter


def main():
    # 1. 数据加载与对齐
    print("=" * 50)
    print("[1/5] 加载数据...")
    cases = load_and_align()
    print(f"      加载完成，共 {len(cases)} 条 Case")

    # 2. 构建 Prompt
    print("[2/5] 构建 Prompt...")
    builder = TaskBuilder()
    prompts = [builder.build_prompt(case) for case in cases]
    print(f"      共生成 {len(prompts)} 条 Prompt")

    # 3. LLM 评分
    print("[3/5] LLM 评分中...")
    judge = LLMJudge()
    raw_results = []
    for i, prompt in enumerate(prompts):
        case_id = cases[i]["id"]
        print(f"      [{i + 1}/{len(prompts)}] 评分 {case_id} ...")
        raw_results.append(judge.judge(prompt))
    print(f"      评分完成，共 {len(raw_results)} 条")

    # 4. 解析结果
    print("[4/5] 解析评分结果...")
    scores = []
    for case, raw in zip(cases, raw_results):
        result = ResponseBuilder.parse(case["id"], raw)
        scores.append(result)
    error_count = sum(1 for s in scores if s.get("is_error"))
    print(f"      解析完成，{error_count} 条异常")

    # 5. 生成报告
    print("[5/5] 生成报告...")
    reporter = Reporter(scores)
    reporter.print_summary()
    report = reporter.generate_report()
    reporter.save_report(report)
    print("\n流水线执行完毕。")


if __name__ == "__main__":
    main()
