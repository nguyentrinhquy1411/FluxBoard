from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings


def app_database_url(settings: Settings) -> str:
    if not settings.tidb_url:
        return "sqlite:///./cpv_local.db"
    parsed = urlsplit(settings.tidb_url)
    scheme = "mysql+pymysql" if parsed.scheme == "mysql" else parsed.scheme
    path = f"/{settings.app_db_name}"
    return urlunsplit((scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def server_database_url(settings: Settings) -> str:
    if not settings.tidb_url:
        return app_database_url(settings)
    parsed = urlsplit(settings.tidb_url)
    scheme = "mysql+pymysql" if parsed.scheme == "mysql" else parsed.scheme
    return urlunsplit((scheme, parsed.netloc, parsed.path or "/sys", parsed.query, parsed.fragment))


def engine_kwargs(settings: Settings) -> dict:
    if settings.tidb_url and settings.tidb_require_ssl:
        return {"pool_pre_ping": True, "connect_args": {"ssl": {}}}
    return {"pool_pre_ping": True}


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(app_database_url(settings), **engine_kwargs(settings))


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with session_scope() as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_database_exists(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not settings.tidb_url:
        return
    engine = create_engine(server_database_url(settings), **engine_kwargs(settings))
    with engine.begin() as connection:
        connection.execute(text(f"CREATE DATABASE IF NOT EXISTS `{settings.app_db_name}`"))
