"""
全局配置。所有配置项在这一个文件里集中管理。
从 .env 自动加载,支持环境变量覆盖。
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM 相关配置。"""
    model_config = SettingsConfigDict(env_prefix="LLM_", extra="ignore")
    
    primary_model: str = "gpt-4o-mini"
    fallback_model: str = "claude-3-5-haiku-latest"
    temperature: float = 0.0
    max_tokens: int = 2048
    request_timeout: int = 60   # 秒
    
    openai_api_key: SecretStr = Field(...)
    anthropic_api_key: SecretStr | None = None


class DatabaseSettings(BaseSettings):
    """数据库配置。"""
    model_config = SettingsConfigDict(env_prefix="DB_", extra="ignore")
    
    postgres_url: str = Field(
        default="postgresql://athena:athena@localhost:5432/athena",
        description="Postgres 连接串,生产环境从 env 读"
    )
    pool_min_size: int = 5
    pool_max_size: int = 20
    redis_url: str = "redis://localhost:6379/0"


class GraphSettings(BaseSettings):
    """LangGraph 行为配置。"""
    model_config = SettingsConfigDict(env_prefix="GRAPH_", extra="ignore")
    
    max_research_topics: int = 6        # planner 最多拆几个方向
    max_revision_count: int = 2         # reviewer 最多打回几次
    recursion_limit: int = 50           # 递归上限
    parallel_researchers: int = 5       # 并行研究员数
    hitl_timeout_seconds: int = 1800    # 人工审核超时,30 分钟


class CostSettings(BaseSettings):
    """成本守门配置。"""
    model_config = SettingsConfigDict(env_prefix="COST_", extra="ignore")
    
    max_cost_per_task_cny: float = 1.0           # 单任务最大 ¥1
    cost_warning_threshold_cny: float = 0.5       # 超过 ¥0.5 告警
    gpt_4o_mini_input_cny_per_1k: float = 0.001
    gpt_4o_mini_output_cny_per_1k: float = 0.004


class ObservabilitySettings(BaseSettings):
    """可观测性配置。"""
    model_config = SettingsConfigDict(env_prefix="OBS_", extra="ignore")
    
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "athena-prod"
    otel_endpoint: str = "http://localhost:4317"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"


class Settings(BaseSettings):
    """聚合所有子配置。"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    env: Literal["dev", "staging", "prod"] = "dev"
    service_name: str = "athena"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    llm: LLMSettings = Field(default_factory=LLMSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    graph: GraphSettings = Field(default_factory=GraphSettings)
    cost: CostSettings = Field(default_factory=CostSettings)
    obs: ObservabilitySettings = Field(default_factory=ObservabilitySettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """全局唯一的 Settings 实例,FastAPI 注入用。"""
    return Settings()