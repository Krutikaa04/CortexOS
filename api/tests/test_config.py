from cortex.config import Settings


def test_async_db_url_rewrites_managed_scheme():
    s = Settings(db_url="postgres://u:p@db.example.com:5432/cortex")
    assert s.async_db_url.startswith("postgresql+asyncpg://")
    assert "db.example.com" in s.async_db_url


def test_async_db_url_strips_libpq_only_params():
    s = Settings(db_url="postgresql://u:p@h/db?sslmode=require&channel_binding=require")
    url = s.async_db_url
    assert "sslmode" not in url
    assert "channel_binding" not in url


def test_async_db_url_leaves_docker_url_untouched_scheme():
    s = Settings(db_url="postgresql+asyncpg://cortex:pw@cortex-db:5432/cortex")
    assert s.async_db_url == "postgresql+asyncpg://cortex:pw@cortex-db:5432/cortex"


def test_db_connect_args_ssl_from_sslmode():
    s = Settings(db_url="postgres://u:p@h/db?sslmode=require")
    assert s.db_connect_args == {"ssl": True}


def test_db_connect_args_forced_off_and_on():
    assert Settings(db_ssl="false", db_url="postgres://u:p@h/db?sslmode=require").db_connect_args == {}
    assert Settings(db_ssl="true", db_url="postgres://u:p@localhost/db").db_connect_args == {"ssl": True}


def test_db_connect_args_local_dev_no_ssl():
    s = Settings(db_url="postgresql+asyncpg://cortex:pw@cortex-db:5432/cortex", env="dev")
    assert s.db_connect_args == {}


def test_db_connect_args_production_remote_defaults_to_ssl():
    s = Settings(db_url="postgresql://u:p@managed.host/db", env="production")
    assert s.db_connect_args == {"ssl": True}


def test_db_connect_args_production_local_no_ssl():
    s = Settings(db_url="postgresql://u:p@localhost/db", env="production")
    assert s.db_connect_args == {}


def test_allowed_origins_parsing():
    s = Settings(allowed_origins="https://a.vercel.app, https://b.com ,")
    assert s.allowed_origins_list == ["https://a.vercel.app", "https://b.com"]


def test_is_production():
    assert Settings(env="production").is_production
    assert Settings(env="prod").is_production
    assert not Settings(env="dev").is_production
