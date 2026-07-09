"""
项目配置模块：从 config/model.yaml 加载所有配置项。
所有配置项均定义在 model.yaml 中，缺失时抛出明确错误（无硬编码默认值），
以避免配置未生效而静默回退的问题。

唯一例外：API Key 允许通过环境变量 SILICONFLOW_API_KEY 覆盖。
"""

import os
from pathlib import Path
from typing import Any, Dict

import yaml

# ---- 路径常量 ----
ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "model.yaml"

# ---- 内部配置缓存 ----
_config: Dict[str, Any] = {}


def _load_yaml() -> Dict[str, Any]:
    """从 model.yaml 读取原始配置字典。"""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"配置文件不存在: {CONFIG_PATH}\n"
            f"请参考 config/model.yaml.example 创建你的配置文件。"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        if data is None:
            raise ValueError(f"配置文件为空: {CONFIG_PATH}")
        return data


def _require(section: str, key: str) -> Any:
    """从配置中读取指定字段，缺失时抛出明确错误（无静默回退）。"""
    section_data = _config.get(section)
    if section_data is None:
        raise KeyError(
            f"配置节缺失: {section}\n"
            f"请在 config/model.yaml 中补充 [{section}] 节，参考 config/model.yaml.example。"
        )
    if key not in section_data:
        raise KeyError(
            f"配置项缺失: {section}.{key}\n"
            f"请在 config/model.yaml 中补充该字段，参考 config/model.yaml.example。"
        )
    return section_data[key]


def reload() -> None:
    """重新加载配置（运行时可调用，用于热更新）。"""
    global _config
    _config = _load_yaml()


# 模块导入时自动加载
_config = _load_yaml()


# ================================================================
# 便捷访问函数
# ================================================================


def get_api_key() -> str:
    """
    获取硅基流动 API Key。
    优先读取环境变量 SILICONFLOW_API_KEY，回退至 YAML 配置文件。
    """
    key = os.getenv("SILICONFLOW_API_KEY")
    if key:
        return key
    key = _require("api", "key")
    if not key or key == "your-api-key-here":
        raise EnvironmentError(
            "未找到有效的 API Key。请执行以下任一操作：\n"
            "1. 设置环境变量: export SILICONFLOW_API_KEY=sk-xxx\n"
            "2. 在 config/model.yaml 中填写 api.key 字段\n"
            "参考 config/model.yaml.example 创建配置文件。"
        )
    return key


def get_api_key_masked() -> str:
    """获取脱敏后的 Key，用于日志打印（不泄露完整 Key）。"""
    try:
        key = get_api_key()
        if len(key) <= 8:
            return key[:2] + "***"
        return key[:8] + "..." + key[-4:]
    except (EnvironmentError, KeyError):
        return "[未加载]"


def get_base_url() -> str:
    """API 基础 URL。"""
    return _require("api", "base_url")


def get_model_name() -> str:
    """模型标识名。"""
    return _require("model", "name")


def get_temperature() -> float:
    """推理温度（越低越确定性）。"""
    return _require("model", "temperature")


def get_max_tokens() -> int:
    """单次请求最大输出 token 数。"""
    return _require("model", "max_tokens")


def get_top_p() -> float:
    """核采样阈值。"""
    return _require("model", "top_p")


def get_retry_config() -> dict:
    """重试策略配置。"""
    return {
        "max_attempts": _require("retry", "max_attempts"),
        "backoff_timeout": _require("retry", "backoff_timeout"),
        "backoff_server_error": _require("retry", "backoff_server_error"),
    }
