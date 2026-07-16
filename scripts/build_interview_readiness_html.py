#!/usr/bin/env python3
"""Build the offline AI Infra interview-readiness mind map."""

import argparse
import html
import json
import posixpath
import re
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT / "docs/interview-prep/AI_INFRA_INTERVIEW_READINESS.md"
DEFAULT_OUTPUT = ROOT / "docs/interview-prep/AI_INFRA_INTERVIEW_READINESS.html"

TOPIC_HEADING = re.compile(r"^### (\d{2})｜(.+?)\s*$", re.MULTILINE)
FIELD_LINE = r"^- \*\*{label}：\*\*\s*(.+?)\s*$"


def _field(block: str, label: str) -> str:
    match = re.search(
        FIELD_LINE.format(label=re.escape(label)), block, re.MULTILINE
    )
    if not match:
        raise ValueError("topic is missing field: {}".format(label))
    return match.group(1).strip()


def _parse_mastery(value: str) -> Dict[str, str]:
    levels = dict(re.findall(r"(原理|源码|手写|实验)\s+(L[0-3])", value))
    expected = {"原理", "源码", "手写", "实验"}
    if set(levels) != expected:
        raise ValueError("invalid mastery field: {}".format(value))
    return levels


def parse_topics(index_path: Path = DEFAULT_INDEX) -> List[Dict[str, object]]:
    """Parse and validate topic registry entries from the Markdown index."""

    index_path = Path(index_path).resolve()
    source = index_path.read_text(encoding="utf-8")
    matches = list(TOPIC_HEADING.finditer(source))
    if not matches:
        raise ValueError("no interview-readiness topics found")

    topics_root = (index_path.parent / "topics").resolve()
    topics: List[Dict[str, object]] = []
    seen = set()
    for position, match in enumerate(matches):
        topic_id, title = match.groups()
        if topic_id in seen:
            raise ValueError("duplicate topic id: {}".format(topic_id))
        seen.add(topic_id)
        end = matches[position + 1].start() if position + 1 < len(matches) else len(source)
        block = source[match.end() : end]

        priority_text = _field(block, "优先级")
        priority_match = re.match(r"(P[0-3])\b", priority_text)
        if not priority_match:
            raise ValueError("invalid priority for topic {}".format(topic_id))

        detail_match = re.search(
            r"^- \*\*详情：\*\* \[[^\]]+\]\((topics/[^)]+\.md)\)\s*$",
            block,
            re.MULTILINE,
        )
        if not detail_match:
            raise ValueError("topic {} is missing detail link".format(topic_id))
        detail_relative = detail_match.group(1)
        detail_path = (index_path.parent / detail_relative).resolve()
        if detail_path.parent != topics_root or not detail_path.is_file():
            raise ValueError(
                "topic {} detail must resolve inside {}".format(
                    topic_id, topics_root
                )
            )

        topics.append(
            {
                "id": topic_id,
                "title": title.strip(),
                "priority": priority_match.group(1),
                "priority_text": priority_text,
                "state": _field(block, "状态"),
                "mastery": _parse_mastery(_field(block, "目标熟练度")),
                "capability": _field(block, "能力结果"),
                "boundary": _field(block, "边界"),
                "detail_relative": detail_relative,
                "detail_path": detail_path,
            }
        )

    expected_ids = ["{:02d}".format(number) for number in range(1, len(topics) + 1)]
    actual_ids = [str(topic["id"]) for topic in topics]
    if actual_ids != expected_ids:
        raise ValueError(
            "topic ids must be contiguous and ordered: {}".format(actual_ids)
        )
    return topics


def _safe_href(raw_href: str, relative_root: str) -> Optional[str]:
    href = html.unescape(raw_href).strip()
    if href.startswith(("https://", "http://", "#")):
        return href
    if ":" in href.split("/", 1)[0]:
        return None
    normalized = posixpath.normpath(posixpath.join(relative_root, href))
    if normalized.startswith("../"):
        return None
    return normalized


