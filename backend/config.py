from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DeepSeek LLM (primary)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # Gemini Flash (fallback)
    gemini_api_key: str = ""

    # App
    app_port: int = 8100
    db_path: str = "./data/geojisekki.db"
    log_path: str = "./logs/crawler.log"

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # CORS
    allowed_origins: list[str] = [
        "https://geoji-sekki.zzimong.com",
        "http://localhost:5173",
        "http://localhost:8100",
    ]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path}"

    @property
    def db_abs_path(self) -> Path:
        return Path(self.db_path).resolve()


settings = Settings()
