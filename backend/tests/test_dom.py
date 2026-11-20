"""极简 DOM/选择器与位置追踪测试（只用标准库，不依赖第三方解析库）。"""
from __future__ import annotations

import pytest

from app.migration.dom import SelectorError, parse_html, select, select_first

HTML = """<!DOCTYPE html>
<html>
  <body id="main">
    <section class="notice-box">
      <p class="notice-line">临时开放时间：08:30 — 17:30</p>
    </section>
    <article>
      <h1 class="notice-title">测试公告标题</h1>
      <div class="article-body">
        <p>第一段正文</p>
        <p>第二段正文</p>
      </div>
    </article>
  </body>
</html>
"""


def test_type_class_and_id_selectors() -> None:
    root = parse_html(HTML)
    assert select_first(root, "h1.notice-title").get_text() == "测试公告标题"
    assert select_first(root, "#main").tag == "body"
    assert len(select(root, "p")) == 3
    assert select_first(root, ".notice-line").get_text().startswith("临时开放时间")


def test_descendant_and_child_combinators() -> None:
    root = parse_html(HTML)
    assert len(select(root, ".article-body p")) == 2
    assert len(select(root, "article > h1")) == 1
    assert select(root, "section > h1") == []


def test_empty_and_invalid_selectors_raise() -> None:
    root = parse_html(HTML)
    for bad in ("", "   ", "div.", ".", "h1..x"):
        with pytest.raises(SelectorError):
            select(root, bad)


def test_node_position_tracks_decoded_text_offset() -> None:
    root = parse_html(HTML)
    node = select_first(root, "h1.notice-title")
    expected = HTML.index("<h1")
    assert node.start_pos == expected
    assert node.start_line == HTML[:expected].count("\n") + 1


def test_find_text_position() -> None:
    root = parse_html(HTML)
    body = select_first(root, ".article-body")
    pos, line = body.find_text_position("第二段正文")
    assert HTML[pos:pos + 5] == "第二段正文"
    assert line == HTML[:pos].count("\n") + 1


def test_whitespace_normalized_in_text() -> None:
    root = parse_html(HTML)
    text = select_first(root, ".article-body").get_text()
    assert "\n" not in text
    # 段落间的空白文本节点折叠后不再产生多余空格
    assert text == "第一段正文第二段正文"
