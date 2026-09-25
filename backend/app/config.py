from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field,SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / '.env', extra='ignore')
    database_url: str = 'mysql+pymysql://impact:impact@localhost:3306/impact?charset=utf8mb4'
    secret_key: str = Field(min_length=32)
    storage_dir: str = './storage'
    cookie_secure: bool = False
    allowed_origin: str = 'http://localhost:5173'
    evaluation_adapter: str = 'mock'
    max_upload_mb: int = 200
    batch_max_files: int = 200
    batch_max_total_mb: int = 2048
    archive_max_expanded_mb: int = 5120
    pdf_max_pages: int = 1000
    task_timeout_seconds: int = 600
    codex_binary: str = ''
    codex_model: str = 'gpt-6-astra'
    codex_reasoning_effort: str = 'medium'
    codex_timeout_seconds: int = 480
    codex_search: bool = True
    codex_max_input_chars: int = 600000
    v19_api_key: SecretStr = SecretStr('')
    v19_base_url: str = ''
    v19_model: str = ''
    v19_transport: str = 'codex'


@lru_cache
def settings():
    return Settings()
