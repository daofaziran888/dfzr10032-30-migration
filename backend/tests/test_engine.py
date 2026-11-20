"""解析引擎与编目核查测试：双版本标题逐字一致、开放时间挂起、未解析字段留位置。"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.migration.engine import ParseEngine, build_catalog_decisions
from app.migration.models import (
    PARSE_OK,
    PARSE_UNRESOLVED,
    CrawlDefinition,
    FieldProvenance,
    PageSample,
)

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "migration"
ARCHIVE = FIXTURE_ROOT / "archive"


def _title_selector(value: str) -> FieldProvenance:
    return FieldProvenance("title_selector", value, "已迁移", "L", "标题选择器", value)


def _content_selector(value: str | None) -> FieldProvenance:
    if value is None:
        return FieldProvenance("content_selector", None, "留原文待核", "L", "内容选择器", "",
                               note="旧字段为空，留原文待核，不猜默认选择器")
    return FieldProvenance("content_selector", value, "已迁移", "L", "正文选择器", value)


def _definition(version: str, scope: str, title: str, content: str | None, legacy: str) -> CrawlDefinition:
    return CrawlDefinition(
        definition_id="LIB-12", version=version, scope=scope,
        target_url=FieldProvenance("target_url", "u", "已迁移", legacy, "目标网址", "u"),
        encoding=FieldProvenance("encoding", "UTF-8", "已迁移", legacy, "字符编码", "UTF-8"),
        crawl_frequency=FieldProvenance("crawl_frequency", "每日", "已迁移", legacy, "抓取频率", "每日"),
        title_selector=_title_selector(title),
        content_selector=_content_selector(content),
        derived_from_legacy_id=legacy,
    )


@pytest.fixture()
def engine() -> ParseEngine:
    return ParseEngine(ARCHIVE)


@pytest.fixture()
def lib12_sample() -> PageSample:
    return PageSample(
        sample_id="SMP-1", legacy_ref="LIB-12", legacy_version=None,
        archive_path="lib12_notice_2024.html",
        source_url="https://lib.example.gov.cn/notice/2024-spring",
        encoding="UTF-8", archived_at="2024-03-01",
    )


def test_both_versions_read_same_title_verbatim(engine: ParseEngine, lib12_sample: PageSample) -> None:
    full = _definition("1.0.0", "full_page", "h1.notice-title", "body", "L-A")
    body = _definition("1.1.0", "body_only", "h1.notice-title", "div.article-body", "L-B")
    record = engine.parse_sample(lib12_sample, [full, body])
    titles = {
        f.value
        for vr in record.version_results
        for f in vr.fields if f.field_name == "announcement_title"
    }
    assert titles == {"市图书馆2024年春季服务调整公告"}
    assert record.selected_for_review == ["LIB-12@1.0.0", "LIB-12@1.1.0"]


def test_only_full_page_version_carries_opening_hours_without_credential(
    engine: ParseEngine, lib12_sample: PageSample,
) -> None:
    full = _definition("1.0.0", "full_page", "h1.notice-title", "body", "L-A")
    body = _definition("1.1.0", "body_only", "h1.notice-title", "div.article-body", "L-B")
    record = engine.parse_sample(lib12_sample, [full, body])
    full_result = next(vr for vr in record.version_results if vr.scope == "full_page")
    body_result = next(vr for vr in record.version_results if vr.scope == "body_only")
    hours = [f for f in full_result.fields if f.field_name == "temporary_opening_hours"]
    assert len(hours) == 1 and hours[0].status == PARSE_OK
    assert "08:30 — 17:30" in hours[0].value
    assert hours[0].char_position and hours[0].line_number
    assert "凭据" in hours[0].note
    # 正文版本不采集通告框，不伪造开放时间字段
    assert all(f.field_name != "temporary_opening_hours" for f in body_result.fields)


def test_catalog_holds_opening_hours_but_accepts_title(engine: ParseEngine, lib12_sample: PageSample) -> None:
    full = _definition("1.0.0", "full_page", "h1.notice-title", "body", "L-A")
    body = _definition("1.1.0", "body_only", "h1.notice-title", "div.article-body", "L-B")
    record = engine.parse_sample(lib12_sample, [full, body])
    decision = build_catalog_decisions([record])[0]
    assert decision.title_catalogable is True
    held = [h for h in decision.held_fields if h["field"] == "temporary_opening_hours"]
    assert held and "凭据" in held[0]["reason"]
    assert decision.announcement_title == "市图书馆2024年春季服务调整公告"


def test_unresolved_body_kept_pending_without_default_selector(engine: ParseEngine) -> None:
    sample = PageSample(
        sample_id="SMP-31", legacy_ref="LIB-31", legacy_version=None,
        archive_path="lib31_reading_month.html",
        source_url="u", encoding="GBK", archived_at="2020-12-05",
    )
    definition = _definition("0.0.0", "unknown", "h2.ann-head", None, "L-31")
    record = engine.parse_sample(sample, [definition])
    title = next(f for vr in record.version_results for f in vr.fields
                 if f.field_name == "announcement_title")
    body = next(f for vr in record.version_results for f in vr.fields
                if f.field_name == "announcement_body")
    assert title.status == PARSE_OK and "全民阅读月" in title.value
    assert body.status == PARSE_UNRESOLVED
    assert body.selector is None and "不猜" in body.note


def test_gbk_archive_decodes_with_declared_encoding(engine: ParseEngine) -> None:
    sample = PageSample(
        sample_id="SMP-31", legacy_ref="LIB-31", legacy_version=None,
        archive_path="lib31_reading_month.html",
        source_url="u", encoding="GBK", archived_at="2020-12-05",
    )
    markup = engine.load_markup(sample)
    assert "市图书馆全民阅读月活动公告" in markup


def test_selector_with_no_match_is_unresolved_not_silently_empty(
    engine: ParseEngine, lib12_sample: PageSample,
) -> None:
    definition = _definition("1.0.0", "body_only", "h1.not-exist", "div.article-body", "L-X")
    record = engine.parse_sample(lib12_sample, [definition])
    title = record.version_results[0].fields[0]
    assert title.status == PARSE_UNRESOLVED
    assert "无匹配" in title.note


def test_unknown_legacy_ref_produces_unresolved_record(engine: ParseEngine) -> None:
    sample = PageSample(
        sample_id="SMP-X", legacy_ref="LIB-NOPE", legacy_version=None,
        archive_path="lib12_notice_2024.html", source_url="u",
        encoding="UTF-8", archived_at="",
    )
    record = engine.parse_all([sample], [], {"OTHER": []})
    assert record[0].overall_status == PARSE_UNRESOLVED
    assert record[0].candidate_definitions == []
