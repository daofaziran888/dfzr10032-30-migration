"""零依赖的极简 HTML/DOM 与 CSS 选择器实现。

迁移解析必须能在“新运行环境”里离线复核归档原页，不能假设装了第三方解析库，
因此只使用标准库 ``html.parser``。支持的选择器子集足以覆盖旧清单里的登记：

- 类型/类/ID：``h1``、``.notice-box``、``#main``、``div.notice``
- 后代与子代组合：``div.article p``、``ul > li``

解析时为每个节点记录它在**解码后页面文本**中的起始字符位置，便于在解析记录里
写出“未能解析的字段位置”，而不是只给一个空结果。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

VOID_TAGS = {"br", "img", "meta", "link", "input", "hr", "source", "area", "base", "col", "embed", "param", "track", "wbr"}


class SelectorError(ValueError):
    """选择器为空或语法不受支持时抛出；调用方按“未能解析”处理，不做猜测。"""


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    classes: list[str]
    element_id: str | None
    start_pos: int
    start_line: int
    parent: "Node | None" = None
    children: list["Node"] = field(default_factory=list)
    # (文本片段, 该片段在解码后页面中的绝对字符位置)
    text_segments: list[tuple[str, int]] = field(default_factory=list)

    def get_text(self) -> str:
        # 汇总自身与后代的全部文本片段，再折叠空白
        collected: list[str] = []
        self._collect_text(collected)
        return _normalize_ws("".join(collected))

    def _collect_text(self, out: list[str]) -> None:
        for text, _pos in self.text_segments:
            out.append(text)
        for child in self.children:
            child._collect_text(out)

    def iter_descendants(self) -> "list[Node]":
        result: list[Node] = []
        for child in self.children:
            result.append(child)
            result.extend(child.iter_descendants())
        return result

    def find_text_position(self, needle: str) -> tuple[int, int] | None:
        """在本节点（含后代）文本里找 needle，返回 (绝对字符位置, 所在行号)。"""
        for text, pos in self.text_segments:
            idx = text.find(needle)
            if idx >= 0:
                return pos + idx, _line_at(self._line_starts(), pos + idx)
        for child in self.children:
            found = child.find_text_position(needle)
            if found is not None:
                return found
        return None

    def _line_starts(self) -> list[int]:
        root = self
        while root.parent is not None:
            root = root.parent
        return root.line_starts  # type: ignore[attr-defined,no-any-return]

    # 由解析器在根节点上注入
    line_starts: list[int] = field(default_factory=list)


def _line_at(line_starts: list[int], pos: int) -> int:
    import bisect

    return bisect.bisect_right(line_starts, pos)


def _normalize_ws(text: str) -> str:
    return " ".join(text.split())


class _TreeBuilder(HTMLParser):
    def __init__(self, line_starts: list[int]) -> None:
        super().__init__(convert_charrefs=True)
        self.line_starts = line_starts
        self.root = Node(
            tag="#root", attrs={}, classes=[], element_id=None,
            start_pos=0, start_line=1,
        )
        self.root.line_starts = line_starts
        self.stack: list[Node] = [self.root]

    def _abs_pos(self) -> tuple[int, int]:
        line, column = self.getpos()
        return self.line_starts[line - 1] + column, line

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        pos, line = self._abs_pos()
        attr_dict = {k: (v or "") for k, v in attrs}
        node = Node(
            tag=tag.lower(),
            attrs=attr_dict,
            classes=attr_dict.get("class", "").split(),
            element_id=attr_dict.get("id"),
            start_pos=pos,
            start_line=line,
            parent=self.stack[-1],
        )
        node.line_starts = self.line_starts
        self.stack[-1].children.append(node)
        if tag.lower() not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_TAGS:
            # XHTML 式自闭合非空标签：补一次出栈
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for depth in range(len(self.stack) - 1, 0, -1):
            if self.stack[depth].tag == tag:
                del self.stack[depth:]
                return

    def handle_data(self, data: str) -> None:
        pos, _line = self._abs_pos()
        self.stack[-1].text_segments.append((data, pos))


def parse_html(markup: str) -> Node:
    """把解码后的 HTML 文本解析为节点树，根节点 tag 为 ``#root``。"""
    line_starts = [0]
    for idx, ch in enumerate(markup):
        if ch == "\n":
            line_starts.append(idx + 1)
    builder = _TreeBuilder(line_starts)
    builder.feed(markup)
    builder.close()
    return builder.root


@dataclass
class _Compound:
    tag: str | None
    element_id: str | None
    classes: list[str]


def _parse_compound(token: str) -> _Compound:
    tag: str | None = None
    element_id: str | None = None
    classes: list[str] = []
    token = token.strip()
    if not token:
        raise SelectorError("选择器片段为空")
    buf = ""
    parts: list[str] = []
    for ch in token:
        if ch in ".#":
            if buf:
                parts.append(buf)
                buf = ""
            parts.append(ch)
        else:
            buf += ch
    if buf:
        parts.append(buf)
    i = 0
    while i < len(parts):
        part = parts[i]
        if part in (".", "#"):
            # 标记后必须紧跟名称；构造器已挡住首尾悬空的情况，这里再兜一层
            if i + 1 >= len(parts) or parts[i + 1] in (".", "#"):
                raise SelectorError(f"不支持的选择器写法：{token}")
            if part == ".":
                classes.append(parts[i + 1])
            else:
                element_id = parts[i + 1]
            i += 2
        else:
            if tag is None:
                tag = part.lower()
            else:
                raise SelectorError(f"不支持的复合选择器：{token}")
            i += 1
    return _Compound(tag=tag, element_id=element_id, classes=classes)


def _match_compound(node: Node, compound: _Compound) -> bool:
    if compound.tag is not None and node.tag != compound.tag:
        return False
    if compound.element_id is not None and node.element_id != compound.element_id:
        return False
    if any(cls not in node.classes for cls in compound.classes):
        return False
    return True


def _tokenize_selector(selector: str) -> list[tuple[str, _Compound]]:
    tokens = selector.split()
    if not tokens:
        raise SelectorError("选择器为空")
    parsed: list[tuple[str, _Compound]] = []
    combinator = " "
    for token in tokens:
        if token == ">":
            combinator = ">"
            continue
        parsed.append((combinator, _parse_compound(token)))
        combinator = " "
    return parsed


def select(root: Node, selector: str) -> list[Node]:
    """按选择器返回匹配节点（文档顺序、去重）。空/非法选择器抛 SelectorError。"""
    if selector is None or not str(selector).strip():
        raise SelectorError("选择器为空，按规则不得猜测默认选择器")
    tokens = _tokenize_selector(str(selector).strip())
    _comb, first = tokens[0]
    current = [node for node in root.iter_descendants() if _match_compound(node, first)]
    for combinator, compound in tokens[1:]:
        nxt: list[Node] = []
        for node in current:
            pool = node.children if combinator == ">" else node.iter_descendants()
            for candidate in pool:
                if _match_compound(candidate, compound) and candidate not in nxt:
                    nxt.append(candidate)
        current = nxt
    return current


def select_first(root: Node, selector: str) -> Node | None:
    matches = select(root, selector)
    return matches[0] if matches else None
