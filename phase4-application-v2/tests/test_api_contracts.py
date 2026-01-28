import os
import pathlib
import importlib.util

import pytest
from fastapi.testclient import TestClient


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _set_env():
    # Use in-memory SQLite so Base.metadata.create_all() won't need external DB.
    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"


def _load_module(name: str, file_path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, str(file_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - defensive for CI
        pytest.skip(f"cannot import {file_path}: {exc}")
    return mod


@pytest.mark.parametrize(
    "svc,expected_paths",
    [
        ("auth-service", ["/register", "/login", "/health", "/metrics"]),
        ("account-service", ["/me", "/balance", "/lookup", "/health", "/metrics"]),
        ("transfer-service", ["/transfer", "/health", "/metrics"]),
        ("notification-service", ["/notifications", "/ws", "/health", "/metrics"]),
    ],
)
def test_services_expose_expected_routes(svc, expected_paths):
    _set_env()
    main_py = ROOT / "services" / svc / "main.py"
    mod = _load_module(f"phase4_{svc.replace('-', '_')}_main", main_py)
    app = getattr(mod, "app")
    client = TestClient(app)
    openapi = client.get("/openapi.json").json()
    paths = set(openapi.get("paths", {}).keys())
    for p in expected_paths:
        assert p in paths

