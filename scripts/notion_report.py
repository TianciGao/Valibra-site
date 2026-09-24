"""Render the supported Notion export blocks without summarising their contents.

The Markdown snapshot is the editorial source, not a prompt for rewriting.
Unsupported external objects stay visible as explicitly labelled source links.
Code-fence contents are never passed through Markdown or whitespace cleanup.
"""
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import json
import re
from urllib.parse import urlsplit

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
COLORS = {name for base in ("gray", "brown", "orange", "yellow", "green", "blue", "purple", "pink", "red")
          for name in (base, base + "_bg")}


def attrs(text):
    return dict(re.findall(r'([\w-]+)="([^"]*)"', text))


def color_class(attributes):
    color = attributes.get("color")
    return " notion-" + color if color in COLORS else ""


def safe_url(url, local=False):
    parts = urlsplit(url)
    if parts.scheme in ("https", "http") and parts.netloc:
        return escape(url, quote=True)
    if local and re.fullmatch(r"assets/notion-zh-[1-5]\.(svg|png)", url):
        return url
    raise ValueError("Unsupported URL scheme or image path")


def inline_html(tokens, idx, options, env):
    raw = tokens[idx].content
    if raw in ("</span>", "<br>", "<br/>", "<br />"):
        return raw
    if re.fullmatch(r'<span(?:\s+(?:color|underline)="[\w]+")*\s*>', raw):
        attributes = attrs(raw)
        classes = color_class(attributes).strip()
        if attributes.get("underline") == "true":
            classes += " notion-underline"
        return f'<span class="{classes.strip()}">'
    # Never let an imported rich-text fragment introduce executable HTML.
    return escape(raw)


MD = MarkdownIt("commonmark", {"html": True, "typographer": False}).enable("strikethrough")
MD.renderer.rules["html_inline"] = inline_html


def rich(text):
    return MD.renderInline(text)


