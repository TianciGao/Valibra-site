#!/usr/bin/env python3
"""Build only allowlisted assets and aligned Chinese and Russian full reports.

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
from notion_report import render_chinese, render_russian

ROOT = Path(__file__).resolve().parents[1]
RELEASE = Path("site/data/core_results.json")
ASSETS = ("site.css", "site.js", "framework-zh.svg", "framework-ru.svg",
          "notion-report.css", "notion-report.js", "notion-zh-1.svg",
          "notion-zh-2.png", "notion-zh-3.png", "notion-zh-4.png", "notion-zh-5.png",
          "notion-ru-1.svg", "notion-ru-2.svg", "notion-ru-3.svg", "notion-ru-4.svg", "notion-ru-5.svg")
DOWNLOADS = ("glm52_full600_baseline_score_table.xlsx", "current_candidate_full600_baseline_format.xlsx")
DATA_KEYS = {
    "schema_version", "evaluation", "model", "execution_profile", "scores",
    "paired_changes", "status_transitions", "reported_token_usage",
    "mechanism_counts", "limitations",
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
    if language == "ru":
        return render_russian()
    raise ValueError(f"Unsupported report language: {language}")


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
