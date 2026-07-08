"""
项目配置模块：从 config/model.yaml 加载所有配置项。

配置优先级：环境变量 > YAML 默认值（API Key 可被环境变量 SILICONFLOW_API_KEY 覆盖）。
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
            f"   配置文件不存在: {CONFIG_PATH}\n"
            f"   请参考 config/model.yaml.example 创建你的配置文件。"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        if data is None:
            raise ValueError(f"  配置文件为空: {CONFIG_PATH}")
        return data


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
    key = _config.get("api", {}).get("key", "")
    if not key or key == "your-api-key-here":
        raise EnvironmentError(
            "   未找到有效的 API Key。请执行以下任一操作：\n"
            "   1. 设置环境变量: export SILICONFLOW_API_KEY=sk-xxx\n"
            "   2. 在 config/model.yaml 中填写 api.key 字段\n"
            "   参考 config/model.yaml.example 创建配置文件。"
        )
    return key


def get_api_key_masked() -> str:
    """获取脱敏后的 Key，用于日志打印（不泄露完整 Key）。"""
    try:
        key = get_api_key()
        if len(key) <= 8:
            return key[:2] + "***"
        return key[:8] + "..." + key[-4:]
    except EnvironmentError:
        return "[未加载]"


def get_base_url() -> str:
    """API 基础 URL。"""
    return _config.get("api", {}).get("base_url", "https://api.siliconflow.cn/v1/chat/completions")


def get_model_name() -> str:
    """模型标识名。"""
    return _config.get("model", {}).get("name", "deepseek-ai/DeepSeek-V3")


def get_temperature() -> float:
    """推理温度（越低越确定性）。"""
    return _config.get("model", {}).get("temperature", 0.1)


def get_max_tokens() -> int:
    """单次请求最大输出 token 数。"""
    return _config.get("model", {}).get("max_tokens", 1024)


def get_top_p() -> float:
    """核采样阈值。"""
    return _config.get("model", {}).get("top_p", 0.9)


def get_retry_config() -> dict:
    """重试策略配置。"""
    return _config.get("retry", {
        "max_attempts": 3,
        "backoff_timeout": [1, 2, 4],
        "backoff_server_error": [5, 10],
    })
