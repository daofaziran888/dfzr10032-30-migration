"""迁移构建器：旧平铺清单 -> 带版本的结构化采集定义 + 迁移对照明细。

不可违背的口径：

* 一条旧规则独立构建一个定义，所有字段溯源都指向同一条 ``legacy_id``，
  构建完成后做一次自检，防止把 A 规则的抓取频率和 B 规则的正文选择器拼成一套；
* 旧字段含义足够才结构化；含义不足（空值、自相矛盾、无法识别的键）只保留原文
  并标 ``留原文待核``，不猜测、不补任何默认选择器；
* 同一规则编号下的多份旧规格各自得到独立版本，版本按“全页 / 正文”范围分配，
  两个版本并存、互不替代。
"""
from __future__ import annotations

from typing import Any

from app.migration.models import (
    LEGACY_CONTENT_SELECTOR_FIELDS,
    LEGACY_ENCODING_FIELDS,
    LEGACY_FREQUENCY_FIELDS,
    LEGACY_PAGE_SELECTOR_FIELDS,
    LEGACY_SCOPE_FIELDS,
    LEGACY_TITLE_SELECTOR_FIELDS,
    LEGACY_URL_FIELDS,
    MIGRATED,
    REVIEW_RAW,
    CrawlDefinition,
    FieldProvenance,
    LegacyRule,
    MigrationEntry,
)

SCOPE_FULL_PAGE = "full_page"
SCOPE_BODY_ONLY = "body_only"
SCOPE_UNKNOWN = "unknown"

# 能被结构化识别的旧字段全集；不在其中的键一律留原文待核
_KNOWN_KEYS: set[str] = set()
for _group in (
    LEGACY_URL_FIELDS,
    LEGACY_ENCODING_FIELDS,
    LEGACY_FREQUENCY_FIELDS,
    LEGACY_SCOPE_FIELDS,
    LEGACY_TITLE_SELECTOR_FIELDS,
    LEGACY_CONTENT_SELECTOR_FIELDS,
    LEGACY_PAGE_SELECTOR_FIELDS,
):
    _KNOWN_KEYS.update(_group)


def _first_present(flat: dict[str, Any], candidates: tuple[str, ...]) -> tuple[str, Any] | None:
    for key in candidates:
        if key in flat:
            return key, flat[key]
    return None


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _prov(
    field_name: str,
    legacy_id: str,
    found: tuple[str, Any] | None,
    *,
    require_selector: bool = False,
    note: str = "",
) -> FieldProvenance:
    """把一个旧字段转成带溯源的结构化字段；空值/异常值一律留原文待核。"""
    if found is None:
        return FieldProvenance(
            field_name=field_name, value=None, status=REVIEW_RAW,
            source_legacy_id=None, source_legacy_field=None, raw_value=None,
            note=note or "旧清单未登记该字段，保留空缺待人工核对，不猜默认值",
        )
    old_key, raw = found
    if _is_blank(raw):
        return FieldProvenance(
            field_name=field_name, value=None, status=REVIEW_RAW,
            source_legacy_id=legacy_id, source_legacy_field=old_key,
            raw_value=raw, note=note or "旧字段为空，留原文待核，不猜默认选择器",
        )
    text = str(raw).strip()
    if require_selector and text in ("待定", "TODO", "无", "n/a", "N/A", "？", "?"):
        return FieldProvenance(
            field_name=field_name, value=None, status=REVIEW_RAW,
            source_legacy_id=legacy_id, source_legacy_field=old_key,
            raw_value=raw, note=note or f"旧值「{raw}」不构成可用选择器，留原文待核",
        )
    return FieldProvenance(
        field_name=field_name, value=text, status=MIGRATED,
        source_legacy_id=legacy_id, source_legacy_field=old_key,
        raw_value=raw, note=note,
    )


def _resolve_scope(flat: dict[str, Any], content_selector: FieldProvenance) -> str:
    """判断抓取范围：显式范围字段优先；否则依据正文选择器是否覆盖全页容器推断。

    推断只在旧字段本身给出明确依据时进行（如 body/html/#main），
    没有依据就返回 unknown，绝不替馆员决定。
    """
    found = _first_present(flat, LEGACY_SCOPE_FIELDS)
    if found and not _is_blank(found[1]):
        marker = str(found[1]).strip()
        if "全页" in marker or "整页" in marker or marker.lower() in ("full", "full_page", "all"):
            return SCOPE_FULL_PAGE
        if "正文" in marker or marker.lower() in ("body", "content", "body_only"):
            return SCOPE_BODY_ONLY
    if content_selector.status == MIGRATED:
        selector = str(content_selector.value).replace(" ", "")
        if selector in ("body", "html", "#main", "#page", ".page"):
            return SCOPE_FULL_PAGE
        if any(tok in selector for tok in ("article", ".content", ".article", "#content", ".body")):
            return SCOPE_BODY_ONLY
    return SCOPE_UNKNOWN


def _pick_title_selector(flat: dict[str, Any], legacy_id: str) -> FieldProvenance:
    """标题选择器：旧系统有明确标题字段就用；没有不猜，留待核。"""
    found = _first_present(flat, LEGACY_TITLE_SELECTOR_FIELDS)
    return _prov("title_selector", legacy_id, found, require_selector=True)


