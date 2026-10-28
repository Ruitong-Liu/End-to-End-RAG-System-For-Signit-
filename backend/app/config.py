from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-flash"
    deepseek_api_base: str = "https://api.deepseek.com"
    corpus_dir: str = "../data/demo"
    index_dir: str = "../data/index"
    retrieval_mode: str = "hybrid_rerank"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    reranker_model: str = "BAAI/bge-reranker-base"
    model_device: str = "cpu"
    retrieval_depth: int = Field(20, ge=5, le=100)
    top_k: int = Field(5, ge=1, le=10)
    context_tokens: int = Field(2200, ge=256, le=12000)
    min_rerank_score: float = 0.5
    cache_size: int = Field(128, ge=0, le=2048)
    cache_ttl: int = Field(300, ge=1)
    input_usd_per_million: float = Field(0, ge=0)
    output_usd_per_million: float = Field(0, ge=0)
