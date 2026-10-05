"""Configuração local por .env, com limite de tokens compatível com Ollama."""

import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider

ROOT = Path(__file__).resolve().parents[2]
MODELO_PADRAO = "cinedata-rocket"


@dataclass(frozen=True)
class Config:
    db_path: str
    model: str = MODELO_PADRAO
    snapshot: bool = False


def carregar_ambiente():
    load_dotenv(ROOT / ".env")
    os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
    path = Path(os.getenv("DB_PATH", "cinerocket.db")).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return Config(
        str(path),
        os.getenv("MODELO_LLM", MODELO_PADRAO),
        os.getenv("DB_SNAPSHOT", "false").lower() == "true",
    )


def criar_modelo(nome=MODELO_PADRAO):
    if "cloud" in nome.lower():
        raise ValueError("Escolha um modelo local, sem sufixo cloud.")
    client = AsyncOpenAI(
        base_url="http://127.0.0.1:11434/v1",
        api_key="ollama",
        http_client=httpx.AsyncClient(trust_env=False),
        max_retries=0,
        timeout=None,
    )
    return OpenAIChatModel(
        nome,
        provider=OpenAIProvider(openai_client=client),
        # Ollama 0.35.1 lê max_tokens, não max_completion_tokens.
        profile=OpenAIModelProfile(
            openai_chat_supports_max_completion_tokens=False,
            supports_json_schema_output=True,
        ),
    )