def _inline_markdown(text: str, relative_root: str = "topics") -> str:
    escaped = html.escape(text, quote=True)

    def replace_link(match: re.Match) -> str:
        label, raw_href = match.groups()
        href = _safe_href(raw_href, relative_root)
        if href is None:
            return label
        target = ' target="_blank" rel="noopener noreferrer"' if href.startswith("http") else ""
        return '<a href="{}"{}>{}</a>'.format(
            html.escape(href, quote=True), target, label
        )

    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_link, escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def markdown_to_html(source: str, relative_root: str = "topics") -> str:
    """Render the small Markdown subset used by the topic detail pages."""

    lines = source.splitlines()
    output: List[str] = []
    paragraph: List[str] = []
    list_kind: Optional[str] = None
    in_code = False
    code_lines: List[str] = []
    code_language = ""

    def flush_paragraph() -> None:
        if paragraph:
            output.append(
                "<p>{}</p>".format(
                    _inline_markdown(" ".join(paragraph), relative_root)
                )
            )
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            output.append("</{}>".format(list_kind))
            list_kind = None

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if in_code:
            if stripped.startswith("```"):
                output.append(
                    '<pre><code class="language-{}">{}</code></pre>'.format(
                        html.escape(code_language, quote=True),
                        html.escape("\n".join(code_lines)),
                    )
                )
                in_code = False
                code_lines = []
                code_language = ""
            else:
                code_lines.append(line)
            index += 1
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            in_code = True
            code_language = stripped[3:].strip()
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines):
            separator = lines[index + 1].strip()
            if separator.startswith("|") and re.search(r"---", separator):
                flush_paragraph()
                close_list()
                table_lines = [line]
                index += 2
                while index < len(lines) and lines[index].strip().startswith("|"):
                    table_lines.append(lines[index])
                    index += 1
                rows = [
                    [cell.strip() for cell in row.strip().strip("|").split("|")]
                    for row in table_lines
                ]
                output.append("<div class=\"table-wrap\"><table><thead><tr>")
                output.extend(
                    "<th>{}</th>".format(_inline_markdown(cell, relative_root))
                    for cell in rows[0]
                )
                output.append("</tr></thead><tbody>")
                for row in rows[1:]:
                    output.append("<tr>")
                    output.extend(
                        "<td>{}</td>".format(_inline_markdown(cell, relative_root))
                        for cell in row
                    )
                    output.append("</tr>")
                output.append("</tbody></table></div>")
                continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            close_list()
            level = min(len(heading.group(1)) + 1, 6)
            output.append(
                "<h{0}>{1}</h{0}>".format(
                    level, _inline_markdown(heading.group(2), relative_root)
                )
            )
            index += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            close_list()
            quote_lines = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote_lines.append(lines[index].strip()[1:].strip())
                index += 1
            quote_text = " ".join(item for item in quote_lines if item)
            if quote_text:
                output.append(
                    "<blockquote>{}</blockquote>".format(
                        _inline_markdown(quote_text, relative_root)
                    )
                )
            continue

        list_match = re.match(r"^[-*]\s+(.+)$", stripped)
        ordered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if list_match or ordered_match:
            flush_paragraph()
            wanted_kind = "ul" if list_match else "ol"
            if list_kind != wanted_kind:
                close_list()
                output.append("<{}>".format(wanted_kind))
                list_kind = wanted_kind
            item = (list_match or ordered_match).group(1)
            output.append(
                "<li>{}</li>".format(_inline_markdown(item, relative_root))
            )
            index += 1
            continue

        if not stripped:
            flush_paragraph()
            close_list()
        else:
            paragraph.append(stripped)
        index += 1

    if in_code:
        output.append("<pre><code>{}</code></pre>".format(html.escape("\n".join(code_lines))))
    flush_paragraph()
    close_list()
    return "\n".join(output)


def _status_group(state: str) -> str:
    if "从零" in state:
        return "from-zero"
    if any(marker in state for marker in ("已有", "已建立", "旧笔记")):
        return "foundation"
    return "pending"


