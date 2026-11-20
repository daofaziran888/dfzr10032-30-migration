"""格式解析引擎：依据迁移对照明细为每份归档样本选择可复核的采集定义。

每份样本的解析记录都会写明：

* 旧引用（可能无版本号）回查到哪些候选定义版本，实际用了哪些 ``定义@版本`` 复核；
* 每个字段在每个版本下的解析值与所用选择器；
* 未能解析字段在**归档原页解码文本中的字符位置/行号**，而不是静默留空；
* 临时开放时间这类不在旧选择器登记内的页面信息，只做页面取证，
  能读到值也要标明“缺少采集版本凭据”。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.migration.dom import Node, SelectorError, parse_html, select, select_first
from app.migration.models import (
    PARSE_AMBIGUOUS,
    PARSE_OK,
    PARSE_UNRESOLVED,
    CatalogDecision,
    CrawlDefinition,
    PageSample,
    ParsedField,
    SampleParseRecord,
    VersionParseResult,
)

OPENING_HOURS_PATTERN = re.compile(r"(临时开放时间|开放时间)[：:\s]*([0-9]{1,2}[：:][0-9]{2}\s*[—\-~至]\s*[0-9]{1,2}[：:][0-9]{2})")
SNIPPET_LIMIT = 120

# 结构化字段 -> 定义上携带溯源的选择器属性
_SELECTOR_ATTR = {
    "announcement_title": "title_selector",
    "announcement_body": "content_selector",
}


def _snippet(text: str, pos: int) -> str:
    start = max(pos, 0)
    return text[start:start + SNIPPET_LIMIT].replace("\n", " ")


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


class ParseEngine:
    def __init__(self, archive_root: Path) -> None:
        self.archive_root = archive_root

    # ------------------------------------------------------------------ 样本读取
    def load_markup(self, sample: PageSample) -> str:
        """按归档登记的字符编码解码原页；解码失败如实上抛，不替换编码。"""
        path = (self.archive_root / sample.archive_path).resolve()
        if not str(path).startswith(str(self.archive_root.resolve())):
            raise ValueError(f"归档路径越界，拒绝读取：{sample.archive_path}")
        raw = path.read_bytes()
        return raw.decode(sample.encoding)

    # ------------------------------------------------------------------ 单字段解析
    def _parse_selector_field(
        self,
        root: Node,
        markup: str,
        field_name: str,
        definition: CrawlDefinition,
    ) -> ParsedField:
        prov = getattr(definition, _SELECTOR_ATTR[field_name])
        if prov.status != "已迁移" or not prov.value:
            return ParsedField(
                field_name=field_name, selector=None, status=PARSE_UNRESOLVED,
                value=None, char_position=None, line_number=None,
                snippet="",
                note=f"定义 {definition.definition_id}@{definition.version} 的 {field_name} "
                     f"在迁移对照中为「{prov.status}」，没有可复核选择器（不猜默认值）",
            )
        selector = str(prov.value)
        try:
            node = select_first(root, selector)
        except SelectorError as exc:
            return ParsedField(
                field_name=field_name, selector=selector, status=PARSE_UNRESOLVED,
                value=None, char_position=0, line_number=1,
                snippet=_snippet(markup, 0),
                note=f"选择器不可执行：{exc}；字段位置以页首占位，待人工核对",
            )
        if node is None:
            return ParsedField(
                field_name=field_name, selector=selector, status=PARSE_UNRESOLVED,
                value=None, char_position=0, line_number=1,
                snippet=_snippet(markup, 0),
                note=f"选择器 {selector} 在归档原页无匹配节点；无法定位字段位置，标记页首待核",
            )
        text = node.get_text()
        if not text:
            return ParsedField(
                field_name=field_name, selector=selector, status=PARSE_UNRESOLVED,
                value=None, char_position=node.start_pos, line_number=node.start_line,
                snippet=_snippet(markup, node.start_pos),
                note="匹配节点存在但无文本内容，留待核",
            )
        return ParsedField(
            field_name=field_name, selector=selector, status=PARSE_OK,
            value=text, char_position=node.start_pos, line_number=node.start_line,
            snippet=_snippet(markup, node.start_pos),
            note=f"依据 {definition.definition_id}@{definition.version}（溯源旧规则 "
                 f"{definition.derived_from_legacy_id}）逐字提取",
        )

    @staticmethod
    def _find_opening_hours(root: Node, markup: str) -> ParsedField:
        """全页扫描临时开放时间；它不是旧选择器登记字段，找到也只算页面取证。"""
        match = OPENING_HOURS_PATTERN.search(markup)
        if match is None:
            return ParsedField(
                field_name="temporary_opening_hours", selector=None,
                status=PARSE_UNRESOLVED, value=None,
                char_position=None, line_number=None, snippet="",
                note="归档原页未出现临时开放时间文本",
            )
        pos = match.start()
        return ParsedField(
            field_name="temporary_opening_hours", selector=None,
            status=PARSE_OK, value=match.group(0).strip(),
            char_position=pos, line_number=_line_of(markup, pos),
            snippet=_snippet(markup, pos),
            note="全页文本取证所得，无任何版本的采集选择器登记该字段，"
                 "开放时间仍欠采集版本凭据，不能据此直接编目",
        )

    # ------------------------------------------------------------------ 单版本复核
    def parse_with_definition(
        self,
        sample: PageSample,
        definition: CrawlDefinition,
        root: Node,
        markup: str,
    ) -> VersionParseResult:
        fields = [
            self._parse_selector_field(root, markup, "announcement_title", definition),
            self._parse_selector_field(root, markup, "announcement_body", definition),
        ]
        # 只有“全页”版本覆盖页首通告框；正文版本不采集该区域，不伪造结果
        if definition.scope == "full_page":
            fields.append(self._find_opening_hours(root, markup))
        return VersionParseResult(
            definition_id=definition.definition_id,
            version=definition.version,
            derived_from_legacy_id=definition.derived_from_legacy_id,
            scope=definition.scope,
            fields=fields,
            page_char_length=len(markup),
        )

    # ------------------------------------------------------------------ 整份样本
    def parse_sample(
        self,
        sample: PageSample,
        candidates: list[CrawlDefinition],
    ) -> SampleParseRecord:
        markup = self.load_markup(sample)
        root = parse_html(markup)

        version_results = [self.parse_with_definition(sample, d, root, markup) for d in candidates]
        candidate_labels = [f"{d.definition_id}@{d.version}" for d in candidates]

        unresolved: list[ParsedField] = []
        for result in version_results:
            for f in result.fields:
                if f.status == PARSE_UNRESOLVED:
                    unresolved.append(f)

        # 选定“可复核”的版本：标题字段在该版本下确实解析成功
        selected = [
            f"{r.definition_id}@{r.version}"
            for r in version_results
            if any(f.field_name == "announcement_title" and f.status == PARSE_OK for f in r.fields)
        ]

        title_values = {
            f.value
            for r in version_results
            for f in r.fields
            if f.field_name == "announcement_title" and f.status == PARSE_OK
        }
        if len(version_results) > 1 and title_values and len(title_values) == 1 and selected:
            overall = PARSE_OK if not unresolved else PARSE_AMBIGUOUS
        elif not selected:
            overall = PARSE_UNRESOLVED
        else:
            overall = PARSE_AMBIGUOUS if unresolved else PARSE_OK

        return SampleParseRecord(
            sample_id=sample.sample_id,
            legacy_ref=sample.legacy_ref,
            legacy_version=sample.legacy_version,
            source_url=sample.source_url,
            archive_path=sample.archive_path,
            candidate_definitions=candidate_labels,
            selected_for_review=selected,
            version_results=version_results,
            unresolved_locations=unresolved,
            overall_status=overall,
        )

    def parse_all(
        self,
        samples: list[PageSample],
        definitions: list[CrawlDefinition],
        ref_to_definition_ids: dict[str, list[str]],
    ) -> list[SampleParseRecord]:
        records: list[SampleParseRecord] = []
        index = {(d.definition_id, d.version): d for d in definitions}
        for sample in samples:
            ids = ref_to_definition_ids.get(sample.legacy_ref, [])
            candidates = [d for d in definitions if d.definition_id in ids]
            candidates.sort(key=lambda d: d.version)
            if not candidates:
                records.append(SampleParseRecord(
                    sample_id=sample.sample_id,
                    legacy_ref=sample.legacy_ref,
                    legacy_version=sample.legacy_version,
                    source_url=sample.source_url,
                    archive_path=sample.archive_path,
                    candidate_definitions=[],
                    selected_for_review=[],
                    version_results=[],
                    unresolved_locations=[ParsedField(
                        field_name="*", selector=None, status=PARSE_UNRESOLVED,
                        value=None, char_position=None, line_number=None,
                        snippet="", note="旧引用在迁移对照中找不到任何采集定义，待人工核查",
                    )],
                    overall_status=PARSE_UNRESOLVED,
                ))
                continue
            records.append(self.parse_sample(sample, candidates))
        return records


def build_catalog_decisions(records: list[SampleParseRecord]) -> list[CatalogDecision]:
    """按解析记录给出编目结论：双版本逐字一致的标题可编目，其余待核查。"""
    decisions: list[CatalogDecision] = []
    for record in records:
        title_evidence: list[dict[str, Any]] = []
        title_values: list[str] = []
        held: list[dict[str, Any]] = []

        for vr in record.version_results:
            for f in vr.fields:
                if f.field_name == "announcement_title" and f.status == PARSE_OK:
                    title_evidence.append({
                        "definition": f"{vr.definition_id}@{vr.version}",
                        "legacy_id": vr.derived_from_legacy_id,
                        "selector": f.selector,
                        "value": f.value,
                        "char_position": f.char_position,
                        "line_number": f.line_number,
                    })
                    title_values.append(str(f.value))
                if f.status == PARSE_UNRESOLVED:
                    held.append({
                        "definition": f"{vr.definition_id}@{vr.version}",
                        "field": f.field_name,
                        "selector": f.selector,
                        "char_position": f.char_position,
                        "line_number": f.line_number,
                        "reason": f.note,
                    })
                if f.field_name == "temporary_opening_hours" and f.status == PARSE_OK:
                    held.append({
                        "definition": f"{vr.definition_id}@{vr.version}",
                        "field": "temporary_opening_hours",
                        "value": f.value,
                        "char_position": f.char_position,
                        "line_number": f.line_number,
                        "reason": "仅全页版本页面取证，缺少采集版本凭据，暂不编入目录",
                    })

        distinct_titles = set(title_values)
        multi_version_agreement = len(title_evidence) >= 2 and len(distinct_titles) == 1
        single_version_ok = len(title_evidence) == 1 and len(distinct_titles) == 1
        catalogable = multi_version_agreement or single_version_ok
        title = next(iter(distinct_titles), None)

        if catalogable and not held:
            decision, reason = "可编目", "标题由可复核采集定义逐字核实，无待核字段"
        elif catalogable:
            decision = "可编目（部分字段挂起）"
            reason = "标题凭据充分可建目录；开放时间或正文字段仍欠版本凭据，列入待核查"
        else:
            decision, reason = "待核查", "没有任何版本能逐字核实公告标题，暂不编目"

        decisions.append(CatalogDecision(
            sample_id=record.sample_id,
            announcement_title=title,
            title_evidence=title_evidence,
            title_catalogable=catalogable,
            held_fields=held,
            decision=decision,
            reason=reason,
        ))
    return decisions
