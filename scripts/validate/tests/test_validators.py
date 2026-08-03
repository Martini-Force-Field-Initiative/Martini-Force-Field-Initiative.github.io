"""Tests for the validators themselves.

A validation framework that is itself unvalidated proves nothing: a check
that silently stopped firing would look exactly like a clean repository. Each
test below reproduces a defect that was actually present in this repository
before the framework existed, and asserts that the corresponding rule fires
with the right identifier.

Run with:  make test
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.validate.core.divs import parse_divs, slugify  # noqa: E402
from scripts.validate.core.itp import lint  # noqa: E402
from scripts.validate.core.links import classify  # noqa: E402
from scripts.validate.core.qmd import parse_qmd, strip_comment  # noqa: E402
from scripts.validate.core.schema import Schema  # noqa: E402

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"


def write(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class FrontMatterParsingTests(unittest.TestCase):
    """The parser must not repeat the split('---') bug it replaced."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_horizontal_rule_in_body_is_not_front_matter(self):
        path = write(self.root, "post.qmd",
                     '---\ntitle: "Real"\n---\n\nIntro\n\n---\n\nMore text\n')
        doc = parse_qmd(path, self.root)
        self.assertEqual(doc.fm.get("title"), "Real")
        self.assertEqual(doc.fm_end_line, 3)

    def test_body_without_front_matter_is_not_scanned(self):
        # A file that opens with a heading has NO front matter, even though a
        # '---' appears later. The old parser invented one from the body.
        path = write(self.root, "post.qmd",
                     "# Heading\n\ntext\n\n---\n\ntitle: not-front-matter\n")
        doc = parse_qmd(path, self.root)
        self.assertFalse(doc.fm_present)

    def test_unterminated_front_matter_is_reported(self):
        path = write(self.root, "post.qmd", '---\ntitle: "x"\n\nbody\n')
        doc = parse_qmd(path, self.root)
        self.assertTrue(doc.fm_unterminated)

    def test_duplicate_keys_are_recorded(self):
        # Exactly the state six posts were left in by a careless rename.
        path = write(self.root, "post.qmd",
                     '---\nsidebar: false\ntitle: "x"\nsidebar: false\n---\n')
        doc = parse_qmd(path, self.root)
        self.assertIn("sidebar", [k for k, _ in doc.duplicate_keys])

    def test_key_line_numbers_are_reported_for_annotations(self):
        path = write(self.root, "post.qmd",
                     '---\ntitle: "x"\ntoc: false\ndate: "01/02/2026"\n---\n')
        doc = parse_qmd(path, self.root)
        self.assertEqual(doc.line_of("date"), 4)

    def test_trailing_comments_are_captured(self):
        path = write(self.root, "post.qmd",
                     '---\ntitle: "x"   # Title of the announcement\n---\n')
        doc = parse_qmd(path, self.root)
        self.assertIn("title", doc.key_comments)

    def test_block_scalar_body_is_not_mistaken_for_keys(self):
        path = write(self.root, "post.qmd",
                     '---\ndescription: |\n  date: not a key\n  more text\n'
                     'toc: false\n---\n')
        doc = parse_qmd(path, self.root)
        self.assertNotIn("date", doc.key_lines)
        self.assertIn("toc", doc.key_lines)


class CommentStrippingTests(unittest.TestCase):
    def test_hash_inside_quotes_is_kept(self):
        code, comment = strip_comment('banner: "#FDF7F4"')
        self.assertEqual(code, 'banner: "#FDF7F4"')
        self.assertIsNone(comment)

    def test_trailing_comment_is_split_off(self):
        code, comment = strip_comment('title: "x"   # do not change')
        self.assertEqual(code, 'title: "x"')
        self.assertEqual(comment, "# do not change")


