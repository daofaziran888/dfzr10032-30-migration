#!/usr/bin/env python3
"""接口层离线核验（不依赖 fastapi/httpx/uvicorn）。

做两件事：
1. 遍历迁移注册表的全部对外视图，确认 JSON 可序列化、关键业务结论成立；
2. 静态检查路由模块声明的路径与方法，保证装上依赖后接口可直接挂载。

用法：python3 -I scripts/run_api_check.py
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.migration.registry import MigrationRegistry  # noqa: E402

FIXTURE_ROOT = BACKEND / "fixtures" / "migration"
ROUTER_FILE = BACKEND / "app" / "routers" / "crawler_migration.py"

EXPECTED_ROUTES = {
    ("/summary", "GET"),
    ("/legacy-rules", "GET"),
    ("/definitions", "GET"),
    ("/migration-mapping", "GET"),
    ("/samples", "GET"),
    ("/parse-records", "GET"),
    ("/parse-records/{sample_id}", "GET"),
    ("/catalog-review", "GET"),
    ("/resolve-ref", "GET"),
    ("/archive/{sample_id}", "GET"),
    ("/rerun", "POST"),
}


def check_views_are_json_serializable() -> list[str]:
    registry = MigrationRegistry(fixture_root=FIXTURE_ROOT)
    payloads: dict[str, object] = {
        "summary": registry.summary(),
        "legacy_rules": registry.legacy_rules_view(),
        "definitions": registry.definitions_view(),
        "migration": registry.migration_view(),
        "samples": registry.samples_view(),
        "parse_records": registry.parse_records_view(),
        "catalog": registry.catalog_view(),
        "resolve": registry.resolve_reference("LIB-12"),
        "archive": {k: v for k, v in registry.open_archived_page("SMP-2024-0301").items()},
    }
    for name, payload in payloads.items():
        json.dumps(payload, ensure_ascii=False)  # 抛错即失败
    print(f"[1/3] 全部 {len(payloads)} 个视图 JSON 序列化通过")
    return []


def check_business_assertions() -> list[str]:
    registry = MigrationRegistry(fixture_root=FIXTURE_ROOT)
    errors: list[str] = []

    definitions = registry.definitions_view()
    lib12 = [d for d in definitions if d["definition_id"] == "LIB-12"]
    if {d["version"] for d in lib12} != {"1.0.0", "1.1.0"}:
        errors.append("LIB-12 未形成 1.0.0/1.1.0 双版本")
    if {d["scope"] for d in lib12} != {"full_page", "body_only"}:
        errors.append("LIB-12 双版本范围不正确")

    # 跨规则隔离：每个定义已迁移字段的溯源必须等于自身 legacy_id
    for d in definitions:
        lid = d["derived_from_legacy_id"]
        for key in ("target_url", "encoding", "crawl_frequency", "title_selector", "content_selector"):
            prov = d[key]
            if prov["status"] == "已迁移" and prov["source_legacy_id"] != lid:
                errors.append(f"定义 {d['definition_id']}@{d['version']} 字段 {key} 溯源串号")

    decisions = {d["sample_id"]: d for d in registry.catalog_view()}
    lib12_decision = decisions["SMP-2024-0301"]
    if not lib12_decision["title_catalogable"]:
        errors.append("双版本逐字一致的标题应可编目")
    if not any(h["field"] == "temporary_opening_hours" for h in lib12_decision["held_fields"]):
        errors.append("临时开放时间应作为欠凭据字段挂起")
    if len(lib12_decision["title_evidence"]) != 2:
        errors.append("标题证据应保留两个版本")

    lib31 = decisions["SMP-2020-1205"]
    if not any(h["field"] == "announcement_body" for h in lib31["held_fields"]):
        errors.append("LIB-31 空内容选择器应保持正文待核，不猜默认值")

    status = "通过" if not errors else "失败：" + "；".join(errors)
    print(f"[2/3] 业务口径断言{'' if not errors else ' ' + status}")
    return errors


def check_router_declarations() -> list[str]:
    tree = ast.parse(ROUTER_FILE.read_text(encoding="utf-8"))
    found: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute):
                    method = deco.func.attr.upper()
                    if deco.args and isinstance(deco.args[0], ast.Constant):
                        found.add((deco.args[0].value, method))
    missing = EXPECTED_ROUTES - found
    print(f"[3/3] 路由声明核验：期望 {len(EXPECTED_ROUTES)} 条，实读 {len(found & EXPECTED_ROUTES)} 条")
    return [f"缺少路由 {route}" for route in sorted(missing)]


def main() -> int:
    errors: list[str] = []
    errors += check_views_are_json_serializable()
    errors += check_business_assertions()
    errors += check_router_declarations()
    if errors:
        print("\n核验未通过：")
        for err in errors:
            print(" -", err)
        return 1
    print("\n全部接口核验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
