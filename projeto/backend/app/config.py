"""Configurações da aplicação lidas de variáveis de ambiente."""

import os


class Config:
    """Configurações da aplicação e do banco de dados."""

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://radar_api:radar_api@localhost:5432/radar",
    )
    DB_POOL_MIN: int = int(os.getenv("DB_POOL_MIN", "1"))
    DB_POOL_MAX: int = int(os.getenv("DB_POOL_MAX", "10"))
    DB_POOL_TIMEOUT: float = float(os.getenv("DB_POOL_TIMEOUT", "30.0"))
