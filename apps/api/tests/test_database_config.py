from app.config import Settings
from app.database.session import app_database_url


def test_tidb_url_targets_app_database_not_sys() -> None:
    settings = Settings(
        tidb_url="mysql://user:password@example.com:4000/sys",
        app_db_name="cpv_app",
    )

    assert app_database_url(settings) == "mysql+pymysql://user:password@example.com:4000/cpv_app"
