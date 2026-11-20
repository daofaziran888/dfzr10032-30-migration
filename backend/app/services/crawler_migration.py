"""采集规则迁移业务服务：对外只读暴露迁移、解析、回查与编目核查结果。"""
from __future__ import annotations

from typing import Any

from app.migration.registry import get_registry, reload_registry


class CrawlerMigrationService:
    def summary(self) -> dict[str, Any]:
        return get_registry().summary()

    def list_legacy_rules(self) -> list[dict[str, Any]]:
        return get_registry().legacy_rules_view()

    def list_definitions(self) -> list[dict[str, Any]]:
        return get_registry().definitions_view()

    def list_migration_entries(self) -> list[dict[str, Any]]:
        return get_registry().migration_view()

    def list_samples(self) -> list[dict[str, Any]]:
        return get_registry().samples_view()

    def list_parse_records(self) -> list[dict[str, Any]]:
        return get_registry().parse_records_view()

    def get_parse_record(self, sample_id: str) -> dict[str, Any] | None:
        for record in get_registry().parse_records_view():
            if record["sample_id"] == sample_id:
                return record
        return None

    def catalog_decisions(self) -> list[dict[str, Any]]:
        return get_registry().catalog_view()

    def resolve_reference(self, legacy_ref: str) -> dict[str, Any]:
        return get_registry().resolve_reference(legacy_ref)

    def open_archived_page(self, sample_id: str) -> dict[str, Any] | None:
        try:
            return get_registry().open_archived_page(sample_id)
        except KeyError:
            return None

    def rerun(self) -> dict[str, Any]:
        registry = reload_registry()
        return {"ok": True, "message": "已重新装载归档并重跑迁移解析", **registry.summary()}
