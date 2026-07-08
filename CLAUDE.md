# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指导。

## 项目概述

使用 **LLM-as-Judge** 评估电商客服自动回复的质量。系统对 20 条自动回复与人工参考回复在 4 个维度上进行对比打分，计算加权综合得分并生成 Markdown 报告。

这是一个**离线批处理流水线**，而非 Web 服务。

## 常用命令

```bash
# 安装依赖（venv 已创建）
source .venv/Scripts/activate
pip install -r requirements.txt

# 运行评估流水线
python src/main.py
```

## 架构

流水线包含 **5 个顺序模块**，均位于 `src/` 目录下：

| 模块 | 文件 | 职责 |
|---|---|---|
| DataRouter | `src/data_ruoter.py` | 加载并校验 `data/task3_auto_replies.json` + `data/task3_human_ref.json`，按 `id` 对齐 → `List[Case]` |
| TaskBuilder | `src/task_builder.py` | 加载 `config/prompt_template`，注入 `{user_question}`、`{auto_reply}`、`{human_reply}`、`{analysis}` → 完整 prompt 字符串 |
| LLMJudge | `src/llm_judge.py` | 调用硅基流动 API（`deepseek-ai/DeepSeek-V3`），`temperature=0.1`，`response_format: json_object`，指数退避重试 → 原始 JSON 响应 |
| ResponseBuilder | `src/response_builder.py` | 解析 LLM JSON 输出，解析失败时用正则清洗提取，缺失字段用默认值填充 → `ScoreResult` |
| Reporter | `src/reporter.py` | 计算统计量，筛选最差 3 条 Case，生成 `report.md` |

**数据流向**：JSON 文件 → DataRouter（按 id 对齐）→ TaskBuilder（注入模板）→ LLMJudge（API 调用）→ ResponseBuilder（解析 JSON）→ Reporter（聚合 + 输出报告）

## 评分模型

每条 Case 在单次 API 调用中完成 4 个维度的评分：

| 维度 | 分值范围 | 权重 |
|---|---|---|
| `factual_accuracy`（信息准确性） | 1–5 | 0.35 |
| `problem_resolution`（问题解决度） | 1–5 | 0.35 |
| `politeness`（礼貌亲和度） | 1–5 | 0.20 |
| `hallucination_flag`（幻觉标记） | 0/1 | 0.10（奖励分） |

**综合得分** = `(事实准确性 × 0.35) + (问题解决度 × 0.35) + (礼貌亲和度 × 0.20) + ((1 − 幻觉标记) × 0.10)`。若 `hallucination_flag = 1`，总分再乘以 **0.6** 作为惩罚。

LLM 应返回的 JSON 格式：`{"factual_accuracy": 4, "problem_resolution": 5, "politeness": 3, "hallucination_flag": 0, "reason": "..."}`

## API 集成

- **服务商**：硅基流动（`https://api.siliconflow.cn/v1/chat/completions`）
- **模型**：`deepseek-ai/DeepSeek-V3`
- **鉴权**：请求头中携带 `Bearer {API_KEY}`（密钥存放在 `config/model.yaml` 中，`src/config.py` 统一加载；环境变量 `SILICONFLOW_API_KEY` 可覆盖）
- **参数**：`temperature=0.1`，`max_tokens=1024`，`top_p=0.9`，`response_format={"type": "json_object"}`
- **重试**：最多 3 次，指数退避（超时：1s/2s/4s；服务端错误 429/502/503：5s/10s）
- **降级**：不可恢复的失败时，标记 `is_error=True`，分数设为 `-1`

## 关键文件

- `src/config.py` — 配置加载模块：读取 `config/model.yaml`，提供 API Key、模型参数等统一访问入口
- `config/model.yaml.example` — 配置示例文件；复制为 `model.yaml` 并填入真实 Key 即可使用（已加入 `.gitignore`）
- `config/prompt_template` — 评估提示词模板，注入 Case 数据；定义了 4 个维度的评分细则
- `data/task3_auto_replies.json` — 20 条自动回复，含 `id`、`user_question`、`auto_reply`
- `data/task3_human_ref.json` — 20 条人工参考回复，含 `id`、`human_reference`、`annotator_notes`
- `docs/设计` — 技术设计文档：架构、API 细节、异常处理策略
- `docs/需求规格说明` — 需求文档：业务目标、指标定义、风险分析

## 设计决策

- **单次多维度调用**（每个 Case 一次 API 调用，而非 4 次单独调用）— 降低 API 成本，同时保持各维度评分语境一致
- **幻觉判定为二值标记**（0/1），而非连续分值 — 将其视为安全红线，而非质量谱系
- **容错优先**：单个 Case 失败不阻塞整个流水线；错误 Case 的分数记为 `-1` 并继续进入报告环节
- **仅支持单轮上下文**：当前评估限定于单轮首响质量，不涉及多轮对话
