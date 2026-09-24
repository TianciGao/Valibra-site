#!/usr/bin/env python3
"""Build only allowlisted website assets, a Chinese Notion report and Russian summary.

The explicitly imported Chinese page is the source of its full report text.
Never walks or imports the private research repository or linked evidence files.
"""
from __future__ import annotations

import argparse
import html
import json
from hashlib import sha256
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notion_report import render_chinese

ROOT = Path(__file__).resolve().parents[1]
RELEASE = Path("site/data/core_results.json")
ASSETS = ("site.css", "site.js", "framework-zh.svg", "framework-ru.svg",
          "notion-report.css", "notion-report.js", "notion-zh-1.svg",
          "notion-zh-2.png", "notion-zh-3.png", "notion-zh-4.png", "notion-zh-5.png")
DOWNLOADS = ("glm52_full600_baseline_score_table.xlsx", "current_candidate_full600_baseline_format.xlsx")
DATA_KEYS = {
    "schema_version", "evaluation", "model", "execution_profile", "scores",
    "paired_changes", "status_transitions", "reported_token_usage",
    "mechanism_counts", "limitations",
}
LANG = {
    "zh": {
        "html_lang": "zh-CN", "title": "Valibra · 四维框架设计与评测分析",
        "heading": "先整理信息，再编写 SQL。",
        "lead": "BIRD-Interact 上的四维信息整理、受控修订与独立补救：一次关于流程可靠性、任务表现和成本的阶段性研究。",
        "eyebrow": "RESEARCH REPORT / 2026.09", "nav_label": "章节导航",
        "nav": ["研究概览", "框架设计", "实际案例", "成绩与成本", "限制与方向", "版本与资料"],
        "sidebar_note": "公开摘要 · 组内证据不随站点发布。\n\n评测：600 题 / a-interact\n主模型：GLM-5.2",
        "skip": "跳转到正文", "repo": "网站源码 ↗",
        "footer": "Valibra / 阶段性研究报告。网站仅发布经过审阅的静态内容；Notion 修改不会自动同步。",
        "metric_labels": ["P1 通过", "两阶段全通过", "总 Reward", "总 token 变化"],
        "metric_notes": ["相对基线 +6 题", "相对基线 −4 题", "相对基线 +3.0", "包含独立 Grounding"],
        "result_headers": ["指标", "基线", "Valibra", "变化"],
        "result_labels": ["P1 通过", "两阶段全通过", "Reward", "输入 token", "输出 token", "总 token"],
        "mechanism_headers": ["路径", "P1 通过", "两阶段全通过"],
        "mechanism_labels": ["主流程", "补救新增", "最终合计"],
        "usage_headers": ["部分", "输入 token", "输出 token", "总 token"],
        "usage_labels": ["独立 Grounding", "Main 与补救", "用户模拟器", "合计"],
    },
    "ru": {
        "html_lang": "ru", "title": "Valibra · Архитектура и результаты исследования",
        "heading": "Сначала информация. Затем SQL.",
        "lead": "Четыре компонента информации, управляемый пересмотр и независимое восстановление в BIRD-Interact: промежуточное исследование надёжности процесса, результатов и затрат.",
        "eyebrow": "ИССЛЕДОВАТЕЛЬСКИЙ ОТЧЁТ / 2026.09", "nav_label": "Содержание",
        "nav": ["Обзор", "Архитектура", "Примеры", "Результаты и затраты", "Ограничения", "Версия и материалы"],
        "sidebar_note": "Публичное резюме без внутренних журналов.\n\n600 задач / a-interact\nОсновная модель: GLM-5.2",
        "skip": "Перейти к содержимому", "repo": "Код сайта ↗",
        "footer": "Valibra / промежуточный исследовательский отчёт. Публикуются только проверенные статические материалы; изменения Notion не синхронизируются автоматически.",
        "metric_labels": ["P1 пройден", "Оба этапа пройдены", "Суммарный Reward", "Изменение токенов"],
        "metric_notes": ["+6 к базовой системе", "−4 к базовой системе", "+3.0 к базовой системе", "Включая Grounding"],
        "result_headers": ["Показатель", "Базовая", "Valibra", "Изменение"],
        "result_labels": ["P1 пройден", "Оба этапа пройдены", "Reward", "Входные токены", "Выходные токены", "Всего токенов"],
        "mechanism_headers": ["Путь", "P1 пройден", "Оба этапа"],
        "mechanism_labels": ["Основной процесс", "Добавлено восстановлением", "Итого"],
        "usage_headers": ["Компонент", "Вход", "Выход", "Всего"],
        "usage_labels": ["Независимый Grounding", "Main и восстановление", "Симулятор пользователя", "Итого"],
    },
}


