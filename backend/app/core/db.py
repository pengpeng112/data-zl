from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings
from .database_guard import validate_test_database_url

# 111 号 S1：在 create_engine 之前强制测试数据库门禁，防止 --noconftest 或
# 直接 import SessionLocal 绕过门禁误连非测试库。
validate_test_database_url(settings.db_url)

engine = create_engine(
    settings.db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
