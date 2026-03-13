from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import event, text

from backend.config import settings

engine = create_async_engine(settings.db_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    """SQLite WAL 모드 + 성능 최적화"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")  # 64MB
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    """테이블 생성"""
    from backend.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