def _serializable_topics(topics: List[Dict[str, object]]) -> List[Dict[str, object]]:
    serialized = []
    for topic in topics:
        detail_path = Path(topic["detail_path"])
        detail_source = detail_path.read_text(encoding="utf-8")
        value = {
            key: topic[key]
            for key in (
                "id",
                "title",
                "priority",
                "priority_text",
                "state",
                "mastery",
                "capability",
                "boundary",
                "detail_relative",
            )
        }
        value["status_group"] = _status_group(str(topic["state"]))
        value["has_p0_defense"] = "P0 防守" in str(topic["priority_text"])
        value["detail_html"] = markdown_to_html(detail_source)
        value["search_text"] = " ".join(
            (
                str(topic["id"]),
                str(topic["title"]),
                str(topic["priority_text"]),
                str(topic["state"]),
                str(topic["capability"]),
                str(topic["boundary"]),
                re.sub(r"\s+", " ", detail_source),
            )
        ).lower()
        serialized.append(value)
    return serialized


HTML_TEMPLATE = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>AI Infra 面试就绪知识图谱</title>
  <style>
    :root {
      --ink: #17201d;
      --muted: #68736e;
      --paper: #f4f1e8;
      --panel: rgba(255, 254, 249, .94);
      --line: #d7d2c4;
      --p0: #d26444;
      --p0-soft: #f5d8ca;
      --p1: #2f7c70;
      --p1-soft: #d5ebe5;
      --accent: #274d62;
      --shadow: 0 12px 34px rgba(31, 42, 38, .12);
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; margin: 0; }
    body {
      overflow: hidden;
      color: var(--ink);
      background:
        radial-gradient(circle at 15% 15%, rgba(210,100,68,.10), transparent 30%),
        radial-gradient(circle at 85% 85%, rgba(47,124,112,.12), transparent 34%),
        var(--paper);
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Noto Sans CJK SC", sans-serif;
    }
    button, input, select { font: inherit; }
    button { color: inherit; }
    .app { display: flex; flex-direction: column; height: 100%; }
    .topbar {
      min-height: 72px;
      display: flex;
      align-items: center;
      gap: 18px;
      padding: 12px 18px;
      border-bottom: 1px solid var(--line);
      background: rgba(250,248,241,.88);
      backdrop-filter: blur(16px);
      z-index: 20;
    }
    .brand { min-width: 250px; }
    .brand h1 { margin: 0; font-family: Georgia, "Songti SC", serif; font-size: 19px; letter-spacing: .01em; }
    .brand p { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
    .filters { display: flex; flex: 1; gap: 8px; align-items: center; flex-wrap: wrap; }
    .control, .icon-btn {
      height: 36px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: rgba(255,255,255,.78);
      outline: none;
    }
    .control:focus, .icon-btn:focus-visible { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(39,77,98,.14); }
    .search { position: relative; min-width: 230px; flex: 1; max-width: 390px; }
    .search input { width: 100%; padding: 0 34px 0 12px; }
    .search kbd { position: absolute; right: 9px; top: 9px; color: #8d948f; font-size: 11px; }
    select.control { padding: 0 28px 0 10px; color: #39423f; }
    .icon-btn { padding: 0 11px; cursor: pointer; transition: .16s ease; }
    .icon-btn:hover { border-color: #a8aca5; transform: translateY(-1px); }
    .workspace { display: grid; grid-template-columns: minmax(0, 1fr) 430px; min-height: 0; flex: 1; }
    .canvas-wrap { position: relative; min-width: 0; overflow: hidden; }
    #mindmap-svg { width: 100%; height: 100%; display: block; cursor: grab; touch-action: none; }
    #mindmap-svg.dragging { cursor: grabbing; }
    .canvas-hint {
      position: absolute; left: 18px; bottom: 16px;
      color: var(--muted); font-size: 12px; pointer-events: none;
      background: rgba(250,248,241,.78); border: 1px solid var(--line); border-radius: 9px; padding: 7px 10px;
    }
    .canvas-tools { position: absolute; right: 16px; bottom: 16px; display: flex; gap: 6px; }
    .canvas-tools .icon-btn { min-width: 38px; background: rgba(255,254,249,.9); box-shadow: 0 4px 14px rgba(31,42,38,.08); }
    .detail {
      min-width: 0; overflow: hidden; border-left: 1px solid var(--line);
      background: var(--panel); backdrop-filter: blur(16px); display: flex; flex-direction: column;
    }
    .detail-head { padding: 19px 22px 16px; border-bottom: 1px solid var(--line); }
    .eyebrow { color: var(--muted); font-size: 11px; letter-spacing: .12em; text-transform: uppercase; }
    .detail-head h2 { margin: 6px 0 10px; font: 700 22px/1.25 Georgia, "Songti SC", serif; }
    .badges { display: flex; flex-wrap: wrap; gap: 6px; }
    .badge { display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 999px; font-size: 11px; background: #ece9df; color: #505a56; }
    .badge.p0 { color: #8b3e28; background: var(--p0-soft); }
    .badge.p1 { color: #1b6358; background: var(--p1-soft); }
    .detail-body { padding: 0 22px 50px; overflow: auto; scroll-behavior: smooth; line-height: 1.72; font-size: 14px; }
    .detail-body h2 { margin: 28px 0 8px; font: 700 20px/1.35 Georgia, "Songti SC", serif; }
    .detail-body h3 { margin: 24px 0 7px; font-size: 16px; }
    .detail-body h4 { margin: 20px 0 6px; font-size: 14px; color: var(--accent); }
    .detail-body p { margin: 9px 0; }
    .detail-body ul, .detail-body ol { margin: 8px 0 12px; padding-left: 23px; }
    .detail-body li { margin: 5px 0; }
    .detail-body blockquote { margin: 14px 0; padding: 10px 13px; border-left: 3px solid var(--accent); background: #eeeee8; color: #4f5c57; border-radius: 0 8px 8px 0; }
    .detail-body code { padding: 1px 5px; border-radius: 5px; background: #e8e8e1; color: #8b3e28; font-family: "SFMono-Regular", Consolas, monospace; font-size: .9em; }
    .detail-body pre { overflow: auto; padding: 14px; border-radius: 10px; background: #202a27; color: #edf3ef; line-height: 1.55; }
    .detail-body pre code { padding: 0; background: transparent; color: inherit; }
    .detail-body a { color: #176a7b; text-decoration-thickness: 1px; text-underline-offset: 2px; }
    .table-wrap { overflow-x: auto; margin: 12px 0; }
    table { border-collapse: collapse; width: 100%; font-size: 12px; }
    th, td { padding: 8px; border: 1px solid var(--line); text-align: left; vertical-align: top; }
    th { background: #ece9df; }
    .summary-card { margin: 18px 0; padding: 15px; border: 1px solid var(--line); border-radius: 12px; background: #faf9f4; }
    .summary-card strong { display: block; margin-bottom: 5px; }
    .overview { padding-top: 18px; }
    .overview-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; margin: 16px 0; }
    .metric { padding: 12px; border: 1px solid var(--line); border-radius: 11px; background: #faf9f4; }
    .metric b { display: block; font-size: 22px; font-family: Georgia, serif; }
    .metric span { color: var(--muted); font-size: 11px; }
    .notice { border-left: 3px solid var(--p0); padding: 10px 12px; background: #f7e9df; border-radius: 0 9px 9px 0; }
    .node { cursor: pointer; outline: none; }
    .node rect { transition: stroke-width .15s, filter .15s; }
    .node:hover rect, .node:focus-visible rect { stroke-width: 2.5; filter: drop-shadow(0 5px 7px rgba(32,42,39,.15)); }
    .edge { fill: none; stroke: #aeb3ac; stroke-width: 1.6; opacity: .78; }
    .edge.p0 { stroke: #d09b87; }
    .edge.p1 { stroke: #80aaa2; }
    .empty-map { font-size: 18px; fill: var(--muted); text-anchor: middle; }
    .result-count { margin-left: auto; color: var(--muted); font-size: 12px; white-space: nowrap; }
    @media (max-width: 1050px) {
      .topbar { align-items: flex-start; flex-wrap: wrap; }
      .brand { min-width: 100%; }
      .workspace { grid-template-columns: minmax(0, 1fr) 380px; }
    }
    @media (max-width: 780px) {
      .workspace { display: block; position: relative; }
      .detail { position: absolute; inset: 20% 0 0; z-index: 12; border-left: 0; border-top: 1px solid var(--line); border-radius: 16px 16px 0 0; box-shadow: var(--shadow); transform: translateY(calc(100% - 64px)); transition: transform .22s ease; }
      .detail.open { transform: translateY(0); }
      .detail-head { cursor: pointer; }
      .search { min-width: 180px; max-width: none; }
      .canvas-hint { display: none; }
    }
  </style>
</head>
<body>
  <main class="app">
    <header class="topbar">
      <div class="brand">
        <h1>AI Infra 面试就绪知识图谱</h1>
        <p>2027 校招 · LLM Serving / 推理平台 / AI Infra</p>
      </div>
      <div class="filters" aria-label="图谱筛选">
        <label class="search">
          <input class="control" id="topic-search" type="search" placeholder="搜索主题、知识点或源码…" autocomplete="off">
          <kbd>/</kbd>
        </label>
        <select class="control" id="priority-filter" aria-label="优先级">
          <option value="all">全部优先级</option><option value="P0">P0 核心</option><option value="P1">P1 深挖</option>
        </select>
        <select class="control" id="mastery-filter" aria-label="目标熟练度">
          <option value="all">全部熟练度</option>
          <option value="原理:L3">原理 L3</option><option value="源码:L3">源码 L3</option>
          <option value="手写:L3">手写 L3</option><option value="实验:L3">实验 L3</option>
          <option value="手写:L0">手写 L0</option><option value="实验:L0">实验 L0</option>
        </select>
        <select class="control" id="status-filter" aria-label="学习状态">
          <option value="all">全部状态</option><option value="from-zero">从零开始</option>
          <option value="foundation">已有基础</option><option value="pending">范围敲定，待训练</option>
        </select>
        <button class="icon-btn" id="expand-all" type="button">全部展开</button>
        <button class="icon-btn" id="collapse-all" type="button">全部收起</button>
        <span class="result-count" id="result-count"></span>
      </div>
    </header>
    <section class="workspace">
      <div class="canvas-wrap" id="canvas-wrap">
        <svg id="mindmap-svg" role="tree" aria-label="AI Infra 面试知识导图">
          <g id="viewport"></g>
        </svg>
        <div class="canvas-hint">滚轮缩放 · 拖动画布 · 点击节点查看详情</div>
        <div class="canvas-tools" aria-label="画布工具">
          <button class="icon-btn" id="zoom-out" type="button" title="缩小">−</button>
          <button class="icon-btn" id="fit-view" type="button" title="适应画布">适应</button>
          <button class="icon-btn" id="zoom-in" type="button" title="放大">＋</button>
        </div>
      </div>
      <aside class="detail" id="detail-panel" aria-live="polite">
        <div class="detail-head" id="detail-head">
          <div class="eyebrow">Knowledge Map</div>
          <h2 id="detail-title">使用说明</h2>
          <div class="badges" id="detail-badges"><span class="badge">13 个主题</span></div>
        </div>
        <div class="detail-body" id="detail-body"></div>
      </aside>
    </section>
  </main>
  <script id="topic-data" type="application/json">__TOPIC_DATA__</script>
  <script>
    "use strict";
    const topics = JSON.parse(document.getElementById("topic-data").textContent);
    const NS = "http://www.w3.org/2000/svg";
    const svg = document.getElementById("mindmap-svg");
    const viewport = document.getElementById("viewport");
    const panel = document.getElementById("detail-panel");
    const filters = {
      search: document.getElementById("topic-search"),
      priority: document.getElementById("priority-filter"),
      mastery: document.getElementById("mastery-filter"),
      status: document.getElementById("status-filter")
    };
    const groups = {
      P0: { label: "P0 · 面试启动门槛", color: "#d26444", soft: "#f5d8ca", expanded: true },
      P1: { label: "P1 · 深挖与防守", color: "#2f7c70", soft: "#d5ebe5", expanded: true }
    };
    let transform = { x: 40, y: 30, scale: 1 };
    let dragging = false;
    let dragOrigin = null;

    function el(name, attrs = {}, text = "") {
      const node = document.createElementNS(NS, name);
      Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
      if (text) node.textContent = text;
      return node;
    }

    function shortLines(text, limit = 17) {
      if (text.length <= limit) return [text];
      let first = text.slice(0, limit);
      const boundary = Math.max(first.lastIndexOf(" "), first.lastIndexOf("与"));
      if (boundary > 7) first = text.slice(0, boundary + 1);
      const rest = text.slice(first.length);
      return [first, rest.length > limit ? rest.slice(0, limit - 1) + "…" : rest];
    }

    function matches(topic) {
      const query = filters.search.value.trim().toLowerCase();
      if (query && !topic.search_text.includes(query)) return false;
      if (filters.priority.value !== "all" && topic.priority !== filters.priority.value) return false;
      if (filters.status.value !== "all" && topic.status_group !== filters.status.value) return false;
      if (filters.mastery.value !== "all") {
        const [dimension, level] = filters.mastery.value.split(":");
        if (topic.mastery[dimension] !== level) return false;
      }
      return true;
    }

    function edge(x1, y1, x2, y2, priority) {
      const bend = (x2 - x1) * .5;
      return el("path", {
        d: `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`,
        class: `edge ${priority.toLowerCase()}`
      });
    }

    function nodeBox({ x, y, width, height, fill, stroke, title, subtitle, kind, dataId, priority }) {
      const group = el("g", { class: `node ${kind}`, transform: `translate(${x},${y})`, tabindex: "0", role: "treeitem" });
      group.appendChild(el("rect", { width, height, rx: 13, fill, stroke, "stroke-width": 1.4 }));
      const lines = shortLines(title, kind === "topic" ? 18 : 20);
      lines.forEach((line, index) => {
        group.appendChild(el("text", { x: 14, y: 24 + index * 18, fill: "#17201d", "font-size": kind === "root" ? 16 : 14, "font-weight": "700" }, line));
      });
      if (subtitle) group.appendChild(el("text", { x: 14, y: height - 11, fill: "#68736e", "font-size": 10.5 }, subtitle));
      const activate = () => {
        if (kind === "group") {
          groups[priority].expanded = !groups[priority].expanded;
          renderMindmap();
        } else if (kind === "topic") {
          showTopic(dataId);
        } else {
          showOverview();
        }
      };
      group.addEventListener("click", (event) => { event.stopPropagation(); activate(); });
      group.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); activate(); }
      });
      return group;
    }

    function renderMindmap() {
      viewport.replaceChildren();
      const visible = topics.filter(matches);
      document.getElementById("result-count").textContent = `${visible.length} / ${topics.length} 个主题`;
      const byPriority = { P0: visible.filter(t => t.priority === "P0"), P1: visible.filter(t => t.priority === "P1") };
      const layout = [];
      let cursorY = 0;
      Object.keys(groups).forEach(priority => {
        const group = groups[priority];
        const children = group.expanded ? byPriority[priority] : [];
        const span = Math.max(84, children.length * 86);
        const center = cursorY + span / 2;
        layout.push({ priority, group, children, center });
        cursorY += span + 38;
      });
      const activeGroups = layout.filter(item => byPriority[item.priority].length || filters.priority.value === "all");
      const rootY = activeGroups.length ? activeGroups.reduce((sum, item) => sum + item.center, 0) / activeGroups.length : 100;
      const rootX = 20, groupX = 340, topicX = 680;
      viewport.appendChild(nodeBox({ x: rootX, y: rootY - 38, width: 244, height: 76, fill: "#fffdf7", stroke: "#274d62", title: "AI Infra 面试就绪", subtitle: "点击查看完成门槛", kind: "root" }));
      if (!visible.length) {
        viewport.appendChild(el("text", { x: 560, y: rootY, class: "empty-map" }, "没有匹配的主题，请调整筛选条件"));
      }
      layout.forEach(item => {
        const { priority, group, children, center } = item;
        if (!byPriority[priority].length && filters.priority.value !== "all") return;
        viewport.insertBefore(edge(rootX + 244, rootY, groupX, center, priority), viewport.firstChild);
        const arrow = group.expanded ? "−" : "+";
        viewport.appendChild(nodeBox({ x: groupX, y: center - 34, width: 230, height: 68, fill: group.soft, stroke: group.color, title: `${arrow} ${group.label}`, subtitle: `${byPriority[priority].length} 个主题`, kind: "group", priority }));
        children.forEach((topic, index) => {
          const childY = center - ((children.length - 1) * 86) / 2 + index * 86;
          viewport.insertBefore(edge(groupX + 230, center, topicX, childY, priority), viewport.firstChild);
          const defense = topic.has_p0_defense ? " · 含 P0 防守" : "";
          viewport.appendChild(nodeBox({ x: topicX, y: childY - 35, width: 286, height: 70, fill: "#fffefb", stroke: group.color, title: `${topic.id}｜${topic.title}`, subtitle: `${topic.mastery.原理}/${topic.mastery.源码}/${topic.mastery.手写}/${topic.mastery.实验}${defense}`, kind: "topic", dataId: topic.id, priority }));
        });
      });
      applyTransform();
    }

    function badges(topic) {
      const mastery = Object.entries(topic.mastery).map(([key, value]) => `<span class="badge">${key} ${value}</span>`).join("");
      const defense = topic.has_p0_defense ? '<span class="badge p0">面试启动前 P0 防守</span>' : "";
      return `<span class="badge ${topic.priority.toLowerCase()}">${topic.priority}</span>${defense}${mastery}`;
    }

    function showTopic(id) {
      const topic = topics.find(item => item.id === id);
      if (!topic) return;
      document.getElementById("detail-title").textContent = `${topic.id}｜${topic.title}`;
      document.getElementById("detail-badges").innerHTML = badges(topic);
      document.getElementById("detail-body").innerHTML = `
        <div class="summary-card"><strong>能力结果</strong>${topic.capability}</div>
        <div class="summary-card"><strong>当前状态</strong>${topic.state}</div>
        <div class="summary-card"><strong>范围边界</strong>${topic.boundary}</div>
        ${topic.detail_html}`;
      document.getElementById("detail-body").scrollTop = 0;
      panel.classList.add("open");
    }

    function showOverview() {
      const p0 = topics.filter(topic => topic.priority === "P0").length;
      const p1 = topics.filter(topic => topic.priority === "P1").length;
      document.getElementById("detail-title").textContent = "使用说明";
      document.getElementById("detail-badges").innerHTML = '<span class="badge">知识体系总览</span>';
      document.getElementById("detail-body").innerHTML = `
        <div class="overview">
          <p>点击主题节点查看完整知识列表；点击 P0/P1 分支可以展开或收起。搜索会覆盖主题摘要和详情正文。</p>
          <div class="overview-grid">
            <div class="metric"><b>${topics.length}</b><span>知识主题</span></div>
            <div class="metric"><b>${p0}</b><span>P0 核心节点</span></div>
            <div class="metric"><b>${p1}</b><span>P1 深挖节点</span></div>
            <div class="metric"><b>4D</b><span>原理 / 源码 / 手写 / 实验</span></div>
          </div>
          <div class="notice"><strong>证据边界</strong><br>“范围已敲定”不等于能力已经完成。项目表述继续使用 roadmap、shipped、experimentally validated、simulated 四种状态。</div>
          <div class="summary-card"><strong>ToolGap-KV 保持独立</strong>本图只展示通用 AI Infra 知识体系。ToolGap-KV 项目答辩树在 <code>docs/agent-kv/INTERVIEW_MAP.md</code> 独立维护，不合并进本图。</div>
          <div class="summary-card"><strong>内容更新方式</strong>修改索引或专题 Markdown 后，运行 <code>python3 scripts/build_interview_readiness_html.py</code> 重新生成本文件。</div>
        </div>`;
    }

    function applyTransform() {
      viewport.setAttribute("transform", `translate(${transform.x} ${transform.y}) scale(${transform.scale})`);
    }

    function zoomAt(factor, clientX = svg.clientWidth / 2, clientY = svg.clientHeight / 2) {
      const rect = svg.getBoundingClientRect();
      const x = clientX - rect.left, y = clientY - rect.top;
      const next = Math.min(2.2, Math.max(.42, transform.scale * factor));
      const ratio = next / transform.scale;
      transform.x = x - (x - transform.x) * ratio;
      transform.y = y - (y - transform.y) * ratio;
      transform.scale = next;
      applyTransform();
    }

    function fitView() {
      const bounds = viewport.getBBox();
      const width = Math.max(1, svg.clientWidth - 80), height = Math.max(1, svg.clientHeight - 80);
      const scale = Math.min(1.15, width / Math.max(bounds.width, 1), height / Math.max(bounds.height, 1));
      transform = { x: (svg.clientWidth - bounds.width * scale) / 2 - bounds.x * scale, y: (svg.clientHeight - bounds.height * scale) / 2 - bounds.y * scale, scale };
      applyTransform();
    }

    svg.addEventListener("wheel", event => { event.preventDefault(); zoomAt(event.deltaY < 0 ? 1.1 : .9, event.clientX, event.clientY); }, { passive: false });
    svg.addEventListener("pointerdown", event => {
      if (event.target.closest && event.target.closest(".node")) return;
      dragging = true; dragOrigin = { x: event.clientX - transform.x, y: event.clientY - transform.y };
      svg.classList.add("dragging"); svg.setPointerCapture(event.pointerId);
    });
    svg.addEventListener("pointermove", event => {
      if (!dragging) return;
      transform.x = event.clientX - dragOrigin.x; transform.y = event.clientY - dragOrigin.y; applyTransform();
    });
    svg.addEventListener("pointerup", event => { dragging = false; svg.classList.remove("dragging"); if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId); });
    svg.addEventListener("pointercancel", () => { dragging = false; svg.classList.remove("dragging"); });

    Object.values(filters).forEach(control => control.addEventListener("input", () => { renderMindmap(); requestAnimationFrame(fitView); }));
    document.getElementById("expand-all").addEventListener("click", () => { Object.values(groups).forEach(group => group.expanded = true); renderMindmap(); requestAnimationFrame(fitView); });
    document.getElementById("collapse-all").addEventListener("click", () => { Object.values(groups).forEach(group => group.expanded = false); renderMindmap(); requestAnimationFrame(fitView); });
    document.getElementById("zoom-in").addEventListener("click", () => zoomAt(1.15));
    document.getElementById("zoom-out").addEventListener("click", () => zoomAt(.85));
    document.getElementById("fit-view").addEventListener("click", fitView);
    document.getElementById("detail-head").addEventListener("click", () => { if (window.innerWidth <= 780) panel.classList.toggle("open"); });
    document.addEventListener("keydown", event => {
      if (event.key === "/" && document.activeElement !== filters.search) { event.preventDefault(); filters.search.focus(); }
      if (event.key === "Escape") { filters.search.value = ""; renderMindmap(); }
    });
    window.addEventListener("resize", () => requestAnimationFrame(fitView));

    showOverview();
    renderMindmap();
    requestAnimationFrame(fitView);
  </script>
</body>
</html>
'''


def build_html(topics: List[Dict[str, object]]) -> str:
    data = json.dumps(
        _serializable_topics(topics), ensure_ascii=False, indent=2
    ).replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__TOPIC_DATA__", data)


def generate(index_path: Path = DEFAULT_INDEX, output_path: Path = DEFAULT_OUTPUT) -> int:
    topics = parse_topics(index_path)
    document = build_html(topics)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return len(topics)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    count = generate(args.index, args.output)
    print("generated {} topics: {}".format(count, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