class AnnouncementSchemaTests(unittest.TestCase):
    """Regressions drawn from the real pre-framework state of the repo."""

    @classmethod
    def setUpClass(cls):
        cls.schema = Schema.load(SCHEMA_DIR / "announcement.yml")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _check(self, front_matter: str):
        path = write(self.root, "docs/announcements/posts/2026-01-01-x/index.qmd",
                     f"---\n{front_matter}---\n\nBody text.\n")
        return self.schema.check(parse_qmd(path, self.root))

    def _rules(self, findings):
        return {f.rule for f in findings}

    def test_valid_post_passes(self):
        findings = self._check(
            'title: "Bentopy"\ndescription: "A tool."\nsidebar: false\n'
            'toc: false\nauthor: "A Person"\ndate: "02/12/2026"\n'
        )
        self.assertEqual([f for f in findings if f.severity.name == "ERROR"], [])

    def test_iso_date_is_rejected(self):
        # The bentopy post shipped with this and crashed the feed generator.
        findings = self._check(
            'title: "x"\ndescription: "y"\nsidebar: false\ntoc: false\n'
            'author: "A"\ndate: "2026-02-12"\n'
        )
        self.assertIn("announcement.field-format", self._rules(findings))

    def test_sideber_typo_is_rejected(self):
        # The misspelling in the entry template propagated to 13 posts.
        findings = self._check(
            'title: "x"\ndescription: "y"\nsideber: false\ntoc: false\n'
            'author: "A"\ndate: "02/12/2026"\n'
        )
        rules = self._rules(findings)
        self.assertIn("announcement.field-missing", rules)
        self.assertIn("announcement.unknown-field", rules)

    def test_trailing_comment_is_rejected(self):
        # The Lambda emails these to every subscriber.
        findings = self._check(
            'title: "x"   # Title of the announcement (required)\n'
            'description: "y"\nsidebar: false\ntoc: false\n'
            'author: "A"\ndate: "02/12/2026"\n'
        )
        self.assertIn("announcement.trailing-comment", self._rules(findings))

    def test_impossible_calendar_date_is_rejected(self):
        # 02/31 is correctly shaped, so the schema pattern accepts it; the
        # relational rule is what knows February has no 31st.
        from scripts.validate.rules.announcements import date_is_real
        path = write(self.root, "docs/announcements/posts/2026-01-01-x/index.qmd",
                     '---\ntitle: "x"\ndescription: "y"\nsidebar: false\n'
                     'toc: false\nauthor: "A"\ndate: "02/31/2026"\n---\n\nBody.\n')
        findings = date_is_real(parse_qmd(path, self.root), None)
        self.assertIn("announcement.date-not-a-real-day",
                      {f.rule for f in findings})

    def test_missing_description_is_rejected(self):
        # Without it the Lambda throws and no email is ever sent.
        findings = self._check(
            'title: "x"\nsidebar: false\ntoc: false\n'
            'author: "A"\ndate: "02/12/2026"\n'
        )
        self.assertIn("announcement.field-missing", self._rules(findings))


class PublicationSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = Schema.load(SCHEMA_DIR / "publication.yml")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    BODY = ("\n## Citation (APA 7)\n\n> Author, A. (2024). Title.\n\n"
            "## Abstract\n\nText.\n")

    def _check(self, front_matter: str, year: str = "2024"):
        path = write(
            self.root,
            f"docs/publications/entries/{year}/Author{year}_Key.qmd",
            f"---\n{front_matter}---\n{self.BODY}",
        )
        return self.schema.check(parse_qmd(path, self.root))

    VALID = ('title: "T"\ntype: "article"\nsidebar: false\ntoc: false\n'
             'author: "A"\nyear: "2024"\npublication: "J"\n'
             'doi: "https://doi.org/10.1000/x"\npreprint: ""\nmaterials: ""\n'
             'categories:\n  - Journal article\n')

    def test_valid_entry_passes(self):
        findings = self._check(self.VALID)
        self.assertEqual([f for f in findings if f.severity.name == "ERROR"], [])

    def test_doi_with_prefix_is_rejected(self):
        # An entry shipped with doi: "DOI https://doi.org/...".
        findings = self._check(
            self.VALID.replace('doi: "https://doi.org/10.1000/x"',
                               'doi: "DOI https://doi.org/10.1000/x"'))
        self.assertTrue(
            {"publication.field-type", "publication.field-format"}
            & {f.rule for f in findings}
        )

    def test_doi_with_leading_space_is_rejected(self):
        findings = self._check(
            self.VALID.replace('doi: "https://doi.org/10.1000/x"',
                               'doi: " https://doi.org/10.1000/x"'))
        self.assertTrue(
            {"publication.field-type", "publication.field-format"}
            & {f.rule for f in findings}
        )

    def test_missing_abstract_is_rejected(self):
        path = write(self.root, "docs/publications/entries/2024/A2024_K.qmd",
                     f"---\n{self.VALID}---\n\n## Citation (APA 7)\n\n> A.\n")
        findings = self.schema.check(parse_qmd(path, self.root))
        self.assertIn("publication.heading-missing", {f.rule for f in findings})

    def test_citation_without_blockquote_is_rejected(self):
        path = write(self.root, "docs/publications/entries/2024/A2024_K.qmd",
                     f"---\n{self.VALID}---\n\n## Citation (APA 7)\n\n"
                     f"Author, A. (2024).\n\n## Abstract\n\nText.\n")
        findings = self.schema.check(parse_qmd(path, self.root))
        self.assertIn("publication.section-format", {f.rule for f in findings})

    def test_unknown_category_is_only_a_warning(self):
        # New terms are normal; they should surface for curation, not block a
        # paper from being added.
        findings = self._check(
            self.VALID.replace("  - Journal article",
                               "  - Totally Novel Category"))
        matching = [f for f in findings if f.rule == "publication.vocabulary-unknown"]
        self.assertTrue(matching)
        self.assertEqual(matching[0].severity.name, "WARNING")


class SlugifyTests(unittest.TestCase):
    def test_periods_survive(self):
        # Pandoc keeps '.', so "Step 1. Set up" -> "step-1.-set-up". Stripping
        # it reported phantom breakage on every heading with a filename.
        self.assertEqual(slugify("Step 1. Set up the box"),
                         "step-1.-set-up-the-box")

    def test_matches_authored_explicit_id(self):
        self.assertEqual(slugify("Part I. Protein complexes at equilibrium"),
                         "part-i.-protein-complexes-at-equilibrium")

    def test_inline_html_is_stripped(self):
        self.assertEqual(slugify('<i class="fa-solid fa-atom"></i> Ions'), "ions")


