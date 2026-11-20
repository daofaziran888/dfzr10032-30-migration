#!/usr/bin/env python3
"""离线路由冒烟：用标准库桩替代 fastapi/pydantic，直接执行迁移路由端点。

评测环境无法 pip 安装第三方包，但路由层逻辑仍需验证。本脚本只在进程内注入
最小桩模块（不写入业务目录），随后像 ASGI 框架那样调用各端点函数并断言返回，
从而覆盖 router -> service -> migration registry 的完整调用链。
真实环境安装 requirements 后由 tests/test_http_api.py 走 TestClient 复核。
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


def _install_stubs() -> None:
    # ---- pydantic 桩 ----
    pydantic = types.ModuleType("pydantic")

    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def model_dump(self):
            return dict(self.__dict__)

    def Field(default=None, **_kwargs):  # noqa: N802
        return default

    pydantic.BaseModel = BaseModel
    pydantic.Field = Field
    sys.modules["pydantic"] = pydantic

    # ---- fastapi 桩 ----
    fastapi = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str = ""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class APIRouter:
        def __init__(self, *args, **kwargs):
            self.routes: list[tuple[str, str]] = []

        def _register(self, method: str):
            def decorator(func):
                self.routes.append((method, func.__name__))
                return func
            return decorator

        def get(self, path: str, **_kwargs):
            return self._register("GET")

        def post(self, path: str, **_kwargs):
            return self._register("POST")

    def Query(default=None, **_kwargs):  # noqa: N802
        return default

    class Request:  # noqa: D401  仅占位
        pass

    fastapi.APIRouter = APIRouter
    fastapi.HTTPException = HTTPException
    fastapi.Query = Query
    fastapi.Request = Request
    sys.modules["fastapi"] = fastapi


def main() -> int:
    _install_stubs()
    from app.routers import crawler_migration as router_mod  # noqa: E402

    failures: list[str] = []

    def check(name: str, condition: bool, extra: str = "") -> None:
        print(f"{'✓' if condition else '✗'} {name} {extra}")
        if not condition:
            failures.append(name)

    summary = router_mod.summary()
    check("summary 端点", summary["definition_count"] == 4 and summary["sample_count"] == 3)

    mapping = router_mod.migration_mapping()
    check("migration-mapping 端点", mapping["total"] == 4)

    defs = router_mod.definitions()
    lib12 = {d["version"]: d for d in defs["items"] if d["definition_id"] == "LIB-12"}
    check("同编号双版本并存", set(lib12) == {"1.0.0", "1.1.0"})

    records = router_mod.parse_records()
    check("parse-records 端点", records["total"] == 3)

    one = router_mod.parse_record("SMP-2024-0301")
    check("单样本解析记录", one["legacy_ref"] == "LIB-12" and len(one["version_results"]) == 2)

    review = router_mod.catalog_review()
    ids = {c["sample_id"] for c in review["catalogable"]}
    check("编目核查可编目集合", "SMP-2024-0301" in ids and "SMP-2020-1205" in ids)

    resolved = router_mod.resolve_ref(legacy_ref="LIB-12")
    check("无版本号旧引用回查双版本", len(resolved["candidate_definitions"]) == 2)

    archive = router_mod.archive_page("SMP-2020-1205")
    check("GBK 归档原页回查", archive["declared_encoding"] == "GBK" and "全民阅读月" in archive["markup"])

    rerun = router_mod.rerun()
    check("rerun 动作端点", rerun.ok is True)

    # 错误路径：不存在的样本与引用应抛 HTTPException
    from fastapi import HTTPException  # type: ignore[import-not-found]

    for label, call in (
        ("缺失样本 404", lambda: router_mod.archive_page("NOPE")),
        ("缺失引用 404", lambda: router_mod.resolve_ref(legacy_ref="NOPE")),
        ("缺失解析记录 404", lambda: router_mod.parse_record("NOPE")),
    ):
        try:
            call()
            check(label, False, "（未抛出异常）")
        except HTTPException as exc:
            check(label, exc.status_code == 404)

    registered = {m for _m, name in router_mod.router.routes for m in [name]}
    check("路由装饰器全部生效", len(router_mod.router.routes) >= 11, f"实挂 {len(router_mod.router.routes)} 条")

    if failures:
        print("\n路由冒烟未通过：", failures)
        return 1
    print("\n路由层全链路冒烟通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