class Text(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.feed(source)

    def handle_data(self, data):
        self.parts.append(data)


def plain(source):
    return "".join(Text(source).parts)


class Report:
    def __init__(self, source):
        self.source = source
        self.lines = source.splitlines()
        self.records = []
        self.nav = []
        self.counts = {name: 0 for name in ("details", "tables", "cells", "code", "images", "unknown", "attachments")}
        self.heading_count = 0
        self.top_detail_count = 0

    def record(self, kind, source, literal=False):
        value = escape(source) if literal else rich(source)
        index = len(self.records)
        self.records.append({"kind": kind, "text": source if literal else plain(value)})
        return f'data-source-block="{index}"', value

    def table(self, source):
        self.counts["tables"] += 1
        header = attrs(source.splitlines()[0]).get("header-row") == "true"
        rows = []
        for i, row in enumerate(re.findall(r"<tr[^>]*>(.*?)</tr>", source, re.S)):
            cells = []
            for match in re.finditer(r"<td([^>]*)>(.*?)</td>", row, re.S):
                self.counts["cells"] += 1
                label, value = self.record("cell", match[2])
                tag = "th" if header and i == 0 else "td"
                scope = ' scope="col"' if tag == "th" else ""
                cells.append(f'<{tag} {label}{scope} class="{color_class(attrs(match[1])).strip()}">{value}</{tag}>')
            rows.append("<tr>" + "".join(cells) + "</tr>")
        if not rows:
            raise ValueError("Empty or unsupported table")
        head = "<thead>" + rows.pop(0) + "</thead>" if header else ""
        return '<div class="table-wrap"><table>' + head + '<tbody>' + "".join(rows) + '</tbody></table></div>'

    def render(self):
        output, stack = [], []
        i = 0
        while i < len(self.lines):
            line = self.lines[i].lstrip("\t")
            i += 1
            if not line.strip():
                continue
            fence = re.fullmatch(r"```(.*)", line)
            if fence:
                code = []
                while i < len(self.lines) and self.lines[i].lstrip("\t") != "```":
                    code.append(self.lines[i])
                    i += 1
                if i == len(self.lines):
                    raise ValueError("Unclosed code fence")
                i += 1
                self.counts["code"] += 1
                label, value = self.record("code", "\n".join(code) + ("\n" if code else ""), literal=True)
                language = re.sub(r"[^a-z0-9_-]", "-", fence[1].lower())
                output.append(f'<pre {label}><code class="language-{language}">{value}</code></pre>')
                continue
            if line.startswith("<table ") or line == "<table>":
                table = [line]
                while i < len(self.lines) and self.lines[i].lstrip("\t") != "</table>":
                    table.append(self.lines[i].lstrip("\t"))
                    i += 1
                if i == len(self.lines):
                    raise ValueError("Unclosed table")
                i += 1
                table.append("</table>")
                output.append(self.table("\n".join(table)))
                continue
            if re.fullmatch(r'<details(?: color="[\w]+")?>', line):
                self.counts["details"] += 1
                top = "details" not in stack
                identifier = f'detail-{self.counts["details"]}'
                if top:
                    self.top_detail_count += 1
                    identifier = ("case-success", "case-recovery", "case-failure", "evidence")[self.top_detail_count - 1]
                output.append(f'<details class="notion-toggle{ " case" if top else ""}{color_class(attrs(line))}" id="{identifier}">')
                stack.append("details")
                continue
            if line.startswith("<summary>") and line.endswith("</summary>"):
                content = line[len("<summary>"):-len("</summary>")]
                label, value = self.record("summary", content)
                output.append(f'<summary {label}>{value}</summary><div class="toggle-body">')
                if self.top_detail_count == 4 and stack.count("details") == 1:
                    self.nav.append(("evidence", plain(value)))
                continue
            if line.startswith("<callout"):
                attributes = attrs(line)
                icon = escape(attributes.get("icon", ""))
                output.append(f'<aside class="notion-callout{color_class(attributes)}"><span class="callout-icon" aria-hidden="true">{icon}</span><div>')
                stack.append("callout")
                continue
            if line in ("</details>", "</callout>"):
                tag = line[2:-1]
                if not stack or stack.pop() != tag:
                    raise ValueError("Unbalanced Notion containers")
                output.append("</div></details>" if tag == "details" else "</div></aside>")
                continue
            image = re.fullmatch(r"!\[([^\]]*)\]\((.*?)\)", line)
            if image:
                self.counts["images"] += 1
                url = safe_url(image[2], local=True)
                caption = f'<figcaption>{rich(image[1])}</figcaption>' if image[1] else ""
                output.append(f'<figure><a href="{url}" target="_blank" rel="noopener"><img src="{url}" alt="{escape(image[1], quote=True)}" loading="lazy"></a>{caption}</figure>')
                continue
            page = re.fullmatch(r'<page url="([^"]*)">(.*?)</page>', line)
            if page:
                label, value = self.record("page", page[2])
                output.append(f'<p class="notion-page-link"><a {label} href="{safe_url(page[1])}">{value}</a></p>')
                continue
            attachment = re.fullmatch(r'<file src="([^"]*)">(.*?)</file>', line)
            if attachment:
                self.counts["attachments"] += 1
                output.append(f'<div class="source-unavailable"><a href="{safe_url(attachment[1])}">{escape(attachment[2])} ↗</a><small>Notion 附件入口；当前连接无法下载该附件，查看可能需要原页面权限。</small></div>')
                continue
            if line.startswith("<unknown "):
                self.counts["unknown"] += 1
                output.append(f'<div class="source-unavailable"><a href="{safe_url(attrs(line)["url"])}">在 Notion 查看此嵌入块 ↗</a><small>此对象不受当前连接支持，未转换为网页内容；原位置与入口已保留。</small></div>')
                continue
            heading = re.fullmatch(r"(#{1,4}) (.*)", line)
            if heading:
                self.heading_count += 1
                level = len(heading[1])
                content = heading[2]
                label, value = self.record("heading", content)
                identifier = {"摘要": "overview", "一、框架设计与实现": "architecture", "二、实际案例分析": "cases", "三、600 题成绩与成本": "results"}.get(content, f"heading-{self.heading_count}")
                if level == 2:
                    self.nav.append((identifier, plain(value)))
                output.append(f'<h{level} id="{identifier}" {label}>{value}</h{level}>')
                continue
            if line.startswith("- ") or re.match(r"\d+\. ", line):
                numbered = not line.startswith("- ")
                pattern = r"\d+\. (.*)" if numbered else r"- (.*)"
                tag = "ol" if numbered else "ul"
                start = f' start="{int(line.split(".", 1)[0])}"' if numbered else ""
                items = []
                while True:
                    content = re.fullmatch(pattern, line)[1]
                    label, value = self.record("list-item", content)
                    items.append(f'<li {label}>{value}</li>')
                    if i == len(self.lines) or not re.fullmatch(pattern, self.lines[i].lstrip("\t")):
                        break
                    line = self.lines[i].lstrip("\t")
                    i += 1
                output.append(f'<{tag}{start}>' + "".join(items) + f'</{tag}>')
                continue
            if line.startswith("> "):
                label, value = self.record("quote", line[2:])
                output.append(f'<blockquote {label}>{value}</blockquote>')
                continue
            if line == "---":
                output.append("<hr>")
                continue
            if line.startswith("<") and not line.startswith("<span"):
                raise ValueError(f"Unsupported Notion block near source line {i}")
            label, value = self.record("paragraph", line)
            output.append(f'<p {label}>{value}</p>')
        if stack:
            raise ValueError("Unclosed Notion container")
        return "\n".join(output)


def render_chinese():
    source = (ROOT / "site/content/zh.notion.md").read_text(encoding="utf-8")
    report = Report(source)
    body = report.render()
    metadata = json.loads((ROOT / "site/content/zh.notion.json").read_text(encoding="utf-8"))
    nav = "".join(f'<a href="#{identifier}">{escape(label)}</a>' for identifier, label in report.nav)
    source_url = safe_url(metadata["source_url"])
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="BIRD-Interact 四维框架设计与评测分析，中文 Notion 原文迁移版。">
<meta name="referrer" content="strict-origin-when-cross-origin"><title>BIRD-Interact 四维框架设计与评测分析 · Valibra</title>
<link rel="stylesheet" href="assets/site.css"><link rel="stylesheet" href="assets/notion-report.css">
<script src="assets/notion-report.js" defer></script></head><body class="notion-page">
<a class="skip" href="#main">跳转到正文</a>
<header class="topbar"><div class="topbar-inner"><a class="brand" href="index.html">Valibra<span>.</span></a><div class="toplinks"><a class="repo-link" href="{source_url}">Notion 原文 ↗</a><nav class="language" aria-label="语言切换"><a href="index.html" lang="zh-CN" aria-current="page">中文</a><a href="ru/index.html" lang="ru" title="俄语页暂为此前的摘要版">Русский</a></nav></div></div></header>
<div class="layout"><aside class="sidebar"><div class="overline">章节导航</div><nav aria-label="章节导航">{nav}</nav><div class="sidebar-note">中文：Notion 原文迁移<br>俄语：此前摘要版<br><br>本次读取：{escape(metadata['fetched_on'])}<br>不自动同步后续修改。</div></aside>
<main id="main"><div class="migration-note"><strong>迁移说明（非原文）</strong>：以下按 Notion 当前可读取内容保留原文与结构。1 个嵌入对象、2 个 Excel 附件暂保留原入口；接口将此页面标记为不完整，不能据此宣称所有对象均已迁移。正文中的本地路径仅作原文引用，不代表对应文件已公开。</div>
<div class="report-controls"><button class="subtle-button" data-report-toggle hidden>展开全部折叠内容</button></div>
<article class="notion-report">{body}</article>
<footer class="footer">网站排版与正文分开维护。<a href="{source_url}">查看 Notion 原文</a>；本站未改动 Notion 页面。俄语站尚未同步为原文版。</footer></main></div></body></html>
'''
