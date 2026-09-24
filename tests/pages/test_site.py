"""Offline checks for explicit publishing scope and faithful report conversion."""
import importlib.util
import base64
from hashlib import sha256
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile
import unittest
import zipfile
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("build_pages", ROOT / "scripts/build_pages.py")
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids, self.links, self.text = [], [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        for key in ("href", "src"):
            if key in attrs:
                self.links.append(attrs[key])

    def handle_data(self, text):
        self.text.append(text)


class PublicSiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / "Valibra-site"
        self.files = site.build(self.output)

    def test_exact_publish_allowlist(self):
        expected = {"index.html", "ru/index.html", ".nojekyll", "assets/core_results.json"}
        expected.update("assets/" + name for name in site.ASSETS)
        expected.update("downloads/" + name for name in site.DOWNLOADS)
        actual = {p.relative_to(self.output).as_posix() for p in self.output.rglob("*") if p.is_file()}
        self.assertEqual(actual, expected)
        self.assertEqual(len(self.files), 22)

    def test_local_links_and_anchors_under_project_prefix(self):
        for page in (self.output / "index.html", self.output / "ru/index.html"):
            document = Document(page.read_text())
            self.assertEqual(len(document.ids), len(set(document.ids)))
            for link in document.links:
                parsed = urlsplit(link)
                if parsed.scheme:
                    self.assertIn(parsed.scheme, ("https", "http"))
                    continue
                self.assertFalse(parsed.netloc)
                self.assertFalse(parsed.path.startswith("/"), link)
                target = (page.parent / unquote(parsed.path)).resolve() if parsed.path else page
                self.assertTrue(target.is_relative_to(self.output), link)
                self.assertTrue(target.is_file(), link)
                if parsed.fragment:
                    self.assertIn(unquote(parsed.fragment), Document(target.read_text()).ids)

    def test_bilingual_sections_and_no_untranslated_russian_prose(self):
        for language, path in (("zh", "index.html"), ("ru", "ru/index.html")):
            text = (self.output / path).read_text()
            document = Document(text)
            sections = ("overview", "architecture", "cases", "results", "evidence")
            for section in sections:
                self.assertIn(section, document.ids)
            self.assertEqual(text.count('<details '), 50)
            self.assertNotIn("{{", text)
            self.assertIn(f'assets/notion-{language}-1.svg', text)
            if language == "ru":
                # Original file paths are identifiers, not untranslated prose.
                visible = "".join(document.text)
                for label in ("中文", "当前", "600题对照_含完整Token审计.xlsx"):
                    visible = visible.replace(label, "")
                self.assertFalse(re.search(r"[\u4e00-\u9fff]", visible))

    def test_aggregate_reconciliation(self):
        data = site.load_data()
        self.assertEqual(json.loads((self.output / "assets/core_results.json").read_text()), data)
        usage = data["reported_token_usage"]
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            self.assertEqual(usage["candidate_all"][field], sum(usage[key][field] for key in (
                "candidate_grounding", "candidate_main_and_fallback", "candidate_user_simulator")))
        counts = data["mechanism_counts"]
        self.assertEqual(counts["primary_p1_pass"] + counts["fallback_new_p1"], 150)
        self.assertEqual(counts["primary_full_pass"] + counts["fallback_new_full"], 75)
        self.assertEqual(sum(row["count"] for row in data["status_transitions"]), 600)

    def test_public_pages_omit_migration_metadata_and_notion_links(self):
        forbidden = ("迁移说明", "本次读取", "不自动同步", "Примечание к переводу",
                     "Снимок источника", "синхронизируются автоматически",
                     'class="migration-note"', 'class="sidebar-note"',
                     'class="notion-page-link"', '<footer')
        for filename in ("index.html", "ru/index.html"):
            text = (self.output / filename).read_text()
            for phrase in forbidden:
                self.assertNotIn(phrase, text)
            document = Document(text)
            for link in document.links:
                host = urlsplit(link).hostname or ""
                self.assertFalse(host == "notion.com" or host.endswith(".notion.com")
                                 or host == "notion.so" or host.endswith(".notion.so"), link)
            self.assertIn("https://github.com/TianciGao/Valibra", document.links)
            self.assertEqual(text.count(' download="'), 2)
            self.assertIn('aria-label="章节导航"' if filename == "index.html" else 'aria-label="Содержание"', text)
            self.assertIn('lang="zh-CN"', text)
            self.assertIn('lang="ru"', text)

    def test_no_credentials_or_temporary_signed_urls(self):
        # User explicitly requested the report's SQL/state records verbatim.
        # Its original citations and local paths are text, not copied directories.
        prohibited = (r"data:image/", r"X-Amz-", r"file://",
                      r"gh[pousr]_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}",
                      r"sk-[A-Za-z0-9]{20,}", r"BEGIN .*PRIVATE KEY")
        for path in self.files + [ROOT / "site/content/zh.notion.md", ROOT / "site/content/ru.notion.md"]:
            if path.suffix == ".png":
                continue
            if path.suffix == ".xlsx":
                with zipfile.ZipFile(path) as book:
                    text = "\n".join(book.read(name).decode() for name in book.namelist() if name.endswith((".xml", ".rels")))
            else:
                text = path.read_text()
            if path.name == "notion-ru-2.svg":
                # This translated vector overlay contains exactly the reviewed
                # original screenshot, not an arbitrary new binary payload.
                embedded = re.findall(r'data:image/png;base64,([A-Za-z0-9+/=]+)', text)
                self.assertEqual(len(embedded), 1)
                self.assertEqual(base64.b64decode(embedded[0]), (ROOT / "site/assets/notion-zh-2.png").read_bytes())
                text = text.replace("data:image/png;base64," + embedded[0], "REVIEWED_SCREENSHOT")
            for pattern in prohibited:
                self.assertIsNone(re.search(pattern, text), f"{path}: {pattern}")

    def test_downloads_preserve_reviewed_desktop_workbooks(self):
        reviewed = {
            "glm52_full600_baseline_score_table.xlsx": "77bf272e823fd48ac3cb13b31ef94210b0262bf628980d1d3aded2698c750d7d",
            "current_candidate_full600_baseline_format.xlsx": "b0cd982047b833531080b6bfbe0707d208b395da74cccef22228168875f61497",
        }
        metadata = json.loads((ROOT / "site/content/zh.notion.json").read_text())
        for item in metadata["attachments"]:
            path = self.output / item["local_url"]
            data = path.read_bytes()
            self.assertEqual(sha256(data).hexdigest(), reviewed[item["name"]])
            self.assertEqual(data, (ROOT / "site/downloads" / item["name"]).read_bytes())
            self.assertEqual(len(data), item["bytes"])
            with zipfile.ZipFile(path) as book:
                self.assertFalse(any(re.search(r"externalLinks|vbaProject|embeddings|connections", name) for name in book.namelist()))
                detail = ET.fromstring(book.read("xl/worksheets/sheet2.xml"))
                ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                self.assertEqual(len(detail.findall("m:sheetData/m:row", ns)), 601)

    def test_svg_is_local_vector_with_translated_text(self):
        for language in ("zh", "ru"):
            root = ET.parse(self.output / f"assets/framework-{language}.svg").getroot()
            self.assertTrue(root.tag.endswith("svg"))
            texts = []
            for element in root.iter():
                self.assertNotIn(element.tag.split("}")[-1], ("script", "image", "foreignObject"))
                for key, value in element.attrib.items():
                    if key.endswith("href"):
                        self.assertTrue(value.startswith("#"))
                texts.extend(element.itertext())
            if language == "ru":
                self.assertFalse(re.search(r"[\u4e00-\u9fff]", "".join(texts)))

    def test_refuse_unexpected_output_without_deleting(self):
        stray = self.output / "private.txt"
        stray.write_text("must survive")
        with self.assertRaises(ValueError):
            site.build(self.output)
        self.assertEqual(stray.read_text(), "must survive")

    def test_refuse_symlink_output(self):
        link = Path(self.tmp.name) / "link"
        link.symlink_to(self.output, target_is_directory=True)
        with self.assertRaises(ValueError):
            site.build(link)
        (self.output / "assets/linked.txt").symlink_to(ROOT / "README.md")
        with self.assertRaises(ValueError):
            site.build(self.output)

    def test_schema_changes_require_review(self):
        data = site.load_data()
        data["raw_logs"] = []
        release = Path(self.tmp.name) / site.RELEASE
        release.parent.mkdir(parents=True)
        release.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            site.load_data(Path(self.tmp.name))

    def test_table_escapes_text(self):
        text = site.table(["<heading>"], [["<script>unsafe</script>"]])
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)


if __name__ == "__main__":
    unittest.main()
