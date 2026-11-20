"""迁移子系统的数据类型。

全部用标准库 dataclass，并提供 ``to_dict`` 方便 JSON 序列化。
关键设计约束（对应业务要求）：

1. 旧字段含义不足时只保留原文、标记 ``待核``，绝不猜测或补默认选择器；
2. 每条结构化定义的每个字段都带 ``source_legacy_id``，保证一个旧规则的抓取频率
   不会与另一个旧规则的正文选择器被拼成一套；
3. 页面样本的旧引用（可无版本号）与解析结果分离，两个版本并存时仍可凭旧引用
   回查归档原页。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# 旧清单中可识别的平铺字段名（其余字段一律按“含义不足/无法识别”保留原文待核）
LEGACY_URL_FIELDS = ("目标网址", "target_url", "url")
LEGACY_ENCODING_FIELDS = ("字符编码", "encoding", "charset")
LEGACY_FREQUENCY_FIELDS = ("抓取频率", "frequency", "cron")
LEGACY_SCOPE_FIELDS = ("抓取范围", "采集范围", "scope")
# 选择器类字段：旧系统里“内容选择器”的叫法不统一，需要逐一甄别，不能想当然
LEGACY_TITLE_SELECTOR_FIELDS = ("标题选择器", "title_selector")
LEGACY_CONTENT_SELECTOR_FIELDS = ("内容选择器", "正文选择器", "content_selector", "body_selector")
LEGACY_PAGE_SELECTOR_FIELDS = ("页面选择器", "page_selector", "容器选择器")

# 字段迁移状态
MIGRATED = "已迁移"        # 含义明确，已结构化
REVIEW_RAW = "留原文待核"  # 含义不足，保留原值等人工核对，不猜默认值

# 解析状态
PARSE_OK = "已解析"
PARSE_AMBIGUOUS = "多版本待核"
PARSE_UNRESOLVED = "未能解析"


@dataclass
class FieldProvenance:
    """单个结构化字段的迁移溯源：值来自哪条旧规则的哪个旧字段。"""

    field_name: str
    value: Any
    status: str                      # MIGRATED / REVIEW_RAW
    source_legacy_id: str | None    # 必须是同一条旧规则，杜绝跨规则拼字段
    source_legacy_field: str | None
    raw_value: Any = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LegacyRule:
    """旧清单里的一条平铺登记。``legacy_id`` 在旧库内唯一（同编号可有多条）。"""

    legacy_id: str
    rule_no: str                     # 规则编号，允许重复（同编号两份旧规格）
    flat_fields: dict[str, Any]
    archived_at: str = ""
    remark: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CrawlDefinition:
    """新版本的结构化采集定义（带语义化版本号）。"""

    definition_id: str               # 与旧规则编号挂钩，如 LIB-12
    version: str                     # 语义化版本 1.0.0 / 1.1.0
    scope: str                       # full_page / body_only / unknown
    target_url: FieldProvenance
    encoding: FieldProvenance
    crawl_frequency: FieldProvenance
    title_selector: FieldProvenance
    content_selector: FieldProvenance
    page_selector: FieldProvenance | None = None
    extra_fields: list[FieldProvenance] = field(default_factory=list)
    derived_from_legacy_id: str = ""
    status: str = "生效中"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


@dataclass
class MigrationEntry:
    """历史抓取规则迁移对照明细中的一行：一条旧规则 -> 一个新版本定义。"""

    legacy_id: str
    rule_no: str
    definition_id: str
    version: str
    field_mappings: list[FieldProvenance]
    review_fields: list[FieldProvenance]
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "legacy_id": self.legacy_id,
            "rule_no": self.rule_no,
            "definition_id": self.definition_id,
            "version": self.version,
            "field_mappings": [m.to_dict() for m in self.field_mappings],
            "review_fields": [m.to_dict() for m in self.review_fields],
            "note": self.note,
        }


@dataclass
class PageSample:
    """随旧登记送来的归档页面样本；旧引用可以没有版本号。"""

    sample_id: str
    legacy_ref: str                   # 样本仍带的旧规则引用（规则编号或 legacy_id）
    legacy_version: str | None        # 可能为 None：归档时没有版本号
    archive_path: str                 # 归档原页相对路径（新环境凭此回查原出处）
    source_url: str
    encoding: str
    archived_at: str
    content_encoding: str = "utf-8"   # 归档文件自身的字节编码

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedField:
    """某个定义版本下一个字段的解析结果。"""

    field_name: str
    selector: str | None
    status: str                       # PARSE_OK / PARSE_UNRESOLVED
    value: str | None = None
    char_position: int | None = None  # 未能解析时给出字段在归档原页中的字符位置
    line_number: int | None = None
    snippet: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VersionParseResult:
    """一份样本在某一个采集定义版本下的完整解析记录。"""

    definition_id: str
    version: str
    derived_from_legacy_id: str
    scope: str
    fields: list[ParsedField]
    page_char_length: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition_id": self.definition_id,
            "version": self.version,
            "derived_from_legacy_id": self.derived_from_legacy_id,
            "scope": self.scope,
            "page_char_length": self.page_char_length,
            "fields": [f.to_dict() for f in self.fields],
        }


@dataclass
class SampleParseRecord:
    """格式解析器为一份样本写出的解析记录（可含多个候选版本）。"""

    sample_id: str
    legacy_ref: str
    legacy_version: str | None
    source_url: str
    archive_path: str
    candidate_definitions: list[str]    # 实际用于复核的 definition_id@version
    selected_for_review: list[str]
    version_results: list[VersionParseResult]
    unresolved_locations: list[ParsedField]
    overall_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "legacy_ref": self.legacy_ref,
            "legacy_version": self.legacy_version,
            "source_url": self.source_url,
            "archive_path": self.archive_path,
            "candidate_definitions": self.candidate_definitions,
            "selected_for_review": self.selected_for_review,
            "version_results": [v.to_dict() for v in self.version_results],
            "unresolved_locations": [u.to_dict() for u in self.unresolved_locations],
            "overall_status": self.overall_status,
        }


@dataclass
class CatalogDecision:
    """编目结论：标题是否有足够版本凭据可编目，开放时间等字段为何仍待核查。"""

    sample_id: str
    announcement_title: str | None
    title_evidence: list[dict[str, Any]]
    title_catalogable: bool
    held_fields: list[dict[str, Any]]
    decision: str                       # 可编目 / 待核查
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