def table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th scope=\"col\">{html.escape(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(
        f'<td{chr(32) + "class=" + chr(34) + "number" + chr(34) if i else ""}>{html.escape(str(x))}</td>'
        for i, x in enumerate(row)) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def load_data(root: Path = ROOT) -> dict:
    data = json.loads((root / RELEASE).read_text(encoding="utf-8"))
    if set(data) != DATA_KEYS:
        raise ValueError("Release summary schema changed; review public-data scope first")
    b, c = data["scores"]["baseline"], data["scores"]["candidate"]
    for score in (b, c):
        if score["tasks"] != 600 or not 0 <= score["full_pass"] <= score["p1_pass"] <= 600:
            raise ValueError("Invalid evaluation score")
        if abs(score["reward"] - (0.7 * score["p1_pass"] + 0.3 * score["full_pass"])) > 1e-6:
            raise ValueError("Reward does not match P1 / Full")
    for usage in data["reported_token_usage"].values():
        if usage["input_tokens"] + usage["output_tokens"] != usage["total_tokens"]:
            raise ValueError("Token totals do not reconcile")
    return data


def render(language: str, data: dict) -> str:
    if language == "zh":
        return render_chinese()
    ui = LANG[language]
    prefix = "../" if language == "ru" else ""
    b, c = data["scores"]["baseline"], data["scores"]["candidate"]
    usage = data["reported_token_usage"]
    fmt = lambda n: f"{n:,}"
    percent = lambda x, y: f"{(y / x - 1) * 100:+.2f}%"
    values = [f'{c["p1_pass"]} / 600', f'{c["full_pass"]} / 600', str(c["reward"]),
              percent(usage["baseline_all"]["total_tokens"], usage["candidate_all"]["total_tokens"])]
    metrics = "".join(f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-note{ " caution" if i in (1, 3) else ""}">{note}</div></div>'
                      for i, (label, value, note) in enumerate(zip(ui["metric_labels"], values, ui["metric_notes"])))
    results = []
    for i, key in enumerate(("p1_pass", "full_pass", "reward")):
        x, y = b[key], c[key]
        results.append([ui["result_labels"][i], f"{x} / 600" if i < 2 else str(x),
                        f"{y} / 600" if i < 2 else str(y), f"{y-x:+g}"])
    for i, key in enumerate(("input_tokens", "output_tokens", "total_tokens"), 3):
        x, y = usage["baseline_all"][key], usage["candidate_all"][key]
        results.append([ui["result_labels"][i], fmt(x), fmt(y), percent(x, y)])
    m = data["mechanism_counts"]
    mechanism = [[ui["mechanism_labels"][0], m["primary_p1_pass"], m["primary_full_pass"]],
                 [ui["mechanism_labels"][1], m["fallback_new_p1"], m["fallback_new_full"]],
                 [ui["mechanism_labels"][2], c["p1_pass"], c["full_pass"]]]
    usage_rows = [[label] + [fmt(usage[key][n]) for n in ("input_tokens", "output_tokens", "total_tokens")]
                  for label, key in zip(ui["usage_labels"], ("candidate_grounding", "candidate_main_and_fallback", "candidate_user_simulator", "candidate_all"))]
    body = (ROOT / "site/content" / f"{language}.html").read_text(encoding="utf-8")
    for key, value in {"ROOT": prefix, "RESULTS_TABLE": table(ui["result_headers"], results),
                       "MECHANISM_TABLE": table(ui["mechanism_headers"], mechanism),
                       "USAGE_TABLE": table(ui["usage_headers"], usage_rows)}.items():
        body = body.replace("{{" + key + "}}", value)
    if "{{" in body:
        raise ValueError("Unresolved template marker")
    ids = ("overview", "architecture", "cases", "results", "limitations", "resources")
    nav = "".join(f'<a href="#{id_}">{label}</a>' for id_, label in zip(ids, ui["nav"]))
    sidebar_note = html.escape(ui["sidebar_note"]).replace("\n", "<br>")
    language_links = ''.join(f'<a href="{href}" lang="{lang}" hreflang="{lang}"{ " aria-current=\"page\"" if current else ""}>{label}</a>'
                             for href, lang, label, current in [(prefix + "index.html", "zh-CN", "中文", language == "zh"), (prefix + "ru/index.html", "ru", "Русский", language == "ru")])
    return f'''<!doctype html>
<html lang="{ui['html_lang']}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{html.escape(ui['lead'], quote=True)}"><meta name="referrer" content="strict-origin-when-cross-origin">
<title>{ui['title']}</title><link rel="stylesheet" href="{prefix}assets/site.css">
<link rel="alternate" hreflang="zh-CN" href="{prefix}index.html"><link rel="alternate" hreflang="ru" href="{prefix}ru/index.html">
<script src="{prefix}assets/site.js" defer></script></head><body>
<a class="skip" href="#main">{ui['skip']}</a>
<header class="topbar"><div class="topbar-inner"><a class="brand" href="{prefix}index.html">Valibra<span>.</span></a><div class="toplinks"><a class="repo-link" href="https://github.com/TianciGao/Valibra-site">{ui['repo']}</a><nav class="language" aria-label="Language / Язык">{language_links}</nav></div></div></header>
<div class="layout"><aside class="sidebar"><div class="overline">{ui['nav_label']}</div><nav aria-label="{ui['nav_label']}">{nav}</nav><div class="sidebar-note">{sidebar_note}</div></aside>
<main id="main"><div class="hero"><div class="eyebrow">{ui['eyebrow']}</div><h1>{ui['heading']}</h1><p class="lead">{ui['lead']}</p><div class="tags"><span class="tag">BIRD-INTERACT</span><span class="tag">SQL GROUNDING V1</span><span class="tag">FULL600 · GLM-5.2</span></div></div>
<div class="metrics">{metrics}</div>{body}<footer class="footer">{ui['footer']}</footer></main></div></body></html>
'''


