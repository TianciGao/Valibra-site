"""Render the supported Notion export blocks without summarising their contents.

The Markdown snapshot is the editorial source, not a prompt for rewriting.
User-confirmed object mappings resolve imported links without rewriting the snapshot.
Any still-unsupported external objects stay visible as labelled source links.
Code-fence contents are never passed through Markdown or whitespace cleanup.
"""
from html import escape
from hashlib import sha256
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
    if local and re.fullmatch(r"assets/notion-(?:zh-[1-5]\.(?:svg|png)|ru-[1-5]\.svg)", url):
        return url
    if local and url in (
        "downloads/glm52_full600_baseline_score_table.xlsx",
        "downloads/current_candidate_full600_baseline_format.xlsx",
    ):
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
    def __init__(self, source, metadata=None, language="zh"):
        if language not in ("zh", "ru"):
            raise ValueError("Unsupported report language")
        self.language = language
        self.prefix = "../" if language == "ru" else ""
        self.source = source
        self.metadata = metadata or {}
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
                url = self.prefix + safe_url(image[2], local=True)
                if image[2] == "assets/notion-ru-1.svg":
                    # Refresh cached diagrams whenever the editable SVG changes.
                    revision = sha256((ROOT / "site" / image[2]).read_bytes()).hexdigest()[:12]
                    url += f"?v={revision}"
                caption = f'<figcaption>{rich(image[1])}</figcaption>' if image[1] else ""
                output.append(f'<figure><a href="{url}" target="_blank" rel="noopener"><img src="{url}" alt="{escape(image[1], quote=True)}" loading="lazy"></a>{caption}</figure>')
                continue
            page = re.fullmatch(r'<page url="([^"]*)">(.*?)</page>', line)
            if page:
                # Keep source-page references in the archival snapshot only.
                # The public header already provides the language switch.
                continue
            attachment = re.fullmatch(r'<file src="([^"]*)">(.*?)</file>', line)
            if attachment:
                self.counts["attachments"] += 1
                resolved = next((item for item in self.metadata.get("attachments", [])
                                 if item["url"] == attachment[1] and item["name"] == attachment[2]
                                 and item.get("status") == "resolved_from_user_desktop"), None)
                if resolved:
                    url = self.prefix + safe_url(resolved["local_url"], local=True)
                    download_label = "Скачать Excel" if self.language == "ru" else "下载 Excel"
                    note = f'<small>{escape(resolved["note"])}</small>' if resolved.get("note") else ""
                    output.append(f'<div class="source-resource attachment-download"><a href="{url}" download="{escape(resolved["name"], quote=True)}">{escape(resolved["title"])} · {download_label} ↓</a><small>{escape(resolved["name"])}</small>{note}</div>')
                else:
                    output.append(f'<div class="source-unavailable"><a href="{safe_url(attachment[1])}">{escape(attachment[2])} ↗</a><small>Notion 附件入口；当前连接无法下载该附件，查看可能需要原页面权限。</small></div>')
                continue
            if line.startswith("<unknown "):
                self.counts["unknown"] += 1
                source_url = attrs(line)["url"]
                block_id = urlsplit(source_url).fragment.replace("-", "")
                resolved = self.metadata.get("resolved_embeds", {}).get(block_id)
                if resolved:
                    output.append(f'<div class="source-resource repository-link"><a href="{safe_url(resolved["url"])}">{escape(resolved["title"])} ↗</a><small>{escape(resolved["note"])}</small></div>')
                else:
                    output.append(f'<div class="source-unavailable"><a href="{safe_url(source_url)}">在 Notion 查看此嵌入块 ↗</a><small>此对象不受当前连接支持，未转换为网页内容；原位置与入口已保留。</small></div>')
                continue
            heading = re.fullmatch(r"(#{1,4}) (.*)", line)
            if heading:
                self.heading_count += 1
                level = len(heading[1])
                content = heading[2]
                label, value = self.record("heading", content)
                identifier = {"摘要": "overview", "一、框架设计与实现": "architecture", "二、实际案例分析": "cases", "三、600 题成绩与成本": "results",
                              "Аннотация": "overview", "I. Проектирование и реализация системы": "architecture", "II. Анализ реальных примеров": "cases", "III. Результаты и затраты на 600 задачах": "results"}.get(content, f"heading-{self.heading_count}")
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
    metadata = json.loads((ROOT / "site/content/zh.notion.json").read_text(encoding="utf-8"))
    report = Report(source, metadata)
    body = report.render()
    if 'class="source-unavailable"' in body:
        raise ValueError("Chinese page still has unresolved source objects")
    nav = "".join(f'<a href="#{identifier}">{escape(label)}</a>' for identifier, label in report.nav)
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="BIRD-Interact 四维框架设计与评测分析。">
<meta name="referrer" content="strict-origin-when-cross-origin"><title>BIRD-Interact 四维框架设计与评测分析 · Valibra</title>
<link rel="stylesheet" href="assets/site.css"><link rel="stylesheet" href="assets/notion-report.css">
<script src="assets/notion-report.js" defer></script></head><body class="notion-page">
<a class="skip" href="#main">跳转到正文</a>
<header class="topbar"><div class="topbar-inner"><a class="brand" href="index.html">Valibra<span>.</span></a><div class="toplinks"><nav class="language" aria-label="语言切换"><a href="index.html" lang="zh-CN" aria-current="page">中文</a><a href="ru/index.html" lang="ru">Русский</a></nav></div></div></header>
<div class="layout"><aside class="sidebar"><div class="overline">章节导航</div><nav aria-label="章节导航">{nav}</nav></aside>
<main id="main">
<div class="report-controls"><button class="subtle-button" data-report-toggle hidden>展开全部折叠内容</button></div>
<article class="notion-report">{body}</article>
</main></div></body></html>
'''


def russian_metadata():
    """Fail closed if the Chinese editorial source changed since translation review."""
    directory = ROOT / "site/content"
    translation = json.loads((directory / "ru.notion.json").read_text(encoding="utf-8"))
    for filename, key in (("zh.notion.md", "source_sha256"),
                          ("zh.notion.json", "source_metadata_sha256"),
                          ("ru.notion.md", "translation_sha256")):
        if sha256((directory / filename).read_bytes()).hexdigest() != translation[key]:
            raise ValueError(f"Review Russian translation alignment: {filename}")
    for name, digest in translation["image_sources"].items():
        if sha256((ROOT / "site/assets" / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Review translated figure alignment: {name}")
    metadata = json.loads((directory / "zh.notion.json").read_text(encoding="utf-8"))
    for item in metadata["resolved_embeds"].values():
        item.update(title=translation["repository_title"], note=translation["repository_note"])
    for item in metadata["attachments"]:
        item.update(translation["attachments"][item["name"]])
    return metadata


def render_russian():
    metadata = russian_metadata()
    source = (ROOT / "site/content/ru.notion.md").read_text(encoding="utf-8")
    report = Report(source, metadata, language="ru")
    body = report.render()
    if 'class="source-unavailable"' in body:
        raise ValueError("Russian page still has unresolved source objects")
    nav = "".join(f'<a href="#{identifier}">{escape(label)}</a>' for identifier, label in report.nav)
    return f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Полный русский перевод отчёта BIRD-Interact: четырёхкомпонентная система, реальные примеры и результаты оценки.">
<meta name="referrer" content="strict-origin-when-cross-origin"><title>BIRD-Interact: проектирование четырёхкомпонентной системы и анализ оценки · Valibra</title>
<link rel="stylesheet" href="../assets/site.css"><link rel="stylesheet" href="../assets/notion-report.css">
<script src="../assets/notion-report.js" defer></script></head><body class="notion-page">
<a class="skip" href="#main">Перейти к содержимому</a>
<header class="topbar"><div class="topbar-inner"><a class="brand" href="index.html">Valibra<span>.</span></a><div class="toplinks"><nav class="language" aria-label="Выбор языка"><a href="../index.html" lang="zh-CN">中文</a><a href="index.html" lang="ru" aria-current="page">Русский</a></nav></div></div></header>
<div class="layout"><aside class="sidebar"><div class="overline">Содержание</div><nav aria-label="Содержание">{nav}</nav></aside>
<main id="main">
<div class="report-controls"><button class="subtle-button" data-report-toggle hidden>Развернуть все блоки</button></div>
<article class="notion-report">{body}</article>
</main></div></body></html>
'''
