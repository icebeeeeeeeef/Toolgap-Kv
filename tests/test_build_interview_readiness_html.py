import unittest
from pathlib import Path

from scripts import build_interview_readiness_html as builder


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs/interview-prep/AI_INFRA_INTERVIEW_READINESS.md"


class InterviewReadinessMarkdownParserTest(unittest.TestCase):
    def test_parses_the_thirteen_ordered_topics(self):
        topics = builder.parse_topics(INDEX)

        self.assertEqual(13, len(topics))
        self.assertEqual(
            [f"{number:02d}" for number in range(1, 14)],
            [topic["id"] for topic in topics],
        )

    def test_parses_topic_metadata_and_mastery_levels(self):
        topic = builder.parse_topics(INDEX)[0]

        self.assertEqual("PyTorch 与张量编程", topic["title"])
        self.assertEqual("P0", topic["priority"])
        self.assertEqual(
            {"原理": "L2", "源码": "L1", "手写": "L3", "实验": "L2"},
            topic["mastery"],
        )
        self.assertIn("Transformer", topic["capability"])
        self.assertIn("不系统学习", topic["boundary"])

    def test_every_detail_link_resolves_inside_the_topics_directory(self):
        topics_root = (INDEX.parent / "topics").resolve()

        for topic in builder.parse_topics(INDEX):
            detail_path = topic["detail_path"].resolve()
            self.assertEqual(topics_root, detail_path.parent)
            self.assertTrue(detail_path.is_file(), detail_path)


class InterviewReadinessHtmlTest(unittest.TestCase):
    def setUp(self):
        self.topics = builder.parse_topics(INDEX)

    def test_embeds_every_topic_and_the_full_detail_content(self):
        document = builder.build_html(self.topics)

        for topic in self.topics:
            self.assertIn('"id": "{}"'.format(topic["id"]), document)
            self.assertIn(str(topic["title"]), document)
        self.assertIn("Tensor 心智模型", document)
        self.assertIn("Move-only RAII 资源封装", document)

    def test_contains_the_mindmap_and_progressive_disclosure_controls(self):
        document = builder.build_html(self.topics)

        for marker in (
            'id="mindmap-svg"',
            'id="topic-search"',
            'id="priority-filter"',
            'id="mastery-filter"',
            'id="status-filter"',
            'id="expand-all"',
            'id="collapse-all"',
            'id="zoom-in"',
            'id="zoom-out"',
            'id="fit-view"',
            'id="detail-panel"',
        ):
            self.assertIn(marker, document)

    def test_is_a_self_contained_offline_document(self):
        document = builder.build_html(self.topics)

        self.assertNotIn('src="http', document)
        self.assertNotIn("src='http", document)
        self.assertNotIn('<link rel="stylesheet"', document)
        self.assertIn("function renderMindmap()", document)
        self.assertIn("addEventListener(\"wheel\"", document)
        self.assertIn("pointermove", document)

    def test_generation_is_deterministic(self):
        self.assertEqual(
            builder.build_html(self.topics), builder.build_html(self.topics)
        )

    def test_index_links_the_html_and_documents_regeneration(self):
        index_source = INDEX.read_text(encoding="utf-8")

        self.assertIn("AI_INFRA_INTERVIEW_READINESS.html", index_source)
        self.assertIn(
            "python3 scripts/build_interview_readiness_html.py", index_source
        )


if __name__ == "__main__":
    unittest.main()
