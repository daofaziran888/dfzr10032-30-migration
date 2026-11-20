"""FastAPI 接口测试：仅在装有 fastapi + httpx 的环境收集。

离线评测环境没有第三方包，这些用例自动跳过；CI 安装 requirements 后会正常执行。
"""
from __future__ import annotations

import pytest


def _missing(name: str) -> bool:
    try:
        __import__(name)
    except ImportError:
        return True
    return False


pytestmark = pytest.mark.skipif(
    _missing("fastapi") or _missing("httpx"),
    reason="未安装 fastapi/httpx，接口层改由 scripts/run_api_check.py 以标准库验证",
)


def test_http_endpoints() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get("/api/crawler-migration/summary").status_code == 200
    mapping = client.get("/api/crawler-migration/migration-mapping").json()
    assert mapping["total"] == 4

    parse = client.get("/api/crawler-migration/parse-records/SMP-2024-0301")
    assert parse.status_code == 200
    assert parse.json()["legacy_ref"] == "LIB-12"

    review = client.get("/api/crawler-migration/catalog-review").json()
    catalogable_ids = {item["sample_id"] for item in review["catalogable"]}
    assert "SMP-2024-0301" in catalogable_ids

    resolved = client.get("/api/crawler-migration/resolve-ref", params={"legacy_ref": "LIB-12"})
    assert resolved.status_code == 200
    assert len(resolved.json()["candidate_definitions"]) == 2

    archive = client.get("/api/crawler-migration/archive/SMP-2020-1205")
    assert archive.status_code == 200
    assert archive.json()["declared_encoding"] == "GBK"

    assert client.get("/api/crawler-migration/resolve-ref", params={"legacy_ref": "NOPE"}).status_code == 404
    assert client.get("/api/crawler-migration/archive/NOPE").status_code == 404
