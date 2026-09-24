"""Losslessness checks for text, code, nesting and inaccessible-object handling."""
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from notion_report import Report, rich, render_chinese


class Extract(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.records = {}
        self.active = None
        self.active_tag = None
        self.details = []
        self.detail_depth = 0
        self.tag_counts = {}
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        self.tag_counts[tag] = self.tag_counts.get(tag, 0) + 1
        if tag == "details":
            self.detail_depth += 1
            self.details.append(self.detail_depth)
        if "data-source-block" in attributes:
            if self.active is not None:
                raise AssertionError("Nested source-record elements")
            self.active = int(attributes["data-source-block"])
            self.active_tag = tag
            self.records[self.active] = ""

    def handle_endtag(self, tag):
        if tag == "details":
            self.detail_depth -= 1
        if tag == self.active_tag:
            self.active = self.active_tag = None

    def handle_data(self, value):
        if self.active is not None:
            self.records[self.active] += value


class NotionReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "site/content/zh.notion.md").read_text()
        cls.metadata = json.loads((ROOT / "site/content/zh.notion.json").read_text())
        cls.report = Report(cls.source, cls.metadata)
        cls.body = cls.report.render()
        cls.dom = Extract(cls.body)

    def test_all_1163_text_units_survive_in_order(self):
        self.assertEqual(len(self.report.records), 1163)
        self.assertEqual(list(self.dom.records), list(range(1163)))
        for index, record in enumerate(self.report.records):
            self.assertEqual(self.dom.records[index], record["text"], f"Source block {index} ({record['kind']})")

    def test_all_116_code_blocks_are_byte_for_byte_preserved(self):
        blocks = re.findall(r"^\t*```[^\n]*\n(.*?)^\t*```$", self.source, re.M | re.S)
        self.assertEqual(len(blocks), 116)
        actual = [self.dom.records[i] for i, record in enumerate(self.report.records) if record["kind"] == "code"]
        self.assertEqual(actual, blocks)

    def test_nested_folding_matches_source(self):
        depths, depth = [], 0
        in_code = False
        for raw in self.source.splitlines():
            line = raw.lstrip("\t")
            if line.startswith("```"):
                in_code = not in_code
            elif not in_code:
                if line.startswith("<details"):
                    depth += 1
                    depths.append(depth)
                elif line == "</details>":
                    depth -= 1
        self.assertEqual(self.dom.details, depths)
        self.assertEqual(len(depths), 50)
        self.assertEqual(self.dom.detail_depth, 0)

    def test_original_tables_and_images_are_not_summarised(self):
        self.assertEqual(self.dom.tag_counts["table"], 18)
        self.assertEqual(self.dom.tag_counts["tr"], 158)
        self.assertEqual(self.dom.tag_counts["td"] + self.dom.tag_counts["th"], 496)
        self.assertEqual(self.dom.tag_counts["img"], 5)
        cells = re.findall(r'<td[^>]*>(.*?)</td>', self.source, re.S)
        rendered_cells = [record["text"] for record in self.report.records if record["kind"] == "cell"]
        from notion_report import plain
        self.assertEqual(rendered_cells, [plain(rich(cell)) for cell in cells])

    def test_original_editorial_changes_and_order(self):
        for sentence in ("我们在原 BIRD-Interact Agent", "调用工具——信息来源", "maintenance cost（维护成本）", "ratio of A to B （明确A与B之比）"):
            self.assertIn(sentence, self.body)
        self.assertLess(self.body.index('id="case-success"'), self.body.index('id="case-recovery"'))
        self.assertLess(self.body.index('id="case-recovery"'), self.body.index('id="case-failure"'))

    def test_source_objects_are_explicit_not_silently_lost(self):
        page = render_chinese()
        self.assertEqual(self.report.counts["unknown"], 1)
        self.assertEqual(self.report.counts["attachments"], 2)
        self.assertNotIn('class="source-unavailable"', self.body)
        self.assertNotIn("接口将此页面标记为不完整", page)
        self.assertIn('href="https://github.com/TianciGao/Valibra"', self.body)
        self.assertIn("代码仓库保持私有", self.body)
        self.assertEqual(self.body.count(' download="'), 2)
        self.assertIn("未包含独立 Grounding 用量", self.body)
        self.assertIn("glm52_full600_baseline_score_table.xlsx", self.body)
        self.assertIn("current_candidate_full600_baseline_format.xlsx", self.body)

    def test_missing_resolutions_keep_original_entry_points(self):
        body = Report(self.source).render()
        self.assertEqual(body.count('class="source-unavailable"'), 3)

    def test_imported_html_cannot_execute(self):
        unsafe = rich('Text <script>alert(1)</script> <span color="red" onclick="alert(1)">x</span> [x](javascript:alert(1))')
        self.assertNotIn("<script>", unsafe)
        self.assertNotIn('<span color="red" onclick=', unsafe)
        self.assertNotIn('href="javascript:', unsafe)
        self.assertIn('<span class="notion-red"><strong>强调</strong></span>', rich('<span color="red">**强调**</span>'))

    def test_unknown_new_block_types_fail_instead_of_disappearing(self):
        with self.assertRaises(ValueError):
            Report('<database url="https://example.com">new</database>').render()
        with self.assertRaises(ValueError):
            Report('```sql\nSELECT 1').render()

    def test_import_snapshot_has_not_been_editorially_rewritten(self):
        # Only image and attachment URLs were normalised during initial import.
        self.assertEqual(sha256(self.source.encode()).hexdigest(), '59c7ec37e2173c7444f7de28c902d5dac4f69be265a530ecc16ef2a4a96a2744')


if __name__ == "__main__":
    unittest.main()
