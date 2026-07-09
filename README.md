# 自动回复质量评估流水线

使用 **LLM-as-Judge** 评估电商客服自动回复的质量。系统对 20 条自动回复与人工参考回复在 4 个维度上进行对比打分，计算加权综合得分并生成 Markdown 报告。


## 指标定义

每条 Case 在单次 API 调用中完成 4 个维度的评分：

| 维度 | 分值范围 | 权重 | 说明 |
|---|---|---|---|
| `factual_accuracy`（信息准确性） | 1–5 | 0.35 | 自动回复中的事实性信息与人工参考回复保持一致，无错误或矛盾。5 分=完全正确；3 分=一处明显事实偏差但不影响主干；1 分=核心事实完全错误。 |
| `problem_resolution`（问题解决度） | 1–5 | 0.35 | 回复是否直接、确定性地解决了用户当前问题，提供了可执行的下一步动作或最终答案。5 分=给出具体操作步骤或明确结论；3 分=给出方向但需二次追问；1 分=完全答非所问。 |
| `politeness`（礼貌亲和度） | 1–5 | 0.20 | 措辞是否礼貌、温和，是否包含共情表达。5 分=包含共情词汇，语气柔和；3 分=中性、机械；1 分=命令式或冷冰冰。 |
| `hallucination_flag`（幻觉标记） | 0/1 | 0.10（奖励分） | 回复中是否存在人工参考中未提及、且无法由常识推理得出的"无依据信息"。0=无幻觉，1=存在幻觉。 |

**综合得分计算公式**：

```
综合得分 = (事实准确性 × 0.35) + (问题解决度 × 0.35) + (礼貌亲和度 × 0.20) + ((1 − 幻觉标记) × 0.10)
```

**补充惩罚规则**：若 `hallucination_flag = 1`，最终综合得分 **乘以 0.6**，以体现"一票否决"的严重性。

LLM 应返回的 JSON 格式：

```json
{"factual_accuracy": 4, "problem_resolution": 5, "politeness": 3, "hallucination_flag": 0, "reason": "..."}
```

## 评估方法

### 核心策略：LLM-as-Judge

采用高性能大语言模型（SiliconFlow / DeepSeek-V3）作为统一评判员：

- **一致性**：避免人工评分的主观波动。
- **可解释性**：可要求模型输出评分理由，便于追溯。
- **效率**：20 条数据可在数分钟内完成全维度评分。

### 数据流图

```
  auto_replies.json (20 条)
         │
         v
human_ref.json  ─────> 数据加载与校验 (DataRouter)
                                   │  按 id 对齐，输出 List[Case]
                                   v
                            Prompt 组装 (TaskBuilder)
                                   │  注入 {user_question}, {auto_reply}, {human_reply}, {analysis}
                                   v
                            LLM 评判 (LLMJudge)
                                   │  硅基流动 API, DeepSeek-V3
                                   │  temperature=0.1, response_format=json_object
                                   v
                            结果解析 (ResponseBuilder)
                                   │  解析 JSON，缺失字段兜底
                                   v
                            指标聚合与报告 (Reporter)
                                   │  计算统计量，筛选最差 Case
                                   v
                              report.md
```

### 模块划分

| 模块 | 文件 | 职责 |
|---|---|---|
| DataRouter | `src/data_ruoter.py` | 加载并校验 `data/task3_auto_replies.json` + `data/task3_human_ref.json`，按 `id` 对齐 → `List[Case]` |
| TaskBuilder | `src/task_builder.py` | 加载 `config/prompt_template`，注入 Case 字段 → 完整 prompt 字符串 |
| LLMJudge | `src/llm_judge.py` | 调用硅基流动 API（`deepseek-ai/DeepSeek-V3`），指数退避重试 → 原始 JSON 响应 |
| ResponseBuilder | `src/response_builder.py` | 解析 LLM JSON 输出，解析失败时用正则清洗提取，缺失字段用默认值填充 → `ScoreResult` |
| Reporter | `src/reporter.py` | 计算统计量，筛选最差 3 条 Case，生成 `report.md` |

### API 集成细节

- **服务商**：硅基流动（`https://api.siliconflow.cn/v1/chat/completions`）
- **模型**：`deepseek-ai/DeepSeek-V3`
- **鉴权**：请求头中携带 `Bearer {API_KEY}`（密钥存放在 `config/model.yaml` 中，环境变量 `SILICONFLOW_API_KEY` 可覆盖）
- **参数**：`temperature=0.1`，`max_tokens=1024`，`top_p=0.9`，`response_format={"type": "json_object"}`
- **重试策略**：
  - 超时：指数退避（1s / 2s / 4s），最多 3 次
  - 服务端错误（429 / 502 / 503）：等待后重试（5s / 10s），最多 3 次
