"""历史抓取规则迁移接口。

把网页采集规则的旧平铺清单迁移为带版本的结构化采集定义，并围绕归档样本提供：
迁移对照明细、样本解析记录（含未解析字段位置）、旧引用回查原页、编目核查结论。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult
from app.services.crawler_migration import CrawlerMigrationService

router = APIRouter(prefix="/api/crawler-migration", tags=["历史抓取规则迁移"])

service = CrawlerMigrationService()


@router.get("/summary")
def summary() -> dict[str, Any]:
    """迁移总览：旧规则数、版本化定义数、待核字段数与编目结论统计。"""
    return service.summary()


@router.get("/legacy-rules")
def legacy_rules() -> dict[str, Any]:
    """旧平铺清单原文（含含义不足、留原文待核的字段）。"""
    items = service.list_legacy_rules()
    return {"total": len(items), "items": items}


@router.get("/definitions")
def definitions() -> dict[str, Any]:
    """迁移生成的带版本结构化采集定义（逐字段带溯源）。"""
    items = service.list_definitions()
    return {"total": len(items), "items": items}


@router.get("/migration-mapping")
def migration_mapping() -> dict[str, Any]:
    """历史抓取规则迁移对照明细：每条旧规则 -> 定义版本与逐字段去向。"""
    items = service.list_migration_entries()
    return {"total": len(items), "items": items}


@router.get("/samples")
def samples() -> dict[str, Any]:
    """随旧登记归档的页面样本登记（旧引用可无版本号）。"""
    items = service.list_samples()
    return {"total": len(items), "items": items}


@router.get("/parse-records")
def parse_records() -> dict[str, Any]:
    """格式解析器为每份样本写出的解析记录与未解析字段位置。"""
    items = service.list_parse_records()
    return {"total": len(items), "items": items}


@router.get("/parse-records/{sample_id}")
def parse_record(sample_id: str) -> dict[str, Any]:
    """单份样本的解析记录；不存在时给出可读错误。"""
    record = service.get_parse_record(sample_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"样本 {sample_id} 没有解析记录")
    return record


@router.get("/catalog-review")
def catalog_review() -> dict[str, Any]:
    """编目核查：本轮哪些公告可编目、哪些字段（如临时开放时间）仍待核查。"""
    items = service.catalog_decisions()
    catalogable = [item for item in items if item["title_catalogable"]]
    held = [item for item in items if not item["title_catalogable"]]
    return {
        "total": len(items),
        "catalogable": catalogable,
        "pending_review": held,
        "items": items,
    }


@router.get("/resolve-ref")
def resolve_ref(legacy_ref: str = Query(..., description="样本仍带的旧规则引用，可无版本号")) -> dict[str, Any]:
    """凭旧引用回查候选定义版本与归档样本，保证切换环境后仍能追溯原出处。"""
    result = service.resolve_reference(legacy_ref)
    if not result["resolved"]:
        raise HTTPException(status_code=404, detail=f"旧引用 {legacy_ref} 无法回查到任何定义或归档样本")
    return result


@router.get("/archive/{sample_id}")
def archive_page(sample_id: str) -> dict[str, Any]:
    """从旧引用打开归档原页：返回解码后的原始 HTML 与出处信息，不发起网络抓取。"""
    page = service.open_archived_page(sample_id)
    if page is None:
        raise HTTPException(status_code=404, detail=f"归档样本 {sample_id} 不存在")
    return page


@router.post("/rerun", response_model=ActionResult)
def rerun() -> ActionResult:
    """重新装载归档并执行一遍迁移与解析（演示环境无数据库，便于核对可重复性）。"""
    result = service.rerun()
    return ActionResult(ok=True, message=result.pop("message"), entry=result)