class LinkClassificationTests(unittest.TestCase):
    def test_chemical_nomenclature_is_not_treated_as_a_path(self):
        # Abstracts contain constructs like poly[(N,N'-bis...)](NDI), which
        # match link syntax exactly.
        self.assertEqual(classify("NDI"), "bare-word")

    def test_bare_email_is_detected(self):
        self.assertEqual(classify("c.s.brasnett@rug.nl"), "bare-email")

    def test_listing_filter_is_not_an_anchor(self):
        # The tutorials page deep-links this; resolving it as a heading anchor
        # would be a false positive on the one link that matters most.
        self.assertEqual(classify("#category=!\U0001f378Core papers"),
                         "listing-filter")

    def test_ordinary_relative_link_is_internal(self):
        self.assertEqual(classify("LipidsI/index.qmd"), "internal")


class DivParsingTests(unittest.TestCase):
    def test_nested_divs_are_tracked(self):
        lines = list(enumerate([
            "::: tutorial-item",
            "**Title**",
            "::: tutorial-buttons",
            "[Start](X/index.qmd)",
            ":::",
            ":::",
        ], start=1))
        result = parse_divs(lines)
        items = [d for d in result.divs if d.has_class("tutorial-item")]
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0].children), 1)
        self.assertEqual(result.unclosed, [])

    def test_unclosed_div_is_reported(self):
        lines = list(enumerate(["::: software-card", "### Tool"], start=1))
        result = parse_divs(lines)
        self.assertEqual(len(result.unclosed), 1)

    def test_first_significant_child_detects_wrong_heading_level(self):
        lines = list(enumerate(
            ["::: software-card", "## Tool", "text", ":::"], start=1))
        result = parse_divs(lines)
        kind, level, _ = result.divs[0].first_significant()
        self.assertEqual((kind, level), ("heading", 2))


class ItpLinterTests(unittest.TestCase):
    GOOD = """; Martini 3 test topology
[ moleculetype ]
  MOL   1

[ atoms ]
  1  Q1   1  MOL  A1  1   1.0
  2  Q5   1  MOL  A2  2  -1.0

[ bonds ]
  1  2  1  0.47  1250
"""

    def test_valid_topology_is_clean(self):
        self.assertEqual(lint(self.GOOD), [])

    def test_index_out_of_range(self):
        text = self.GOOD.replace("  1  2  1  0.47  1250", "  1  7  1  0.47  1250")
        self.assertIn("itp.index-out-of-range", {i.rule for i in lint(text)})

    def test_non_integral_charge(self):
        text = self.GOOD.replace("-1.0", "-0.5")
        self.assertIn("itp.non-integral-charge", {i.rule for i in lint(text)})

    def test_unknown_bead_type(self):
        text = self.GOOD.replace("  2  Q5 ", "  2  ZZ9")
        self.assertIn("itp.bead-type-grammar", {i.rule for i in lint(text)})

    def test_bond_and_constraint_on_same_pair(self):
        text = self.GOOD + "\n[ constraints ]\n  1  2  1  0.47\n"
        self.assertIn("itp.bond-and-constraint", {i.rule for i in lint(text)})

    def test_self_bond(self):
        text = self.GOOD.replace("  1  2  1  0.47  1250", "  1  1  1  0.47  1250")
        self.assertIn("itp.self-bond", {i.rule for i in lint(text)})

    def test_atom_numbering_gap(self):
        text = self.GOOD.replace("  2  Q5   1  MOL  A2  2  -1.0",
                                 "  3  Q5   1  MOL  A2  2  -1.0")
        self.assertIn("itp.atom-numbering", {i.rule for i in lint(text)})

    def test_missing_moleculetype(self):
        self.assertIn("itp.no-moleculetype", {i.rule for i in lint("; nothing\n")})

    def test_disconnected_fragments(self):
        text = self.GOOD.replace(
            "  2  Q5   1  MOL  A2  2  -1.0",
            "  2  Q5   1  MOL  A2  2  -1.0\n  3  C1   1  MOL  A3  3   0.0\n"
            "  4  C1   1  MOL  A4  4   0.0",
        ) + "  3  4  1  0.47  1250\n"
        self.assertIn("itp.disconnected-fragments", {i.rule for i in lint(text)})


class SchemaIntegrityTests(unittest.TestCase):
    """Every shipped schema must load and name only registered rules."""

    def test_all_schemas_load_and_rules_exist(self):
        from scripts.validate import rules
        rules.load_all()
        for path in sorted(SCHEMA_DIR.glob("*.yml")):
            with self.subTest(schema=path.name):
                schema = Schema.load(path)
                for rule_name in schema.rules:
                    rules.get(rule_name)   # raises KeyError if unregistered


if __name__ == "__main__":
    unittest.main()
