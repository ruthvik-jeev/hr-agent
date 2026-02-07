from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from ..configs.config import settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.db_url, future=True)
    return _engine
