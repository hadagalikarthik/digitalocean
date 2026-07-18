import os
from collections.abc import Generator

import fakeredis
import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure settings load before app import
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("BASE_URL", "http://testserver")

from app.api.deps import get_db, get_redis
from app.config import get_settings
from app.db.base import Base
from app.main import create_app


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def redis_client() -> Generator[redis.Redis, None, None]:
    client: redis.Redis = fakeredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        client.flushdb()
        client.close()


@pytest.fixture()
def client(db_session: Session, redis_client: redis.Redis) -> Generator[TestClient, None, None]:
    get_settings.cache_clear()
    app = create_app()

    def _override_db() -> Generator[Session, None, None]:
        yield db_session

    def _override_redis() -> redis.Redis:
        return redis_client

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_redis] = _override_redis

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()
