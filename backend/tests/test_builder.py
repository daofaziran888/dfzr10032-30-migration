"""迁移构建器单元测试：逐字段溯源、留原文待核、同编号多版本、跨规则隔离。"""
from __future__ import annotations

import pytest

from app.migration.builder import build_definitions
from app.migration.models import LEGACY_CONTENT_SELECTOR_FIELDS, MIGRATED, REVIEW_RAW, LegacyRule


def _rule(legacy_id: str, rule_no: str, flat: dict) -> LegacyRule:
    return LegacyRule(legacy_id=legacy_id, rule_no=rule_no, flat_fields=flat)


def test_flat_fields_become_versioned_definitions_with_provenance() -> None:
    rules = [_rule("L-A", "R-1", {
        "目标网址": "https://x/1", "字符编码": "UTF-8", "抓取频率": "每日 06:00",
        "抓取范围": "全页", "标题选择器": "h1.t", "内容选择器": "body",
    })]
    defs, entries = build_definitions(rules)
    assert len(defs) == 1 and len(entries) == 1
    d = defs[0]
    assert d.definition_id == "R-1" and d.version == "1.0.0" and d.scope == "full_page"
    assert d.target_url.status == MIGRATED
    assert d.target_url.source_legacy_id == "L-A"
    assert d.crawl_frequency.value == "每日 06:00"
    assert d.content_selector.value == "body"


def test_same_rule_number_gets_two_coexisting_versions() -> None:
    rules = [
        _rule("L-A", "R-9", {"目标网址": "u", "字符编码": "UTF-8", "抓取频率": "每日",
                             "抓取范围": "全页", "标题选择器": "h1", "内容选择器": "body"}),
        _rule("L-B", "R-9", {"目标网址": "u", "字符编码": "UTF-8", "抓取频率": "每周",
                             "抓取范围": "正文", "标题选择器": "h1", "正文选择器": "div.body"}),
    ]
    defs, entries = build_definitions(rules)
    versions = sorted(d.version for d in defs)
    assert versions == ["1.0.0", "1.1.0"]
    assert {d.scope for d in defs} == {"full_page", "body_only"}
    # 两版本并存、各自溯源到不同旧规则
    sources = {d.derived_from_legacy_id for d in defs}
    assert sources == {"L-A", "L-B"}
    assert all(e.note for e in entries)


def test_versions_are_independent_per_rule_number() -> None:
    rules = [
        _rule("L-1", "R-1", {"目标网址": "u", "字符编码": "UTF-8", "抓取频率": "每日",
                             "抓取范围": "全页", "标题选择器": "h1", "内容选择器": "body"}),
        _rule("L-2", "R-2", {"目标网址": "u", "字符编码": "UTF-8", "抓取频率": "每日",
                             "抓取范围": "正文", "标题选择器": "h2", "正文选择器": "div.c"}),
    ]
    defs, _ = build_definitions(rules)
    assert {d.version for d in defs} == {"1.0.0"}


def test_empty_content_selector_is_held_raw_without_default() -> None:
    rules = [_rule("L-31", "R-31", {
        "目标网址": "u", "字符编码": "GBK", "抓取频率": "每日",
        "标题选择器": "h2.x", "内容选择器": "",
    })]
    defs, _ = build_definitions(rules)
    content = defs[0].content_selector
    assert content.status == REVIEW_RAW
    assert content.value is None and content.raw_value == ""
    assert "不猜" in content.note


def test_unknown_fields_kept_raw_for_review() -> None:
    rules = [_rule("L-40", "R-40", {
        "目标网址": "u", "字符编码": "UTF-8", "抓取频率": "每日",
        "标题选择器": "h1", "内容选择器": "div.c",
        "旧系统内部代号": "X-7723", "抓取位": "第二块（待确认）",
    })]
    defs, entries = build_definitions(rules)
    extra_names = {p.field_name for p in defs[0].extra_fields}
    assert extra_names == {"旧系统内部代号", "抓取位"}
    assert all(p.status == REVIEW_RAW and p.raw_value is not None for p in defs[0].extra_fields)
    review_names = {p.field_name for p in entries[0].review_fields}
    assert {"旧系统内部代号", "抓取位"} <= review_names


def test_conflicting_content_selectors_are_held_not_picked() -> None:
    rules = [_rule("L-X", "R-X", {
        "目标网址": "u", "字符编码": "UTF-8", "抓取频率": "每日",
        "标题选择器": "h1", "内容选择器": "div.a", "正文选择器": "div.b",
    })]
    defs, _ = build_definitions(rules)
    content = defs[0].content_selector
    assert content.status == REVIEW_RAW and content.value is None
    assert "冲突" in content.note


def test_every_migrated_field_traces_to_the_same_legacy_rule() -> None:
    """构造两条规则，验证 A 的频率不会和 B 的选择器混到同一套定义里。"""
    rules = [
        _rule("L-A", "R-1", {"目标网址": "ua", "字符编码": "UTF-8", "抓取频率": "A专属频率",
                             "标题选择器": "h1.a", "内容选择器": "div.a"}),
        _rule("L-B", "R-2", {"目标网址": "ub", "字符编码": "UTF-8", "抓取频率": "B专属频率",
                             "标题选择器": "h1.b", "内容选择器": "div.b"}),
    ]
    defs, _ = build_definitions(rules)
    by_source = {d.derived_from_legacy_id: d for d in defs}
    a = by_source["L-A"]
    assert a.crawl_frequency.value == "A专属频率"
    assert a.content_selector.value == "div.a"
    b = by_source["L-B"]
    assert b.crawl_frequency.value == "B专属频率"
    assert b.title_selector.value == "h1.b"
    for d in defs:
        for prov in (d.target_url, d.encoding, d.crawl_frequency, d.title_selector, d.content_selector):
            if prov.status == MIGRATED:
                assert prov.source_legacy_id == d.derived_from_legacy_id


def test_provenance_self_check_raises_on_tampering() -> None:
    rules = [_rule("L-A", "R-1", {"目标网址": "ua", "字符编码": "UTF-8", "抓取频率": "f",
                                  "标题选择器": "h1", "内容选择器": "div.a"})]
    defs, _ = build_definitions(rules)
    defs[0].crawl_frequency.source_legacy_id = "L-OTHER"
    from app.migration.builder import _assert_single_legacy_provenance

    with pytest.raises(RuntimeError, match="禁止把不同旧规则"):
        _assert_single_legacy_provenance(defs[0], "L-A")


def test_known_selector_field_names_are_covered() -> None:
    """迁移口径依赖的字段别名集合保持稳定，防止回归时漏识别。"""
    assert "内容选择器" in LEGACY_CONTENT_SELECTOR_FIELDS
    assert "正文选择器" in LEGACY_CONTENT_SELECTOR_FIELDS