- **降级**：不可恢复的失败时，标记 `is_error=True`，分数设为 `-1`

### 设计决策

- **单次多维度调用**（每个 Case 一次 API 调用，而非 4 次单独调用）— 降低 API 成本，同时保持各维度评分语境一致。
- **幻觉判定为二值标记**（0/1），而非连续分值 — 将其视为安全红线，而非质量谱系。
- **容错优先**：单个 Case 失败不阻塞整个流水线；错误 Case 的分数记为 `-1` 并继续进入报告环节。
- **仅支持单轮上下文**：当前评估限定于单轮首响质量，不涉及多轮对话。

## 局限性

| 风险 | 影响分析 | 应对策略 |
|---|---|---|
| LLM 评分偏见 | 模型可能对特定措辞（如数字、长句）有过严或过宽的倾向。 | 对比人工标注的 analysis 做调优，必要时引入 Few-shot 示例。 |
| 单轮上下文不足 | 20 条数据均为单轮对话，若真实场景含多轮，评估可能失准。 | 明确当前评估仅限"单轮首响"，后续迭代可引入对话历史拼接。 |
| 人工参考回复质量 | 若 `human_reply` 本身就有错误，评估基准会失效。 | 在报告中备注异常 Case，建议业务方抽检人工标准。 |
| 幻觉判定边界 | 常识性内容（如"请您登录官网"）是否算幻觉？ | 在 Prompt 中明确"显式业务信息"才判幻觉，通用操作话术不标记。 |
| LLM 评分一致性 | 即使 temperature=0.1，LLM 输出仍存在随机性；相同输入在多次运行中可能产生略有差异的分数。 | 使用低温度参数降低方差；对于关键决策，建议多次运行取均值，或增加人工抽检环节。 |

## AI 工具使用声明

本项目在以下环节使用了 AI 工具（Claude Code 内置 DeepSeek V4 Pro）：

- **代码骨架生成**：部分模块（如 Reporter）的初始代码结构由 AI 生成，我进行了审阅、修改和补全。
- **Code Review**：AI 协助审查了模块间的逻辑链路，发现了字段不匹配、公式重复、统计污染等问题，由我确认并逐条修复。
- **Prompt 设计**：评分 Prompt 模板的核心指标和"强化主动服务判定"规则由我设计，AI 协助优化了措辞和 JSON 格式约束。
- **文档撰写**：本 README 的初稿骨架由 AI 辅助生成，内容由我从设计文档和需求文档中整理填充。

核心设计决策（指标定义、综合得分公式、异常兜底策略、模块划分）均由我独立完成。所有代码经过我逐行审阅和测试验证后提交。

## 项目结构

```
Auto-reply-quality-evaluation/
├── config/
│   ├── model.yaml              # API 密钥与模型配置（已 gitignore）
│   ├── model.yaml.example      # 配置示例，复制后填入真实 Key 即可
│   └── prompt_template         # 评估提示词模板，定义 4 个维度的评分细则
├── data/
│   ├── task3_auto_replies.json # 20 条自动回复（含 id, user_question, auto_reply）
│   └── task3_human_ref.json   # 20 条人工参考回复（含 id, human_reference, annotator_notes）
├── docs/
│   ├── 设计                     # 技术设计文档：架构、API 细节、异常处理策略
│   └── 需求规格说明             # 需求文档：业务目标、指标定义、风险分析
├── results/                    # 输出目录（生成的 report.md 存放于此）
├── src/
│   ├── main.py                 # 主入口：串联 5 个模块，输出进度
│   ├── config.py               # 配置加载：读取 model.yaml，提供统一访问入口
│   ├── data_ruoter.py          # 数据加载与对齐
│   ├── task_builder.py         # Prompt 组装器
│   ├── llm_judge.py            # LLM 评判引擎（API 调用 + 重试）
│   ├── response_builder.py     # 结果解析与存储
│   └── reporter.py             # 指标聚合与报告生成
├── CLAUDE.md                   # Claude Code 项目指导
├── README.md                   # 本文件
└── requirements.txt            # Python 依赖
```

## 运行方式

### 环境准备

```bash
# 克隆仓库
git clone <repo-url>
cd Auto-reply-quality-evaluation

# 创建并激活虚拟环境
python -m venv .venv
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate    # Linux/macOS

# 安装依赖
pip install -r requirements.txt

# 配置 API 密钥
cp config/model.yaml.example config/model.yaml
# 编辑 config/model.yaml，填入你的硅基流动 API Key
```

### 运行评估流水线

```bash
python src/main.py
```

运行后将生成 `results/report.md`，并在终端打印统计摘要。
