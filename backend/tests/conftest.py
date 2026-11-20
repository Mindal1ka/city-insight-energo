"""Спільні фікстури тестів.

Старі тести (написані до появи ролей) звертаються до захищених ендпоінтів без токена —
для них підставляємо енергоменеджера через dependency_overrides. Нові тести перевіряють доступ самі.
"""

import os

os.environ.setdefault("REQUIRE_LOGIN", "0")  # тести доступу ролей перевіряють залежності, а не загальний бар'єр
os.environ.setdefault("SURPLUS_CLASS", "1")  # тести класів перевіряють повну шкалу

import pytest

from app.auth import User, current_user
from app.main import app

LEGACY_MODULES = {"test_independence", "test_forecast", "test_map", "test_solar"}


@pytest.fixture(autouse=True)
def _legacy_energy_manager(request):
    name = request.module.__name__.rsplit(".", 1)[-1]
    if name not in LEGACY_MODULES:
        yield
        return
    app.dependency_overrides[current_user] = lambda: User(
        full_name="Тест", position="Тест", role="energy_manager", role_name="Провідний фахівець з енергозабезпечення")
    try:
        yield
    finally:
        app.dependency_overrides.pop(current_user, None)