def build(output: Path) -> list[Path]:
    data = load_data()
    metadata = json.loads((ROOT / "site/content/zh.notion.json").read_text(encoding="utf-8"))
    downloads = {}
    for name in DOWNLOADS:
        item = next(entry for entry in metadata["attachments"] if entry["name"] == name)
        payload = (ROOT / "site/downloads" / name).read_bytes()
        if sha256(payload).hexdigest() != item["sha256"] or len(payload) != item["bytes"]:
            raise ValueError(f"Attachment differs from reviewed desktop original: {name}")
        downloads[name] = payload
    if output.is_symlink():
        raise ValueError("Output directory must not be a symlink")
    output = output.resolve()
    # Existing unexpected files are never silently uploaded or recursively removed.
    allowed = {"index.html", "ru/index.html", ".nojekyll", "assets/core_results.json"}
    allowed.update(f"assets/{name}" for name in ASSETS)
    allowed.update(f"downloads/{name}" for name in DOWNLOADS)
    if output.exists():
        for path in output.rglob("*"):
            if path.is_symlink() or (path.is_file() and path.relative_to(output).as_posix() not in allowed):
                raise ValueError(f"Unexpected output path; review before publishing: {path}")
    for rel in allowed:
        (output / rel).parent.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(render("zh", data), encoding="utf-8")
    (output / "ru/index.html").write_text(render("ru", data), encoding="utf-8")
    (output / ".nojekyll").write_text("", encoding="utf-8")
    (output / "assets/core_results.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in ASSETS:
        (output / "assets" / name).write_bytes((ROOT / "site/assets" / name).read_bytes())
    for name, payload in downloads.items():
        (output / "downloads" / name).write_bytes(payload)
    return [output / rel for rel in sorted(allowed)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/pages")
    args = parser.parse_args()
    paths = build(args.output)
    print(f"Built {len(paths)} allowlisted files in {args.output}")
