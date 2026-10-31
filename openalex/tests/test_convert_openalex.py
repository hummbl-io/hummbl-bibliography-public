"""Unit tests for the OpenAlex converter and the external-manifest verifier (stdlib only)."""
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent))

import convert_openalex as conv  # noqa: E402
import verify  # noqa: E402


def work(**overrides):
    base = {
        "id": "https://openalex.org/W1",
        "doi": "https://doi.org/10.1000/ABC.1",
        "title": "A Test   Title",
        "publication_year": 2020,
        "publication_date": "2020-03-04",
        "type": "article",
        "is_retracted": False,
        "is_paratext": False,
        "authorships": [{"author": {"display_name": "Jane Q. Doe"}},
                        {"author": {"display_name": "Ada Lovelace"}}],
        "primary_location": {
            "landing_page_url": "https://example.org/a",
            "source": {"display_name": "Journal {X}", "issn_l": "1234-5678",
                       "host_organization_name": "Pub Co"},
        },
        "biblio": {"volume": "7", "issue": "2", "first_page": "10", "last_page": "20"},
        "primary_topic": {"domain": {"display_name": "Life Sciences"}},
        "abstract_inverted_index": {"secret": [0]},
    }
    base.update(overrides)
    return base


class MappingTests(unittest.TestCase):
    def test_doi_is_normalised(self):
        self.assertEqual(conv.norm_doi("https://doi.org/10.1000/ABC.1 "), "10.1000/abc.1")
        self.assertEqual(conv.norm_doi("doi:10.1/X"), "10.1/x")
        self.assertIsNone(conv.norm_doi(None))

    def test_rejections_have_reasons(self):
        self.assertEqual(conv.map_work(work(is_retracted=True))[0], "retracted")
        self.assertEqual(conv.map_work(work(is_paratext=True))[0], "paratext")
        self.assertEqual(conv.map_work(work(title="  "))[0], "no_title")
        self.assertEqual(conv.map_work(work(id=None))[0], "missing_id")

    def test_article_mapping_and_no_abstract(self):
        reason, mapped = conv.map_work(work())
        self.assertIsNone(reason)
        fields = mapped["fields"]
        self.assertEqual(mapped["bibtype"], "article")
        self.assertEqual(fields["author"], "Jane Q. Doe and Ada Lovelace")
        self.assertEqual(fields["pages"], "10--20")
        self.assertEqual(fields["month"], "mar")
        self.assertEqual(fields["journal"], "Journal \\{X\\}")
        self.assertEqual(fields["doi"], "10.1000/abc.1")
        self.assertEqual(mapped["domain"], "life")
        text = conv.format_entry(mapped["bibtype"], "Doe2020A", fields)
        self.assertNotIn("secret", text)
        self.assertNotIn("booktitle", text)  # not defined for @article

    def test_entry_fields_are_on_the_allowlist(self):
        for bibtype in set(conv.ENTRY_TYPE.values()) | {"misc"}:
            fields = {name: "x" for name in conv.FIELD_ORDER}
            text = conv.format_entry(bibtype, "K2020Word", fields)
            used = set(re.findall(r"(?m)^\s*([A-Za-z][A-Za-z0-9_-]*)\s*=", text))
            self.assertLessEqual(used, set(conv.ALLOWED_FIELDS), bibtype)

    def test_non_latin_title_uses_openalex_number(self):
        key = conv.base_key("Zhang Wei", 2019, "全文", "https://openalex.org/W2224891875")
        # Family is the last token as OpenAlex orders display names ("Zhang Wei" -> Wei).
        self.assertEqual(key, "Wei2019W2224891875")

    def test_suffix_lengthens_until_unused(self):
        oid = "https://openalex.org/W7122356991"
        first = conv.unique_suffixed_key("Base2020X", oid, set())
        self.assertEqual(len(first.rsplit("_oa", 1)[1]), 8)
        second = conv.unique_suffixed_key("Base2020X", oid, {first.casefold()})
        self.assertEqual(len(second.rsplit("_oa", 1)[1]), 12)
        self.assertTrue(second.startswith(first))

    def test_arxiv_doi_sets_eprint(self):
        _, mapped = conv.map_work(work(doi="https://doi.org/10.48550/arXiv.2510.04380"))
        self.assertEqual(mapped["fields"]["eprint"], "2510.04380")
        self.assertEqual(mapped["fields"]["archiveprefix"], "arXiv")


class ShardTests(unittest.TestCase):
    def test_rotation_respects_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = conv.SHARD_CAP_BYTES
            conv.SHARD_CAP_BYTES = 100
            try:
                shards = conv.ShardSet(Path(tmp))
                for _ in range(10):
                    shards.write("life", b"x" * 40)
                rows = shards.close_all()
            finally:
                conv.SHARD_CAP_BYTES = old
            self.assertTrue(all(row["bytes"] <= 100 for row in rows))
            self.assertEqual(sum(row["records"] for row in rows), 10)
            self.assertEqual(len(rows), 5)


class ExternalVerifyTests(unittest.TestCase):
    def test_external_manifest_passes_and_detects_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bibliography").mkdir()
            entry = conv.format_entry("article", "Doe2020A", {"title": "T", "year": "2020"})
            data = entry.encode("utf-8")
            (root / "bibliography" / "OA_life_p001.bib").write_bytes(data)
            sidecar = b"citation_key\topenalex_id\tdoi\tshard\n"
            (root / "OA_keymap.tsv.gz").write_bytes(sidecar)
            manifest = {
                "edition": "test", "records": 1, "bibtex_files": 1,
                "allowed_fields": conv.ALLOWED_FIELDS,
                "files": [{"path": "bibliography/OA_life_p001.bib", "records": 1,
                           "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}],
                "sidecars": [{"path": "OA_keymap.tsv.gz", "bytes": len(sidecar),
                              "sha256": hashlib.sha256(sidecar).hexdigest()}],
            }
            (root / "MANIFEST.openalex.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = verify.verify(root, "MANIFEST.openalex.json")
            self.assertEqual(result["integrity"], "pass")
            (root / "bibliography" / "OA_life_p001.bib").write_bytes(data + b"\n")
            with self.assertRaises(ValueError):
                verify.verify(root, "MANIFEST.openalex.json")


if __name__ == "__main__":
    unittest.main()
