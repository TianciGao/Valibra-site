"""Parity and provenance checks for the complete Russian report."""
import base64
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from notion_report import Report, render_russian, russian_metadata
from test_notion_report import Extract


class RussianReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zh = Report((ROOT / "site/content/zh.notion.md").read_text())
        cls.zh_body = cls.zh.render()
        cls.ru = Report((ROOT / "site/content/ru.notion.md").read_text(), russian_metadata(), language="ru")
        cls.ru_body = cls.ru.render()
        cls.manifest = json.loads((ROOT / "site/content/ru.notion.json").read_text())

    def test_all_source_units_and_nested_structure_have_counterparts(self):
        self.assertEqual(self.zh.counts, self.ru.counts)
        self.assertEqual(len(self.ru.records), 1163)
        self.assertEqual([x["kind"] for x in self.zh.records], [x["kind"] for x in self.ru.records])
        zh, ru = Extract(self.zh_body), Extract(self.ru_body)
        self.assertEqual(zh.details, ru.details)
        self.assertEqual(zh.tag_counts["tr"], ru.tag_counts["tr"])
        for index, record in enumerate(self.ru.records):
            self.assertEqual(ru.records[index], record["text"])

    def test_sql_and_original_records_unchanged_except_documented_language(self):
        zh = [x["text"] for x in self.zh.records if x["kind"] == "code"]
        ru = [x["text"] for x in self.ru.records if x["kind"] == "code"]
        self.assertEqual(len(ru), 116)
        differences = [i for i, pair in enumerate(zip(zh, ru)) if pair[0] != pair[1]]
        self.assertEqual(differences, [37, 39, 87])
        self.assertEqual(differences, [int(i) for i in self.manifest["translated_code_blocks_zero_based"]])
        for i in (37, 39):
            without_comments = lambda s: re.sub(r"#[^\n]*", "", s)
            self.assertEqual(without_comments(zh[i]), without_comments(ru[i]))
        marker = "[VALIBRA SQL WRITER CONTEXT BEGIN]"
        self.assertEqual(zh[87].split(marker)[1], ru[87].split(marker)[1])
        self.assertNotRegex(ru[87], r"[\u4e00-\u9fff]")

    def test_numbers_in_every_table_cell_preserved(self):
        numeric = lambda s: re.findall(r"[−+-]?\d+(?:[.,]\d+)*", s)
        for i, (zh, ru) in enumerate(zip(self.zh.records, self.ru.records)):
            if zh["kind"] == "cell":
                # Russian prose can reorder P1 and P2; numeric cells stay exact.
                self.assertEqual(Counter(numeric(zh["text"])), Counter(numeric(ru["text"])), f"Cell at block {i}")

    def test_technical_inline_identifiers_and_citations_preserved(self):
        for zh, ru in zip(self.zh.source.splitlines(), self.ru.source.splitlines()):
            if not re.search(r"[\u4e00-\u9fff]", zh):
                continue
            if zh.lstrip().startswith(("#", "!", "<page")):
                continue
            # Inline backticks contain source paths, hashes and identifiers.
            identifiers = re.findall(r"`([^`]+)`", zh)
            translated = re.findall(r"`([^`]+)`", ru)
            self.assertEqual(len(identifiers), len(translated))
            for identifier in identifiers:
                if not re.search(r"[\u4e00-\u9fff]", identifier) or "/" in identifier:
                    self.assertIn(identifier, translated)
            self.assertEqual(re.findall(r"\b[CED]\d{2}\b", zh), re.findall(r"\b[CED]\d{2}\b", ru))

    def test_resource_links_and_russian_controls(self):
        page = render_russian()
        self.assertIn('href="https://github.com/TianciGao/Valibra"', page)
        self.assertIn("репозиторий", page.lower())
        self.assertEqual(page.count(' download="'), 2)
        self.assertIn('href="../downloads/glm52_full600_baseline_score_table.xlsx"', page)
        self.assertIn('href="../downloads/current_candidate_full600_baseline_format.xlsx"', page)
        self.assertIn("не включает независимый Grounding", page)
        self.assertIn("Развернуть все блоки", page)
        self.assertNotIn("source-unavailable", page)
        self.assertNotIn("file-upload://", page)
        self.assertNotIn("<mention-page", page)
        self.assertEqual([x[0] for x in self.zh.nav], [x[0] for x in self.ru.nav])

    def test_architecture_redesign_preserves_every_original_label(self):
        root = ET.parse(ROOT / "site/assets/notion-ru-1.svg").getroot()
        texts = root.findall(".//{http://www.w3.org/2000/svg}text")
        labels = ["".join(node.itertext()) for node in texts]
        self.assertEqual(len(labels), 58)
        self.assertEqual([node.get("data-label") for node in texts], [str(i) for i in range(58)])
        # Frozen from the original published diagram, before layout changes.
        self.assertEqual(sha256("\n".join(labels).encode()).hexdigest(),
                         "0a9a03ff1f32696476a35c5262d3bb990ad071f91b8ce23ac95973d2505b88ed")

    def test_architecture_uses_one_font_size(self):
        root = ET.parse(ROOT / "site/assets/notion-ru-1.svg").getroot()
        style = root.find("{http://www.w3.org/2000/svg}style").text
        self.assertEqual(re.findall(r"font-size:\s*(\d+)px", style), ["20"])
        for node in root.iter():
            # Long labels must wrap rather than shrink or stretch to fit.
            for attribute in ("font-size", "textLength", "lengthAdjust", "transform", "style"):
                self.assertNotIn(attribute, node.attrib)

    def test_architecture_url_changes_with_svg_content(self):
        revision = sha256((ROOT / "site/assets/notion-ru-1.svg").read_bytes()).hexdigest()[:12]
        self.assertIn(f'src="../assets/notion-ru-1.svg?v={revision}"', self.ru_body)
        self.assertIn(f'href="../assets/notion-ru-1.svg?v={revision}"', self.ru_body)

    def test_five_translated_figures_are_self_contained_and_safe(self):
        for i in range(1, 6):
            path = ROOT / f"site/assets/notion-ru-{i}.svg"
            root = ET.parse(path).getroot()
            visible = "".join(root.itertext())
            self.assertRegex(visible, "[А-Яа-я]")
            self.assertNotRegex(visible, r"[\u4e00-\u9fff]")
            for node in root.iter():
                self.assertNotIn(node.tag.split("}")[-1], ("script", "foreignObject"))
                for key, value in node.attrib.items():
                    self.assertFalse(key.lower().startswith("on"))
                    if key.endswith("href"):
                        if value.startswith("#"):
                            continue
                        self.assertEqual(i, 2)
                        self.assertTrue(value.startswith("data:image/png;base64,"))
                        self.assertEqual(sha256(base64.b64decode(value.split(",", 1)[1])).hexdigest(), self.manifest["image_sources"]["notion-zh-2.png"])
            self.assertIn(f'../assets/notion-ru-{i}.svg', self.ru_body)


if __name__ == "__main__":
    unittest.main()