def _pick_content_selector(flat: dict[str, Any], legacy_id: str) -> FieldProvenance:
    """正文/内容选择器：同一条旧规则里若多个候选键并存且取值冲突，保留原文待核。"""
    present = [(k, flat[k]) for k in LEGACY_CONTENT_SELECTOR_FIELDS if k in flat and not _is_blank(flat[k])]
    if not present:
        # 找到的都是空值也要留痕
        blank = _first_present(flat, LEGACY_CONTENT_SELECTOR_FIELDS)
        return _prov("content_selector", legacy_id, blank, require_selector=True)
    distinct = {str(v).strip() for _k, v in present}
    if len(distinct) > 1:
        keys = "、".join(k for k, _v in present)
        return FieldProvenance(
            field_name="content_selector", value=None, status=REVIEW_RAW,
            source_legacy_id=legacy_id,
            source_legacy_field=keys,
            raw_value={k: v for k, v in present},
            note="同一旧登记中多个内容选择器字段取值冲突，留原文待核，不任选其一",
        )
    chosen_key, chosen_val = present[0]
    return _prov("content_selector", legacy_id, (chosen_key, chosen_val), require_selector=True)


def _version_for(rule_no: str, scope: str, scope_orders: dict[str, list[str]]) -> str:
    """同编号下按出现顺序分配 1.0.0 / 1.1.0；版本序列只在同一规则编号内推进。

    范围未知（unknown）不抢占已知范围的版本位，先给 0.x.0 留待人工确认。
    """
    orders = scope_orders.setdefault(rule_no, [])
    if scope in (SCOPE_FULL_PAGE, SCOPE_BODY_ONLY):
        if scope not in orders:
            orders.append(scope)
        return f"1.{orders.index(scope)}.0"
    unknown_index = len(orders)
    return f"0.{unknown_index}.0"


def build_definitions(
    legacy_rules: list[LegacyRule],
) -> tuple[list[CrawlDefinition], list[MigrationEntry]]:
    """执行迁移；返回结构化定义列表与逐字段对照明细（顺序与旧清单一致）。"""
    definitions: list[CrawlDefinition] = []
    entries: list[MigrationEntry] = []
    # 每个规则编号各自维护一份范围出现顺序，避免不同编号之间版本串号
    scope_orders: dict[str, list[str]] = {}

    for rule in legacy_rules:
        flat = rule.flat_fields
        lid = rule.legacy_id

        url = _prov("target_url", lid, _first_present(flat, LEGACY_URL_FIELDS))
        encoding = _prov("encoding", lid, _first_present(flat, LEGACY_ENCODING_FIELDS))
        frequency = _prov("crawl_frequency", lid, _first_present(flat, LEGACY_FREQUENCY_FIELDS))
        title_sel = _pick_title_selector(flat, lid)
        content_sel = _pick_content_selector(flat, lid)
        page_sel = _prov("page_selector", lid, _first_present(flat, LEGACY_PAGE_SELECTOR_FIELDS),
                         require_selector=True)

        scope = _resolve_scope(flat, content_sel)
        version = _version_for(rule.rule_no, scope, scope_orders)
        definition_id = rule.rule_no

        # 无法识别的旧键：含义不足，整体留原文待核（保留键和值），绝不猜测语义
        extra: list[FieldProvenance] = []
        for key, value in flat.items():
            if key in _KNOWN_KEYS:
                continue
            extra.append(FieldProvenance(
                field_name=key, value=None, status=REVIEW_RAW,
                source_legacy_id=lid, source_legacy_field=key,
                raw_value=value, note="未登记语义的历史字段，留原文待核",
            ))

        definition = CrawlDefinition(
            definition_id=definition_id,
            version=version,
            scope=scope,
            target_url=url,
            encoding=encoding,
            crawl_frequency=frequency,
            title_selector=title_sel,
            content_selector=content_sel,
            page_selector=page_sel,
            extra_fields=extra,
            derived_from_legacy_id=lid,
        )
        _assert_single_legacy_provenance(definition, lid)
        definitions.append(definition)

        mappings = [p for p in (url, encoding, frequency, title_sel, content_sel, page_sel)
                    if p is not None and p.status == MIGRATED]
        reviews = [p for p in (url, encoding, frequency, title_sel, content_sel, page_sel)
                   if p is not None and p.status == REVIEW_RAW] + extra
        note = "同编号存在多份旧规格，已分别建版，两版本并存" if _count_rule_no(legacy_rules, rule.rule_no) > 1 else ""
        entries.append(MigrationEntry(
            legacy_id=lid, rule_no=rule.rule_no,
            definition_id=definition_id, version=version,
            field_mappings=mappings, review_fields=reviews, note=note,
        ))

    return definitions, entries


def _count_rule_no(rules: list[LegacyRule], rule_no: str) -> int:
    return sum(1 for r in rules if r.rule_no == rule_no)


def _assert_single_legacy_provenance(definition: CrawlDefinition, legacy_id: str) -> None:
    """自检：所有已迁移字段必须来自同一条旧规则，杜绝跨规则拼装。"""
    provenance = [
        definition.target_url, definition.encoding, definition.crawl_frequency,
        definition.title_selector, definition.content_selector,
    ]
    if definition.page_selector is not None:
        provenance.append(definition.page_selector)
    for prov in provenance:
        if prov.status == MIGRATED and prov.source_legacy_id != legacy_id:
            raise RuntimeError(
                f"迁移完整性校验失败：定义 {definition.definition_id}@{definition.version} "
                f"的字段 {prov.field_name} 混入了 {prov.source_legacy_id} 的值，"
                "禁止把不同旧规则的频率/选择器拼成一套"
            )
