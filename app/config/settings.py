import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("DB_PATH", "data/crypto.db")

    bitpin_base_url: str = os.getenv(
        "BITPIN_BASE_URL",
        "https://api.bitpin.ir",
    ).rstrip("/")

    markets_path: str = os.getenv(
        "BITPIN_MARKETS_PATH",
        "/api/v1/mkt/markets/",
    )

    bars_path: str = os.getenv(
        "BITPIN_BARS_PATH",
        "/v1/mkt/tv/get_bars/",
    )

    timeout: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
