from pydantic import BaseModel
from dotenv import load_dotenv
import os

# Load .env file before reading environment variables
load_dotenv()


class Settings(BaseModel):
    demo_user_email: str = os.getenv("DEMO_USER_EMAIL", "alex.kim@acme.com")
    db_url: str = os.getenv("DB_URL", "sqlite:///./hr_demo.db")

    llm_provider: str = os.getenv(
        "LLM_PROVIDER", "openai_compatible"
    )  # openai_compatible
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_model: str = os.getenv(
        "LLM_MODEL", "gpt-4o-mini"
    )  # or your Databricks endpoint name

    # API Server settings
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))


settings = Settings()
