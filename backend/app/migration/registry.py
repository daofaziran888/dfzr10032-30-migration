"""迁移注册表：新运行环境里的归档、版本化定义与解析结果的统一入口。

两个版本并存时，页面样本仍带旧引用（可能无版本号）。注册表负责：

* 加载旧清单与归档样本，执行迁移并预跑解析；
* 凭旧引用回查它对应的全部候选定义版本，以及归档原页字节/解码文本，
  保证“从旧引用打开仍是原页”；
* 输出迁移对照明细、解析记录与编目核查结论。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.migration.builder import build_definitions
from app.migration.engine import ParseEngine, build_catalog_decisions
from app.migration.models import (
    CrawlDefinition,
    LegacyRule,
    MigrationEntry,
    PageSample,
    SampleParseRecord,
)

DEFAULT_FIXTURE_ROOT = Path(__file__).resolve().parent.parent.parent / "fixtures" / "migration"


class MigrationRegistry:
    def __init__(self, fixture_root: Path | str | None = None) -> None:
        self.fixture_root = Path(fixture_root) if fixture_root else DEFAULT_FIXTURE_ROOT
        self.archive_root = self.fixture_root / "archive"
        self.legacy_rules: list[LegacyRule] = []
        self.definitions: list[CrawlDefinition] = []
        self.migration_entries: list[MigrationEntry] = []
        self.samples: list[PageSample] = []
        self.parse_records: list[SampleParseRecord] = []
        self._ref_index: dict[str, list[str]] = {}
        self._engine = ParseEngine(self.archive_root)
        self.reload()

    # ---------------------------------------------------------------- 装载与迁移
    def reload(self) -> None:
        self.legacy_rules = self._load_legacy_rules()
        self.definitions, self.migration_entries = build_definitions(self.legacy_rules)
        self.samples = self._load_samples()
        self._ref_index = self._build_ref_index()
        self.parse_records = self._engine.parse_all(
            self.samples, self.definitions, self._ref_index,
        )

    def _load_json(self, name: str) -> Any:
        with (self.fixture_root / name).open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _load_legacy_rules(self) -> list[LegacyRule]:
        payload = self._load_json("legacy_rules.json")
        rules: list[LegacyRule] = []
        for item in payload:
            rules.append(LegacyRule(
                legacy_id=str(item["legacy_id"]),
                rule_no=str(item["rule_no"]),
                flat_fields=dict(item["flat_fields"]),
                archived_at=str(item.get("archived_at", "")),
                remark=str(item.get("remark", "")),
            ))
        return rules

    def _load_samples(self) -> list[PageSample]:
        payload = self._load_json("page_samples.json")
        samples: list[PageSample] = []
        for item in payload:
            samples.append(PageSample(
                sample_id=str(item["sample_id"]),
                legacy_ref=str(item["legacy_ref"]),
                legacy_version=item.get("legacy_version"),
                archive_path=str(item["archive_path"]),
                source_url=str(item["source_url"]),
                encoding=str(item["encoding"]),
                archived_at=str(item.get("archived_at", "")),
                content_encoding=str(item.get("content_encoding", "utf-8")),
            ))
        return samples

    def _build_ref_index(self) -> dict[str, list[str]]:
        """旧引用 -> 可回查的 definition_id 列表（编号引用与 legacy_id 引用都登记）。"""
        index: dict[str, list[str]] = {}
        for rule in self.legacy_rules:
            definition_ids = {d.definition_id for d in self.definitions
                              if d.derived_from_legacy_id == rule.legacy_id}
            for ref in {rule.legacy_id, rule.rule_no}:
                bucket = index.setdefault(ref, [])
                for did in definition_ids:
                    if did not in bucket:
                        bucket.append(did)
        return index

    # ---------------------------------------------------------------- 查询视图
    def legacy_rules_view(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.legacy_rules]

    def definitions_view(self) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self.definitions]

    def migration_view(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self.migration_entries]

    def samples_view(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.samples]

    def parse_records_view(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.parse_records]

    def catalog_view(self) -> list[dict[str, Any]]:
        return [d.to_dict() for d in build_catalog_decisions(self.parse_records)]

    def summary(self) -> dict[str, Any]:
        catalog = build_catalog_decisions(self.parse_records)
        review_fields = sum(len(e.review_fields) for e in self.migration_entries)
        return {
            "legacy_rule_count": len(self.legacy_rules),
            "definition_count": len(self.definitions),
            "sample_count": len(self.samples),
            "parse_record_count": len(self.parse_records),
            "pending_review_field_count": review_fields,
            "catalogable_samples": [d.sample_id for d in catalog if d.title_catalogable],
            "held_samples": [d.sample_id for d in catalog if not d.title_catalogable],
        }

    # ---------------------------------------------------- 旧引用回查（原页出处）
    def resolve_reference(self, legacy_ref: str) -> dict[str, Any]:
        """凭样本上的旧引用回查：候选定义版本、关联旧规则与归档样本。"""
        definition_ids = self._ref_index.get(legacy_ref, [])
        versions = [
            {
                "definition_id": d.definition_id,
                "version": d.version,
                "scope": d.scope,
                "derived_from_legacy_id": d.derived_from_legacy_id,
            }
            for d in self.definitions if d.definition_id in definition_ids
        ]
        related_legacy = [
            r.legacy_id for r in self.legacy_rules
            if legacy_ref in (r.legacy_id, r.rule_no)
        ]
        related_samples = [
            {
                "sample_id": s.sample_id,
                "archive_path": s.archive_path,
                "source_url": s.source_url,
                "legacy_version": s.legacy_version,
            }
            for s in self.samples if s.legacy_ref == legacy_ref
        ]
        return {
            "legacy_ref": legacy_ref,
            "resolved": bool(versions or related_samples),
            "related_legacy_ids": related_legacy,
            "candidate_definitions": versions,
            "archived_samples": related_samples,
        }

    def open_archived_page(self, sample_id: str) -> dict[str, Any]:
        """从旧引用打开归档原页：返回解码文本与字节级出处信息，不重新抓取网络。"""
        sample = next((s for s in self.samples if s.sample_id == sample_id), None)
        if sample is None:
            raise KeyError(sample_id)
        path = self.archive_root / sample.archive_path
        raw = path.read_bytes()
        markup = raw.decode(sample.encoding)
        return {
            "sample_id": sample.sample_id,
            "legacy_ref": sample.legacy_ref,
            "legacy_version": sample.legacy_version,
            "source_url": sample.source_url,
            "archive_path": sample.archive_path,
            "declared_encoding": sample.encoding,
            "byte_length": len(raw),
            "char_length": len(markup),
            "markup": markup,
        }


_REGISTRY: MigrationRegistry | None = None


def get_registry() -> MigrationRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = MigrationRegistry()
    return _REGISTRY


def reload_registry() -> MigrationRegistry:
    global _REGISTRY
    _REGISTRY = MigrationRegistry()
    return _REGISTRY
