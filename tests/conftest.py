from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_storage(monkeypatch, tmp_path: Path):
    """
    Изолируем на тест файловое хранилище (rate_limit / metrics / logs) в свежую tmp-директорию,
    и глушим внешние интеграции (AI/SMTP), чтобы тесты не били наружу.
    """
    from app.core import config
    from app.repositories import metrics as m_repo
    from app.repositories import rate_limit as rl_repo

    monkeypatch.setattr(config.settings, "storage_dir", str(tmp_path))
    monkeypatch.setattr(config.settings, "smtp_user", "")
    monkeypatch.setattr(config.settings, "smtp_password", "")
    monkeypatch.setattr(config.settings, "openrouter_api_key", "")
    monkeypatch.setattr(config.settings, "rate_limit_max", 1000)
    monkeypatch.setattr(config.settings, "rate_limit_window_seconds", 60)

    m_repo._store = None
    rl_repo._store = None
    yield
    m_repo._store = None
    rl_repo._store = None


@pytest.fixture()
def client(monkeypatch):
    """TestClient со свежим приложением и заглушённой отправкой писем."""

    async def _no_send(*args, **kwargs):
        return None

    # Сервис contact импортирует функции по имени — патчим именно на нём.
    monkeypatch.setattr("app.services.contact.send_owner_notification", _no_send)
    monkeypatch.setattr("app.services.contact.send_user_confirmation", _no_send)

    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
