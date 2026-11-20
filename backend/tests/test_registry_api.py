"""注册表端到端测试：旧引用回查、归档原页、迁移汇总（纯标准库可运行）。"""
from __future__ import annotations

from pathlib import Path

from app.migration.registry import MigrationRegistry

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "migration"


def _registry() -> MigrationRegistry:
    return MigrationRegistry(fixture_root=FIXTURE_ROOT)


def test_registry_end_to_end_business_path() -> None:
    registry = _registry()
    summary = registry.summary()
    assert summary["legacy_rule_count"] == 4
    assert summary["definition_count"] == 4
    # 无版本号样本与 GBK 样本都完成解析
    assert summary["sample_count"] == 3 and summary["parse_record_count"] == 3

    # 同编号两份规格并存，无版本号旧引用能回查到两个候选版本
    resolved = registry.resolve_reference("LIB-12")
    versions = {(d["definition_id"], d["version"]) for d in resolved["candidate_definitions"]}
    assert versions == {("LIB-12", "1.0.0"), ("LIB-12", "1.1.0")}

    # 从旧引用打开的仍是归档原页
    page = registry.open_archived_page("SMP-2024-0301")
    assert page["source_url"].endswith("/2024-spring")
    assert "临时开放时间" in page["markup"]


def test_catalog_distinguishes_catalogable_and_pending_review() -> None:
    registry = _registry()
    decisions = {d["sample_id"]: d for d in registry.catalog_view()}
    lib12 = decisions["SMP-2024-0301"]
    assert lib12["title_catalogable"] is True
    held_fields = {h["field"] for h in lib12["held_fields"]}
    assert "temporary_opening_hours" in held_fields
    # 双版本逐字一致，证据里保留两个版本
    assert len(lib12["title_evidence"]) == 2

    lib31 = decisions["SMP-2020-1205"]
    held = {h["field"] for h in lib31["held_fields"]}
    assert "announcement_body" in held


def test_unresolved_field_records_character_location() -> None:
    registry = _registry()
    record = next(r for r in registry.parse_records if r.sample_id == "SMP-2024-0301")
    # 全页版本的开放时间带有归档原页字符位置
    full = next(vr for vr in record.version_results if vr.scope == "full_page")
    hours = next(f for f in full.fields if f.field_name == "temporary_opening_hours")
    assert isinstance(hours.char_position, int) and hours.line_number >= 1
    page = registry.open_archived_page("SMP-2024-0301")
    assert page["markup"][hours.char_position:].startswith("临时开放时间")


def test_rerun_is_repeatable() -> None:
    registry = _registry()
    before = registry.summary()
    registry.reload()
    assert registry.summary() == before
