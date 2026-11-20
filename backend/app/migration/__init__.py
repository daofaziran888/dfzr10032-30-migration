"""历史抓取规则迁移子系统。

把网页采集规则的旧清单（平铺字段：目标网址、内容选择器、字符编码……）迁移为
带版本的结构化采集定义，并对随旧登记归档的页面样本做可复核解析：

- ``models``     迁移过程中使用的结构化数据类型；
- ``dom``        不依赖第三方库的极简 HTML/DOM 与 CSS 选择器实现；
- ``builder``    旧清单 -> 版本化采集定义 + 迁移对照明细（逐字段溯源，禁止跨规则拼装）；
- ``engine``     依据迁移对照为每份样本选择可复核定义，写出解析版本与未解析字段位置；
- ``registry``   在新运行环境中持有归档、定义与解析结果，并支持凭旧引用回查原出处；
- ``catalog``    汇总本轮可编目公告与仍待核查项（含临时开放时间的版本凭据缺口）。
"""
from __future__ import annotations

from app.migration.registry import MigrationRegistry, get_registry, reload_registry

__all__ = ["MigrationRegistry", "get_registry", "reload_registry"]
